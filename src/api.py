import json
import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import  Any, Dict, Annotated
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Form
from fastapi.responses import RedirectResponse

from .auth.auth_handler import signJWT
from .auth.auth_bearer import JWTBearer
from .schemas.transcripts import LoginRequest, SuccessResponse, PdfFile
from .request_service import RequestService
from .config import configs

from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from src.database import Database
from src.agent import PDFExtractor


logging.basicConfig(level=logging.INFO)
logging.addLevelName(logging.DEBUG, "DEBUG")
logger = logging.getLogger(__name__)


db = Database()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.connect_db()
    yield
    # Shutdown
    await db.disconnect_db()

app = FastAPI(title="PDF Order Extractor API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # /vercel.svg is automatically served when included in the public/** directory.
    return RedirectResponse("/vercel.svg", status_code=307)

@app.get("/")
async def root():
    return SuccessResponse(message="PDF Order Extractor API is running")

@app.get("/health")
async def health():
    return SuccessResponse(message="API is healthy")


@app.post("/login")
async def login(login_request: LoginRequest):
    """Authenticate user from query params, JSON body, or form data.
    Args:
        username (str): The username of the user.
        password (str): The password of the user.
    Returns:
        JSONResponse: A JSON response containing the JWT token if authentication is successful.
    """
   
    logger.info(f"Login attempt for user: {login_request}")

    client = db.client
    if client is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    # Find user by unique username, then verify password
    user = await client.user.find_unique(
        where={'name': login_request.username},
    )
    if not user or user.password != login_request.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    logger.info(f"User authenticated: {user.name}")

    token = signJWT(str(user.id))
    return SuccessResponse(message="Login successful", data=token)  

@app.get("/customers", dependencies=[Depends(JWTBearer())], tags=["Customers"])
async def get_customers(token: str = Depends(JWTBearer())):
    """Endpoint to get list of customers."""

    #configure third party api call
    company_id = await JWTBearer().get_company_id(token)
    config = configs.get(int(company_id)) if company_id else None
    if not config:
        raise HTTPException(status_code=404, detail="Company configuration not found.")
    api_service = config.get("api-service", "")
    if not api_service:
        raise HTTPException(status_code=400, detail="API service URL not configured for this company.")
    
    customers = api_service.get("customers", "")
    api_key = config.get("api-key", "")
    if not customers:
        raise HTTPException(status_code=400, detail="Customers endpoint not configured for this company.")
    

    #call third party api
    response = await RequestService.post_request(customers, data={})
    return SuccessResponse(message="Customers retrieved successfully", data=response.json())

@app.post("/extract-order", dependencies=[Depends(JWTBearer())], tags=["Order Extraction"])
async def extract_order(order_request: Annotated[PdfFile, Form()], token: str = Depends(JWTBearer())) -> SuccessResponse:
    if order_request.file.content_type != "application/pdf" and order_request.file.content_type != "image/png":
        raise HTTPException(status_code=400, detail="Only PDF and PNG files are supported.")

    # Save uploaded file
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}.pdf"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(order_request.file.file, f)

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        #get compony_id from token
        company_id = await JWTBearer().get_company_id(token)
        extractor = PDFExtractor(company_id=int(company_id) if company_id else None)

        #here is the agent call
        orders = await extractor(file_bytes, order_request.file.content_type)

        #call third party api
        #configure third party api call
        ms_code = await JWTBearer().get_user_ms_code(token)
        config = configs.get(int(company_id)) if company_id else None
        api_service = config.get("api-service", "") # type: ignore
        
        orders_endpoint = api_service.get("order", "")
        if not orders_endpoint:
            raise HTTPException(status_code=400, detail="Order endpoint not configured for this company.")
        
        #send orders to third party service
        response = await RequestService.post_request(orders_endpoint, data={
            "ms_code": str(ms_code),
            "cus_id": str(order_request.cus_id),
            "orders": orders
        })
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to send orders to third party service.")
        
        result = response.json()
        resp = result.get("data", {})

        return SuccessResponse(message="PDF/PNG extraction successful", data=resp)
    except Exception as e:
        logger.error(f"Error during order extraction: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during order extraction.")
    finally:
        if file_path.exists():
            file_path.unlink()

@app.post("verify", dependencies=[Depends(JWTBearer())], tags=["order"])
async def verify_order(order_id:str, token: str = Depends(JWTBearer())) -> SuccessResponse:
    """Endpoint to verify order extraction functionality."""

    #
    company_id = await JWTBearer().get_company_id(token)
    config = configs.get(int(company_id)) if company_id else None
    api_service = config.get("api-service", "") # type: ignore
    verify_endpoint = api_service.get("verify", "")

    if not verify_endpoint:
        raise HTTPException(status_code=400, detail="Verify endpoint not configured for this company.")
    
    response = await RequestService.post_request(verify_endpoint, data={
        "order_id": order_id
    })

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to verify order extraction.")
    
    result = response.json()
    resp = result.get("data", {})

    return SuccessResponse(message="Order extraction verified successfully", data=resp)



@app.delete("/cleanup-uploads", dependencies=[Depends(JWTBearer())], tags=["Maintenance"])
async def cleanup_uploads():
    """Endpoint to clean up all files in the uploads directory."""
    for file in UPLOAD_DIR.iterdir():
        if file.is_file():
            file.unlink()
    return SuccessResponse(message="Upload directory cleaned up successfully.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)