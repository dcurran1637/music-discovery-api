import os
import base64
import time
import httpx
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import defaultdict, Counter

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
logger = logging.getLogger(__name__)

CLIENT_TOKEN: Optional[str] = None
TOKEN_EXPIRES: float = 0
MAX_SEEDS = 5
DEFAULT_GENRES = ["pop", "rock", "dance", "edm", "indie"]
FALLBACK_ARTISTS = ["6XyY86QOPPrYVGvF9ch6wz", "4IliztYDlfMvzQzbx50o60"] 
FALLBACK_TRACKS = ["4Yf5bqU3NK4kNOypcrLYwU", "3E619cvUK3bgsm4xH9A34H"]  
DEFAULT_MARKET = os.getenv("SPOTIFY_MARKET") or "GB"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


async def get_available_genre_seeds(spotify_token: str) -> List[str]:
    """Fetch Spotify-supported genre seeds for recommendations."""
    if not spotify_token:
        return []
    url = f"{SPOTIFY_API_BASE}/recommendations/available-genre-seeds"
    headers = {"Authorization": f"Bearer {spotify_token}"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, timeout=10)
        if r.status_code == 401:
            raise Exception("Spotify user token expired")
        if r.status_code != 200:
            return []
        return r.json().get("genres", [])


async def get_spotify_token() -> Optional[str]:
    """Get a Spotify token via client credentials (non-user-specific requests)."""
    global CLIENT_TOKEN, TOKEN_EXPIRES
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    if CLIENT_TOKEN and TOKEN_EXPIRES - 30 > time.time():
        return CLIENT_TOKEN

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth_header}"},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        CLIENT_TOKEN = data["access_token"]
        TOKEN_EXPIRES = time.time() + data["expires_in"]
        return CLIENT_TOKEN


async def get_user_top_artists(
    access_token: str, limit: int = 20, time_range: str = "medium_term"
) -> List[Dict[str, Any]]:
    url = f"{SPOTIFY_API_BASE}/me/top/artists"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"limit": limit, "time_range": time_range}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 401:
            raise Exception("Spotify user token expired")
        if r.status_code != 200:
            return []
        return r.json().get("items", [])


async def get_user_top_tracks(
    access_token: str, limit: int = 20, time_range: str = "medium_term"
) -> List[Dict[str, Any]]:
    url = f"{SPOTIFY_API_BASE}/me/top/tracks"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"limit": limit, "time_range": time_range}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 401:
            raise Exception("Spotify user token expired")
        if r.status_code != 200:
            return []
        return r.json().get("items", [])


