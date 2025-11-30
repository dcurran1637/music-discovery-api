from app import db
from app.database import Playlist
from datetime import datetime


def test_get_playlists_for_user_genre_filter(monkeypatch):
    """Test genre filtering for playlists."""
    
    class MockPlaylist:
        def __init__(self, id, userId, tracks):
            self.id = id
            self.userId = userId
            self.name = "Test Playlist"
            self.description = "Test"
            self.tracks = tracks
            self.createdAt = datetime.utcnow()
            self.updatedAt = datetime.utcnow()
    
    playlists = [
        MockPlaylist("p1", "user_demo_1", [
            {"trackId": "t1", "genre": "Rock"}, 
            {"trackId": "t2", "genre": "Pop"}, 
            {"trackId": "t3", "genre": None}
        ]),
        MockPlaylist("p2", "user_demo_1", []),
    ]
    
    class MockQuery:
        def filter(self, *args):
            return self
        
        def all(self):
            return playlists
    
    class MockSession:
        def query(self, model):
            return MockQuery()
        
        def close(self):
            pass
    
    monkeypatch.setattr(db, "SessionLocal", lambda: MockSession())
    
    out = db.get_playlists_for_user("user_demo_1", genre_filter="rock")
    assert isinstance(out, list)
    # first playlist tracks should be filtered to only rock
    assert len(out[0]["tracks"]) == 1
    assert out[0]["tracks"][0]["trackId"] == "t1"
