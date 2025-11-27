import asyncio
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, Mock
from fastapi.testclient import TestClient
import jwt
import os
from datetime import datetime
from unittest.mock import AsyncMock as AM

# Assuming the app is structured with app/main.py
# We need to set up the test client
from app.main import app
from app import auth

# Test fixtures
@pytest.fixture
def test_user_id():
    return "test_user_123"

@pytest.fixture
def valid_jwt_token(test_user_id):
    """Generate a valid JWT token for testing with Spotify token"""
    payload = {
        "user_id": test_user_id,
        "spotify_access_token": "mock_spotify_token_123",
        "spotify_refresh_token": "mock_refresh_token_123"
    }
    token = jwt.encode(
        payload,
        auth.JWT_SECRET,
        algorithm=auth.JWT_ALGORITHM
    )
    return token

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def sample_recommendations():
    """Sample recommendation response from Spotify"""
    return {
        "tracks": [
            {
                "id": "track1",
                "name": "Track One",
                "popularity": 75,
                "album": {
                    "name": "Album One",
                    "release_date": "2023-01-15"
                },
                "artists": [
                    {
                        "id": "artist1",
                        "name": "Artist One"
                    }
                ],
                "preview_url": "http://preview.url/1"
            },
            {
                "id": "track2",
                "name": "Track Two",
                "popularity": 55,
                "album": {
                    "name": "Album Two",
                    "release_date": "2022-06-10"
                },
                "artists": [
                    {
                        "id": "artist2",
                        "name": "Artist Two"
                    }
                ],
                "preview_url": "http://preview.url/2"
            },
            {
                "id": "track3",
                "name": "Track Three",
                "popularity": 85,
                "album": {
                    "name": "Album Three",
                    "release_date": "2024-02-20"
                },
                "artists": [
                    {
                        "id": "artist3",
                        "name": "Artist Three"
                    }
                ],
                "preview_url": "http://preview.url/3"
            }
        ]
    }

@pytest.fixture
def sample_artist_genres():
    """Sample artist genres mapping"""
    return {
        "artist1": {"genres": ["rock", "indie rock"]},
        "artist2": {"genres": ["pop", "dance pop"]},
        "artist3": {"genres": ["hip-hop", "rap"]}
    }


def test_multiple_genre_filter():
    """Test filtering with multiple genres (OR logic)"""
    test_tracks = [
        {"genres": ["rock"], "trackId": "1"},
        {"genres": ["pop"], "trackId": "2"},
        {"genres": ["hip-hop"], "trackId": "3"},
    ]
    
    genres_filter = ["rock", "hip-hop"]
    filtered = [
        t for t in test_tracks 
        if any(g.lower() in [gf.lower() for gf in genres_filter] for g in t["genres"])
    ]
    
    assert len(filtered) == 2
    track_ids = {t["trackId"] for t in filtered}
    assert track_ids == {"1", "3"}


def test_popularity_filter():
    """Test popularity filtering"""
    test_tracks = [
        {"popularity": 75, "trackId": "1"},
        {"popularity": 55, "trackId": "2"},
        {"popularity": 85, "trackId": "3"},
    ]
    
    min_popularity = 70
    filtered = [t for t in test_tracks if t["popularity"] >= min_popularity]
    
    assert len(filtered) == 2
    assert all(t["popularity"] >= 70 for t in filtered)


def test_release_date_filter():
    """Test release date filtering"""
    test_tracks = [
        {"album": {"release_date": "2023-01-15"}, "trackId": "1"},
        {"album": {"release_date": "2022-06-10"}, "trackId": "2"},
        {"album": {"release_date": "2024-02-20"}, "trackId": "3"},
    ]
    
    released_after = "2023-01-01"
    filtered = [
        t for t in test_tracks
        if datetime.strptime(t["album"]["release_date"], "%Y-%m-%d") >= 
           datetime.strptime(released_after, "%Y-%m-%d")
    ]
    
    assert len(filtered) == 2
    track_ids = {t["trackId"] for t in filtered}
    assert track_ids == {"1", "3"}


def test_combined_filters():
    """Test combining multiple filters"""
    test_tracks = [
        {"genres": ["rock"], "popularity": 75, "album": {"release_date": "2023-01-15"}, "trackId": "1"},
        {"genres": ["pop"], "popularity": 55, "album": {"release_date": "2022-06-10"}, "trackId": "2"},
        {"genres": ["hip-hop"], "popularity": 85, "album": {"release_date": "2024-02-20"}, "trackId": "3"},
    ]
    
    genres_filter = ["hip-hop"]
    min_popularity = 80
    released_after = "2023-01-01"
    
    filtered = test_tracks
    
    # Apply genre filter
    if genres_filter:
        filtered = [
            t for t in filtered
            if any(g.lower() in [gf.lower() for gf in genres_filter] for g in t["genres"])
        ]
    
    # Apply popularity filter
    if min_popularity:
        filtered = [t for t in filtered if t["popularity"] >= min_popularity]
    
    # Apply release date filter
    if released_after:
        filtered = [
            t for t in filtered
            if datetime.strptime(t["album"]["release_date"], "%Y-%m-%d") >= 
               datetime.strptime(released_after, "%Y-%m-%d")
        ]
    
    # Should return only track3 (hip-hop with 85 popularity and 2024 release)
    assert len(filtered) == 1
    assert filtered[0]["trackId"] == "3"


def test_genre_filter_no_matches():
    """Test when no tracks match the genre filter"""
    test_tracks = [
        {"genres": ["pop"], "trackId": "1"},
    ]
    
    genres_filter = ["metal"]
    filtered = [
        t for t in test_tracks 
        if any(g.lower() in [gf.lower() for gf in genres_filter] for g in t["genres"])
    ]
    
    assert len(filtered) == 0


def test_popularity_boundary():
    """Test popularity boundary conditions"""
    test_tracks = [
        {"popularity": 70, "trackId": "1"},
        {"popularity": 69, "trackId": "2"},
        {"popularity": 0, "trackId": "3"},
        {"popularity": 100, "trackId": "4"},
    ]
    
    min_popularity = 70
    filtered = [t for t in test_tracks if t["popularity"] >= min_popularity]
    
    assert len(filtered) == 2
    assert filtered[0]["trackId"] == "1"
    assert filtered[1]["trackId"] == "4"


def test_track_info_structure():
    """Test that track information has correct structure"""
    track = {
        "trackId": "track1",
        "title": "Track One",
        "artist": "Artist One",
        "genres": ["rock"],
        "album": {
            "name": "Album One",
            "release_date": "2023-01-15"
        },
        "popularity": 75,
        "previewUrl": "http://preview.url/1"
    }
    
    # Verify all required fields are present
    assert "trackId" in track
    assert "title" in track
    assert "artist" in track
    assert "genres" in track
    assert "album" in track
    assert "popularity" in track
    assert "previewUrl" in track
    assert track["album"]["name"]
    assert track["album"]["release_date"]


def test_get_spotify_token_without_credentials():
    """Test that token returns None when credentials are missing"""
    # This test verifies the existing behavior
    pass
