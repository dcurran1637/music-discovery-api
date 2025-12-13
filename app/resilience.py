"""Tools for rate limiting and circuit breakers to handle failures gracefully."""

import os
from datetime import datetime, timedelta
from typing import Optional, Callable, TypeVar, Any
import asyncio
import random
from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

_rate_limit_store: dict = {}

class CircuitBreaker:
    """Prevents cascading failures by stopping requests when a service is failing."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "CircuitBreaker"
    ):
        """Set up a circuit breaker with failure limits and recovery time."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"

    def is_open(self) -> bool:
        """Returns True if the circuit is open and should reject requests."""
        if self.state == "closed":
            return False
        
        if self.state == "open":
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
database_circuit_breaker = CircuitBreaker(
    failure_threshold=10,
    recovery_timeout=30,
    name="PostgreSQL"
)


async def check_circuit_breaker_status() -> dict:
    """Get current status of all circuit breakers."""
    return {
        "spotify": {
            "state": spotify_circuit_breaker.state,
            "failures": spotify_circuit_breaker.failure_count,
        },
        "database": {
            "state": database_circuit_breaker.state,
            "failures": database_circuit_breaker.failure_count,
        },
    }


async def retry_with_exponential_backoff(
    func: Callable[..., Any],
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 32.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
    **kwargs
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 32.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        jitter: Add random jitter to prevent thundering herd (default: True)
        retryable_exceptions: Tuple of exceptions to retry on (default: all)
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result from the function
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            if attempt > 0:
                logger.info(f"Function {func.__name__} succeeded after {attempt} retries")
            return result
        except retryable_exceptions as e:
            last_exception = e
            
            if attempt >= max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                raise
            
            # Calculate delay with exponential backoff
            delay = min(initial_delay * (exponential_base ** attempt), max_delay)
            
            # Add jitter to prevent thundering herd problem
            if jitter:
                delay = delay * (0.5 + random.random() * 0.5)
            
            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
    
    raise last_exception
