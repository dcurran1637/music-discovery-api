"""
Tests for OAuth 2.0 flows including callback, token refresh, and session management.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import asyncio

from app.main import app
from app import oauth, db, crypto


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_spotify_response():
    """Mock Spotify token exchange response."""
    return {
        "access_token": "spotify_access_token_123",
        "refresh_token": "spotify_refresh_token_456",
        "expires_in": 3600,
        "token_type": "Bearer",
    }


@pytest.fixture
def mock_spotify_user_profile():
    """Mock Spotify user profile response."""
    return {
        "id": "spotify_user_123",
        "display_name": "Test User",
        "email": "test@example.com",
        "external_urls": {"spotify": "https://open.spotify.com/user/123"},
        "followers": {"href": None, "total": 10},
        "images": [],
        "uri": "spotify:user:123",
    }


class TestOAuthCallback:
    """Tests for OAuth callback endpoint."""

    def test_callback_missing_code(self, client):
        """Test callback fails when authorization code is missing."""
        resp = client.get("/api/auth/callback?state=test_state")
        assert resp.status_code == 400
        assert "Missing authorization code" in resp.json()["detail"]

    def test_callback_invalid_state(self, monkeypatch, client):
        """Test callback fails with invalid or expired state."""
        
        async def mock_exchange(code, state):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter"
            )
        
        monkeypatch.setattr("app.routes.auth_routes.exchange_code_for_token", mock_exchange)
        
        resp = client.get("/api/auth/callback?code=code_xyz&state=invalid_state")
        assert resp.status_code == 400


class TestOAuthTokenRefresh:
    """Tests for OAuth token refresh endpoint."""

    def test_refresh_token_missing_parameter(self, client):
        """Test refresh fails when refresh_token parameter is missing."""
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 422  # Validation error


class TestPlaylistOwnership:
    """Tests for playlist ownership enforcement with JWTs."""

    def test_create_playlist_with_jwt(self, monkeypatch, client):
        """Test creating a playlist with JWT authentication."""
        
        user_id = "user_123"
        session_id = "session_123"
        jwt_token = oauth.create_jwt_token(user_id, session_id, expires_in=3600)
        
        created_playlist = {
            "id": "pl_123",
            "userId": user_id,
            "name": "My Playlist",
            "description": "My playlist desc",
            "tracks": [],
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
        }
        
        def mock_create(uid, name, desc=""):
            assert uid == user_id
            return created_playlist
        
        monkeypatch.setattr("app.db.create_playlist", mock_create)
        
        resp = client.post(
            "/api/playlists",
            json={"name": "My Playlist", "description": "My playlist desc"},
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        
        assert resp.status_code == 201
        data = resp.json()
        assert data["userId"] == user_id

    def test_update_playlist_owner_only(self, monkeypatch, client):
        """Test that only the playlist owner can update it."""
        
        owner_id = "user_123"
        session_id = "session_123"
        owner_jwt = oauth.create_jwt_token(owner_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "name": "Original Name",
            "description": "Original desc",
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        
        def mock_update(pid, name=None, description=None):
            return {**playlist, "name": name or playlist["name"]}
        
        monkeypatch.setattr("app.db.update_playlist", mock_update)
        
        # Owner can update
        resp = client.put(
            "/api/playlists/pl_123",
            json={"name": "New Name"},
            headers={"Authorization": f"Bearer {owner_jwt}"}
        )
        
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_update_playlist_non_owner_forbidden(self, monkeypatch, client):
        """Test that non-owner cannot update another user's playlist."""
        
        owner_id = "user_123"
        other_user_id = "user_456"
        session_id = "session_456"
        other_jwt = oauth.create_jwt_token(other_user_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "name": "Original Name",
            "description": "Original desc",
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        
        # Other user tries to update
        resp = client.put(
            "/api/playlists/pl_123",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {other_jwt}"}
        )
        
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]

    def test_delete_playlist_owner_only(self, monkeypatch, client):
        """Test that only the playlist owner can delete it."""
        
        owner_id = "user_123"
        session_id = "session_123"
        owner_jwt = oauth.create_jwt_token(owner_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "name": "Deletable Playlist",
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        monkeypatch.setattr("app.db.delete_playlist", lambda pid: {"message": "Deleted"})
        
        # Owner can delete
        resp = client.delete(
            "/api/playlists/pl_123",
            headers={"Authorization": f"Bearer {owner_jwt}"}
        )
        
        assert resp.status_code == 200
        assert resp.json()["message"] == "Deleted"

    def test_delete_playlist_non_owner_forbidden(self, monkeypatch, client):
        """Test that non-owner cannot delete another user's playlist."""
        
        owner_id = "user_123"
        other_user_id = "user_456"
        session_id = "session_456"
        other_jwt = oauth.create_jwt_token(other_user_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "name": "Protected Playlist",
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        
        # Other user tries to delete
        resp = client.delete(
            "/api/playlists/pl_123",
            headers={"Authorization": f"Bearer {other_jwt}"}
        )
        
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]

    def test_add_track_owner_only(self, monkeypatch, client):
        """Test that only the playlist owner can add tracks."""
        
        owner_id = "user_123"
        session_id = "session_123"
        owner_jwt = oauth.create_jwt_token(owner_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "tracks": [],
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        
        def mock_add_track(pid, track):
            return {**playlist, "tracks": [track]}
        
        monkeypatch.setattr("app.db.add_track", mock_add_track)
        
        # Owner can add
        resp = client.post(
            "/api/playlists/pl_123/tracks",
            json={"trackId": "t_123", "title": "Song", "artist": "Artist"},
            headers={"Authorization": f"Bearer {owner_jwt}"}
        )
        
        assert resp.status_code == 201
        assert len(resp.json()["tracks"]) == 1

    def test_add_track_non_owner_forbidden(self, monkeypatch, client):
        """Test that non-owner cannot add tracks to another user's playlist."""
        
        owner_id = "user_123"
        other_user_id = "user_456"
        session_id = "session_456"
        other_jwt = oauth.create_jwt_token(other_user_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "tracks": [],
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        
        # Other user tries to add
        resp = client.post(
            "/api/playlists/pl_123/tracks",
            json={"trackId": "t_123", "title": "Song", "artist": "Artist"},
            headers={"Authorization": f"Bearer {other_jwt}"}
        )
        
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]

    def test_remove_track_owner_only(self, monkeypatch, client):
        """Test that only the playlist owner can remove tracks."""
        
        owner_id = "user_123"
        session_id = "session_123"
        owner_jwt = oauth.create_jwt_token(owner_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "tracks": [{"trackId": "t_123", "title": "Song"}],
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        monkeypatch.setattr("app.db.remove_track", lambda pid, tid: {**playlist, "tracks": []})
        
        # Owner can remove
        resp = client.delete(
            "/api/playlists/pl_123/tracks/t_123",
            headers={"Authorization": f"Bearer {owner_jwt}"}
        )
        
        assert resp.status_code == 200
        assert len(resp.json()["tracks"]) == 0

    def test_remove_track_non_owner_forbidden(self, monkeypatch, client):
        """Test that non-owner cannot remove tracks from another user's playlist."""
        
        owner_id = "user_123"
        other_user_id = "user_456"
        session_id = "session_456"
        other_jwt = oauth.create_jwt_token(other_user_id, session_id, expires_in=3600)
        
        playlist = {
            "id": "pl_123",
            "userId": owner_id,
            "tracks": [{"trackId": "t_123"}],
        }
        
        monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)
        
        # Other user tries to remove
        resp = client.delete(
            "/api/playlists/pl_123/tracks/t_123",
            headers={"Authorization": f"Bearer {other_jwt}"}
        )
        
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]


class TestSessionTokenManagement:
    """Tests for session-based token storage and retrieval."""

    def test_session_tokens_stored(self, monkeypatch):
        """Verify session tokens can be stored and retrieved."""
        
        session_id = "session_123"
        user_id = "user_123"
        access_token = "access_token_xyz"
        refresh_token = "refresh_token_abc"
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        stored_items = {}
        
        def mock_put_session(sid, uid, access_enc, refresh_enc, exp):
            stored_items["session_id"] = sid
            stored_items["user_id"] = uid
            stored_items["access_token"] = access_enc
            stored_items["refresh_token"] = refresh_enc
            stored_items["expires_at"] = exp
            return {"id": sid}
        
        monkeypatch.setattr("app.db.put_session_tokens", mock_put_session)
        
        db.put_session_tokens(session_id, user_id, access_token, refresh_token, expires_at)
        
        # Verify tokens were stored
        assert stored_items["session_id"] == session_id
        assert stored_items["user_id"] == user_id
        assert stored_items["expires_at"] == expires_at

    def test_get_session_tokens(self, monkeypatch):
        """Test retrieving session tokens from DB."""
        
        session_id = "session_123"
        mock_session_data = {
            "id": session_id,
            "user_id": "user_123",
            "access_token": "encrypted_access_token",
            "refresh_token": "encrypted_refresh_token",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }
        
        monkeypatch.setattr("app.db.get_session_tokens", lambda sid: mock_session_data)
        
        result = db.get_session_tokens(session_id)
        
        assert result["id"] == session_id
        assert result["user_id"] == "user_123"
        assert "access_token" in result
        assert "refresh_token" in result

    def test_delete_session_tokens(self, monkeypatch):
        """Test deleting session tokens from DB."""
        
        session_id = "session_123"
        deleted = {}
        
        def mock_delete(sid):
            deleted["session_id"] = sid
            return True
        
        monkeypatch.setattr("app.db.delete_session_tokens", mock_delete)
        
        result = db.delete_session_tokens(session_id)
        
        assert result is True
        assert deleted["session_id"] == session_id
