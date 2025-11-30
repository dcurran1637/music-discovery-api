from fastapi import APIRouter, HTTPException, Query, Header, status
from typing import Optional
from .. import db, schemas, auth
from ..oauth import get_user_profile
import os

router = APIRouter(prefix="/api/playlists", tags=["playlists"])

async def get_authenticated_user(
    authorization: Optional[str],
    x_api_key: Optional[str],
    x_user_id: Optional[str],
    require_write: bool = False
) -> str:
    """Resolve the real user id.
    Rules:
    - If Authorization Bearer present: try JWT decode first, then Spotify token validation
    - Else if X-API-KEY present: validate key and require X-USER-ID header.
    - No demo fallback; missing credentials => 401.
    - For read (require_write=False) API key flow still needs X-USER-ID.
    """
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header must start with 'Bearer '")
        token = authorization.split(" ")[1]
        
        # Try JWT decode first
        try:
            payload = auth.decode_jwt_token(token)
            user_id = payload.get("user_id")
            if user_id:
                return user_id
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
                return user_id
        except Exception:
            # Not a valid Spotify token either
            pass
            
    if x_api_key:
        auth.require_write_api_key(x_api_key)
        if not x_user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-USER-ID header")
        return x_user_id
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication or invalid token")

# -----------------------------
# Playlist CRUD
# -----------------------------
@router.post("", status_code=201)
async def create_playlist(payload: schemas.PlaylistCreate, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    user_id = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    try:
        return db.create_playlist(user_id, payload.name, payload.description)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")

@router.get("")
async def list_playlists(genres: Optional[str] = Query(None), authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    user_id = await get_authenticated_user(authorization, x_api_key, x_user_id)
    try:
        return db.get_playlists_for_user(user_id, genre_filter=genres)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")

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
async def update_playlist(playlist_id: str, payload: schemas.PlaylistCreate, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    try:
        existing = db.get_playlist(playlist_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    if existing.get("userId") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")

    try:
        return db.update_playlist(playlist_id, name=payload.name, description=getattr(payload, "description", None))
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")

@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: str, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    try:
        existing = db.get_playlist(playlist_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    if existing.get("userId") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this playlist")

    try:
        return db.delete_playlist(playlist_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")

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

    user_id = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
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

    user_id = await get_authenticated_user(authorization, x_api_key, x_user_id, require_write=True)
    if existing.get("userId") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")

    try:
        updated = db.remove_track(playlist_id, track_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage unavailable. Configure DynamoDB or endpoint.")
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return updated
