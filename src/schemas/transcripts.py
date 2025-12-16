
import os
import sys
import logging
import asyncio

from fastapi import File, UploadFile
from pydantic import BaseModel

# Add project root to path for local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from dataclasses import dataclass

from typing import Any, Dict, Optional, List
from pydantic_ai import Agent, BinaryContent
from pydantic import Field

from dataclasses import dataclass


@dataclass
class Argument:
    argument: str


@dataclass
class Item:
    name:       str
    barcode:    str
    quantity:   int

@dataclass
class Order:
    items: List[Item]


PROMPT_DEFAULT = """You are a data extraction assistant. Extract only purchase/order information from the provided document, regardless of language.

STRICT MATCHING RULES:
- You must extract barcodes EXACTLY as they appear in the document.
- Do NOT correct, fix, repair, autocomplete, or change any barcode digits.
- Do NOT extract any barcode that is “similar” or “close” to one in the document.
- If a barcode differs by even ONE digit, it must NOT be extracted.
- If you are uncertain whether a number is a barcode, skip it.
- Never guess or generate barcode numbers.

Extraction Rules:
1. Extract ONLY:
   - Name: the product name associated with each barcode.
   - Barcode: long numeric codes (usually 10–14 digits) if and ONLY if they appear identically in the document.
   - Quantity: the ordered amount directly associated with each barcode.

2. Multilingual support:
   The document may be in English, Mongolian, Russian, or mixed.
"""



### API Models ###
class LoginRequest(BaseModel):
    username: str
    password: str

class PdfFile(BaseModel):
    #form data upload
    cus_id: str = Field(..., alias="customer_id")
    file: UploadFile = File(...)


class OrderIdRequest(BaseModel):
    order_id: str

#response models
#success response model
class SuccessResponse(BaseModel):
    message: str
    data: Any | None = {}
    payload: Dict[str, Any] | None = {}