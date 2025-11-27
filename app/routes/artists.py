from fastapi import APIRouter, HTTPException, Query
import os
import json
import redis.asyncio as aioredis
from typing import List
from ..spotify_client import get_artist, spotify_search_artists

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


# -------------------------------------------------------------
# NEW ENDPOINT: Get artists based on top genres
# -------------------------------------------------------------
@router.get("/by-genres/")
async def get_artists_by_genres(genres: List[str] = Query(...)):
    """
    Returns recommended artists based on user's top genres.
    """
    if not genres:
        raise HTTPException(status_code=400, detail="At least one genre is required.")

    cache_key = f"artists:genres:{'-'.join(sorted(genres))}"

    # Try cache
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        if cached:
            await redis.close()
            return json.loads(cached)
        await redis.close()
    except Exception:
        pass

    # Gather artists from Spotify search
    found_artists = {}

    for genre in genres:
        search_results = await spotify_search_artists(f"genre:{genre}")

        for artist in search_results:
            artist_id = artist.get("id")
            if artist_id not in found_artists:
                found_artists[artist_id] = {
                    "id": artist_id,
                    "name": artist.get("name"),
                    "genres": artist.get("genres", []),
                    "images": artist.get("images", []),
                    "followers": artist.get("followers", {}).get("total"),
                    "external_urls": artist.get("external_urls", {}),
                }

    final_results = list(found_artists.values())

    # Save to cache
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(cache_key, json.dumps(final_results), ex=300)
        await redis.close()
    except Exception:
        pass

    return final_results
