import json
import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, Annotated
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Form
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from .auth.auth_handler import signJWT
from .auth.auth_bearer import JWTBearer
from .schemas.transcripts import LoginRequest, SuccessResponse, PdfFile, OrderIdRequest
from .request_service import RequestService
from .config import configs
from .database import Database
from .agent import PDFExtractor
from prisma.enums import OrderStatus

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
SUPPORTED_FILE_TYPES = {"application/pdf", "image/png"}

# Initialize database
db = Database()


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    await db.connect_db()
    yield
    await db.disconnect_db()


# Initialize FastAPI app
app = FastAPI(
    title="PDF Order Extractor API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper functions
def get_database_client():
    """Get database client or raise exception."""
    if db.client is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    return db.client


async def get_company_config(token: str) -> Dict[str, Any]:
    """Get company configuration from token."""
    company_id = await JWTBearer().get_company_id(token)
    config = configs.get(int(company_id)) if company_id else None
    
    if not config:
        raise HTTPException(
            status_code=404,
            detail="Company configuration not found"
        )
    
    return config


def validate_file_type(content_type: str):
    """Validate uploaded file type."""
    if content_type not in SUPPORTED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and PNG files are supported"
        )


# Routes
@app.get("/")
async def root():
    """Root endpoint."""
    return SuccessResponse(message="PDF Order Extractor API is running")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return SuccessResponse(message="API is healthy")


@app.post("/login", tags=["Authentication"])
async def login(login_request: LoginRequest):
    """
    Authenticate user and return JWT token.
    
    Args:
        login_request: Login credentials
        
    Returns:
        SuccessResponse with JWT token
    """
    logger.info(f"Login attempt for user: {login_request.username}")
    
    client = get_database_client()
    
    user = await client.user.find_unique(
        where={'name': login_request.username}
    )
    
    if not user or user.password != login_request.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    
    logger.info(f"User authenticated: {user.name}")
    token = signJWT(str(user.id))
    
    return SuccessResponse(message="Login successful", data=token)


@app.get("/customers", dependencies=[Depends(JWTBearer())], tags=["Customers"])
async def get_customers(token: str = Depends(JWTBearer())):
    """
    Get list of customers from third-party API.
    
    Returns:
        SuccessResponse with customer data
    """
    config = await get_company_config(token)
    api_service = config.get("api-service", "")
    
    if not api_service:
        raise HTTPException(
            status_code=400,
            detail="API service URL not configured for this company"
        )
    
    customers_endpoint = api_service.get("customers", "")
    if not customers_endpoint:
        raise HTTPException(
            status_code=400,
            detail="Customers endpoint not configured for this company"
        )
    
    response = await RequestService.post_request(customers_endpoint, data={})
    return SuccessResponse(
        message="Customers retrieved successfully",
        data=response.json()
    )


