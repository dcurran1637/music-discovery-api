from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from .. import db, schemas, auth

router = APIRouter(prefix="/api/playlists", tags=["playlists"])

@router.post("", status_code=201)
def create_playlist(payload: schemas.PlaylistCreate, user_payload: dict = Depends(auth.verify_jwt_token)):
    user_id = user_payload.get("user_id")
    item = db.create_playlist(user_id, payload.name, payload.description)
    return item

@router.get("")
def list_playlists(genres: Optional[str] = Query(None), user_payload: dict = Depends(auth.verify_jwt_token)):
    user_id = user_payload.get("user_id")
    items = db.get_playlists_for_user(user_id, genre_filter=genres)
    return items

@router.get("/{playlist_id}")
def get_playlist(playlist_id: str, user_payload: dict = Depends(auth.verify_jwt_token)):
    item = db.get_playlist(playlist_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    if item.get("userId") != user_payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this playlist")
    return item


@router.put("/{playlist_id}")
def update_playlist(playlist_id: str, payload: schemas.PlaylistCreate, user_payload: dict = Depends(auth.verify_jwt_token)):
    # Check exists
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    if existing.get("userId") != user_payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")
    updated = db.update_playlist(playlist_id, name=payload.name, description=getattr(payload, "description", None))
    return updated


@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: str, user_payload: dict = Depends(auth.verify_jwt_token)):
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    if existing.get("userId") != user_payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this playlist")
    return db.delete_playlist(playlist_id)


@router.post("/{playlist_id}/tracks", status_code=201)
def add_track(playlist_id: str, payload: schemas.PlaylistTrack, user_payload: dict = Depends(auth.verify_jwt_token)):
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    if existing.get("userId") != user_payload.get("user_id"):
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
def remove_track(playlist_id: str, track_id: str, user_payload: dict = Depends(auth.verify_jwt_token)):
    existing = db.get_playlist(playlist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    if existing.get("userId") != user_payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this playlist")
    updated = db.remove_track(playlist_id, track_id)
    if not updated:
        # remove_track returns None when playlist not found; but we checked above
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    return updated

