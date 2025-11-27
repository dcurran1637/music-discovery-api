import asyncio
import os

from app import spotify_client


def test_get_spotify_token_none_when_no_creds(monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)

    token = asyncio.run(spotify_client.get_spotify_token())
    assert token is None


def test_get_track_none_when_no_token(monkeypatch):
    # ensure token won't be retrieved
    async def _none_token():
        return None

    monkeypatch.setattr(spotify_client, "get_spotify_token", _none_token)
    track = asyncio.run(spotify_client.get_track("someid"))
    assert track is None
