import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from .database import SessionLocal, Playlist, UserToken


def create_playlist(user_id: str, name: str, description: str = "") -> Dict:
    """Create a new playlist."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        playlist = Playlist(
            id=str(uuid.uuid4()),
            userId=user_id,
            name=name,
            description=description,
            tracks=[],
            createdAt=now,
            updatedAt=now,
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        
        return {
            "id": playlist.id,
            "userId": playlist.userId,
            "name": playlist.name,
            "description": playlist.description,
            "tracks": playlist.tracks or [],
            "createdAt": playlist.createdAt.isoformat(),
            "updatedAt": playlist.updatedAt.isoformat(),
        }
    finally:
        db.close()


def get_playlists_for_user(user_id: str, genre_filter: Optional[str] = None) -> List[Dict]:
    """Get all playlists for a user, optionally filtered by genre."""
    db = SessionLocal()
    try:
        playlists = db.query(Playlist).filter(Playlist.userId == user_id).all()
        
        items = []
        for p in playlists:
            tracks = p.tracks or []
            if genre_filter:
                genres = set([g.strip().lower() for g in genre_filter.split(",")])
                tracks = [t for t in tracks if t.get("genre") and t["genre"].lower() in genres]
            
            items.append({
                "id": p.id,
                "userId": p.userId,
                "name": p.name,
                "description": p.description,
                "tracks": tracks,
                "createdAt": p.createdAt.isoformat(),
                "updatedAt": p.updatedAt.isoformat(),
            })
        
        return items
    finally:
        db.close()


def get_playlist(playlist_id: str) -> Optional[Dict]:
    """Get a single playlist by ID."""
    db = SessionLocal()
    try:
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist:
            return None
        
        return {
            "id": playlist.id,
            "userId": playlist.userId,
            "name": playlist.name,
            "description": playlist.description,
            "tracks": playlist.tracks or [],
            "createdAt": playlist.createdAt.isoformat(),
            "updatedAt": playlist.updatedAt.isoformat(),
        }
    finally:
        db.close()


def update_playlist(playlist_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Dict]:
    """Update a playlist's name and/or description."""
    db = SessionLocal()
    try:
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist:
            return None
        
        if name:
            playlist.name = name
        if description is not None:
            playlist.description = description
        
        playlist.updatedAt = datetime.utcnow()
        db.commit()
        db.refresh(playlist)
        
        return {
            "id": playlist.id,
            "userId": playlist.userId,
            "name": playlist.name,
            "description": playlist.description,
            "tracks": playlist.tracks or [],
            "createdAt": playlist.createdAt.isoformat(),
            "updatedAt": playlist.updatedAt.isoformat(),
        }
    finally:
        db.close()


def delete_playlist(playlist_id: str) -> Dict:
    """Delete a playlist."""
    db = SessionLocal()
    try:
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if playlist:
            db.delete(playlist)
            db.commit()
        return {"message": "Playlist deleted successfully"}
    finally:
        db.close()


def add_track(playlist_id: str, track: Dict) -> Optional[Dict]:
    """Add a track to a playlist."""
    db = SessionLocal()
    try:
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist:
            return None
        
        tracks = playlist.tracks or []
        tracks.append(track)
        playlist.tracks = tracks
        playlist.updatedAt = datetime.utcnow()
        
        db.commit()
        db.refresh(playlist)
        
        return {
            "id": playlist.id,
            "userId": playlist.userId,
            "name": playlist.name,
            "description": playlist.description,
            "tracks": playlist.tracks or [],
            "createdAt": playlist.createdAt.isoformat(),
            "updatedAt": playlist.updatedAt.isoformat(),
        }
    finally:
        db.close()


