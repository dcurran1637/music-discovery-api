from fastapi import APIRouter, HTTPException, Header, Query, status
from typing import Optional
import os
import json
import redis.asyncio as aioredis

from ..spotify_client import (
    get_spotify_recommendations,
    refresh_spotify_token,
    FALLBACK_ARTISTS,
    FALLBACK_TRACKS,
    DEFAULT_GENRES,
    MAX_SEEDS,
    DEFAULT_MARKET
)
from .. import db, auth
from ..crypto import decrypt
from ..logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/discover/recommendations", tags=["recommendations"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 300


async def authenticate_user(authorization: str):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authorization header must start with 'Bearer '")
    token_str = authorization.split(" ")[1]
    
    # Try to decode as JWT first (for backward compatibility with tests and legacy clients)
    spotify_token = None
    user_id = None
    
    try:
        user_payload = auth.decode_jwt_token(token_str)
        user_id = user_payload.get("user_id")
        spotify_token = user_payload.get("spotify_access_token")
        
        if spotify_token:
            logger.info(f"Extracted Spotify token from JWT for user {user_id}")
            return user_id, spotify_token, "JWT_TOKEN"
    except:
        # Not a JWT or invalid JWT - treat as raw Spotify token
        pass
    
    # If not a JWT or JWT doesn't contain Spotify token, treat token_str as Spotify access token
    if not spotify_token:
        spotify_token = token_str
        try:
            # Import at function level to avoid circular dependency
            from ..oauth import get_user_profile
            profile = await get_user_profile(spotify_token)
            user_id = profile.get("id")  # Spotify user ID
            
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid Spotify token: no user ID in profile")
            
            logger.info(f"Authenticated Spotify user directly: {user_id}")
            return user_id, spotify_token, "JWT_TOKEN"
            
        except HTTPException as e:
            logger.error(f"Spotify token validation failed: {e.detail}")
            raise HTTPException(status_code=401, detail="Invalid or expired access token")
        except Exception as e:
            logger.error(f"Unexpected authentication error: {str(e)}")
            raise HTTPException(status_code=401, detail="Authentication failed")


async def fetch_recommendations(
    spotify_token: str,
    market: str,
    limit: int,
    min_popularity: Optional[int],
    seed_artists: Optional[list[str]] = None,
    seed_tracks: Optional[list[str]] = None,
    seed_genres: Optional[list[str]] = None,
    time_range: str = "medium_term"
):
    tracks, meta = await get_spotify_recommendations(
        spotify_token,
        seed_artists=seed_artists,
        seed_tracks=seed_tracks,
        genres=seed_genres,
        market_override=market,
        limit=limit,
        min_popularity=min_popularity,
        return_meta=True,
        time_range=time_range
    )
    return tracks, meta


async def redis_cache_get(key: str):
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        cached = await redis.get(key)
        await redis.close()
        return json.loads(cached) if cached else None
    except Exception as e:
        logger.warning(f"Redis cache error: {e}")
        return None


async def redis_cache_set(key: str, value: dict):
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(key, json.dumps(value), ex=CACHE_TTL)
        await redis.close()
    except Exception as e:
        logger.warning(f"Redis save error: {e}")


def build_cache_key(user_id: str, seed_type: str, seeds: list[str], market: str, min_popularity: Optional[int]):
    return f"recommendations:{user_id}:{seed_type}:{','.join(seeds)}:{market}:{min_popularity}"


