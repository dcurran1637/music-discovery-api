"""
Rate limiting and circuit breaker utilities for production resilience.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Callable
import asyncio
from .logging_config import get_logger

logger = get_logger(__name__)

# Rate limiting state (in production, use Redis)
_rate_limit_store: dict = {}

# Circuit breaker state
class CircuitBreaker:
    """Simple circuit breaker pattern implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "CircuitBreaker"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open

    def is_open(self) -> bool:
        """Check if circuit is open and should reject requests."""
        if self.state == "closed":
            return False
        
        if self.state == "open":
            # Check if recovery timeout has passed
            if (datetime.utcnow() - self.last_failure_time).seconds > self.recovery_timeout:
                self.state = "half-open"
                logger.info(f"Circuit breaker {self.name} transitioning to half-open")
                return False
            return True
        
        # half-open state: allow request to proceed
        return False

    def record_success(self):
        """Record a successful call."""
        if self.state == "half-open":
            self.state = "closed"
            self.failure_count = 0
            logger.info(f"Circuit breaker {self.name} closed")

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold and self.state != "open":
            self.state = "open"
            logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")

    async def call_with_breaker(self, func: Callable, *args, **kwargs):
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.is_open():
            raise Exception(f"Circuit breaker {self.name} is open")
        
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


# Global circuit breakers for external services
spotify_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="SpotifyAPI"
)
dynamodb_circuit_breaker = CircuitBreaker(
    failure_threshold=10,
    recovery_timeout=30,
    name="DynamoDB"
)


async def check_circuit_breaker_status() -> dict:
    """Get current status of all circuit breakers."""
    return {
        "spotify": {
            "state": spotify_circuit_breaker.state,
            "failures": spotify_circuit_breaker.failure_count,
        },
        "dynamodb": {
            "state": dynamodb_circuit_breaker.state,
            "failures": dynamodb_circuit_breaker.failure_count,
        },
    }
