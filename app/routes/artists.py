from fastapi import APIRouter, HTTPException
import os
import json
import redis.asyncio as aioredis
from ..spotify_client import get_artist

router = APIRouter(prefix="/api/artists", tags=["artists"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@router.get("/{artist_id}")
async def get_artist_info(artist_id: str):
    cache_key = f"artist:{artist_id}"
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        await redis.close()
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = await get_artist(artist_id)
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
        await redis.set(cache_key, json.dumps(result), ex=300)
        await redis.close()
    except Exception:
        pass

    return result
