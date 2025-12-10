from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import httpx
from app.spotify_client import get_spotify_token


class UserPreferences(BaseModel):
    favouriteGenres: List[str] = []
    discoverWeeklyEnabled: bool = True

class User(BaseModel):
    id: str
    username: str
    email: EmailStr
    createdAt: datetime
    preferences: UserPreferences

class Track(BaseModel):
    id: str  # e.g., "spotify:track:789xyz"
    title: str
    artist: str
    album: str
    durationMs: int
    previewUrl: Optional[str] = None
    genres: List[str]

class PlaylistTrack(BaseModel):
    trackId: str
    title: str
    artist: str
    genre: Optional[str] = None

class Playlist(BaseModel):
    id: str  # e.g., "playlist_001"
    name: str
    ownerId: str
    createdAt: datetime
    tracks: List[PlaylistTrack]


class PlaylistCreate(BaseModel):
    """Schema used when creating or updating playlists via the API.

    Fields:
    - name: display name for the playlist (required)
    - description: optional text describing the playlist
    """
    name: str
    description: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {"name": "Chill Vibes", "description": "Laid-back tracks for working"}
        }


class SpotifyPlaylistCreate(BaseModel):
    """Schema for creating a Spotify playlist.
    
    Fields:
    - name: display name for the playlist (required)
    - description: optional text describing the playlist
    - public: whether the playlist is public (default: True)
    - collaborative: whether others can add tracks (default: False)
    """
    name: str
    description: Optional[str] = None
    public: bool = True
    collaborative: bool = False

    class Config:
        schema_extra = {
            "example": {
                "name": "My Awesome Playlist",
                "description": "A collection of my favorite tracks",
                "public": True,
                "collaborative": False
            }
        }


class SpotifyPlaylistUpdate(BaseModel):
    """Schema for updating a Spotify playlist.
    
    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    public: Optional[bool] = None
    collaborative: Optional[bool] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Playlist Name",
                "description": "New description"
            }
        }


class RecommendedTrack(BaseModel):
    trackId: str
    title: str
    artist: str
    genre: Optional[str] = None
    reason: Optional[str] = None

async def get_spotify_recommendations(limit=20):
    token = await get_spotify_token()
    if not token:
        return []

    seed_artists = "4NHQUGzhtTLFvgF5SZesLK"  # demo; replace with user top artists
    url = f"https://api.spotify.com/v1/recommendations?limit={limit}&seed_artists={seed_artists}"

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        data = r.json()

    tracks = []
    for item in data["tracks"]:
        # Fetch artist genres
        artist_id = item["artists"][0]["id"]
        async with httpx.AsyncClient() as client:
            art_resp = await client.get(f"https://api.spotify.com/v1/artists/{artist_id}",
                                        headers={"Authorization": f"Bearer {token}"})
            art_resp.raise_for_status()
            artist_data = art_resp.json()
        tracks.append({
            "trackId": item["id"],
            "title": item["name"],
            "artist": item["artists"][0]["name"],
            "genres": artist_data.get("genres", []),
            "album": item["album"]["name"],
            "previewUrl": item.get("preview_url")
        })
    return tracks

