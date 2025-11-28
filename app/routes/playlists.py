from fastapi import APIRouter, HTTPException, Query, Header, status
from typing import Optional
from .. import db, schemas, auth
import os

router = APIRouter(prefix="/api/playlists", tags=["playlists"])

# Fallback user ID for public/demo access
DEMO_USER_ID = os.getenv("DEMO_USER_ID", "real_demo_user_id")  # replace with actual user ID

def get_authenticated_user(
    authorization: Optional[str], 
    x_api_key: Optional[str], 
    require_write: bool = False
) -> str:
    """
    Resolve user ID from JWT or API key.
    If require_write=True, ensures the user can perform write operations.
    For read-only operations, falls back to DEMO_USER_ID if no auth provided.
    """
    if authorization:
        # Strip "Bearer " prefix if present
        token = authorization.split(" ")[-1] if authorization.startswith("Bearer ") else authorization
        try:
            user_payload = auth.verify_jwt_token(token)
            return user_payload.get("user_id")
        except Exception:
            if require_write:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            return DEMO_USER_ID
    elif x_api_key:
        auth.require_write_api_key(x_api_key)
        return DEMO_USER_ID
    elif not require_write:
        # Read-only public access uses DEMO_USER_ID
        return DEMO_USER_ID
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth")

# -----------------------------
# Playlist CRUD
# -----------------------------
@router.post("", status_code=201)
def create_playlist(payload: schemas.PlaylistCreate, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    user_id = get_authenticated_user(authorization, x_api_key, require_write=True)
    return db.create_playlist(user_id, payload.name, payload.description)

@router.get("")
def list_playlists(genres: Optional[str] = Query(None), authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    user_id = get_authenticated_user(authorization, x_api_key)
    return db.get_playlists_for_user(user_id, genre_filter=genres)

@router.get("/{playlist_id}")
def get_playlist(playlist_id: str):
    item = db.get_playlist(playlist_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return item

@router.put("/{playlist_id}")
def update_playlist(playlist_id: str, payload: schemas.PlaylistCreate, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id = get_authenticated_user(authorization, x_api_key, require_write=True)
    if existing.get("userId") != user_id and user_id != DEMO_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")

    return db.update_playlist(playlist_id, name=payload.name, description=getattr(payload, "description", None))

@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: str, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id = get_authenticated_user(authorization, x_api_key, require_write=True)
    if existing.get("userId") != user_id and user_id != DEMO_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this playlist")

    return db.delete_playlist(playlist_id)

# -----------------------------
# Playlist Tracks
# -----------------------------
@router.post("/{playlist_id}/tracks", status_code=201)
def add_track(playlist_id: str, payload: schemas.PlaylistTrack, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id = get_authenticated_user(authorization, x_api_key, require_write=True)
    if existing.get("userId") != user_id and user_id != DEMO_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")

    track = {
        "trackId": payload.trackId,
        "title": payload.title,
        "artist": payload.artist,
        "genre": getattr(payload, "genre", None),
    }
    updated = db.add_track(playlist_id, track)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return updated

@router.delete("/{playlist_id}/tracks/{track_id}")
def remove_track(playlist_id: str, track_id: str, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    user_id = get_authenticated_user(authorization, x_api_key, require_write=True)
    if existing.get("userId") != user_id and user_id != DEMO_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")

    updated = db.remove_track(playlist_id, track_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return updated
