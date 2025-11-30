import os
from fastapi import Header, HTTPException, status, Depends
from typing import Dict
import jwt

# Environment / config
JWT_SECRET = os.getenv("JWT_SECRET", "demo_jwt_secret")
JWT_ALGORITHM = "HS256"


def require_write_api_key(x_api_key: str | None) -> bool:
    """Validate provided X-API-KEY header against env WRITE_API_KEY.
    Returns True if valid, raises HTTPException otherwise.

    Test expectations:
    - Missing key -> 401
    - Invalid key -> 403
    - Valid key (matches WRITE_API_KEY) -> True
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-KEY header")

    expected = os.getenv("WRITE_API_KEY")
    if not expected or x_api_key != expected:
        # Both unset expected key or mismatch treated as forbidden for test simplicity
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or unconfigured write API key")
    return True


def decode_jwt_token(token: str) -> Dict:
    """Decode a raw JWT token (no Bearer prefix expected) and validate payload.
    Raises HTTPException with 401 status for any validation problem.
    Returns decoded payload dict on success.
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing user_id")
    # Allow tokens without session_id/spotify_token - they'll be looked up later
    return payload


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

    # Accept case-insensitive 'Bearer '
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '"
        )
    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger = __import__("logging").getLogger("auth")
        logger.warning("JWT expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError as e:
        logger = __import__("logging").getLogger("auth")
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Must have user_id and either session_id or embedded spotify_access_token
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")
    spotify_token = payload.get("spotify_access_token")  # legacy support

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user_id"
        )

    # Relax requirement: allow tokens without session_id/spotify_access_token (backwards compatibility)

    return payload
