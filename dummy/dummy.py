import json
import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import RedirectResponse

from fastapi.middleware.cors import CORSMiddleware
import random

from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel


class OrderRequest(BaseModel):
    ms_code: str
    cus_id: str
    orders: list

logging.basicConfig(level=logging.INFO)
logging.addLevelName(logging.DEBUG, "DEBUG")
logger = logging.getLogger(__name__)


app = FastAPI(title="PDF Third party dummy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # /vercel.svg is automatically served when included in the public/** directory.
    return RedirectResponse("/vercel.svg", status_code=307)

@app.get("/")
async def root():
    return {"message": "Welcome to the PDF Third party dummy API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/customers")
async def get_customers():
    try:
        # Dummy response
        customers = [
            {"id": 1, "name": "Customer A", "cus_id": "C001"},
            {"id": 2, "name": "Customer B", "cus_id": "C002"},
        ]

        return {"customers": customers}
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/order")
async def add_order(orders: OrderRequest):
    """
        orders: contains list of orders to be added that
        barcode, quantity
        Example:
        [
            {
                "barcode": "1234567890123",
                "quantity": 2
            },
            {
                "barcode": "9876543210987",
                "quantity": 1
            }
        ]

        then find order details from products.json and return order details with status
        Example response:
        {"message": "Orders added successfully",
         "data": [
            {
                "barcode": "1234567890123",
                "quantity": 2,
                "material_id": "M001",
                "name": "Product A",
                "price": 10.0,
                "status": "added"
            },
            {
                "barcode": "9876543210987",
                "quantity": 1,
                "material_id": "M002",
                "name": "Product B",
                "price": 20.0,
                "status": "added"
            }
        ]
        }

        
    """
    try:
        # Dummy response
        result = []
        products = open("products.json", "r", encoding="utf-8")
        product_data = json.load(products)
        for order in orders.orders:
            try:
                barcode = order.get("barcode")
                quantity = order.get("quantity", 1)
                product_info = product_data.get(barcode, None)

                # make randomaly product that quantity is more than available stock as not available that about 10% of the time
                probability = random.random()
                    
                if product_info:
                    status = "added"
                    if probability < 0.1:
                        status = "not available"
                    result.append({
                        "material_id": product_info["MaterialID"],
                        "barcode": barcode,
                        "name": product_info["ProductName"],
                        "price": product_info["CurrentPrice"],
                        "quantity": quantity,
                        "status": status
                    })
                    continue
            except Exception as e:
                logger.info(f"Error processing order: {e}")
                pass
            result.append({
                "material_id": None,
                "barcode": barcode,
                "name": None,
                "price": None,
                "quantity": quantity,
                "status": "not found"
            })
       
        order_id = str(uuid.uuid4())


        return {
            "message": "Orders added successfully",
            "data": {
                "ms_code": orders.ms_code,
                "cus_id": orders.cus_id,
                "orders": result,
                "order_id": order_id,
                "total_price": sum(order.get("price", 0) * order.get("quantity", 0) for order in result if order.get("status") == "added")
            }
        }
    except Exception as e:
        logger.info(f"Error processing file: {e}")
        return {
            "message": "Error adding orders",
            "data": {
                "ms_code": orders.ms_code,
                "cus_id": orders.cus_id,
                "orders": [],
                "order_id": None,
                "total_price": 0
            }
        }


class OrderRequestId(BaseModel):
    order_id: str

@app.post("/verify")
async def verify_order(order: OrderRequestId):
    """
        Verify order by order_id
        Example response:
        {
            "order_id": "some-order-id",
            "status": "verified"
        }
    """
    # Dummy response
    return {
        "order_id": order.order_id,
        "status": "verified"
    }
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)