@router.get("")
async def recommendations_base(
    authorization: str = Header(...),
    market: Optional[str] = Query(DEFAULT_MARKET),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    released_after: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=1, le=100),
    time_range: Optional[str] = Query("medium_term", pattern="^(short_term|medium_term|long_term)$"),
    debug: Optional[bool] = Query(False)
):
    """Base recommendations endpoint that uses user's top genres from listening history.
    Falls back to default genres if user has no listening history.
    """
    user_id, spotify_token, token_source = await authenticate_user(authorization)

    # Get user's top genres from their top artists
    seeds = []
    try:
        from ..spotify_client import get_user_top_artists
        top_artists = await get_user_top_artists(spotify_token, limit=10, time_range=time_range)
        user_genres = []
        for artist in top_artists:
            user_genres.extend(artist.get("genres", []))
        # Get most common genres
        if user_genres:
            from collections import Counter
            genre_counts = Counter(user_genres)
            seeds = [genre for genre, _ in genre_counts.most_common(MAX_SEEDS)]
    except Exception as e:
        logger.warning(f"Failed to fetch user top genres: {e}")
    
    # Fallback to default genres if no user genres found
    if not seeds:
        seeds = DEFAULT_GENRES[:MAX_SEEDS]

    # Optional: validate released_after format (YYYY-MM-DD). If invalid, leave handling flexible.
    if released_after:
        try:
            # Basic format check; downstream may ignore
            from datetime import datetime
            datetime.strptime(released_after, "%Y-%m-%d")
        except Exception:
            # Return 422 by raising validation error or 400 by explicit exception; tests accept both
            raise HTTPException(status_code=422, detail="Invalid date format, expected YYYY-MM-DD")

    cache_key = build_cache_key(user_id, "genre", seeds, market, min_popularity)
    cached = await redis_cache_get(cache_key)
    if cached:
        return cached

    tracks, meta = await fetch_recommendations(
        spotify_token=spotify_token,
        market=market,
        limit=limit,
        min_popularity=min_popularity,
        seed_genres=seeds,
        time_range=time_range
    )

    response = {"results": tracks, "meta": meta}
    if debug:
        response["debug"] = {
            "userId": user_id,
            "tokenSource": token_source,
            "seeds": seeds,
            "market": market,
            "minPopularity": min_popularity,
        }
    await redis_cache_set(cache_key, response)
    return response


@router.get("/artists")
async def recommendations_artists(
    authorization: str = Header(...),
    seedArtists: Optional[str] = Query(None),
    market: Optional[str] = Query(DEFAULT_MARKET),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    limit: Optional[int] = Query(10, ge=1, le=100),
    time_range: Optional[str] = Query("medium_term", pattern="^(short_term|medium_term|long_term)$"),
    debug: Optional[bool] = Query(False)
):
    user_id, spotify_token, token_source = await authenticate_user(authorization)
    
    # Use provided seeds or get user's top artists
    if seedArtists:
        artist_seeds = [s.strip() for s in seedArtists.split(",") if s.strip()]
    else:
        from ..spotify_client import get_user_top_artists
        top_artists = await get_user_top_artists(spotify_token, limit=MAX_SEEDS, time_range=time_range)
        artist_seeds = [artist["id"] for artist in top_artists]
    
    # Complement artist seeds with genres if we have room
    genre_seeds = []
    total_seeds = len(artist_seeds)
    if total_seeds < MAX_SEEDS:
        from ..spotify_client import get_user_top_artists
        top_artists = await get_user_top_artists(spotify_token, limit=10, time_range=time_range)
        user_genres = []
        for artist in top_artists:
            user_genres.extend(artist.get("genres", []))
        unique_genres = list(set(user_genres))[:MAX_SEEDS - total_seeds]
        genre_seeds = unique_genres if unique_genres else DEFAULT_GENRES[:MAX_SEEDS - total_seeds]
    
    combined_for_cache = artist_seeds + genre_seeds
    cache_key = build_cache_key(user_id, "artist", combined_for_cache, market, min_popularity)
    cached = await redis_cache_get(cache_key)
    if cached:
        return cached

    tracks, meta = await fetch_recommendations(
        spotify_token=spotify_token,
        market=market,
        limit=limit,
        min_popularity=min_popularity,
        seed_artists=artist_seeds,
        seed_genres=genre_seeds if genre_seeds else None,
        time_range=time_range
    )

    response = {"results": tracks, "meta": meta}
    if debug:
        response["debug"] = {
            "userId": user_id,
            "tokenSource": token_source,
            "artistSeeds": artist_seeds,
            "genreSeeds": genre_seeds,
            "market": market,
            "minPopularity": min_popularity
        }
    await redis_cache_set(cache_key, response)
    return response


