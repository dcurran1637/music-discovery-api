from fastapi import APIRouter, HTTPException
import os
import json
import redis.asyncio as aioredis
from ..spotify_client import get_track, get_artist

router = APIRouter(prefix="/api/tracks", tags=["tracks"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@router.get("/{track_id}")
async def get_track_info(track_id: str):
	cache_key = f"track:{track_id}"
	try:
		redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
		cached = await redis.get(cache_key)
		await redis.close()
		if cached:
			return json.loads(cached)
	except Exception:
		pass

	# Try to fetch track (uses client credentials if no user token configured)
	data = await get_track(track_id)
	if not data:
		raise HTTPException(status_code=404, detail="Track not found")

	# Enrich with artist genres (first artist)
	artist_id = data.get("artists", [{}])[0].get("id")
	genres = []
	if artist_id:
		art = await get_artist(artist_id)
		if art:
			genres = art.get("genres", [])

	result = {
		"id": data.get("id"),
		"title": data.get("name"),
		"artist": data.get("artists", [{}])[0].get("name"),
		"album": data.get("album", {}).get("name"),
		"durationMs": data.get("duration_ms"),
		"previewUrl": data.get("preview_url"),
		"genres": genres,
	}

	try:
		redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
		await redis.set(cache_key, json.dumps(result), ex=300)
		await redis.close()
	except Exception:
		pass

	return result
