# Database Setup Guide

## PostgreSQL for Render Deployment

This application uses **PostgreSQL** as the database, which is fully compatible with Render's managed PostgreSQL service.

---

## Local Development Setup

### 1. Using Docker (Recommended)

```bash
# Start PostgreSQL container
docker run -d --name postgres-music-api \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=music_discovery \
  -p 5432:5432 \
  postgres:15-alpine

# Initialize database tables
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/music_discovery" \
  python scripts/init_postgres.py
```

### 2. Using Local PostgreSQL

```bash
# Install PostgreSQL (varies by OS)
# Ubuntu/Debian: sudo apt-get install postgresql
# macOS: brew install postgresql

# Create database
createdb music_discovery

# Initialize tables
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/music_discovery" \
  python scripts/init_postgres.py
```

---

## Render Deployment Setup

### 1. Create PostgreSQL Database on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name**: `music-discovery-db` (or your preferred name)
   - **Database**: `music_discovery`
   - **User**: Auto-generated
   - **Region**: Choose closest to your web service
   - **PostgreSQL Version**: 15 or later
   - **Plan**: Free tier or paid as needed

4. Click **"Create Database"**

### 2. Get Database Connection String

After creation, Render provides:
- **Internal Database URL**: Use this for services in same region (faster)
- **External Database URL**: Use for external connections

Format: `postgresql://user:password@host:port/database`

Example:
```
postgresql://music_db_user:AbCdEf123456@dpg-xxxxx.oregon-postgres.render.com/music_discovery
```

### 3. Configure Web Service Environment Variables

In your Render web service settings:

1. Go to **Environment** tab
2. Add environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Your PostgreSQL Internal Database URL (from step 2)

3. **Important**: Render auto-injects `DATABASE_URL` if you link the database, so you may not need to add it manually.

### 4. Initialize Database Tables

**Option A: Manual (via Render Shell)**
```bash
# In Render web service shell
python scripts/init_postgres.py
```

**Option B: Automatic (via deploy hook)**

Add to your `render.yaml`:
```yaml
services:
  - type: web
    name: music-discovery-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python scripts/init_postgres.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

**Option C: One-time job**

Create a one-time job in Render:
```bash
python scripts/init_postgres.py
```

---

## Database Schema

### Tables Created

#### `playlists`
| Column | Type | Description |
|--------|------|-------------|
| id | String (UUID) | Primary key |
| userId | String | Spotify user ID (indexed) |
| name | String | Playlist name |
| description | Text | Playlist description |
| tracks | JSON | Array of track objects |
| createdAt | DateTime | Creation timestamp |
| updatedAt | DateTime | Last update timestamp |

**Indexes:**
- `idx_playlists_userId` on `userId` column

#### `user_tokens`
| Column | Type | Description |
|--------|------|-------------|
| id | String | Primary key (user_id or session_id) |
| user_id | String | Spotify user ID (indexed) |
| access_token | Text | Encrypted OAuth access token |
| refresh_token | Text | Encrypted OAuth refresh token |
| expires_at | String | Token expiration time |
| type | String | Token type: "user_tokens" or "session_tokens" |

---

## Environment Variables Summary

### Required for Database

```bash
# PostgreSQL Connection (auto-provided by Render)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# For local development
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/music_discovery
```

### Complete .env Example

```bash
# Spotify API
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="https://your-app.onrender.com/api/auth/callback"

# JWT & Security
export JWT_SECRET="your_random_jwt_secret"
export WRITE_API_KEY="your_api_key"
export CRYPTO_KEY="your_encryption_key"

# Database (auto-injected by Render)
export DATABASE_URL="postgresql://user:pass@host:port/music_discovery"

# Redis (optional)
export REDIS_URL="redis://localhost:6379"
```

---

## Testing Database Connection

### Local Test
```bash
# Python test
python -c "from app.database import SessionLocal; db = SessionLocal(); print('✓ Connected!'); db.close()"

# SQL test (requires psql)
psql postgresql://postgres:postgres@localhost:5432/music_discovery -c "SELECT 1;"
```

### Render Test
```bash
# Via Render shell
python -c "from app.database import SessionLocal; db = SessionLocal(); print('✓ Connected!'); db.close()"
```

---

## Troubleshooting

### Error: "Storage unavailable. Configure DynamoDB or endpoint."

**Cause**: Database not initialized or `DATABASE_URL` not set

**Solution**:
1. Verify `DATABASE_URL` is set: `echo $DATABASE_URL`
2. Run initialization: `python scripts/init_postgres.py`
3. Restart application

### Error: "connection refused"

**Cause**: PostgreSQL not running

**Solution**:
- **Local**: Start Docker container or PostgreSQL service
- **Render**: Check database status in dashboard

### Error: "no password supplied"

**Cause**: `DATABASE_URL` missing credentials

**Solution**:
```bash
# Correct format
DATABASE_URL=postgresql://username:password@host:port/database

# NOT this
DATABASE_URL=postgresql://host:port/database
```

### Error: "postgres:// not supported"

**Cause**: Render uses `postgres://` but SQLAlchemy requires `postgresql://`

**Solution**: Already handled in `database.py`:
```python
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
```

---

## Migrations (Future)

For production, consider using Alembic for database migrations:

```bash
# Install
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

---

## Backup & Restore (Render)

### Automatic Backups
Render automatically backs up PostgreSQL databases on paid plans.

### Manual Backup
```bash
# Via pg_dump
pg_dump $DATABASE_URL > backup.sql

# Restore
psql $DATABASE_URL < backup.sql
```

---

## Performance Tips

1. **Connection Pooling**: Already configured in `database.py`
   ```python
   pool_pre_ping=True
   pool_recycle=300
   ```

2. **Indexes**: Create indexes for frequently queried columns
   ```sql
   CREATE INDEX idx_name ON playlists(userId);
   ```

3. **Query Optimization**: Use `.first()` instead of `.all()[0]`

4. **Connection Limits**: Render free tier has connection limits, manage sessions carefully

---

## Summary

✅ **PostgreSQL** is the recommended database for Render
✅ Fully compatible with Render's managed PostgreSQL service
✅ Easy to set up locally with Docker
✅ Automatic URL format handling for Render
✅ Database tables initialized via `scripts/init_postgres.py`
✅ No DynamoDB required!
