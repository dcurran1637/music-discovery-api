from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import time
from dotenv import load_dotenv
import sys

# Load environment variables from .env file (skip in test mode)
if "pytest" not in sys.modules:
    load_dotenv()

from .routes import playlists
from .routes import tracks
from .routes import artists
from .routes import recommendations
from .routes import auth_routes
from .routes import gdpr
from .routes import health
from .logging_config import get_logger

logger = get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Music Discovery API",
    version="v1.0",
    description="""
## Spotify Music Discovery and Playlist Management API

A comprehensive API for discovering music, managing playlists, and generating personalized recommendations using Spotify's Web API.

### Key Features
- **Custom Recommendations Engine**: Built from scratch using Spotify's search, top artists, and top tracks APIs
- **Time-Range Personalization**: Get recommendations based on short-term (4 weeks), medium-term (6 months), or long-term (1 year) listening history
- **Dual Authentication**: Supports both raw Spotify access tokens and JWT tokens
- **PostgreSQL Database**: Full playlist management with PostgreSQL backend (Render-compatible)
- **OAuth 2.0 Flow**: Complete Spotify OAuth integration
- **Caching**: Optional Redis caching for improved performance

### Authentication Methods

**Method 1: Spotify Access Token (Recommended)**
```
Authorization: Bearer <spotify_access_token>
```
Get token from `/api/auth/login` → OAuth flow → `/api/auth/callback`

**Method 2: API Key + User ID**
```
X-API-KEY: <your_api_key>
X-USER-ID: <spotify_user_id>
```

**Method 3: JWT Token (Legacy)**
```
Authorization: Bearer <jwt_token>
```

### Database
- **Type**: PostgreSQL 15+
- **Tables**: `playlists`, `user_tokens`
- **Render Compatible**: Native support for Render's managed PostgreSQL

### Quick Start
1. Get Spotify credentials: https://developer.spotify.com
2. Configure environment variables (see `.env.example`)
3. Initialize database: `python scripts/init_postgres.py`
4. Start server: `uvicorn app.main:app --reload`
5. Access docs: http://localhost:8000/docs
    """,
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://your-app.onrender.com", "description": "Production (Render)"}
    ]
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429,
    content={"detail": "Rate limit exceeded. Please try again later."},
))

# Include routers
app.include_router(playlists.router)
app.include_router(tracks.router)
app.include_router(artists.router)
app.include_router(recommendations.router)
app.include_router(auth_routes.router)
app.include_router(gdpr.router)
app.include_router(health.router)

# Middleware for request/response logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with duration."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} - {str(e)}")
        raise
    
    # Log response with duration
    duration = time.time() - start_time
    logger.info(
        f"Completed request: {request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s"
    )
    
    return response

# root endpoint
@app.get("/")
def root():
    return {
        "message": "Music Discovery API — FastAPI",
        "version": "v1",
        "docs": "/docs",
        "health": "/api/health/live"
    }

