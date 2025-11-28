# Music Discovery API

A FastAPI-based backend for discovering Spotify tracks and artists, managing playlists, and generating personalized recommendations. Supports caching via Redis, JWT authentication, and Spotify API integration.

## Features

- **Spotify Integration**: Fetch artist and track metadata, user top artists/tracks, and recommendations.
- **Playlist Management**: Create, update, delete playlists and manage tracks.
- **User Authentication**: JWT-based authentication with optional API key fallback for legacy/demo usage.
- **Caching**: Redis-based caching for tracks, artists, and recommendations to improve performance.
- **Recommendation Engine**: Generates personalized recommendations based on user top genres, artists, and tracks.

---

## Requirements

- Python 3.11+
- Redis (default at `redis://localhost:6379`)
- Spotify Developer account credentials (Client ID & Client Secret)
- Optional: `.env` file for environment variables

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/music-discovery-api.git
cd music-discovery-api

### 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows

### 3. instal dependencies
pip install -r requirements.txt

### 4. run redis
redis-server

### 5. start the api server
python -m uvicorn app.main:app --reload

###API Endpoints Overview
/api/discover/recommendations

Returns Spotify track recommendations for the authenticated user.

Optional query params: genres, min_popularity, released_after.

Requires Authorization: Bearer <JWT>.

/api/artists/{artist_id}

Returns artist metadata, including genres and images.

Requires JWT authentication.

/api/artists/by-genres/

Returns artists matching specified genres.

Requires JWT authentication.

/api/tracks/{track_id}

Returns track metadata and first artist's genres.

Optional Spotify token can be provided.

/api/playlists

CRUD operations for user playlists.

Supports JWT or demo API key fallback.