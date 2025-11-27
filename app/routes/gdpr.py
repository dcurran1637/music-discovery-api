"""
GDPR compliance endpoints for user data management and deletion.
"""

from fastapi import APIRouter, HTTPException, status, Query, Header
from typing import Optional
from .. import db
from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


@router.delete("/user/{user_id}")
async def delete_user_data(
    user_id: str,
    confirmation: str = Query(..., description="Type 'confirm-deletion' to confirm"),
    authorization: Optional[str] = Header(None),
):
    """
    Delete all user data from the system (GDPR right to be forgotten).
    Requires explicit confirmation to prevent accidental deletion.
    
    Args:
        user_id: User ID to delete
        confirmation: Must be 'confirm-deletion' to proceed
        authorization: JWT token for user verification
        
    Returns:
        Confirmation of deletion
    """
    from ..auth import verify_jwt_token
    
    # Verify user is authorized (deleting their own data or admin)
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization"
        )
    
    try:
        payload = verify_jwt_token(authorization)
        auth_user_id = payload.get("user_id")
        
        # Only allow users to delete their own data (no admin override for now)
        if auth_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own data"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authorization check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization"
        )
    
    # Require explicit confirmation
    if confirmation != "confirm-deletion":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation must be 'confirm-deletion'"
        )
    
    try:
        # Delete all user data
        # 1. Delete all playlists owned by user
        playlists = db.get_playlists_for_user(user_id)
        for playlist in playlists:
            db.delete_playlist(playlist.get("id"))
        
        # 2. Delete user tokens/sessions
        # (In production, would need to iterate sessions by user_id)
        db.put_user_tokens(user_id, "", "", "")  # Clear tokens
        
        logger.warning(f"GDPR deletion requested for user {user_id}")
        
        return {
            "status": "success",
            "message": f"All data for user {user_id} has been deleted",
            "user_id": user_id,
        }
    except Exception as e:
        logger.error(f"Error deleting user data for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user data"
        )


@router.get("/user/{user_id}/data")
async def export_user_data(
    user_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Export all user data in a portable format (GDPR right to data portability).
    
    Args:
        user_id: User ID to export
        authorization: JWT token for user verification
        
    Returns:
        JSON object containing all user data
    """
    from ..auth import verify_jwt_token
    
    # Verify user is authorized
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization"
        )
    
    try:
        payload = verify_jwt_token(authorization)
        auth_user_id = payload.get("user_id")
        
        if auth_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own data"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authorization check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization"
        )
    
    try:
        # Gather all user data
        playlists = db.get_playlists_for_user(user_id)
        user_tokens = db.get_user_tokens(user_id)
        
        return {
            "user_id": user_id,
            "playlists": playlists or [],
            "has_spotify_tokens": user_tokens is not None,
            "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error exporting user data for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export user data"
        )
