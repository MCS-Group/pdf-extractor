from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..database import Database

from .auth_handler import decodeJWT


class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request) # type: ignore
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            if not self.verify_jwt(credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid token or expired token.")
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

    def verify_jwt(self, jwtoken: str) -> bool:
        isTokenValid: bool = False

        try:
            payload = decodeJWT(jwtoken)
        except:
            payload = None
        if payload:
            isTokenValid = True
        return isTokenValid
    
    def get_user_id(self, jwtoken: str) -> str | None:
        try:
            payload = decodeJWT(jwtoken)
            return payload.get("user_id")
        except:
            return None
        
    async def get_company_id(self, jwtoken: str) -> str | None:
        """
            Get company_id from database based on user_id in the token payload.
            Args:
                jwtoken (str): The JWT token.
            Returns:
                str | None: The company_id if found, else None.
        """
        try:
            db = Database()
            db_client = await db.connect_db()
            payload = decodeJWT(jwtoken)
            if not payload:
                return None
            user = await db_client.user.find_unique(
                where={'id': int(payload.get("user_id", ""))},
                include={'company': True}
            )
            if user and user.company:
                return str(user.company.id)
            return None
        except:
            return None
        
    async def get_user_ms_code(self, jwtoken: str):
        """
            Get user object from database based on user_id in the token payload.
            Args:
                jwtoken (str): The JWT token.
            Returns:
                User | None: The user object if found, else None.
        """
        try:
            db = Database()
            db_client = await db.connect_db()
            payload = decodeJWT(jwtoken)
            if not payload:
                return None
            user = await db_client.user.find_unique(
                where={'id': int(payload.get("user_id", ""))}
            )
            return user.ms_code if user else None
        except:
            return None
        