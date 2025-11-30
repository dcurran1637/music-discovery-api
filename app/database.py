"""
PostgreSQL database models and session management.
"""
import os
from sqlalchemy import create_engine, Column, String, Text, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Render uses postgres:// but SQLAlchemy 1.4+ requires postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
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


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
