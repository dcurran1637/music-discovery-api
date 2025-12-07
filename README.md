# Music Discovery API

A REST API that connects to your Spotify account to help you discover music, manage playlists, and get personalized recommendations.

## What Does It Do?

This API lets you:
- 🎵 **Discover Music** - Get personalized track recommendations based on your taste
- 📝 **Manage Playlists** - Create, edit, and delete Spotify playlists through the API
- 💾 **Cache Data** - Store playlist information locally for faster access
- 🔍 **Search & Explore** - Browse artists, tracks, and albums
- 🔐 **Secure Access** - Uses Spotify OAuth for safe authentication

---

## How It Works

1. **You authenticate** with your Spotify account
2. **The API talks to Spotify** to get your music data
3. **Your playlists sync** to a local database for quick access
4. **You make requests** to discover music or manage playlists
5. **Changes sync automatically** back to Spotify and the database

---

## Getting Started

### Prerequisites

- Python 3.8+
- Docker (for database)
- A Spotify account
- Spotify Developer credentials ([create an app here](https://developer.spotify.com/dashboard))

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Database
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/music_discovery"

# Spotify App Credentials (get these from https://developer.spotify.com/dashboard)
export SPOTIFY_CLIENT_ID="your_spotify_client_id"
export SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8000/api/auth/callback"

# Security
export JWT_SECRET="your_random_secret_key_here"

# Optional: Redis for caching
export REDIS_URL="redis://localhost:6379"
```

Load the variables:
```bash
source .env
```

### 3. Start the Database

Start PostgreSQL with Docker:
```bash
docker run -d --name postgres-music-api \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=music_discovery \
  -p 5432:5432 \
  postgres:15-alpine
```

(Optional) Start Redis for caching:
```bash
docker run -d --name redis-local -p 6379:6379 redis:alpine
```

### 4. Initialize the Database

This creates all the necessary tables:
```bash
python scripts/init_postgres.py
```

### 5. Start the API Server

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now running at `http://127.0.0.1:8000`

---

## Using the API

### 1. Authenticate with Spotify

Visit `http://127.0.0.1:8000/api/auth/login` in your browser. This will:
- Redirect you to Spotify to authorize the app
- Return you to the callback URL with a JWT token
- Automatically sync your playlists to the database

### 2. Make API Requests

Use the JWT token in the `Authorization` header:

```bash
# Set your token (you get this from the login callback)
export JWT_TOKEN="your_jwt_token_here"

# Get your playlists from Spotify
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "http://127.0.0.1:8000/api/playlists?source=spotify"

# Get cached playlists from the database (faster)
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "http://127.0.0.1:8000/api/playlists?source=db"

# Create a new playlist
curl -X POST "http://127.0.0.1:8000/api/playlists" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Test Playlist","description":"Created via API","public":true}'

# Get music recommendations
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "http://127.0.0.1:8000/api/discover/recommendations?limit=10"

# Update a playlist
curl -X PUT "http://127.0.0.1:8000/api/playlists/{playlist_id}" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Updated Name","description":"New description"}'

# Delete a playlist
curl -X DELETE "http://127.0.0.1:8000/api/playlists/{playlist_id}" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### 3. Explore the Interactive Docs

Visit `http://127.0.0.1:8000/docs` for interactive API documentation where you can test endpoints directly in your browser.

---

## Key Features Explained

### Playlist Management

- **Create playlists** on Spotify through the API
- **Edit playlist details** (name, description, public/private)
- **Delete playlists** from your Spotify account
- **Auto-sync** - Changes are automatically saved to both Spotify and your local database

### Data Sources

You can choose where to fetch playlist data:
- `source=spotify` - Get live data directly from Spotify (slower but always up-to-date)
- `source=db` - Get cached data from your local database (faster)

### Recommendations Engine

Get personalized music recommendations based on:
- Your listening history
- Specific artists or tracks you like
- Genre preferences
- Audio features (danceability, energy, tempo, etc.)

### Authentication Methods

The API supports multiple authentication options:
1. **JWT tokens** (recommended) - Get from OAuth login flow
2. **Raw Spotify tokens** - Use your Spotify access token directly
3. **API keys** - Use `X-API-KEY` and `X-USER-ID` headers

---

## API Endpoints Overview

### Authentication
- `GET /api/auth/login` - Start Spotify OAuth login
- `GET /api/auth/callback` - OAuth callback (handles token exchange)

### Playlists
- `GET /api/playlists` - List your playlists (with source selection)
- `POST /api/playlists` - Create a new playlist
- `GET /api/playlists/{id}` - Get specific playlist details
- `PUT /api/playlists/{id}` - Update playlist metadata
- `DELETE /api/playlists/{id}` - Delete a playlist
- `POST /api/playlists/sync` - Manually sync all playlists to database

### Discovery
- `GET /api/discover/recommendations` - Get personalized track recommendations
- `GET /api/artists/{id}` - Get artist information
- `GET /api/tracks/{id}` - Get track details

### Health
- `GET /health` - Check API health status

---

## Project Structure

```
music-discovery-api/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── auth.py              # JWT authentication logic
│   ├── oauth.py             # Spotify OAuth implementation
│   ├── spotify_client.py    # Spotify API client functions
│   ├── database.py          # SQLAlchemy models
│   ├── db.py                # Database helper functions
│   ├── schemas.py           # Pydantic request/response models
│   └── routes/              # API endpoint routes
│       ├── auth_routes.py   # Authentication endpoints
│       ├── playlists.py     # Playlist management
│       ├── recommendations.py # Music discovery
│       ├── artists.py       # Artist endpoints
│       ├── tracks.py        # Track endpoints
│       └── health.py        # Health check
├── scripts/
│   └── init_postgres.py     # Database initialization
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## Database Schema

The API uses PostgreSQL to store:

- **user_tokens** - Encrypted Spotify tokens for each user
- **spotify_playlists** - Cached playlist metadata (synced from Spotify)
- **playlists** - (Legacy table, may be deprecated)

Playlists are automatically synced when:
- You log in via OAuth
- You create a new playlist
- You update a playlist
- You manually trigger a sync via `/api/playlists/sync`

---

## Troubleshooting

### "Token expired" errors
Your Spotify token expires after 1 hour. Log in again at `/api/auth/login` to get a fresh token.

### Playlists not showing up
Make sure you've completed the OAuth login flow. Your playlists sync automatically during authentication.

### Database connection errors
Ensure PostgreSQL is running:
```bash
docker ps | grep postgres-music-api
```

If it's not running, start it with the command in step 3 of Getting Started.

### OAuth scope errors
If playlists return empty, ensure your Spotify app has the correct OAuth scopes enabled (the code handles this automatically).

---

## Optional: Database Management UI

Install pgAdmin to view and manage your database:

```bash
docker run -d --name pgadmin \
  -e PGADMIN_DEFAULT_EMAIL=admin@admin.com \
  -e PGADMIN_DEFAULT_PASSWORD=admin \
  -p 5050:80 \
  dpage/pgadmin4
```

Access pgAdmin at `http://localhost:5050` (login: admin@admin.com / admin)

**Connection settings:**
- Host: localhost
- Port: 5432
- Database: music_discovery
- Username: postgres
- Password: postgres

---

## Next Steps

- Check out the interactive docs at `/docs` to explore all endpoints
- Read [DATABASE_SETUP.md](DATABASE_SETUP.md) for detailed database information
- See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment guides

---

## Tech Stack

- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Database ORM
- **PostgreSQL** - Relational database
- **Redis** - Optional caching layer
- **Spotify Web API** - Music data source
- **JWT** - Secure authentication tokens