#here is get, post request service that interacts with the api endpoints to third party services
import httpx


class RequestService:
    @staticmethod
    async def post_request(url: str, data: dict, headers: dict = {}) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response

    @staticmethod
    async def get_request(url: str, headers: dict = {}) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response