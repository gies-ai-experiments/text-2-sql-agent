"""
Resilience patterns for AgentX A2A communication.

Provides:
- CircuitBreaker: Prevents cascading failures when agents are unavailable
- ResilientHTTPClient: HTTP client with retry, circuit breaker, and adaptive timeouts
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
from urllib.parse import urlparse

import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


class CircuitState(Enum):
    """States for circuit breaker pattern."""
    CLOSED = "closed"       # Normal operation, requests allowed
    OPEN = "open"           # Failing, requests rejected immediately
    HALF_OPEN = "half_open" # Testing recovery, one request allowed


@dataclass
class TimeoutConfig:
    """Adaptive timeout configuration for different operation types."""
    health_check: float = 5.0      # Quick health checks
    sql_generation: float = 60.0   # LLM generation can be slow
    schema_fetch: float = 10.0     # Schema operations
    default: float = 30.0          # Default for unknown operations

    def get_timeout(self, operation_type: str) -> float:
        """Get timeout for an operation type."""
        return getattr(self, operation_type, self.default)


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: After failure_threshold failures, reject all requests immediately
    - HALF_OPEN: After recovery_timeout, allow one test request

    Usage:
        breaker = CircuitBreaker()
        if breaker.can_execute():
            try:
                result = await make_request()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
        else:
            raise CircuitOpenError()
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again (half-open)
            half_open_max_calls: Number of test calls allowed in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failures = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def failures(self) -> int:
        """Current failure count."""
        return self._failures

    def record_success(self) -> None:
        """Record a successful call - reset failures and close circuit."""
        self._failures = 0
        self._half_open_calls = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call - increment failures, potentially open circuit."""
        self._failures += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Failed during test - reopen circuit
            self._state = CircuitState.OPEN
        elif self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns:
            True if request should proceed, False if circuit is open
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time is None:
                return True
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                return True
            return False

        # HALF_OPEN state - allow limited test calls
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = None
        self._half_open_calls = 0


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""

    def __init__(self, host: str, message: str = None):
        self.host = host
        self.message = message or f"Circuit breaker open for {host}"
        super().__init__(self.message)


class ResilientHTTPClient:
    """
    HTTP client with retry, circuit breaker, and adaptive timeouts.

    Features:
    - Automatic retry with exponential backoff (3 attempts)
    - Per-host circuit breaker to prevent cascading failures
    - Adaptive timeouts based on operation type
    - Connection pooling via aiohttp.ClientSession

    Usage:
        client = ResilientHTTPClient()
        try:
            response = await client.request(
                "POST",
                "http://agent:8080/generate",
                operation_type="sql_generation",
                json={"question": "...", "schema": {...}}
            )
        except CircuitOpenError:
            # Agent is unavailable, fail fast
            pass
        finally:
            await client.close()
    """

    def __init__(
        self,
        timeout_config: Optional[TimeoutConfig] = None,
        circuit_failure_threshold: int = 3,
        circuit_recovery_timeout: float = 30.0,
    ):
        """
        Initialize resilient HTTP client.

        Args:
            timeout_config: Timeout configuration for different operations
            circuit_failure_threshold: Failures before opening circuit
            circuit_recovery_timeout: Seconds before trying failed host again
        """
        self.timeout_config = timeout_config or TimeoutConfig()
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_recovery_timeout = circuit_recovery_timeout
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create shared aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _get_circuit_breaker(self, host: str) -> CircuitBreaker:
        """Get or create circuit breaker for a host."""
        if host not in self._circuit_breakers:
            self._circuit_breakers[host] = CircuitBreaker(
                failure_threshold=self._circuit_failure_threshold,
                recovery_timeout=self._circuit_recovery_timeout,
            )
        return self._circuit_breakers[host]

    def get_circuit_state(self, host: str) -> CircuitState:
        """Get current circuit state for a host."""
        if host in self._circuit_breakers:
            return self._circuit_breakers[host].state
        return CircuitState.CLOSED

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        timeout: aiohttp.ClientTimeout,
        **kwargs,
    ) -> dict:
        """Internal request method with retry logic."""
        session = await self._get_session()
        async with session.request(method, url, timeout=timeout, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def request(
        self,
        method: str,
        url: str,
        operation_type: str = "default",
        **kwargs,
    ) -> dict:
        """
        Make an HTTP request with resilience patterns.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            operation_type: Type of operation for timeout selection
            **kwargs: Additional arguments passed to aiohttp

        Returns:
            Parsed JSON response

        Raises:
            CircuitOpenError: If circuit breaker is open for the host
            aiohttp.ClientError: On HTTP errors after retries exhausted
            asyncio.TimeoutError: On timeout after retries exhausted
        """
        host = urlparse(url).netloc
        circuit = self._get_circuit_breaker(host)

        if not circuit.can_execute():
            raise CircuitOpenError(host)

        timeout_seconds = self.timeout_config.get_timeout(operation_type)
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)

        try:
            result = await self._request_with_retry(method, url, timeout, **kwargs)
            circuit.record_success()
            return result
        except Exception as e:
            circuit.record_failure()
            raise

    async def get(self, url: str, operation_type: str = "default", **kwargs) -> dict:
        """HTTP GET request."""
        return await self.request("GET", url, operation_type, **kwargs)

    async def post(self, url: str, operation_type: str = "default", **kwargs) -> dict:
        """HTTP POST request."""
        return await self.request("POST", url, operation_type, **kwargs)

    async def close(self) -> None:
        """Close the HTTP session and clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def reset_circuit(self, host: str) -> None:
        """Manually reset circuit breaker for a host."""
        if host in self._circuit_breakers:
            self._circuit_breakers[host].reset()

    def reset_all_circuits(self) -> None:
        """Reset all circuit breakers."""
        for circuit in self._circuit_breakers.values():
            circuit.reset()

    async def __aenter__(self) -> "ResilientHTTPClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - close session."""
        await self.close()
