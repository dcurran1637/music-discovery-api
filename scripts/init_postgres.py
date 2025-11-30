#!/usr/bin/env python
"""
Initialize PostgreSQL database schema for the Music Discovery API.
Creates tables and indexes for playlists and user tokens.
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine, Base, Playlist, UserToken

def main():
    """Create all database tables."""
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/music_discovery")
    
    # Fix Render's postgres:// URL format
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    print(f"Initializing database schema...")
    print(f"Database: {database_url.split('@')[-1] if '@' in database_url else 'local'}")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("✓ Created table: playlists")
        print("  - Columns: id, userId, name, description, tracks, createdAt, updatedAt")
        print("  - Index: idx_playlists_userId")
        print("✓ Created table: user_tokens")
        print("  - Columns: id, user_id, access_token, refresh_token, expires_at, type, createdAt, updatedAt")
        print("\nDatabase initialization complete!")
        
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
