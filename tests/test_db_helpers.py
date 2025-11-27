from app import db


def test_get_playlists_for_user_genre_filter(monkeypatch):
    items = [
        {"id": "p1", "tracks": [{"trackId": "t1", "genre": "Rock"}, {"trackId": "t2", "genre": "Pop"}, {"trackId": "t3", "genre": None}]},
        {"id": "p2", "tracks": []},
    ]

    class FakeTable:
        def query(self, **kwargs):
            return {"Items": items}

    monkeypatch.setattr(db, "table", FakeTable())

    out = db.get_playlists_for_user("user_demo_1", genre_filter="rock")
    assert isinstance(out, list)
    # first playlist tracks should be filtered to only rock
    assert len(out[0]["tracks"]) == 1
    assert out[0]["tracks"][0]["trackId"] == "t1"
