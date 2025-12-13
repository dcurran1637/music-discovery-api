"""Database models and connection setup for PostgreSQL."""
import os
from sqlalchemy import create_engine, Column, String, Text, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL or "postgresql://localhost/music_discovery",
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Playlist(Base):
    __tablename__ = "playlists"
    
    id = Column(String, primary_key=True)
    userId = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    tracks = Column(JSON, default=list)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_playlists_userId', 'userId'),
    )


class SpotifyPlaylist(Base):
    """Stores playlists synced from Spotify."""
    __tablename__ = "spotify_playlists"
    
    id = Column(String, primary_key=True)
    userId = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    public = Column(String, default="true")
    collaborative = Column(String, default="false")
    snapshot_id = Column(String)
    owner_id = Column(String)
    owner_display_name = Column(String)
    track_count = Column(String, default="0")
    images = Column(JSON, default=list)
    external_url = Column(String)
    uri = Column(String)
    raw_data = Column(JSON, default=dict)
    synced_at = Column(DateTime, default=datetime.utcnow)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_spotify_playlists_userId', 'userId'),
        Index('idx_spotify_playlists_synced_at', 'synced_at'),
    )


class UserToken(Base):
    __tablename__ = "user_tokens"
    
    id = Column(String, primary_key=True)  # user_id or session_id
    user_id = Column(String, nullable=True, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(String, nullable=False)
    type = Column(String, default="user_tokens")  # "user_tokens" or "session_tokens"
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OAuthState(Base):
    """Stores OAuth state parameters for verification (replaces Redis when unavailable)."""
    __tablename__ = "oauth_states"
    
    state = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    __table_args__ = (
        Index('idx_oauth_states_expires_at', 'expires_at'),
    )


def get_db():
    """Provides a database session for API requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Creates all database tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
