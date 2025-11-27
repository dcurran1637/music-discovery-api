from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from ..spotify_client import get_spotify_recommendations
from ..auth import verify_jwt_token
import redis.asyncio as aioredis
import os
import json
from datetime import datetime, timedelta
from .. import db
from ..crypto import decrypt, encrypt
from ..oauth import refresh_spotify_token

router = APIRouter(prefix="/api/discover", tags=["recommendations"])

# Redis setup (optional caching)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CACHE_TTL = 300  # seconds

@router.get("/recommendations")
async def recommendations(
    genres: Optional[str] = Query(None, description="Comma-separated genres to filter"),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    released_after: Optional[str] = Query(None, description="YYYY-MM-DD"),
    user_payload = Depends(verify_jwt_token),  # JWT auth - returns full payload
):
    """
    Returns Spotify-based track recommendations filtered by genre, popularity, and release date.
    Uses the Spotify access token from the JWT payload.
    """
    user_id = user_payload.get("user_id")

    # Fetch encrypted tokens from DB
    user_tokens = db.get_user_tokens(user_id)

    spotify_token = None
    # Primary: try persisted tokens
    if user_tokens:
        try:
            spotify_token = decrypt(user_tokens.get("access_token", ""))
        except Exception:
            spotify_token = None

        # If access token expired or missing, try to refresh using stored refresh token
        expires_at = user_tokens.get("expires_at")
        if (not spotify_token) and user_tokens:
            try:
                refresh_enc = user_tokens.get("refresh_token")
                refresh_token = decrypt(refresh_enc) if refresh_enc else None
                if refresh_token:
                    token_data = await refresh_spotify_token(refresh_token)
                    # Persist new tokens
                    enc_access = encrypt(token_data.get("access_token"))
                    enc_refresh = encrypt(token_data.get("refresh_token") or refresh_token)
                    new_expires_at = (datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat()
                    db.put_user_tokens(user_id, enc_access, enc_refresh, new_expires_at)
                    spotify_token = token_data.get("access_token")
            except Exception:
                spotify_token = spotify_token

    # Fallback: if no persisted tokens, allow JWT to contain spotify_access_token (legacy/tests)
    if not spotify_token:
        spotify_token = user_payload.get("spotify_access_token")
        # If JWT carries an expires timestamp for spotify token, we don't validate it here
    
    cache_key = f"recommendations:{user_id}:{genres}:{min_popularity}:{released_after}"
    
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        if cached:
            await redis.close()
            return json.loads(cached)
    except Exception:
        # If redis is not available, continue without caching
        cached = None

    # 1. Fetch Spotify recommendations using user's token
    try:
        genre_list = [g.strip().lower() for g in genres.split(",")] if genres else None
        rec_tracks = await get_spotify_recommendations(
            spotify_token=spotify_token,
            genres=genre_list,
            min_popularity=min_popularity,
            released_after=released_after
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spotify API error: {str(e)}")

    # 2. Cache results
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(cache_key, json.dumps(rec_tracks), ex=CACHE_TTL)
        await redis.close()
    except Exception:
        # If redis is not available, continue without caching
        pass

    return {"recommendedTracks": rec_tracks}