def remove_track(playlist_id: str, track_id: str) -> Optional[Dict]:
    """Remove a track from a playlist."""
    db = SessionLocal()
    try:
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist:
            return None
        
        tracks = playlist.tracks or []
        tracks = [t for t in tracks if t.get("trackId") != track_id]
        playlist.tracks = tracks
        playlist.updatedAt = datetime.utcnow()
        
        db.commit()
        db.refresh(playlist)
        
        return {
            "id": playlist.id,
            "userId": playlist.userId,
            "name": playlist.name,
            "description": playlist.description,
            "tracks": playlist.tracks or [],
            "createdAt": playlist.createdAt.isoformat(),
            "updatedAt": playlist.updatedAt.isoformat(),
        }
    finally:
        db.close()


def put_user_tokens(user_id: str, access_token_encrypted: str, refresh_token_encrypted: str, expires_at_iso: str) -> Dict:
    """Store or update user's Spotify tokens (encrypted) and expiry timestamp (ISO)."""
    db = SessionLocal()
    try:
        token = db.query(UserToken).filter(UserToken.id == user_id).first()
        now = datetime.utcnow()
        
        if token:
            token.access_token = access_token_encrypted
            token.refresh_token = refresh_token_encrypted
            token.expires_at = expires_at_iso
            token.updatedAt = now
        else:
            token = UserToken(
                id=user_id,
                user_id=user_id,
                access_token=access_token_encrypted,
                refresh_token=refresh_token_encrypted,
                expires_at=expires_at_iso,
                type="user_tokens",
                createdAt=now,
                updatedAt=now,
            )
            db.add(token)
        
        db.commit()
        db.refresh(token)
        
        return {
            "id": token.id,
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
            "updatedAt": token.updatedAt.isoformat(),
        }
    finally:
        db.close()


def get_user_tokens(user_id: str) -> Optional[Dict]:
    """Get user's stored tokens."""
    db = SessionLocal()
    try:
        token = db.query(UserToken).filter(UserToken.id == user_id).first()
        if not token:
            return None
        
        return {
            "id": token.id,
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
        }
    except Exception:
        return None
    finally:
        db.close()


def put_session_tokens(session_id: str, user_id: str, access_token_encrypted: str, refresh_token_encrypted: str, expires_at_iso: str) -> Optional[Dict]:
    """Store or update session-scoped Spotify tokens (encrypted) tied to a session_id."""
    db = SessionLocal()
    try:
        token = db.query(UserToken).filter(UserToken.id == session_id).first()
        now = datetime.utcnow()
        
        if token:
            token.user_id = user_id
            token.access_token = access_token_encrypted
            token.refresh_token = refresh_token_encrypted
            token.expires_at = expires_at_iso
            token.updatedAt = now
        else:
            token = UserToken(
                id=session_id,
                user_id=user_id,
                access_token=access_token_encrypted,
                refresh_token=refresh_token_encrypted,
                expires_at=expires_at_iso,
                type="session_tokens",
                createdAt=now,
                updatedAt=now,
            )
            db.add(token)
        
        db.commit()
        db.refresh(token)
        
        return {
            "id": token.id,
            "user_id": token.user_id,
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
            "createdAt": token.createdAt.isoformat(),
            "updatedAt": token.updatedAt.isoformat(),
        }
    except Exception:
        return None
    finally:
        db.close()


def get_session_tokens(session_id: str) -> Optional[Dict]:
    """Retrieve the session-scoped token record by session_id."""
    db = SessionLocal()
    try:
        token = db.query(UserToken).filter(UserToken.id == session_id).first()
        if not token:
            return None
        
        return {
            "id": token.id,
            "user_id": token.user_id,
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
        }
    except Exception:
        return None
    finally:
        db.close()


def delete_session_tokens(session_id: str) -> bool:
    """Delete a session token record (best-effort)."""
    db = SessionLocal()
    try:
        token = db.query(UserToken).filter(UserToken.id == session_id).first()
        if token:
            db.delete(token)
            db.commit()
        return True
    except Exception:
        return False
    finally:
        db.close()
