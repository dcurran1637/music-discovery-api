from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional
from collections import Counter
import os
import json
from datetime import datetime, timedelta
import redis.asyncio as aioredis

from ..spotify_client import (
    get_spotify_recommendations,
    get_user_top_artists,
    get_user_top_tracks
)
from .. import db, auth
from ..oauth import refresh_spotify_token
from ..crypto import decrypt, encrypt
from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/discover", tags=["recommendations"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 300  # seconds
MAX_SEEDS = 5
DEFAULT_GENRES = ["pop", "rock", "hip-hop"]


@router.get("/recommendations")
async def recommendations(
    authorization: Optional[str] = Header(None, description="Bearer JWT token"),
    genres: Optional[str] = Query(None, description="Comma-separated genres to filter"),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    released_after: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """
    Returns Spotify track recommendations filtered by genre, popularity, and release date.
    Automatically determines user's top genres, top artists, and top tracks if not provided.
    Falls back to a demo user if no JWT is provided.
    """

    # ----------------------------
    # Determine user and token
    # ----------------------------
    if authorization and authorization.startswith("Bearer "):
        token_str = authorization.split(" ")[1]
        try:
            user_payload = auth.verify_jwt_token(token_str)
            user_id = user_payload.get("user_id")
            session_id = user_payload.get("session_id")
            spotify_token = user_payload.get("spotify_access_token")
        except Exception:
            # invalid token, fallback to demo
            user_id = "user_demo_1"
            session_id = None
            spotify_token = None
    else:
        # No token, demo fallback
        user_id = "user_demo_1"
        session_id = None
        spotify_token = None

    # ----------------------------
    # Try session or legacy tokens if available
    # ----------------------------
    if not spotify_token and session_id:
        session = db.get_session_tokens(session_id)
        if session:
            try:
                spotify_token = decrypt(session.get("access_token", ""))
            except Exception:
                spotify_token = None

    if not spotify_token and user_id != "user_demo_1":
        user_tokens = db.get_user_tokens(user_id)
        if user_tokens:
            try:
                spotify_token = decrypt(user_tokens.get("access_token", ""))
            except Exception:
                spotify_token = None

    # Demo fallback uses client credentials token
    if not spotify_token:
        from ..spotify_client import get_spotify_token
        spotify_token = await get_spotify_token()

    # ----------------------------
    # Determine seed genres, artists, tracks
    # ----------------------------
    genre_list = []
    seed_artists = []
    seed_tracks = []

    if genres:
        genre_list = [g.strip().lower() for g in genres.split(",") if g.strip()][:MAX_SEEDS]

    if not genre_list:
        try:
            if spotify_token:
                top_artists = await get_user_top_artists(spotify_token, limit=MAX_SEEDS)
                top_tracks = await get_user_top_tracks(spotify_token, limit=MAX_SEEDS)

                if top_artists:
                    genre_counter = Counter()
                    for artist in top_artists:
                        for g in artist.get("genres", []):
                            genre_counter[g.lower()] += 1
                    genre_list = [g for g, _ in genre_counter.most_common(MAX_SEEDS)] or DEFAULT_GENRES

                    seed_artists = [artist["id"] for artist in top_artists[:MAX_SEEDS] if artist.get("id")]
                else:
                    genre_list = DEFAULT_GENRES

                if top_tracks:
                    seed_tracks = [track["id"] for track in top_tracks[:MAX_SEEDS] if track.get("id")]
        except Exception as e:
            logger.error(f"Failed to fetch top genres/artists/tracks: {e}")
            genre_list = DEFAULT_GENRES

    # ----------------------------
    # Redis caching
    # ----------------------------
    cache_key = f"recommendations:{user_id}:{','.join(genre_list)}:{','.join(seed_artists)}:{','.join(seed_tracks)}:{min_popularity}:{released_after}"
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        await redis.close()
        if cached:
            return {"recommendedTracks": json.loads(cached)}
    except Exception:
        pass

    # ----------------------------
    # Fetch Spotify recommendations
    # ----------------------------
    try:
        rec_tracks = await get_spotify_recommendations(
            spotify_token=spotify_token,
            genres=genre_list,
            seed_artists=seed_artists,
            seed_tracks=seed_tracks,
            min_popularity=min_popularity,
            released_after=released_after
        )
    except Exception as e:
        logger.error(f"Spotify API error for user {user_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Spotify API error: {e}")

    # Store in cache
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(cache_key, json.dumps(rec_tracks), ex=CACHE_TTL)
        await redis.close()
    except Exception:
        pass

    return {"recommendedTracks": rec_tracks}