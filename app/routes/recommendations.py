from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from ..spotify_client import get_spotify_recommendations
from ..auth import verify_jwt_token
import aioredis
import os
import json
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/discover", tags=["recommendations"])

# Redis setup (optional caching)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis = aioredis.from_url(REDIS_URL, decode_responses=True)

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
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # 1. Fetch Spotify recommendations
    try:
        rec_tracks = await get_spotify_recommendations(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spotify API error: {str(e)}")

    # 2. Apply genre filtering
    if genres:
        genre_set = set([g.strip().lower() for g in genres.split(",")])
        rec_tracks = [
            t for t in rec_tracks
            if any(g.lower() in genre_set for g in t.get("genres", []))
        ]

    # 3. Apply popularity filter
    if min_popularity is not None:
        rec_tracks = [t for t in rec_tracks if t.get("popularity", 0) >= min_popularity]

    # 4. Apply release date filter
    if released_after:
        try:
            dt = datetime.strptime(released_after, "%Y-%m-%d")
            rec_tracks = [
                t for t in rec_tracks
                if t.get("album", {}).get("release_date") and datetime.strptime(t["album"]["release_date"], "%Y-%m-%d") > dt
            ]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid released_after date format. Use YYYY-MM-DD.")

    # 5. Cache results
    await redis.set(cache_key, json.dumps(rec_tracks), ex=CACHE_TTL)

    return {"recommendedTracks": rec_tracks}
