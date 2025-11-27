from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import time

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
    version="v1",
    description="Spotify music discovery and playlist management API"
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

