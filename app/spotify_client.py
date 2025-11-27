import os, base64, time
import httpx
from datetime import datetime
from typing import Optional, List

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TOKEN = None
TOKEN_EXPIRES = 0

async def get_spotify_token():
    global TOKEN, TOKEN_EXPIRES
    if TOKEN and TOKEN_EXPIRES - 30 > time.time():
        return TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        return None
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"}
        )
        r.raise_for_status()
        data = r.json()
        TOKEN = data["access_token"]
        TOKEN_EXPIRES = time.time() + data["expires_in"]
        return TOKEN

async def get_track(track_id: str):
    token = await get_spotify_token()
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if r.status_code == 200:
            return r.json()
        return None


async def get_artist(artist_id: str, spotify_token: Optional[str] = None):
    """
    Retrieve artist metadata from Spotify.
    If `spotify_token` is not provided, falls back to client credentials token.
    """
    token = spotify_token or await get_spotify_token()
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://api.spotify.com/v1/artists/{artist_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if r.status_code == 200:
            return r.json()
        return None

async def get_spotify_recommendations(
    spotify_token: str,
    limit: int = 20,
    genres: Optional[List[str]] = None,
    min_popularity: Optional[int] = None,
    released_after: Optional[str] = None
):
    """
    Fetch Spotify recommendations with optional filtering using user's OAuth token.
    :param spotify_token: User's Spotify access token from OAuth
    :param limit: Number of recommendations (default 20)
    :param genres: List of genres to filter
    :param min_popularity: Minimum track popularity
    :param released_after: Release date filter "YYYY-MM-DD"
    """
    if not spotify_token:
        return []

    # Demo seed artist; replace with user-specific seeds
    seed_artists = "4NHQUGzhtTLFvgF5SZesLK"
    url = f"https://api.spotify.com/v1/recommendations?limit={limit}&seed_artists={seed_artists}"

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers={"Authorization": f"Bearer {spotify_token}"})
        r.raise_for_status()
        data = r.json()

    filtered_tracks = []

    for item in data["tracks"]:
        # Fetch artist genres
        artist_id = item["artists"][0]["id"]
        async with httpx.AsyncClient() as client:
            art_resp = await client.get(
                f"https://api.spotify.com/v1/artists/{artist_id}",
                headers={"Authorization": f"Bearer {spotify_token}"}
            )
            art_resp.raise_for_status()
            artist_data = art_resp.json()

        track_info = {
            "trackId": item["id"],
            "title": item["name"],
            "artist": item["artists"][0]["name"],
            "genres": artist_data.get("genres", []),
            "album": {
                "name": item["album"]["name"],
                "release_date": item["album"]["release_date"]
            },
            "popularity": item.get("popularity"),
            "previewUrl": item.get("preview_url")
        }

        # Apply genre filter
        if genres:
            track_genres = [g.lower() for g in track_info["genres"]]
            if not any(g.lower() in track_genres for g in genres):
                continue

        # Apply popularity filter
        if min_popularity is not None and track_info.get("popularity", 0) < min_popularity:
            continue

        # Apply release date filter
        if released_after:
            try:
                track_date = track_info["album"]["release_date"]
                track_dt = datetime.strptime(track_date, "%Y-%m-%d")
                released_dt = datetime.strptime(released_after, "%Y-%m-%d")
                if track_dt < released_dt:
                    continue
            except ValueError:
                # Skip if release_date format is unexpected
                pass

        filtered_tracks.append(track_info)

    return filtered_tracks

async def spotify_search_artists(query: str):
    """
    Search artists using Spotify API.
    Returns a list of raw artist objects.
    """
    token = await get_access_token()
    url = "https://api.spotify.com/v1/search"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={"q": query, "type": "artist", "limit": 20},
            headers={"Authorization": f"Bearer {token}"}
        )

    data = response.json()
    return data.get("artists", {}).get("items", [])
