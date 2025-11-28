from fastapi import APIRouter, HTTPException, Query, Header
import os
import json
import redis.asyncio as aioredis
from typing import Optional
from ..spotify_client import get_track, get_artist
from ..crypto import decrypt
from .. import db, auth

router = APIRouter(prefix="/api/tracks", tags=["tracks"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 300  # seconds

# Demo user fallback
DEMO_USER_ID = os.getenv("DEMO_USER_ID", "real_demo_user_id")  # replace with actual demo user ID

def resolve_user_and_token(authorization: Optional[str]):
    """
    Returns (user_id, spotify_token).
    Fallback to DEMO_USER_ID if no JWT is provided.
    """
    user_id = DEMO_USER_ID
    spotify_token = None

    if authorization:
        token = authorization.split(" ")[-1] if authorization.startswith("Bearer ") else authorization
        try:
            user_payload = auth.verify_jwt_token(token)
            user_id = user_payload.get("user_id")
            session_id = user_payload.get("session_id")

            if session_id:
                session = db.get_session_tokens(session_id)
                if session:
                    try:
                        spotify_token = decrypt(session.get("access_token", ""))
                    except Exception:
                        spotify_token = None

            if not spotify_token:
                user_tokens = db.get_user_tokens(user_id)
                if user_tokens:
                    try:
                        spotify_token = decrypt(user_tokens.get("access_token", ""))
                    except Exception:
                        spotify_token = None

            if not spotify_token:
                spotify_token = user_payload.get("spotify_access_token")
        except Exception:
            # Invalid token, fallback to demo user
            pass

    return user_id, spotify_token

# -------------------------
# Get track info
# -------------------------
@router.get("/{track_id}")
async def get_track_info(track_id: str, authorization: Optional[str] = Header(None)):
    user_id, spotify_token = resolve_user_and_token(authorization)

    cache_key = f"track:{user_id}:{track_id}"
    redis = None

    # Try Redis cache
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    finally:
        if redis:
            await redis.close()

    # Fetch track data from Spotify
    data = await get_track(track_id, spotify_token)
    if not data:
        raise HTTPException(status_code=404, detail="Track not found")

    # Enrich with first artist's genres
    artist_info = data.get("artists", [{}])[0]
    artist_id = artist_info.get("id")
    genres = []
    if artist_id:
        art = await get_artist(artist_id, spotify_token)
        if art:
            genres = art.get("genres", [])

    result = {
        "id": data.get("id"),
        "title": data.get("name"),
        "artist": artist_info.get("name"),
        "album": data.get("album", {}).get("name"),
        "durationMs": data.get("duration_ms"),
        "previewUrl": data.get("preview_url"),
        "genres": genres,
    }

    # Save to Redis
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(cache_key, json.dumps(result), ex=CACHE_TTL)
    except Exception:
        pass
    finally:
        if redis:
            await redis.close()

    return result
