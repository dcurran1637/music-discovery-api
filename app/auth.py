import os
from fastapi import Header, HTTPException, status, Depends

WRITE_API_KEY = os.getenv("WRITE_API_KEY", "demo_write_key_123")

def require_write_api_key(x_api_key: str = Header(None)):
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    if x_api_key != WRITE_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return True
