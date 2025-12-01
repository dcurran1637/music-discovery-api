# Music Discovery API

A FastAPI backend for Spotify music discovery, playlist management, and personalized recommendations.

## Features

- Spotify integration for tracks, artists, and recommendations
- Playlist CRUD operations
- JWT authentication with Spotify OAuth
- PostgreSQL database with pgAdmin interface
- Optional Redis caching

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Create `.env` file:
```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/music_discovery"
export SPOTIFY_CLIENT_ID="your_spotify_client_id"
export SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8000/api/auth/callback"
export JWT_SECRET="your_jwt_secret"
```

Then load it:
```bash
source .env
```

### 3. Start services with Docker

**PostgreSQL:**
```bash
docker run -d --name postgres-local \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=music_discovery \
  -p 5432:5432 \
  postgres:15-alpine
```

**pgAdmin (Database UI):**
```bash
docker run -d --name pgadmin \
  -e PGADMIN_DEFAULT_EMAIL=admin@admin.com \
  -e PGADMIN_DEFAULT_PASSWORD=admin \
  -p 5050:80 \
  dpage/pgadmin4
```

**Redis (optional):**
```bash
docker run -d --name redis-local -p 6379:6379 redis:alpine
```

### 4. Initialize database
```bash
python scripts/init_postgres.py
```

### 5. Start API server
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0
```

---

## Access Points

- **API**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs
- **pgAdmin**: http://localhost:5050 (login: admin@admin.com / admin)

### Database Connection (for pgAdmin)
- **Host**: postgres-local (or localhost if not using Docker network)
- **Port**: 5432
- **Database**: music_discovery
- **Username**: postgres
- **Password**: postgres

---

## Key Endpoints

- `GET /api/discover/recommendations` - Get personalized track recommendations
- `GET /api/artists/{artist_id}` - Get artist details
- `GET /api/tracks/{track_id}` - Get track details
- `GET /api/playlists` - List user playlists
- `POST /api/playlists` - Create new playlist
- `GET /api/auth/login` - Start OAuth login flow

All endpoints require JWT authentication via `Authorization: Bearer <token>` header.

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment instructions.