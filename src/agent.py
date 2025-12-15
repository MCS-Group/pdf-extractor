import os
import sys
import logging
import asyncio

# Add project root to path for local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from dataclasses import dataclass

from typing import Optional, List
from pydantic_ai import Agent, BinaryContent
from pydantic import Field

load_dotenv()

from src.config import configs
from src.schemas.transcripts import Order, PROMPT_DEFAULT

logging.basicConfig(filename="logs/agent.log", level=logging.INFO, filemode="w", encoding="utf-8")
logger = logging.getLogger(__name__)



class PDFExtractor:
    def __init__(self, company_id: Optional[int] = None):
        self.company_id = company_id
        self.agent = self.get_agent()

    def get_agent_prompt(self) -> str:
        if self.company_id is not None:
            config = configs.get(self.company_id)
            if config and "prompt" in config:
                return config["prompt"]
        return PROMPT_DEFAULT

    def get_output_type(self):
        if self.company_id is not None:
            config = configs.get(self.company_id)
            if config and "output_type" in config:
                return config["output_type"]
        return Order

    def get_agent(self) -> Agent[None, Order]:
        prompt = self.get_agent_prompt()
        output_type = self.get_output_type()
        pdf_extractor_agent = Agent(
            model="google-gla:gemini-2.5-flash",
            output_type=output_type,
            system_prompt=prompt,
        )
        return pdf_extractor_agent

    async def run_agent(self, file_bytes: bytes, file_media: str = "application/pdf") -> list:
        result = await self.agent.run([
            BinaryContent(file_bytes, media_type=file_media)
        ])
        orders = []
        for item in result.output.items:
            orders.append({
                "name": item.name,
                "barcode": item.barcode,
                "quantity": item.quantity
            })
        return orders

    async def extract_order_from_url(self, file_url: str) -> list:
        file = open(file_url, "rb").read()
        file_media = "application/pdf"
        if not file_url or not file_url.lower().endswith('.pdf'):
            if file_url.lower().endswith('.png'):
                file_media = "image/png"
            raise ValueError("Invalid file URL or unsupported file type. Only PDF files are supported.")
        
        file_bytes = file
        result = await self.run_agent(file_bytes, file_media)
        return result
    
    async def __call__(self, file_bytes: bytes, file_media: str = "application/pdf") -> list:
        return await self.run_agent(file_bytes, file_media)


if __name__ == "__main__":
    async def main():
        file_path = "docs/BTI.pdf"  # Replace with your PDF file path

        extractor = PDFExtractor(company_id=1)
        
        orders = await extractor.extract_order_from_url(file_path)
        for order in orders:
            print(f"Barcode: {order['barcode']}, Quantity: {order['quantity']}")

    asyncio.run(main())
