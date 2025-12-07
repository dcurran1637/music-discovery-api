from fastapi import APIRouter, HTTPException, Query, Header, status
from typing import Optional
from datetime import datetime
from .. import db, schemas, auth
from ..oauth import get_user_profile
from ..spotify_client import (
    get_user_playlists, 
    create_spotify_playlist, 
    update_spotify_playlist, 
    delete_spotify_playlist,
    get_spotify_playlist
)
import os

router = APIRouter(prefix="/api/playlists", tags=["playlists"])

async def get_authenticated_user(
    authorization: Optional[str],
    x_api_key: Optional[str],
    x_user_id: Optional[str],
    require_write: bool = False
) -> tuple[str, Optional[str]]:
    """Resolve the real user id and spotify token.
    Rules:
    - If Authorization Bearer present: try JWT decode first, then Spotify token validation
    - Else if X-API-KEY present: validate key and require X-USER-ID header.
    - No demo fallback; missing credentials => 401.
    - For read (require_write=False) API key flow still needs X-USER-ID.
    
    Returns: (user_id, spotify_token)
    """
    spotify_token = None
    
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header must start with 'Bearer '")
        token = authorization.split(" ")[1]
        
        # Try JWT decode first
        try:
            payload = auth.decode_jwt_token(token)
            user_id = payload.get("user_id")
            spotify_token = payload.get("spotify_access_token")
            if user_id:
                return user_id, spotify_token
        except HTTPException:
            # JWT decode failed - try as raw Spotify token
            pass
        except Exception:
            # JWT decode failed - try as raw Spotify token
            pass
        
        # Try as raw Spotify access token
        try:
            profile = await get_user_profile(token)
            user_id = profile.get("id")
            if user_id:
                return user_id, token  # token is the Spotify access token
        except Exception:
            # Not a valid Spotify token either
            pass
            
    if x_api_key:
        auth.require_write_api_key(x_api_key)
        if not x_user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-USER-ID header")
        return x_user_id, None
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication or invalid token")

# -----------------------------
# Playlist CRUD
# -----------------------------
@router.post("", status_code=201)
async def create_playlist(
    payload: schemas.SpotifyPlaylistCreate,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
):
    """Create a new Spotify playlist for the authenticated user. Auto-syncs to database."""
    user_id, spotify_token = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    
    if not spotify_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Spotify token required to create playlist"
        )
    
    result = await create_spotify_playlist(
        spotify_token=spotify_token,
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        public=payload.public,
        collaborative=payload.collaborative
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to create playlist on Spotify"
        )
    
    # Auto-sync to database
    try:
        db.sync_spotify_playlists(user_id, [result])
    except Exception as e:
        # Log error but don't fail the request
        print(f"Warning: Failed to sync created playlist to database: {e}")
    
    return result

@router.get("")
async def list_playlists(
    limit: int = Query(50, ge=1, le=50, description="Number of playlists to return (max 50)"),
    offset: int = Query(0, ge=0, description="Index of first playlist to return"),
    source: str = Query("spotify", description="Source: 'spotify' (live) or 'db' (synced cache)"),
    authorization: Optional[str] = Header(None), 
    x_api_key: Optional[str] = Header(None), 
    x_user_id: Optional[str] = Header(None)
):
    """
    Get the current user's playlists.
    
    - source='spotify': Fetch live from Spotify API (default)
    - source='db': Get from synced database cache
    """
    user_id, spotify_token = await get_authenticated_user(authorization, x_api_key, x_user_id)
    
    if source == "db":
        # Get from database
        try:
            playlists = db.get_synced_spotify_playlists(user_id)
            return {"items": playlists, "total": len(playlists), "source": "database"}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch playlists from database: {str(e)}"
            )
    
    # Default: Get from Spotify API
    if not spotify_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Spotify token required to fetch playlists"
        )
    
    try:
        playlists_data = await get_user_playlists(spotify_token, limit=limit, offset=offset)
        playlists_data["source"] = "spotify"
        return playlists_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Failed to fetch playlists from Spotify: {str(e)}"
        )


