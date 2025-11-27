from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


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

class RecommendedTrack(BaseModel):
    trackId: str
    title: str
    artist: str
    genre: Optional[str] = None
    reason: Optional[str] = None

class Recommendation(BaseModel):
    userId: str
    generatedAt: datetime
    recommendedTracks: List[RecommendedTrack]