@app.post("/extract-order", dependencies=[Depends(JWTBearer())], tags=["Order Extraction"])
async def extract_order(
    order_request: Annotated[PdfFile, Form()],
    token: str = Depends(JWTBearer())
) -> SuccessResponse:
    """
    Extract order from PDF/PNG and send to third-party service.
    
    Args:
        order_request: PDF/PNG file with customer ID
        token: JWT authentication token
        
    Returns:
        SuccessResponse with order data
    """
    if not order_request.file.content_type:
        raise HTTPException(
            status_code=400,
            detail="File content type is missing"
        )
    
    validate_file_type(order_request.file.content_type)
    
    # Save uploaded file
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}.pdf"
    
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(order_request.file.file, f)
        
        # Extract orders using AI agent
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        company_id = await JWTBearer().get_company_id(token)
        extractor = PDFExtractor(
            company_id=int(company_id) if company_id else None
        )
        orders = await extractor(file_bytes, order_request.file.content_type)
        
        # Send to third-party API
        config = await get_company_config(token)
        api_service = config.get("api-service", "")
        orders_endpoint = api_service.get("order", "")
        
        if not orders_endpoint:
            raise HTTPException(
                status_code=400,
                detail="Order endpoint not configured for this company"
            )
        
        ms_code = await JWTBearer().get_user_ms_code(token)
        
        logger.info(f"Sending orders to: {orders_endpoint}")
        response = await RequestService.post_request(
            orders_endpoint,
            data={
                "ms_code": str(ms_code),
                "cus_id": str(order_request.cus_id),
                "orders": orders
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail="Failed to send orders to third party service"
            )
        
        result = response.json()
        resp = result.get("data", {})
        
        # Save order to database
        await _save_order_to_database(company_id, ms_code, resp)
        
        return SuccessResponse(
            message="PDF/PNG extraction successful",
            data=resp
        )
        
    except Exception as e:
        logger.info(f"Error during order extraction: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred during order extraction"
        )
    finally:
        if file_path.exists():
            file_path.unlink()


async def _save_order_to_database(company_id, ms_code, resp):
    """Helper function to save order and items to database."""
    client = get_database_client()
    
    order_record = await client.order.create(
        data={
            "order_id": str(resp.get("order_id", "")),
            "company_id": int(company_id) if company_id else 0,
            "user_id": str(ms_code) if ms_code else "0",
            "total_amount": resp.get("total_amount", 0.0),
        }
    )
    
    orders_list = resp.get("orders", []) or []
    if orders_list:
        items_to_create: list[dict[str, Any]] = []
        for item in orders_list:
            item_data = {
                "order_id": order_record.id,
                "product_name": item.get("name", ""),
                "barcode": item.get("barcode", ""),
                "quantity": int(item.get("quantity", 0) or 0),
                "price": float(item.get("price", 0.0) or 0.0),
            }
            if item.get("status", "none") == "added":
                items_to_create.append(item_data)
        
        if items_to_create:
            await client.item.create_many(data=items_to_create)  # type: ignore


@app.post("/get_orders", dependencies=[Depends(JWTBearer())], tags=["Order"])
async def get_orders(
    token: str = Depends(JWTBearer())
) -> SuccessResponse:
    """
    Retrieve orders from the database for the authenticated company.
    
    Args:
        token: JWT authentication token
    Returns:
        SuccessResponse with list of orders
    """

    company_id = await JWTBearer().get_company_id(token)
    client = get_database_client()
    
    orders = await client.order.find_many(
        where={"company_id": int(company_id) if company_id else 0},
        include={"items": True}
    )
    
    orders_data = []
    for order in orders:
        total = 0
        order_dict = {
            "id": order.id,
            "order_id": order.order_id,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "items": [
                {
                    "id": item.id,
                    "name": getattr(item, "product_name", ""),
                    "barcode": getattr(item, "barcode", ""),
                    "quantity": item.quantity
                }
                for item in (order.items or [])
            ]
        }

        for item in order.items or []:
            total += item.quantity * item.price
        order_dict["total_amount"] = total

        orders_data.append(order_dict)
    
    return SuccessResponse(
        message="Orders retrieved successfully",
        data=orders_data
    )


@app.post("/verify", dependencies=[Depends(JWTBearer())], tags=["Order"])
async def verify_order(
    order: OrderIdRequest,
    token: str = Depends(JWTBearer())
) -> SuccessResponse:
    """
    Verify order with third-party service.
    
    Args:
        order_id: Order ID to verify
        token: JWT authentication token
        
    Returns:
        SuccessResponse with verification data
    """
    config = await get_company_config(token)
    api_service = config.get("api-service", "")
    verify_endpoint = api_service.get("verify", "")


    if not verify_endpoint:
        raise HTTPException(
            status_code=400,
            detail="Verify endpoint not configured for this company"
        )
    

    response = await RequestService.post_request(
        verify_endpoint,
        data={"order_id": order.order_id}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Failed to verify order extraction"
        )
    #change database status to verified
    client = get_database_client()
    await client.order.update_many(
        where={"order_id": order.order_id},
        data={"status": OrderStatus.COMPLETED}
    )

    result = response.json()
    resp = result.get("data", {})
    
    return SuccessResponse(
        message="Order extraction verified successfully",
        data=resp
    )


@app.delete("/cleanup-uploads", dependencies=[Depends(JWTBearer())], tags=["Maintenance"])
async def cleanup_uploads():
    """Clean up all files in the uploads directory."""
    for file in UPLOAD_DIR.iterdir():
        if file.is_file():
            file.unlink()
    
    return SuccessResponse(message="Upload directory cleaned up successfully")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)