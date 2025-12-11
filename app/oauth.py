"""Handles Spotify OAuth authentication using authorization code flow."""

import os
import base64
import httpx
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "demo_jwt_secret")
JWT_ALGORITHM = "HS256"

# Redis stores auth states, falls back to memory if unavailable
import redis.asyncio as aioredis
import json

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
AUTH_STATE_TTL = 15 * 60

_auth_states_fallback: Dict[str, Dict[str, Any]] = {}


async def _set_state(state: str, user_id: str):
    payload = {"user_id": user_id, "created_at": datetime.utcnow().isoformat()}
    try:
        r = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await r.set(f"oauth_state:{state}", json.dumps(payload), ex=AUTH_STATE_TTL)
        await r.close()
    except Exception:
        _auth_states_fallback[state] = {"user_id": user_id, "created_at": datetime.utcnow()}


async def _pop_state(state: str) -> Optional[Dict[str, Any]]:
    try:
        r = await aioredis.from_url(REDIS_URL, decode_responses=True)
        data = await r.get(f"oauth_state:{state}")
        if data:
            await r.delete(f"oauth_state:{state}")
            await r.close()
            return json.loads(data)
        await r.close()
    except Exception:
        pass

    return _auth_states_fallback.pop(state, None)


async def generate_auth_url(user_id: str) -> tuple[str, str]:
    """Create a Spotify login URL and return it with the security state token."""
    if not SPOTIFY_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spotify Client ID not configured"
        )
    
    state = secrets.token_urlsafe(32)
    # Persist the state in Redis (async)
    await _set_state(state, user_id)
    
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": " ".join([
            "user-read-private",
            "user-read-email",
            "user-library-read",
            "user-top-read",
            "playlist-read-private",
            "playlist-read-collaborative",
            "playlist-modify-public",
            "playlist-modify-private",
            "user-read-playback-state",
        ]),
        "state": state,
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    auth_url = f"{SPOTIFY_AUTH_URL}?{query_string}"
    
    return auth_url, state


async def exchange_code_for_token(code: str, state: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access token.
    
    Args:
        code: Authorization code from Spotify
        state: State parameter for verification
        
    Returns:
        Token response with access_token, refresh_token, etc.
    """
    # Verify state (pop from Redis or fallback)
    state_data = await _pop_state(state)
    if not state_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter"
        )

    # If created_at is stored as ISO string, parse and validate age
    try:
        created = state_data.get("created_at")
        if isinstance(created, str):
            created_dt = datetime.fromisoformat(created)
        else:
            created_dt = created
        if datetime.utcnow() - created_dt > timedelta(minutes=15):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State expired"
            )
    except Exception:
        # If parsing fails, continue (best-effort) — state is considered valid
        pass
    
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spotify credentials not configured"
        )
    
    # Prepare token request
    auth = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
            headers={"Authorization": f"Basic {auth}"},
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token"
            )
        
        token_data = response.json()
        return {
            "user_id": state_data["user_id"],
            "spotify_access_token": token_data.get("access_token"),
            "spotify_refresh_token": token_data.get("refresh_token"),
            "spotify_token_expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type", "Bearer"),
        }


async def refresh_spotify_token(refresh_token: str) -> Dict[str, Any]:
    """
    Refresh expired Spotify access token using refresh token.
    
    Args:
        refresh_token: Spotify refresh token
        
    Returns:
        New token data
    """
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spotify credentials not configured"
        )
    
    auth = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Authorization": f"Basic {auth}"},
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh token"
            )
        
        return response.json()


def create_jwt_token(
    user_id: str,
    session_id: str,
    expires_in: int = 3600,
    spotify_access_token: str | None = None,
    spotify_refresh_token: str | None = None,
) -> str:
    """
    Create JWT token containing Spotify access token.
    
    Args:
        user_id: User ID
        spotify_access_token: Spotify access token
        spotify_refresh_token: Spotify refresh token (optional)
        expires_in: Token expiration time in seconds
        
    Returns:
        JWT token
    """
    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "exp": datetime.utcnow() + timedelta(seconds=expires_in),
        "iat": datetime.utcnow(),
    }
    if spotify_access_token:
        payload["spotify_access_token"] = spotify_access_token
    if spotify_refresh_token:
        payload["spotify_refresh_token"] = spotify_refresh_token
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


async def get_user_profile(spotify_access_token: str) -> Dict[str, Any]:
    """
    Get current user's profile from Spotify.
    
    Args:
        spotify_access_token: Spotify access token
        
    Returns:
        User profile data
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SPOTIFY_API_URL}/me",
            headers={"Authorization": f"Bearer {spotify_access_token}"},
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user profile"
            )
        
        return response.json()
