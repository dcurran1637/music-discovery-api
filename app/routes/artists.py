from fastapi import APIRouter, HTTPException, Query, Depends, Header
from typing import List, Optional
import os
import json
import redis.asyncio as aioredis
from ..spotify_client import get_artist, spotify_search_artists
from ..crypto import decrypt
from .. import db, auth

router = APIRouter(prefix="/api/artists", tags=["artists"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 300  # 5 minutes

# Demo user fallback
DEMO_USER_ID = os.getenv("DEMO_USER_ID", "real_demo_user_id")  # replace with actual demo user ID

def resolve_user_and_token(authorization: Optional[str], require_spotify: bool = True):
    """
    Returns (user_id, spotify_token) tuple.
    If authorization missing/invalid, uses DEMO_USER_ID for read-only access.
    """
    user_id = DEMO_USER_ID
    spotify_token = None

    if authorization:
        token = authorization.split(" ")[-1] if authorization.startswith("Bearer ") else authorization
        try:
            user_payload = auth.verify_jwt_token(token)
            user_id = user_payload.get("user_id")
            session_id = user_payload.get("session_id")
            # Resolve Spotify token from session
            if require_spotify and session_id:
                session = db.get_session_tokens(session_id)
                if session:
                    try:
                        spotify_token = decrypt(session.get("access_token", ""))
                    except Exception:
                        spotify_token = None
            # Fallback to user tokens
            if require_spotify and not spotify_token:
                user_tokens = db.get_user_tokens(user_id)
                if user_tokens:
                    try:
                        spotify_token = decrypt(user_tokens.get("access_token", ""))
                    except Exception:
                        spotify_token = None
            # JWT embedded Spotify token
            if require_spotify and not spotify_token:
                spotify_token = user_payload.get("spotify_access_token")
        except Exception:
            if require_spotify:
                raise HTTPException(status_code=401, detail="Invalid token")
            # else, fallback to DEMO_USER_ID
    elif require_spotify:
        raise HTTPException(status_code=401, detail="Missing auth for Spotify access")

    return user_id, spotify_token

# ----------------------------
# Get artist info by ID
# ----------------------------
@router.get("/{artist_id}")
async def get_artist_info(
    artist_id: str,
    authorization: Optional[str] = Header(None, description="Bearer JWT token")
):
    user_id, spotify_token = resolve_user_and_token(authorization)
    if not spotify_token:
        raise HTTPException(status_code=401, detail="Spotify token unavailable for user")

    cache_key = f"artist:{artist_id}"
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        await redis.close()
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = await get_artist(artist_id, spotify_token)
    if not data:
        raise HTTPException(status_code=404, detail="Artist not found")

    result = {
        "id": data.get("id"),
        "name": data.get("name"),
        "genres": data.get("genres", []),
        "images": data.get("images", []),
        "followers": data.get("followers", {}).get("total"),
        "external_urls": data.get("external_urls", {}),
    }

    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(cache_key, json.dumps(result), ex=CACHE_TTL)
        await redis.close()
    except Exception:
        pass

    return result

# ----------------------------
# Get artists by genres
# ----------------------------
@router.get("/by-genres/")
async def get_artists_by_genres(
    genres: List[str] = Query(..., description="List of genres"),
    authorization: Optional[str] = Header(None, description="Bearer JWT token")
):
    if not genres:
        raise HTTPException(status_code=400, detail="At least one genre is required.")

    user_id, spotify_token = resolve_user_and_token(authorization)
    if not spotify_token:
        raise HTTPException(status_code=401, detail="Spotify token unavailable for user")

    cache_key = f"artists:genres:{user_id}:{'-'.join(sorted(genres))}"

    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        await redis.close()
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    found_artists = {}
    for genre in genres:
        search_results = await spotify_search_artists(f"genre:{genre}", spotify_token)
        for artist in search_results:
            artist_id = artist.get("id")
            if artist_id and artist_id not in found_artists:
                found_artists[artist_id] = {
                    "id": artist_id,
                    "name": artist.get("name"),
                    "genres": artist.get("genres", []),
                    "images": artist.get("images", []),
                    "followers": artist.get("followers", {}).get("total"),
                    "external_urls": artist.get("external_urls", {}),
                }

    final_results = list(found_artists.values())

    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(cache_key, json.dumps(final_results), ex=CACHE_TTL)
        await redis.close()
    except Exception:
        pass

    return final_results
