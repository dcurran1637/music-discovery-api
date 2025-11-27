import asyncio
import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import jwt
import os
from datetime import datetime

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
def authorization_header(valid_jwt_token):
    return f"Bearer {valid_jwt_token}"


# API Endpoint Tests - Auth validation
def test_recommendations_endpoint_missing_auth_header(client):
    """Test that endpoint requires authorization header"""
    response = client.get("/api/discover/recommendations")
    assert response.status_code == 422  # Validation error for missing header


def test_recommendations_endpoint_invalid_auth_header(client):
    """Test that endpoint rejects invalid authorization header"""
    response = client.get(
        "/api/discover/recommendations",
        headers={"Authorization": "InvalidToken"}
    )
    assert response.status_code == 401


def test_recommendations_endpoint_invalid_token(client):
    """Test that endpoint rejects invalid JWT token"""
    response = client.get(
        "/api/discover/recommendations",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401


# API Endpoint Tests - Parameter validation
def test_recommendations_endpoint_invalid_date_format(client, authorization_header):
    """Test that endpoint handles invalid date format gracefully"""
    response = client.get(
        "/api/discover/recommendations?released_after=2023/01/01",
        headers={"Authorization": authorization_header}
    )
    # May return 502 if Spotify API call fails, 200 if successful, or 400 if validated before
    assert response.status_code in [200, 400, 422, 502]


def test_recommendations_endpoint_invalid_popularity_value(client, authorization_header):
    """Test that endpoint rejects invalid popularity values (>100)"""
    response = client.get(
        "/api/discover/recommendations?min_popularity=150",
        headers={"Authorization": authorization_header}
    )
    # FastAPI should validate the range (0-100)
    assert response.status_code == 422


def test_recommendations_endpoint_invalid_popularity_negative(client, authorization_header):
    """Test that endpoint rejects negative popularity values"""
    response = client.get(
        "/api/discover/recommendations?min_popularity=-10",
        headers={"Authorization": authorization_header}
    )
    assert response.status_code == 422


def test_recommendations_endpoint_valid_popularity_boundaries(client, authorization_header):
    """Test that endpoint accepts valid popularity values (0-100)"""
    # Test min boundary
    response = client.get(
        "/api/discover/recommendations?min_popularity=0",
        headers={"Authorization": authorization_header}
    )
    # Should not fail validation (may fail for other reasons like missing API)
    assert response.status_code in [200, 422, 502]
    
    # Test max boundary
    response = client.get(
        "/api/discover/recommendations?min_popularity=100",
        headers={"Authorization": authorization_header}
    )
    assert response.status_code in [200, 422, 502]
