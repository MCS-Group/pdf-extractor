from prisma import Prisma
import logging
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client: Prisma | None = None

    async def connect_db(self) -> Prisma:
        if self.client is None:
            self.client = Prisma()
            await self.client.connect()
            logger.info("Database connected.")
        return self.client

    async def disconnect_db(self):
        if self.client:
            await self.client.disconnect()
            logger.info("Database disconnected.")
            self.client = None