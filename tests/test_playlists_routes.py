from fastapi.testclient import TestClient

from app.main import app


def test_create_playlist_success(monkeypatch):
    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")

    created = {"id": "pl_1", "userId": "user_demo_1", "name": "My List", "description": "desc", "tracks": []}

    def fake_create(user_id, name, description=""):
        assert user_id == "user_demo_1"
        assert name == "My List"
        assert description == "desc"
        return created

    monkeypatch.setattr("app.db.create_playlist", fake_create)

    client = TestClient(app)
    resp = client.post(
        "/api/playlists",
        json={"name": "My List", "description": "desc"},
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert resp.status_code == 201
    assert resp.json() == created


def test_create_playlist_unauthorized_missing_key(monkeypatch):
    client = TestClient(app)
    resp = client.post("/api/playlists", json={"name": "NoKey"})
    assert resp.status_code == 401


def test_list_playlists_returns_items(monkeypatch):
    sample = [{"id": "pl_1", "userId": "user_demo_1", "name": "S", "tracks": []}]

    def fake_list(user_id, genre_filter=None):
        assert user_id == "user_demo_1"
        assert genre_filter is None
        return sample

    monkeypatch.setattr("app.db.get_playlists_for_user", fake_list)

    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")
    client = TestClient(app)
    resp = client.get("/api/playlists", headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"})
    assert resp.status_code == 200
    assert resp.json() == sample


def test_get_playlist_not_found(monkeypatch):
    monkeypatch.setattr("app.db.get_playlist", lambda pid: None)
    client = TestClient(app)
    resp = client.get("/api/playlists/someid")
    assert resp.status_code == 404


def test_update_playlist_success(monkeypatch):
    existing = {"id": "pl_1", "userId": "user_demo_1", "name": "Old", "description": "old"}
    updated = {"id": "pl_1", "name": "New", "description": "new"}

    monkeypatch.setattr("app.db.get_playlist", lambda pid: existing)
    def fake_update(pid, name=None, description=None):
        assert pid == "pl_1"
        return updated

    monkeypatch.setattr("app.db.update_playlist", fake_update)
    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")
    client = TestClient(app)
    resp = client.put(
        "/api/playlists/pl_1",
        json={"name": "New", "description": "new"},
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert resp.status_code == 200
    assert resp.json() == updated


def test_delete_playlist_success(monkeypatch):
    monkeypatch.setattr("app.db.get_playlist", lambda pid: {"id": pid, "userId": "user_demo_1"})
    monkeypatch.setattr("app.db.delete_playlist", lambda pid: {"message": "ok"})
    monkeypatch.setenv("WRITE_API_KEY", "demo_write_key_123")
    client = TestClient(app)
    resp = client.delete(
        "/api/playlists/pl_1",
        headers={"X-API-KEY": "demo_write_key_123", "X-USER-ID": "user_demo_1"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "ok"}


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