async def get_artist(artist_id: str, spotify_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    token = spotify_token or await get_spotify_token()
    if not token:
        return None
    url = f"{SPOTIFY_API_BASE}/artists/{artist_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()


async def get_track(track_id: str, spotify_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    token = spotify_token or await get_spotify_token()
    if not token:
        return None
    url = f"{SPOTIFY_API_BASE}/tracks/{track_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()


async def spotify_search_artists(query: str, spotify_token: str) -> List[Dict[str, Any]]:
    if not spotify_token:
        return []
    url = f"{SPOTIFY_API_BASE}/search"
    params = {"q": query, "type": "artist", "limit": 20}
    headers = {"Authorization": f"Bearer {spotify_token}"}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, headers=headers, params=params, timeout=10)
            r.raise_for_status()
            return r.json().get("artists", {}).get("items", [])
        except Exception:
            return []


async def get_user_playlists(spotify_token: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Fetch the current user's Spotify playlists."""
    if not spotify_token:
        return {"items": [], "total": 0}
    
    url = f"{SPOTIFY_API_BASE}/me/playlists"
    params = {"limit": limit, "offset": offset}
    headers = {"Authorization": f"Bearer {spotify_token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, headers=headers, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Error fetching user playlists: {e}")
            return {"items": [], "total": 0}


async def create_spotify_playlist(
    spotify_token: str, 
    user_id: str,
    name: str, 
    description: Optional[str] = None,
    public: bool = True,
    collaborative: bool = False
) -> Optional[Dict[str, Any]]:
    """Create a new Spotify playlist for the user."""
    if not spotify_token or not user_id:
        return None
    
    url = f"{SPOTIFY_API_BASE}/users/{user_id}/playlists"
    headers = {
        "Authorization": f"Bearer {spotify_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name,
        "public": public,
        "collaborative": collaborative
    }
    if description:
        payload["description"] = description
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, headers=headers, json=payload, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Error creating Spotify playlist: {e}")
            return None


async def update_spotify_playlist(
    spotify_token: str,
    playlist_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    public: Optional[bool] = None,
    collaborative: Optional[bool] = None
) -> bool:
    """Update a Spotify playlist's details."""
    if not spotify_token or not playlist_id:
        return False
    
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}"
    headers = {
        "Authorization": f"Bearer {spotify_token}",
        "Content-Type": "application/json"
    }
    payload = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if public is not None:
        payload["public"] = public
    if collaborative is not None:
        payload["collaborative"] = collaborative
    
    if not payload:
        return True  # Nothing to update
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.put(url, headers=headers, json=payload, timeout=10)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error updating Spotify playlist: {e}")
            return False


async def delete_spotify_playlist(spotify_token: str, playlist_id: str) -> bool:
    """Unfollow (delete) a Spotify playlist. Note: Can only unfollow playlists owned by the user."""
    if not spotify_token or not playlist_id:
        return False
    
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/followers"
    headers = {"Authorization": f"Bearer {spotify_token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.delete(url, headers=headers, timeout=10)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error deleting Spotify playlist: {e}")
            return False


async def get_spotify_playlist(spotify_token: str, playlist_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single Spotify playlist by ID."""
    if not spotify_token or not playlist_id:
        return None
    
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}"
    headers = {"Authorization": f"Bearer {spotify_token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Error fetching Spotify playlist: {e}")
            return None


async def get_spotify_recommendations(
    spotify_token: str,
    limit: int = 10,
    genres: Optional[list[str]] = None,
    seed_artists: Optional[list[str]] = None,
    seed_tracks: Optional[list[str]] = None,
    min_popularity: Optional[int] = None,
    market_override: Optional[str] = None,
    return_meta: bool = False,
    refresh_token: Optional[str] = None,
    time_range: str = "medium_term"
) -> list[dict] | tuple[list[dict], dict]:
    """
    Custom recommendation system since Spotify's /recommendations endpoint returns 404.
    Uses user's top tracks/artists and searches to generate recommendations.
    """
    if not spotify_token:
        return ([], {}) if return_meta else []

    try:
        # Strategy: Use user's top artists and tracks to generate recommendations
        tracks = []
        fallback_used = "custom_algorithm"
        seeds_used = {}
        
        # If specific genres requested, search for those
        if genres is not None and len(genres) > 0:
            seeds_used["seed_genres"] = ",".join(genres)
            tracks = await _search_tracks_by_genres(spotify_token, genres, limit, min_popularity)
        
        # If specific artists requested, get their top tracks
        elif seed_artists:
            seeds_used["seed_artists"] = ",".join(seed_artists)
            tracks = await _get_tracks_from_artists(spotify_token, seed_artists, limit, min_popularity)
        
        # If specific tracks requested, find related tracks (via artist of those tracks)
        elif seed_tracks:
            seeds_used["seed_tracks"] = ",".join(seed_tracks)
            tracks = await _get_related_tracks(spotify_token, seed_tracks, limit, min_popularity)
        
        # Default: Use user's top artists to extract genres
        else:
            # Get user's top artists to extract genres
            top_artists = await get_user_top_artists(spotify_token, limit=10, time_range=time_range)
            user_genres = []
            for artist in top_artists:
                user_genres.extend(artist.get("genres", []))
            
            # Use unique genres from user's top artists
            unique_genres = list(set(user_genres))[:MAX_SEEDS]
            if unique_genres:
                seeds_used["seed_genres"] = ",".join(unique_genres)
                tracks = await _search_tracks_by_genres(spotify_token, unique_genres, limit, min_popularity)
            else:
                # Fallback to top tracks if no genres found
                top_tracks = await get_user_top_tracks(spotify_token, limit=limit, time_range=time_range)
                tracks = top_tracks
                seeds_used["source"] = "user_top_tracks"
        
        # Shuffle for variety
        import random
        random.shuffle(tracks)
        tracks = tracks[:limit]

    except Exception as e:
        logger.warning(f"Custom recommendations failed: {e}")
        tracks = []
        fallback_used = "fallback_used"
        seeds_used = {}
        if seed_artists:
            seeds_used["seed_artists"] = ",".join(seed_artists)
        if seed_tracks:
            seeds_used["seed_tracks"] = ",".join(seed_tracks)
        if genres:
            seeds_used["seed_genres"] = ",".join(genres)

    # Filter by popularity
    filtered = []
    for track in tracks:
        if min_popularity is not None and track.get("popularity", 0) < min_popularity:
            continue
        filtered.append({
            "trackId": track["id"],
            "title": track["name"],
            "artist": track["artists"][0]["name"] if track["artists"] else "",
            "album": {"name": track["album"]["name"], "release_date": track["album"]["release_date"]},
            "popularity": track.get("popularity"),
            "previewUrl": track.get("preview_url"),
        })

    if return_meta:
        meta = {"market": market_override, "fallback": fallback_used, "seedsUsed": seeds_used}
        return filtered, meta

    return filtered

async def refresh_spotify_token(refresh_token: str) -> str:
    """
    Use the Spotify refresh token to get a new access token.
    Returns the new access token.
    """
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError("Missing Spotify client credentials in environment")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(SPOTIFY_TOKEN_URL, data=data, timeout=10)
        r.raise_for_status()
        return r.json()["access_token"]


async def _search_tracks_by_genres(
    spotify_token: str,
    genres: list[str],
    limit: int,
    min_popularity: Optional[int] = None
) -> list[dict]:
    """Search for tracks matching the given genres."""
    tracks = []
    headers = {"Authorization": f"Bearer {spotify_token}"}
    
    async with httpx.AsyncClient() as client:
        for genre in genres[:3]:  # Limit to 3 genres to avoid too many requests
            try:
                # Search for tracks with genre in query
                params = {
                    "q": f"genre:{genre}",
                    "type": "track",
                    "limit": limit,
                    "market": "from_token"
                }
                r = await client.get(f"{SPOTIFY_API_BASE}/search", headers=headers, params=params, timeout=10)
                if r.status_code == 200:
                    items = r.json().get("tracks", {}).get("items", [])
                    tracks.extend(items)
            except Exception as e:
                logger.warning(f"Genre search failed for {genre}: {e}")
                continue
    
    return tracks[:limit * 2]  # Return more than needed for filtering


async def _get_tracks_from_artists(
    spotify_token: str,
    artist_ids: list[str],
    limit: int,
    min_popularity: Optional[int] = None
) -> list[dict]:
    """Get top tracks from the specified artists."""
    tracks = []
    headers = {"Authorization": f"Bearer {spotify_token}"}
    
    async with httpx.AsyncClient() as client:
        for artist_id in artist_ids[:5]:  # Limit to 5 artists
            try:
                # Get artist's top tracks
                r = await client.get(
                    f"{SPOTIFY_API_BASE}/artists/{artist_id}/top-tracks",
                    headers=headers,
                    params={"market": "from_token"},
                    timeout=10
                )
                if r.status_code == 200:
                    items = r.json().get("tracks", [])
                    tracks.extend(items)
            except Exception as e:
                logger.warning(f"Failed to get tracks for artist {artist_id}: {e}")
                continue
    
    return tracks


async def _get_related_tracks(
    spotify_token: str,
    track_ids: list[str],
    limit: int,
    min_popularity: Optional[int] = None
) -> list[dict]:
    """Get related tracks by finding the artists of the seed tracks and getting their top tracks."""
    tracks = []
    headers = {"Authorization": f"Bearer {spotify_token}"}
    artist_ids = set()
    
    async with httpx.AsyncClient() as client:
        # Get the artists from seed tracks
        for track_id in track_ids[:5]:
            try:
                r = await client.get(f"{SPOTIFY_API_BASE}/tracks/{track_id}", headers=headers, timeout=10)
                if r.status_code == 200:
                    track_data = r.json()
                    for artist in track_data.get("artists", [])[:2]:
                        artist_ids.add(artist["id"])
            except Exception as e:
                logger.warning(f"Failed to get track {track_id}: {e}")
                continue
        
        # Get tracks from those artists
        if artist_ids:
            tracks = await _get_tracks_from_artists(spotify_token, list(artist_ids), limit, min_popularity)
    
    return tracks