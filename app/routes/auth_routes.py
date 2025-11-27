"""
OAuth 2.0 authentication routes for Spotify.
"""

from fastapi import APIRouter, Query, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from typing import Optional
import json

from ..oauth import (
    generate_auth_url,
    exchange_code_for_token,
    create_jwt_token,
    verify_jwt_token as verify_token,
    get_user_profile,
    refresh_spotify_token,
)
from .. import db
from ..crypto import encrypt, decrypt
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/login")
async def login(user_id: str = Query(..., description="User ID")):
    """
    Initiate Spotify OAuth login flow.
    Redirects user to Spotify authorization page.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        Redirect to Spotify authorization URL
    """
    try:
        auth_url, state = await generate_auth_url(user_id)
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        return {"error": str(e.detail)}


@router.get("/callback")
async def callback(code: Optional[str] = Query(None), state: str = Query(...)):
    """
    Handle Spotify OAuth callback.
    Exchanges authorization code for access token and creates JWT.
    
    Args:
        code: Authorization code from Spotify
        state: State parameter for verification
        
    Returns:
        JWT token for subsequent API requests
    """
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code"
        )
    
    try:
        # Exchange code for Spotify token
        token_response = await exchange_code_for_token(code, state)
        
        # Persist encrypted tokens server-side and return a JWT session token
        user_id = token_response["user_id"]

        # Encrypt tokens before storing
        enc_access = encrypt(token_response.get("spotify_access_token") or "")
        enc_refresh = encrypt(token_response.get("spotify_refresh_token") or "")
        expires_in = token_response.get("spotify_token_expires_in") or 3600
        expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

        # Store tokens in users table
        db.put_user_tokens(user_id, enc_access, enc_refresh, expires_at)

        # Create a JWT session token (no raw refresh token embedded)
        jwt_token = create_jwt_token(user_id=user_id, expires_in=expires_in)

        # Return token in a secure format
        return {
            "access_token": jwt_token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "user_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback error: {str(e)}"
        )


@router.post("/refresh")
async def refresh_token(refresh_token: str = Query(...)):
    """
    Refresh expired Spotify access token.
    
    Args:
        refresh_token: Spotify refresh token
        
    Returns:
        New access token
    """
    try:
        token_data = await refresh_spotify_token(refresh_token)
        return {
            "access_token": token_data["access_token"],
            "token_type": token_data.get("token_type", "Bearer"),
            "expires_in": token_data["expires_in"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh error: {str(e)}"
        )


@router.get("/me")
async def get_current_user(authorization: str = Query(..., description="Bearer token")):
    """
    Get current authenticated user's Spotify profile.
    
    Args:
        authorization: JWT token in format "Bearer <token>"
        
    Returns:
        User profile from Spotify
    """
    try:
        # Parse bearer token
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format"
            )
        
        token = authorization.split(" ")[1]
        
        # Verify JWT and get user id
        payload = verify_token(token)
        user_id = payload.get("user_id")

        # Fetch user's stored Spotify tokens
        user_tokens = db.get_user_tokens(user_id)
        if not user_tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Spotify tokens not found. Please login with Spotify."
            )

        try:
            spotify_token = decrypt(user_tokens.get("access_token", ""))
        except Exception:
            spotify_token = None

        expires_at = user_tokens.get("expires_at")
        if not spotify_token or (expires_at and datetime.fromisoformat(expires_at) <= datetime.utcnow()):
            try:
                refresh_enc = user_tokens.get("refresh_token")
                refresh_token = decrypt(refresh_enc) if refresh_enc else None
                if refresh_token:
                    token_data = await refresh_spotify_token(refresh_token)
                    enc_access = encrypt(token_data.get("access_token"))
                    enc_refresh = encrypt(token_data.get("refresh_token") or refresh_token)
                    new_expires_at = (datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat()
                    db.put_user_tokens(user_id, enc_access, enc_refresh, new_expires_at)
                    spotify_token = token_data.get("access_token")
            except Exception:
                pass

        # Get user profile from Spotify
        profile = await get_user_profile(spotify_token)
        
        return {
            "id": profile.get("id"),
            "display_name": profile.get("display_name"),
            "email": profile.get("email"),
            "external_urls": profile.get("external_urls"),
            "followers": profile.get("followers"),
            "images": profile.get("images"),
            "uri": profile.get("uri"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user profile: {str(e)}"
        )


@router.get("/logout")
async def logout(user_id: str = Query(...)):
    """
    Logout user (client-side should discard the token).
    
    Args:
        user_id: User ID
        
    Returns:
        Logout confirmation
    """
    return {
        "message": f"User {user_id} logged out. Please discard the token.",
        "status": "success"
    }
