import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from .database import SessionLocal, Playlist, UserToken, SpotifyPlaylist


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


# -----------------------------
# Spotify Playlist Sync Functions
# -----------------------------

def sync_spotify_playlists(user_id: str, playlists_data: List[Dict]) -> Dict:
    """
    Sync Spotify playlists to the database.
    
    Args:
        user_id: Spotify user ID
        playlists_data: List of playlist objects from Spotify API
    
    Returns:
        Dictionary with sync statistics
    """
    db = SessionLocal()
    try:
        stats = {"created": 0, "updated": 0, "total": 0}
        now = datetime.utcnow()
        
        for playlist_data in playlists_data:
            playlist_id = playlist_data.get("id")
            if not playlist_id:
                continue
            
            # Check if playlist already exists
            existing = db.query(SpotifyPlaylist).filter(
                SpotifyPlaylist.id == playlist_id
            ).first()
            
            # Extract data
            owner = playlist_data.get("owner", {})
            tracks_info = playlist_data.get("tracks", {})
            
            playlist_obj = {
                "id": playlist_id,
                "userId": user_id,
                "name": playlist_data.get("name", ""),
                "description": playlist_data.get("description") or "",
                "public": str(playlist_data.get("public", True)).lower(),
                "collaborative": str(playlist_data.get("collaborative", False)).lower(),
                "snapshot_id": playlist_data.get("snapshot_id"),
                "owner_id": owner.get("id"),
                "owner_display_name": owner.get("display_name"),
                "track_count": str(tracks_info.get("total", 0)),
                "images": playlist_data.get("images", []),
                "external_url": playlist_data.get("external_urls", {}).get("spotify"),
                "uri": playlist_data.get("uri"),
                "raw_data": playlist_data,
                "synced_at": now,
                "updatedAt": now,
            }
            
            if existing:
                # Update existing playlist
                for key, value in playlist_obj.items():
                    if key != "createdAt":
                        setattr(existing, key, value)
                stats["updated"] += 1
            else:
                # Create new playlist record
                playlist_obj["createdAt"] = now
                new_playlist = SpotifyPlaylist(**playlist_obj)
                db.add(new_playlist)
                stats["created"] += 1
            
            stats["total"] += 1
        
        db.commit()
        return stats
    finally:
        db.close()


def get_synced_spotify_playlists(user_id: str) -> List[Dict]:
    """Get all synced Spotify playlists for a user."""
    db = SessionLocal()
    try:
        playlists = db.query(SpotifyPlaylist).filter(
            SpotifyPlaylist.userId == user_id
        ).order_by(SpotifyPlaylist.synced_at.desc()).all()
        
        items = []
        for p in playlists:
            items.append({
                "id": p.id,
                "userId": p.userId,
                "name": p.name,
                "description": p.description,
                "public": p.public == "true",
                "collaborative": p.collaborative == "true",
                "snapshot_id": p.snapshot_id,
                "owner": {
                    "id": p.owner_id,
                    "display_name": p.owner_display_name,
                },
                "tracks": {
                    "total": int(p.track_count) if p.track_count else 0
                },
                "images": p.images or [],
                "external_urls": {"spotify": p.external_url} if p.external_url else {},
                "uri": p.uri,
                "synced_at": p.synced_at.isoformat() if p.synced_at else None,
                "createdAt": p.createdAt.isoformat(),
                "updatedAt": p.updatedAt.isoformat(),
            })
        
        return items
    finally:
        db.close()


def get_synced_spotify_playlist(playlist_id: str) -> Optional[Dict]:
    """Get a single synced Spotify playlist by ID."""
    db = SessionLocal()
    try:
        playlist = db.query(SpotifyPlaylist).filter(
            SpotifyPlaylist.id == playlist_id
        ).first()
        
        if not playlist:
            return None
        
        return {
            "id": playlist.id,
            "userId": playlist.userId,
            "name": playlist.name,
            "description": playlist.description,
            "public": playlist.public == "true",
            "collaborative": playlist.collaborative == "true",
            "snapshot_id": playlist.snapshot_id,
            "owner": {
                "id": playlist.owner_id,
                "display_name": playlist.owner_display_name,
            },
            "tracks": {
                "total": int(playlist.track_count) if playlist.track_count else 0
            },
            "images": playlist.images or [],
            "external_urls": {"spotify": playlist.external_url} if playlist.external_url else {},
            "uri": playlist.uri,
            "raw_data": playlist.raw_data,
            "synced_at": playlist.synced_at.isoformat() if playlist.synced_at else None,
            "createdAt": playlist.createdAt.isoformat(),
            "updatedAt": playlist.updatedAt.isoformat(),
        }
    finally:
        db.close()


def delete_synced_spotify_playlist(playlist_id: str) -> bool:
    """Delete a synced Spotify playlist from the database."""
    db = SessionLocal()
    try:
        playlist = db.query(SpotifyPlaylist).filter(
            SpotifyPlaylist.id == playlist_id
        ).first()
        
        if playlist:
            db.delete(playlist)
            db.commit()
            return True
        return False
    except Exception:
        return False
    finally:
        db.close()