@router.get("/tracks")
async def recommendations_tracks(
    authorization: str = Header(...),
    seedTracks: Optional[str] = Query(None),
    market: Optional[str] = Query(DEFAULT_MARKET),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    limit: Optional[int] = Query(10, ge=1, le=100),
    time_range: Optional[str] = Query("medium_term", pattern="^(short_term|medium_term|long_term)$"),
    debug: Optional[bool] = Query(False)
):
    user_id, spotify_token, token_source = await authenticate_user(authorization)
    
    # Use provided seeds or get user's top tracks
    if seedTracks:
        track_seeds = [s.strip() for s in seedTracks.split(",") if s.strip()]
    else:
        from ..spotify_client import get_user_top_tracks
        top_tracks = await get_user_top_tracks(spotify_token, limit=MAX_SEEDS, time_range=time_range)
        track_seeds = [track["id"] for track in top_tracks]
    
    # Complement track seeds with genres if we have room
    genre_seeds = []
    total_seeds = len(track_seeds)
    if total_seeds < MAX_SEEDS:
        from ..spotify_client import get_user_top_artists
        top_artists = await get_user_top_artists(spotify_token, limit=10, time_range=time_range)
        user_genres = []
        for artist in top_artists:
            user_genres.extend(artist.get("genres", []))
        unique_genres = list(set(user_genres))[:MAX_SEEDS - total_seeds]
        genre_seeds = unique_genres if unique_genres else DEFAULT_GENRES[:MAX_SEEDS - total_seeds]
    
    combined_for_cache = track_seeds + genre_seeds
    cache_key = build_cache_key(user_id, "track", combined_for_cache, market, min_popularity)
    cached = await redis_cache_get(cache_key)
    if cached:
        return cached

    tracks, meta = await fetch_recommendations(
        spotify_token=spotify_token,
        market=market,
        limit=limit,
        min_popularity=min_popularity,
        seed_tracks=track_seeds,
        seed_genres=genre_seeds if genre_seeds else None,
        time_range=time_range
    )

    response = {"results": tracks, "meta": meta}
    if debug:
        response["debug"] = {
            "userId": user_id,
            "tokenSource": token_source,
            "trackSeeds": track_seeds,
            "genreSeeds": genre_seeds,
            "market": market,
            "minPopularity": min_popularity
        }
    await redis_cache_set(cache_key, response)
    return response


@router.get("/genres")
async def recommendations_genres(
    authorization: str = Header(...),
    genres: Optional[str] = Query(None),
    market: Optional[str] = Query(DEFAULT_MARKET),
    min_popularity: Optional[int] = Query(None, ge=0, le=100),
    limit: Optional[int] = Query(10, ge=1, le=100),
    time_range: Optional[str] = Query("medium_term", pattern="^(short_term|medium_term|long_term)$"),
    debug: Optional[bool] = Query(False)
):
    user_id, spotify_token, token_source = await authenticate_user(authorization)
    
    # If genres specified, use those; otherwise will extract from user's top artists in get_spotify_recommendations
    genre_seeds = [g.strip().lower() for g in genres.split(",") if g.strip()] if genres else None

    cache_key = build_cache_key(user_id, "genre", genre_seeds or ["user_top"], market, min_popularity)
    cached = await redis_cache_get(cache_key)
    if cached:
        return cached

    tracks, meta = await fetch_recommendations(
        spotify_token=spotify_token,
        market=market,
        limit=limit,
        min_popularity=min_popularity,
        seed_genres=genre_seeds,
        time_range=time_range
    )

    response = {"results": tracks, "meta": meta}
    if debug:
        response["debug"] = {
            "userId": user_id,
            "tokenSource": token_source,
            "genreSeeds": genre_seeds or "user_top_artists_genres",
            "market": market,
            "minPopularity": min_popularity
        }
    await redis_cache_set(cache_key, response)
    return response