@router.post("/sync", status_code=200)
async def sync_playlists(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
):
    """
    Sync all user's Spotify playlists to the database.
    
    This fetches all playlists from Spotify and stores them in PostgreSQL
    for faster access and offline availability.
    """
    user_id, spotify_token = await get_authenticated_user(authorization, x_api_key, x_user_id)
    
    if not spotify_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Spotify token required to sync playlists"
        )
    
    try:
        # Fetch all playlists from Spotify (paginated)
        all_playlists = []
        limit = 50
        offset = 0
        
        while True:
            response = await get_user_playlists(spotify_token, limit=limit, offset=offset)
            items = response.get("items", [])
            all_playlists.extend(items)
            
            # Check if there are more playlists
            total = response.get("total", 0)
            if offset + limit >= total:
                break
            offset += limit
        
        # Sync to database
        stats = db.sync_spotify_playlists(user_id, all_playlists)
        
        return {
            "message": "Playlists synced successfully",
            "user_id": user_id,
            "stats": stats,
            "synced_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to sync playlists: {str(e)}"
        )

@router.get("/{playlist_id}")
async def get_playlist(playlist_id: str):
    try:
        item = db.get_playlist(playlist_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return item

@router.put("/{playlist_id}")
async def update_playlist(
    playlist_id: str,
    payload: schemas.SpotifyPlaylistUpdate,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
):
    """Update a Spotify playlist's details. Only provided fields will be updated. Auto-syncs to database."""
    user_id, spotify_token = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    
    if not spotify_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Spotify token required to update playlist"
        )
    
    success = await update_spotify_playlist(
        spotify_token=spotify_token,
        playlist_id=playlist_id,
        name=payload.name,
        description=payload.description,
        public=payload.public,
        collaborative=payload.collaborative
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to update playlist on Spotify. Check if you own the playlist."
        )
    
    # Auto-sync updated playlist to database
    try:
        updated_playlist = await get_spotify_playlist(spotify_token, playlist_id)
        if updated_playlist:
            db.sync_spotify_playlists(user_id, [updated_playlist])
    except Exception as e:
        # Log error but don't fail the request
        print(f"Warning: Failed to sync updated playlist to database: {e}")
    
    return {"message": "Playlist updated successfully", "playlist_id": playlist_id}

@router.delete("/{playlist_id}")
async def delete_playlist(
    playlist_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
):
    """Unfollow/delete a Spotify playlist. Note: This unfollows the playlist. Auto-removes from database."""
    user_id, spotify_token = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    
    if not spotify_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Spotify token required to delete playlist"
        )
    
    success = await delete_spotify_playlist(
        spotify_token=spotify_token,
        playlist_id=playlist_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to delete playlist on Spotify. Check if you own the playlist."
        )
    
    # Auto-remove from database
    try:
        db.delete_synced_spotify_playlist(playlist_id)
    except Exception as e:
        # Log error but don't fail the request
        print(f"Warning: Failed to remove deleted playlist from database: {e}")
    
    return {"message": "Playlist deleted successfully", "playlist_id": playlist_id}

# -----------------------------
# Playlist Tracks
# -----------------------------
@router.post("/{playlist_id}/tracks", status_code=201)
async def add_track(playlist_id: str, payload: schemas.PlaylistTrack, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    try:
        existing = db.get_playlist(playlist_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id, spotify_token = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    if existing.get("userId") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")

    track = {
        "trackId": payload.trackId,
        "title": payload.title,
        "artist": payload.artist,
        "genre": getattr(payload, "genre", None),
    }
    try:
        updated = db.add_track(playlist_id, track)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return updated

@router.delete("/{playlist_id}/tracks/{track_id}")
async def remove_track(playlist_id: str, track_id: str, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    try:
        existing = db.get_playlist(playlist_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id, spotify_token = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    if existing.get("userId") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")

    try:
        updated = db.remove_track(playlist_id, track_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return updated
