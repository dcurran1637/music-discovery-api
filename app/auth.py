import os
from fastapi import Header, HTTPException, status, Depends
import jwt

WRITE_API_KEY = os.getenv("WRITE_API_KEY", "demo_write_key_123")
JWT_SECRET = os.getenv("JWT_SECRET", "demo_jwt_secret")
JWT_ALGORITHM = "HS256"

def require_write_api_key(x_api_key: str = Header(None)):
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    if x_api_key != WRITE_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return True

def verify_jwt_token(authorization: str = Header(...)):
    """
    Verifies JWT token from Authorization header: "Bearer <token>"
    Returns the full payload including Spotify tokens.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


