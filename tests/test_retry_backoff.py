"""Tests for retry and exponential backoff functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import httpx
from app.resilience import retry_with_exponential_backoff, spotify_circuit_breaker
from app.spotify_client import _spotify_api_call


class TestRetryBackoff:
    """Test retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_first_attempt(self):
        """Test that a successful call doesn't trigger retry."""
        async def successful_func():
            return "success"
        
        result = await retry_with_exponential_backoff(
            successful_func,
            max_retries=3,
            initial_delay=0.1
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self):
        """Test that retry succeeds after initial failures."""
        call_count = 0
        
        async def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPError("Temporary failure")
            return "success"
        
        result = await retry_with_exponential_backoff(
            failing_then_succeeding,
            max_retries=3,
            initial_delay=0.1,
            retryable_exceptions=(httpx.HTTPError,)
        )
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_fails_after_max_attempts(self):
        """Test that retry fails after max attempts."""
        async def always_failing():
            raise httpx.HTTPError("Permanent failure")
        
        with pytest.raises(httpx.HTTPError):
            await retry_with_exponential_backoff(
                always_failing,
                max_retries=2,
                initial_delay=0.1,
                retryable_exceptions=(httpx.HTTPError,)
            )

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Test that delays increase exponentially."""
        call_times = []
        
        async def failing_func():
            call_times.append(asyncio.get_event_loop().time())
            raise httpx.HTTPError("Test failure")
        
        try:
            await retry_with_exponential_backoff(
                failing_func,
                max_retries=3,
                initial_delay=0.1,
                exponential_base=2.0,
                jitter=False,  # Disable jitter for predictable delays
                retryable_exceptions=(httpx.HTTPError,)
            )
        except httpx.HTTPError:
            pass
        
        # Should have 4 attempts (initial + 3 retries)
        assert len(call_times) == 4
        
        # Check that delays increase (approximately exponential)
        delays = [call_times[i+1] - call_times[i] for i in range(len(call_times) - 1)]
        # First delay should be ~0.1s, second ~0.2s, third ~0.4s
        assert 0.05 < delays[0] < 0.15  # Allow some variance
        assert 0.15 < delays[1] < 0.25
        assert 0.35 < delays[2] < 0.50


class TestSpotifyAPICallWithRetry:
    """Test Spotify API call wrapper with retry logic."""

    @pytest.mark.asyncio
    async def test_api_call_success(self):
        """Test successful API call."""
        from unittest.mock import MagicMock
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = await _spotify_api_call(
                "GET",
                "https://api.spotify.com/v1/test",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            assert response.json() == {"data": "test"}

    @pytest.mark.asyncio
    async def test_api_call_handles_rate_limiting(self):
        """Test that API call handles 429 rate limiting."""
        mock_rate_limit_response = AsyncMock()
        mock_rate_limit_response.status_code = 429
        mock_rate_limit_response.headers = {"Retry-After": "1"}
        mock_rate_limit_response.request = AsyncMock()
        
        mock_success_response = AsyncMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": "success"}
        mock_success_response.raise_for_status = AsyncMock()
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_rate_limit_response
            return mock_success_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            # Reset circuit breaker state
            spotify_circuit_breaker.state = "closed"
            spotify_circuit_breaker.failure_count = 0
            
            response = await _spotify_api_call(
                "GET",
                "https://api.spotify.com/v1/test",
                headers={"Authorization": "Bearer test_token"}
            )
            
            # Should succeed after retry
            assert response.status_code == 200
            assert call_count >= 2  # At least one retry

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test that circuit breaker works with retry logic."""
        # Reset circuit breaker
        spotify_circuit_breaker.state = "closed"
        spotify_circuit_breaker.failure_count = 0
        
        async def always_failing():
            raise httpx.HTTPError("Test failure")
        
        # Trigger failures to open circuit breaker
        for _ in range(6):  # More than failure_threshold
            try:
                await spotify_circuit_breaker.call_with_breaker(
                    always_failing
                )
            except Exception:
                pass
        
        # Circuit should be open
        assert spotify_circuit_breaker.state == "open"
        
        # Next call should fail immediately
        with pytest.raises(Exception, match="Circuit breaker.*is open"):
            await spotify_circuit_breaker.call_with_breaker(always_failing)
