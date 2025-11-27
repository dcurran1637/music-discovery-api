from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from ..spotify_client import get_spotify_recommendations, get_user_top_artists
from ..auth import verify_jwt_token
import redis.asyncio as aioredis
import os
import json
from datetime import datetime, timedelta
from .. import db
from ..crypto import decrypt, encrypt
from ..oauth import refresh_spotify_token
from ..logging_config import get_logger
from collections import Counter

logger = get_logger(__name__)

router = APIRouter(prefix="/api/discover", tags=["recommendations"])

# Redis setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CACHE_TTL = 300  # seconds


@router.get("/recommendations")
async def recommendations(
    genres: Optional[str] = Query(None, description="Comma-separated genres to filter"),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    released_after: Optional[str] = Query(None, description="YYYY-MM-DD"),
    user_payload = Depends(verify_jwt_token),
):
    """
    Returns Spotify-based track recommendations filtered by genre, popularity, and release date.
    Automatically determines user's top genres if genres are not provided.
    Uses the Spotify access token from the JWT payload.
    """

    user_id = user_payload.get("user_id")

    # Prefer session-based tokens
    spotify_token = None
    session_id = user_payload.get("session_id")
    if session_id:
        session = db.get_session_tokens(session_id)
        if session:
            try:
                spotify_token = decrypt(session.get("access_token", ""))
            except Exception:
                spotify_token = None

            # Refresh if missing/expired
            if not spotify_token:
                try:
                    refresh_enc = session.get("refresh_token")
                    refresh_token = decrypt(refresh_enc) if refresh_enc else None
                    if refresh_token:
                        token_data = await refresh_spotify_token(refresh_token)
                        enc_access = encrypt(token_data.get("access_token"))
                        enc_refresh = encrypt(token_data.get("refresh_token") or refresh_token)
                        new_expires_at = (
                            datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
                        ).isoformat()
                        db.put_session_tokens(session_id, user_id, enc_access, enc_refresh, new_expires_at)
                        spotify_token = token_data.get("access_token")
                except Exception:
                    spotify_token = spotify_token

    # Fallback: legacy tokens from user table
    if not spotify_token:
        user_tokens = db.get_user_tokens(user_id)
        if user_tokens:
            try:
                spotify_token = decrypt(user_tokens.get("access_token", ""))
            except Exception:
                spotify_token = None

            if not spotify_token:
                try:
                    refresh_enc = user_tokens.get("refresh_token")
                    refresh_token = decrypt(refresh_enc) if refresh_enc else None
                    if refresh_token:
                        token_data = await refresh_spotify_token(refresh_token)
                        enc_access = encrypt(token_data.get("access_token"))
                        enc_refresh = encrypt(token_data.get("refresh_token") or refresh_token)
                        new_expires_at = (
                            datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
                        ).isoformat()
                        db.put_user_tokens(user_id, enc_access, enc_refresh, new_expires_at)
                        spotify_token = token_data.get("access_token")
                except Exception:
                    spotify_token = spotify_token

    # Final fallback: token directly in JWT
    if not spotify_token:
        spotify_token = user_payload.get("spotify_access_token")


    if not genres:
        try:
            top_artists = await get_user_top_artists(spotify_token)

            if top_artists:
                genre_counter = Counter()

                for artist in top_artists:
                    for g in artist.get("genres", []):
                        genre_counter[g.lower()] += 1

                inferred_genres = [g for g, _ in genre_counter.most_common(5)]

                if inferred_genres:
                    genres = ",".join(inferred_genres)

        except Exception as e:
            logger.error(f"Failed to infer genres from top artists: {e}")
            genres = None

    # Convert genres string → list
    genre_list = [g.strip().lower() for g in genres.split(",")] if genres else None

    cache_key = f"recommendations:{user_id}:{genres}:{min_popularity}:{released_after}"

    # Try Redis cache
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        if cached:
            await redis.close()
            return json.loads(cached)
    except Exception:
        pass


    try:
        rec_tracks = await get_spotify_recommendations(
            spotify_token=spotify_token,
            genres=genre_list,
            min_popularity=min_popularity,
            released_after=released_after
        )
    except Exception as e:
        logger.error(f"Spotify API error for user {user_id}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Spotify API error: {str(e)}")

    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(cache_key, json.dumps(rec_tracks), ex=CACHE_TTL)
        await redis.close()
    except Exception:
        pass

    return {"recommendedTracks": rec_tracks}
