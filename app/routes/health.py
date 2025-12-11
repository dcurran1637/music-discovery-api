"""
Health check and status endpoints for operational monitoring.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime
import redis.asyncio as aioredis
import os
from ..database import SessionLocal
from ..logging_config import get_logger
from ..resilience import check_circuit_breaker_status

logger = get_logger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@router.get("/live")
async def liveness():
    """
    Liveness probe - returns 200 if service is running.
    Useful for Kubernetes liveness checks.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ready")
async def readiness():
    """
    Readiness probe - checks if service is ready to handle traffic.
    Useful for Kubernetes readiness checks.
    """
    checks = {
        "database": "unknown",
        "cache": "unknown",
        "overall": "ready",
    }

    # Check database connectivity (PostgreSQL)
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        checks["database"] = "healthy"
    except Exception as e:
        logger.warning(f"Database check failed: {str(e)}")
        checks["database"] = "unhealthy"

    # Check Redis connectivity
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.ping()
        await redis.close()
        checks["cache"] = "healthy"
    except Exception as e:
        logger.warning(f"Cache check failed: {str(e)}")
        checks["cache"] = "unhealthy"

    # If any critical service is unhealthy, mark overall as not ready
    if checks["database"] != "healthy":
        checks["overall"] = "not_ready"

    status_code = 200 if checks["overall"] == "ready" else 503
    return JSONResponse(content=checks, status_code=status_code)


@router.get("/status")
async def status():
    """
    Comprehensive service status including circuit breaker state.
    """
    try:
        circuit_breakers = await check_circuit_breaker_status()
    except Exception as e:
        logger.error(f"Circuit breaker status check failed: {str(e)}")
        circuit_breakers = {}

    return {
        "service": "music-discovery-api",
        "timestamp": datetime.utcnow().isoformat(),
        "circuit_breakers": circuit_breakers,
    }
