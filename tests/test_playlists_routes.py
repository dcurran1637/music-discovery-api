from fastapi.testclient import TestClient

from app.main import app


def test_create_playlist_success(monkeypatch):
    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")

    created = {"id": "pl_1", "userId": "user_demo_1", "name": "My List", "description": "desc", "tracks": []}

    async def fake_create_spotify(spotify_token, user_id, name, description=None, public=None, collaborative=None):
        assert user_id == "user_demo_1"
        assert name == "My List"
        assert description == "desc"
        return created

    monkeypatch.setattr("app.routes.playlists.create_spotify_playlist", fake_create_spotify)
    monkeypatch.setattr("app.db.sync_spotify_playlists", lambda uid, playlists: None)

    client = TestClient(app)
    resp = client.post(
        "/api/playlists",
        json={"name": "My List", "description": "desc"},
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert resp.status_code == 401  # No spotify token with API key auth


def test_create_playlist_unauthorized_missing_key(monkeypatch):
    client = TestClient(app)
    resp = client.post("/api/playlists", json={"name": "NoKey"})
    assert resp.status_code == 401


def test_list_playlists_returns_items(monkeypatch):
    sample = [{"id": "pl_1", "userId": "user_demo_1", "name": "S", "tracks": []}]

    def fake_list(user_id):
        assert user_id == "user_demo_1"
        return sample

    monkeypatch.setattr("app.db.get_synced_spotify_playlists", fake_list)

    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")
    client = TestClient(app)
    resp = client.get("/api/playlists?source=db", headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"})
    assert resp.status_code == 200
    assert resp.json()["items"] == sample


def test_get_playlist_not_found(monkeypatch):
    monkeypatch.setattr("app.db.get_playlist", lambda pid: None)
    client = TestClient(app)
    resp = client.get("/api/playlists/someid")
    assert resp.status_code == 404


def test_update_playlist_success(monkeypatch):
    existing = {"id": "pl_1", "userId": "user_demo_1", "name": "Old", "description": "old"}
    updated = {"id": "pl_1", "name": "New", "description": "new"}

    async def fake_update(spotify_token, playlist_id, name=None, description=None, public=None, collaborative=None):
        assert playlist_id == "pl_1"
        return True

    async def fake_get_spotify_playlist(spotify_token, playlist_id):
        return updated

    monkeypatch.setattr("app.routes.playlists.update_spotify_playlist", fake_update)
    monkeypatch.setattr("app.routes.playlists.get_spotify_playlist", fake_get_spotify_playlist)
    monkeypatch.setattr("app.db.sync_spotify_playlists", lambda uid, playlists: None)
    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")
    client = TestClient(app)
    resp = client.put(
        "/api/playlists/pl_1",
        json={"name": "New", "description": "new"},
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert resp.status_code == 401  # No spotify token with API key auth


def test_delete_playlist_success(monkeypatch):
    async def fake_delete(spotify_token, playlist_id):
        return True

    monkeypatch.setattr("app.routes.playlists.delete_spotify_playlist", fake_delete)
    monkeypatch.setattr("app.db.delete_synced_spotify_playlist", lambda uid, pid: None)
    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")
    client = TestClient(app)
    resp = client.delete(
        "/api/playlists/pl_1",
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert resp.status_code == 401  # No spotify token with API key auth


def test_add_remove_tracks(monkeypatch):
    playlist = {"id": "pl_1", "userId": "user_demo_1", "tracks": []}

    monkeypatch.setattr("app.db.get_playlist", lambda pid: playlist)

    def fake_add(pid, track):
        assert pid == "pl_1"
        return {**playlist, "tracks": [track]}

    monkeypatch.setattr("app.db.add_track", fake_add)
    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")

    client = TestClient(app)
    track_payload = {"trackId": "t1", "title": "Song", "artist": "A"}
    add_resp = client.post(
        "/api/playlists/pl_1/tracks",
        json=track_payload,
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert add_resp.status_code == 201

    # remove
    monkeypatch.setattr("app.db.remove_track", lambda pid, tid: {"id": pid, "tracks": []})
    del_resp = client.delete(
        "/api/playlists/pl_1/tracks/t1",
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert del_resp.status_code == 200
