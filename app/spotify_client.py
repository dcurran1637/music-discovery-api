import os
import base64
import time
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import defaultdict, Counter

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# client credentials fallback token
CLIENT_TOKEN: Optional[str] = None
TOKEN_EXPIRES: float = 0
MAX_SEEDS = 5
DEFAULT_GENRES = ["pop", "rock", "hip-hop"]


async def get_spotify_token() -> Optional[str]:
    """
    Get a Spotify token via client credentials (for non-user-specific requests)
    """
    global CLIENT_TOKEN, TOKEN_EXPIRES
    if CLIENT_TOKEN and TOKEN_EXPIRES - 30 > time.time():
        return CLIENT_TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        return None

    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
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
    access_token: str,
    limit: int = 20,
    time_range: str = "medium_term"
) -> List[Dict[str, Any]]:
    url = f"{SPOTIFY_API_BASE}/me/top/artists"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"limit": limit, "time_range": time_range}

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            return []
        return r.json().get("items", [])


async def get_user_top_tracks(
    access_token: str,
    limit: int = 20,
    time_range: str = "medium_term"
) -> List[Dict[str, Any]]:
    url = f"{SPOTIFY_API_BASE}/me/top/tracks"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"limit": limit, "time_range": time_range}

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params, timeout=10)
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


async def spotify_search_artists(query: str, spotify_token: str):
    """
    Search for artists on Spotify using a given query.
    
    Args:
        query: Search query string (e.g., "genre:rock").
        spotify_token: Valid Spotify access token (user or client credentials)
        
    Returns:
        List of artist objects from Spotify API.
    """
    if not spotify_token:
        return []

    url = f"{SPOTIFY_API_BASE}/search"
    params = {
        "q": query,
        "type": "artist",
        "limit": 20
    }
    headers = {
        "Authorization": f"Bearer {spotify_token}"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("artists", {}).get("items", [])
        except Exception:
            return []




async def get_spotify_recommendations(
    spotify_token: str,
    limit: int = 20,
    genres: Optional[List[str]] = None,
    seed_artists: Optional[List[str]] = None,
    seed_tracks: Optional[List[str]] = None,
    min_popularity: Optional[int] = None,
    released_after: Optional[str] = None
) -> List[Dict[str, Any]]:
    if not spotify_token:
        return []

    if not genres:
        top_artists = await get_user_top_artists(spotify_token, limit=MAX_SEEDS)
        genre_counter = Counter()
        for artist in top_artists:
            for g in artist.get("genres", []):
                genre_counter[g.lower()] += 1
        genres = [g for g, _ in genre_counter.most_common(MAX_SEEDS)]
        if not genres:
            genres = DEFAULT_GENRES

    seeds = defaultdict(list)
    seeds["seed_genres"] = genres[:MAX_SEEDS]
    if seed_artists:
        seeds["seed_artists"] = seed_artists[:MAX_SEEDS]
    if seed_tracks:
        seeds["seed_tracks"] = seed_tracks[:MAX_SEEDS]

    query_params = {"limit": str(limit)}
    query_params.update({k: ",".join(v) for k, v in seeds.items() if v})

    url = f"{SPOTIFY_API_BASE}/recommendations"
    headers = {"Authorization": f"Bearer {spotify_token}"}

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=query_params, timeout=10)
        if r.status_code != 200:
            return []

        tracks = r.json().get("tracks", [])

    filtered = []
    for track in tracks:
        if min_popularity is not None and track.get("popularity", 0) < min_popularity:
            continue
        if released_after:
            try:
                track_date = track["album"]["release_date"]
                if len(track_date) == 4:
                    track_date += "-01-01"
                elif len(track_date) == 7:
                    track_date += "-01"
                track_dt = datetime.strptime(track_date, "%Y-%m-%d")
                if track_dt < datetime.strptime(released_after, "%Y-%m-%d"):
                    continue
            except Exception:
                pass

        filtered.append({
            "trackId": track["id"],
            "title": track["name"],
            "artist": track["artists"][0]["name"] if track["artists"] else "",
            "album": {"name": track["album"]["name"], "release_date": track["album"]["release_date"]},
            "popularity": track.get("popularity"),
            "previewUrl": track.get("preview_url"),
        })

    return filtered
