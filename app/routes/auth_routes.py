"""
OAuth 2.0 authentication routes for Spotify.
"""

from fastapi import APIRouter, Query, HTTPException, status, Depends, Header, BackgroundTasks
from fastapi.responses import RedirectResponse
from typing import Optional
import uuid
from datetime import datetime, timedelta
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
from ..spotify_client import get_user_playlists
from ..crypto import encrypt, decrypt
from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


async def sync_playlists_background(user_id: str, spotify_token: str):
    """Fetch all playlists from Spotify and save them to the database."""
    try:
        logger.info(f"Starting background playlist sync for user {user_id}")
        
        all_playlists = []
        limit = 50
        offset = 0
        
        while True:
            response = await get_user_playlists(spotify_token, limit=limit, offset=offset)
            items = response.get("items", [])
            all_playlists.extend(items)
            
            total = response.get("total", 0)
            if offset + limit >= total:
                break
            offset += limit
        
        stats = db.sync_spotify_playlists(user_id, all_playlists)
        logger.info(f"Background playlist sync completed for user {user_id}: {stats}")
    except Exception as e:
        logger.error(f"Background playlist sync failed for user {user_id}: {e}")


@router.get("/login")
async def login(
    user_id: str = Query(..., description="User ID"),
    json: bool = Query(False, description="Return JSON instead of redirect")
):
    """Send user to Spotify login page or return the login URL as JSON."""
    try:
        auth_url, state = await generate_auth_url(user_id)
        
        if json:
            return {
                "authorization_url": auth_url,
                "state": state,
                "instructions": "Open this URL in your browser to authenticate"
            }
        
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate login")


@router.get("/callback")
async def callback(
    background_tasks: BackgroundTasks,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None)
):
    """Handle the return from Spotify after user logs in."""
    
    logger.info(f"Callback received - code: {'present' if code else 'missing'}, state: {'present' if state else 'missing'}, error: {error}")
    
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Spotify authorization failed: {error}"
        )
    
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code. Please complete the OAuth flow by visiting /api/auth/login?user_id=YOUR_USER_ID&json=true"
        )
    
    if not state:
        logger.warning("Callback missing state parameter - this may indicate a redirect URI mismatch in Spotify Dashboard")
        from ..oauth import SPOTIFY_REDIRECT_URI
        raise HTTPException(
            status_code=400,
            detail=f"Missing state parameter. This usually means your Spotify App's redirect URI doesn't match. Please verify in Spotify Developer Dashboard that the redirect URI is set to: {SPOTIFY_REDIRECT_URI}"
        )
    
    try:
        token_response = await exchange_code_for_token(code, state)
        user_id = token_response["user_id"]

        enc_access = encrypt(token_response.get("spotify_access_token") or "")
        enc_refresh = encrypt(token_response.get("spotify_refresh_token") or "")
        expires_in = token_response.get("spotify_token_expires_in") or 3600
        expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

        session_id = uuid.uuid4().hex
        db.put_session_tokens(session_id, user_id, enc_access, enc_refresh, expires_at)

        spotify_access_token = token_response.get("spotify_access_token")

        background_tasks.add_task(sync_playlists_background, user_id, spotify_access_token)
        
        logger.info(f"Successful OAuth login for user {user_id}, playlist sync queued")

        return {
            "access_token": spotify_access_token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "user_id": user_id,
            "session_id": session_id,
            "refresh_token": token_response.get("spotify_refresh_token"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OAuth callback error: {str(e)}")


@router.post("/refresh")
async def refresh_token(refresh_token: str = Query(...)):
    """Get a new access token when the old one expires."""
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
        raise HTTPException(status_code=500, detail=f"Token refresh error: {str(e)}")


@router.get("/me")
async def get_current_user(authorization: str = Header(..., description="Bearer JWT token")):
    """Get current authenticated user's Spotify profile"""
    try:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        token = authorization.split(" ", 1)[1]

        payload = verify_token(token)
        user_id = payload.get("user_id")
        session_id = payload.get("session_id")

        # Prefer embedded token in JWT (stateless fallback)
        spotify_token = payload.get("spotify_access_token")

        # Prefer session-scoped tokens
        if not spotify_token and session_id:
            session = db.get_session_tokens(session_id)
            if session:
                try:
                    spotify_token = decrypt(session.get("access_token", ""))
                except Exception:
                    spotify_token = None
                expires_at = session.get("expires_at")
                if not spotify_token or (expires_at and datetime.fromisoformat(expires_at) <= datetime.utcnow()):
                    refresh_enc = session.get("refresh_token")
                    refresh_token_val = decrypt(refresh_enc) if refresh_enc else None
                    if refresh_token_val:
                        token_data = await refresh_spotify_token(refresh_token_val)
                        enc_access = encrypt(token_data.get("access_token"))
                        enc_refresh = encrypt(token_data.get("refresh_token") or refresh_token_val)
                        new_expires_at = (datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat()
                        db.put_session_tokens(session_id, user_id, enc_access, enc_refresh, new_expires_at)
                        spotify_token = token_data.get("access_token")

        # Fallback to user-scoped legacy tokens
        if not spotify_token:
            user_tokens = db.get_user_tokens(user_id)
            if user_tokens:
                try:
                    spotify_token = decrypt(user_tokens.get("access_token", ""))
                except Exception:
                    spotify_token = None
                expires_at = user_tokens.get("expires_at")
                if not spotify_token or (expires_at and datetime.fromisoformat(expires_at) <= datetime.utcnow()):
                    refresh_enc = user_tokens.get("refresh_token")
                    refresh_token_val = decrypt(refresh_enc) if refresh_enc else None
                    if refresh_token_val:
                        token_data = await refresh_spotify_token(refresh_token_val)
                        enc_access = encrypt(token_data.get("access_token"))
                        enc_refresh = encrypt(token_data.get("refresh_token") or refresh_token_val)
                        new_expires_at = (datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat()
                        db.put_user_tokens(user_id, enc_access, enc_refresh, new_expires_at)
                        spotify_token = token_data.get("access_token")

        if not spotify_token:
            raise HTTPException(status_code=401, detail="Spotify token unavailable. Please login.")

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
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting user profile: {str(e)}")


@router.get("/logout")
async def logout(user_id: str = Query(...)):
    """Logout user (client-side should discard the JWT token)"""
    return {
        "message": f"User {user_id} logged out. Please discard the token.",
        "status": "success"
    }
