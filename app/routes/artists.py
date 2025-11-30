from fastapi import APIRouter, HTTPException, Query, Depends, Header
from typing import List, Optional
import os
import json
import redis.asyncio as aioredis
from ..spotify_client import get_artist, spotify_search_artists
from ..oauth import get_user_profile
from .. import auth

router = APIRouter(prefix="/api/artists", tags=["artists"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 300  # 5 minutes

async def authenticate_user(authorization: Optional[str]):
    """Authenticate user and return (user_id, spotify_token) tuple."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must start with 'Bearer '")
    
    token_str = authorization.split(" ")[1]
    
    # Try to decode as JWT first (for backward compatibility)
    spotify_token = None
    user_id = None
    
    try:
        user_payload = auth.decode_jwt_token(token_str)
        user_id = user_payload.get("user_id")
        spotify_token = user_payload.get("spotify_access_token")
        
        if spotify_token:
            return user_id, spotify_token
    except:
        # Not a JWT or invalid JWT - treat as raw Spotify token
        pass
    
    # If not a JWT or JWT doesn't contain Spotify token, treat token_str as Spotify access token
    if not spotify_token:
        spotify_token = token_str
        try:
            profile = await get_user_profile(spotify_token)
            user_id = profile.get("id")
            
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid Spotify token: no user ID in profile")
            
            return user_id, spotify_token
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail="Authentication failed")
    
    raise HTTPException(status_code=401, detail="Invalid or expired token")

# ----------------------------
# Get artist info by ID
# ----------------------------
@router.get("/{artist_id}")
async def get_artist_info(
    artist_id: str,
    authorization: Optional[str] = Header(None, description="Bearer JWT token")
):
    user_id, spotify_token = await authenticate_user(authorization)

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

    user_id, spotify_token = await authenticate_user(authorization)
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
