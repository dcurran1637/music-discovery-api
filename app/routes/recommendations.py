from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from ..spotify_client import get_spotify_recommendations
from ..auth import verify_jwt_token
import redis.asyncio as aioredis
import os
import json
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/discover", tags=["recommendations"])

# Redis setup (optional caching)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CACHE_TTL = 300  # seconds

@router.get("/recommendations")
async def recommendations(
    genres: Optional[str] = Query(None, description="Comma-separated genres to filter"),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    released_after: Optional[str] = Query(None, description="YYYY-MM-DD"),
    user_id: str = Depends(verify_jwt_token),  # JWT auth
):
    """
    Returns Spotify-based track recommendations filtered by genre, popularity, and release date.
    """
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

    # 1. Fetch Spotify recommendations
    try:
        genre_list = [g.strip().lower() for g in genres.split(",")] if genres else None
        rec_tracks = await get_spotify_recommendations(
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
