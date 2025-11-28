import os
from fastapi import Header, HTTPException, status, Depends
from typing import Dict
import jwt

# Environment / config
JWT_SECRET = os.getenv("JWT_SECRET", "demo_jwt_secret")
JWT_ALGORITHM = "HS256"


def verify_jwt_token(authorization: str = Header(...)) -> Dict:
    """
    FastAPI dependency: verifies a JWT token from the Authorization header.
    Expects: Authorization: Bearer <token>
    Returns decoded payload dict.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '"
        )

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # Must have user_id and either session_id or embedded spotify_access_token
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")
    spotify_token = payload.get("spotify_access_token")  # legacy support

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user_id"
        )

    if not session_id and not spotify_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing session_id or spotify_access_token"
        )

    return payload
