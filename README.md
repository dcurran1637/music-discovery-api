# Music Discovery API

A REST API that connects to Spotify to help you discover music, manage playlists, and get personalized recommendations. Built with FastAPI, PostgreSQL, and Spotify Web API.

## Features

- **Music Discovery** - Get personalized track recommendations based on listening history and preferences
- **Playlist Management** - Create, update, and delete Spotify playlists
- **Artist & Track Info** - Browse detailed information about artists and tracks
- **OAuth Authentication** - Secure Spotify login with JWT tokens
- **Database Caching** - Fast access to playlist data with PostgreSQL
- **Retry & Backoff** - Resilient API calls with exponential backoff and circuit breakers

## Demo Credentials for Marking

**Production API URL:** `https://music-discovery-api-q03t.onrender.com`

### Option 1: Use the Demo Write API Key (Quickest)

For endpoints that require authentication, use this demo API key:

```bash
# Demo Write API Key
X-API-KEY: demo_write_key_123
X-USER-ID: demo_user
```

Example request:
```bash
curl -H "X-API-KEY: demo_write_key_123" \
     -H "X-USER-ID: demo_user" \
     "https://music-discovery-api-q03t.onrender.com/api/playlists?source=db"
```

### Option 2: OAuth with Your Spotify Account

1. Visit: `https://music-discovery-api-q03t.onrender.com/api/auth/login?user_id=professor_test`
2. Log in with your Spotify account
3. Copy the JWT token from the callback response
4. Use the token in the `Authorization: Bearer <token>` header

### Testing Endpoints

```bash
# Health check (no auth required)
curl "https://music-discovery-api-q03t.onrender.com/api/health/live"

# Get recommendations (with demo API key)
curl -H "X-API-KEY: demo_write_key_123" \
     -H "X-USER-ID: demo_user" \
     "https://music-discovery-api-q03t.onrender.com/api/discover/recommendations?limit=5"

# Interactive API docs
# Visit: https://music-discovery-api-q03t.onrender.com/docs
```

---

## Setup Instructions

### Prerequisites

- Python 3.8+
- A Spotify account
- Spotify Developer credentials ([create an app here](https://developer.spotify.com/dashboard))

### Quick Start

#### 1. Clone and Install Dependencies

```bash
git clone https://github.com/dcurran1637/music-discovery-api.git
cd music-discovery-api
pip install -r requirements.txt
```

#### 2. Set Up Environment Variables

Create a `.env` file:

```bash
# Spotify App Credentials (from https://developer.spotify.com/dashboard)
export SPOTIFY_CLIENT_ID="your_spotify_client_id"
export SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"
export SPOTIFY_REDIRECT_URI="https://music-discovery-api-q03t.onrender.com/api/auth/callback"

# Database
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/music_discovery"

# Security
export JWT_SECRET="your_random_secret_key"
export WRITE_API_KEY="demo_write_key_123"
```

Load the environment:
```bash
source .env
```

#### 3. Start PostgreSQL Database

```bash
docker run -d --name postgres-music-api \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=music_discovery \
  -p 5432:5432 \
  postgres:15-alpine
```

#### 4. Initialize Database Tables

```bash
python scripts/init_postgres.py
```

#### 5. Run the API Server

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 6. Test the API

```bash
# Check health
curl "https://music-discovery-api-q03t.onrender.com/api/health/live"

# View interactive docs
# Open: https://music-discovery-api-q03t.onrender.com/docs
```

---

## API Usage Examples

### Authentication

Start OAuth flow in your browser:
```
https://music-discovery-api-q03t.onrender.com/api/auth/login?user_id=your_username
```

This redirects to Spotify, then returns a JWT token for API requests.

### Get Recommendations

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "https://music-discovery-api-q03t.onrender.com/api/discover/recommendations?limit=10"
```

### Get Artist Information

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "https://music-discovery-api-q03t.onrender.com/api/artists/0OdUWJ0sBjDrqHygGUXeCF"
```

### List Your Playlists

```bash
# From Spotify (live)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "https://music-discovery-api-q03t.onrender.com/api/playlists?source=spotify"

# From database (cached, faster)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "https://music-discovery-api-q03t.onrender.com/api/playlists?source=db"
```

### Create a Playlist

```bash
curl -X POST "https://music-discovery-api-q03t.onrender.com/api/playlists" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My New Playlist",
    "description": "Created via API",
    "public": true
  }'
```

### Update a Playlist

```bash
curl -X PUT "https://music-discovery-api-q03t.onrender.com/api/playlists/{playlist_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Name",
    "description": "New description"
  }'
```

### Delete a Playlist

```bash
curl -X DELETE "https://music-discovery-api-q03t.onrender.com/api/playlists/{playlist_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Key API Endpoints

### Authentication
- `GET /api/auth/login` - Start Spotify OAuth login
- `GET /api/auth/callback` - OAuth callback handler

### Playlists
- `GET /api/playlists` - List playlists (with `?source=spotify` or `?source=db`)
- `POST /api/playlists` - Create new playlist
- `GET /api/playlists/{id}` - Get playlist details
- `PUT /api/playlists/{id}` - Update playlist
- `DELETE /api/playlists/{id}` - Delete playlist
- `POST /api/playlists/sync` - Sync all playlists to database

### Discovery
- `GET /api/discover/recommendations` - Get track recommendations
- `GET /api/discover/recommendations/artists` - Get artist recommendations
- `GET /api/discover/recommendations/genres` - List available genres

### Music Info
- `GET /api/artists/{id}` - Get artist details
- `GET /api/tracks/{id}` - Get track details

### Health
- `GET /api/health/live` - Health check

---

## Project Structure

```
music-discovery-api/
├── app/
│   ├── main.py              # FastAPI application
│   ├── auth.py              # JWT authentication
│   ├── oauth.py             # Spotify OAuth
│   ├── spotify_client.py    # Spotify API client with retry logic
│   ├── resilience.py        # Retry & circuit breaker utilities
│   ├── database.py          # SQLAlchemy models
│   ├── db.py                # Database helpers
│   ├── schemas.py           # Pydantic models
│   └── routes/              # API routes
├── scripts/
│   └── init_postgres.py     # Database setup script
├── tests/                   # Unit tests
├── requirements.txt         # Dependencies
└── README.md               # This file
```

---

## Tech Stack

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Database for caching playlists
- **SQLAlchemy** - ORM for database operations
- **Spotify Web API** - Music data source
- **OAuth 2.0** - Secure authentication
- **JWT** - Token-based auth
- **Retry & Circuit Breaker** - Resilient API calls with exponential backoff
- **Render** - Production hosting platform
- **GitHub Actions** - CI/CD pipeline

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_spotify_client.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

---

## Deployment

The API is deployed on Render with automated CI/CD via GitHub Actions.

**Live Production URL:** `https://music-discovery-api-q03t.onrender.com`

For deployment details, see:
- Infrastructure config: [render.yaml](render.yaml)
- CI/CD workflow: [.github/workflows/](.github/workflows/)
- Kubernetes config: [k8s-deployment.yaml](k8s-deployment.yaml)

---

## Troubleshooting

### Token Expired Error
Spotify tokens expire after 1 hour. Re-authenticate at `/api/auth/login`.

### Database Connection Failed
Ensure PostgreSQL is running:
```bash
docker ps | grep postgres-music-api
```

### Empty Playlists Response
Complete the OAuth flow to sync playlists from your Spotify account.

### Port Already in Use
Change the port in the uvicorn command:
```bash
python -m uvicorn app.main:app --reload --port 8001
```

---

## License

This project is for educational purposes.

---

## Contact

For questions or issues, contact: dcurran1637@gmail.com