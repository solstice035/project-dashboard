"""
Resilience utilities for Project Dashboard.

Provides retry logic with exponential backoff and circuit breaker pattern
for external service calls.
"""

import functools
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic decorator return type
F = TypeVar('F', bound=Callable[..., Any])


class ServiceUnavailableError(Exception):
    """Raised when a service is unavailable after retries or circuit is open."""
    pass


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open and request is rejected."""
    def __init__(self, service_name: str, reset_time: datetime):
        self.service_name = service_name
        self.reset_time = reset_time
        super().__init__(
            f"Circuit breaker open for {service_name}. "
            f"Will reset at {reset_time.isoformat()}"
        )


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    Prevents repeated calls to failing services, giving them time to recover.

    Usage:
        cb = CircuitBreaker("todoist")

        @cb.protect
        def call_todoist():
            ...

        # Or manually:
        if cb.allow_request():
            try:
                result = call_service()
                cb.record_success()
            except Exception:
                cb.record_failure()
    """
    name: str
    failure_threshold: int = 5  # Failures before opening
    reset_timeout_seconds: int = 60  # Time before trying again
    half_open_max_calls: int = 1  # Test calls in half-open state

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current state, checking if reset timeout has passed."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN (attempting reset)")
        return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try resetting."""
        if self._last_failure_time is None:
            return True
        reset_at = self._last_failure_time + timedelta(seconds=self.reset_timeout_seconds)
        return datetime.now() >= reset_at

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        state = self.state  # This may transition OPEN -> HALF_OPEN

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        # OPEN state
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            # Service recovered
            logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (service recovered)")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._state == CircuitState.HALF_OPEN:
            # Service still failing
            logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (still failing)")
            self._state = CircuitState.OPEN

        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit {self.name}: CLOSED -> OPEN "
                    f"({self._failure_count} failures, threshold {self.failure_threshold})"
                )
                self._state = CircuitState.OPEN

    def get_reset_time(self) -> Optional[datetime]:
        """Get time when circuit will attempt reset (if open)."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            return self._last_failure_time + timedelta(seconds=self.reset_timeout_seconds)
        return None

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info(f"Circuit {self.name}: manually reset")

    def protect(self, func: F) -> F:
        """Decorator to protect a function with this circuit breaker."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.allow_request():
                reset_time = self.get_reset_time()
                raise CircuitBreakerError(self.name, reset_time or datetime.now())

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception:
                self.record_failure()
                raise

        return wrapper  # type: ignore


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[F], F]:
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including initial)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff (delay = base_delay * base^attempt)
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry with (exception, attempt)

    Usage:
        @retry(max_attempts=3, base_delay=1.0)
        def call_api():
            ...

        @retry(max_attempts=5, exceptions=(requests.RequestException,))
        def fetch_data():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        # Final attempt failed
                        logger.warning(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay
                    )

                    # Add jitter (0-50% of delay)
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.debug(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            # Should never reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry state")

        return wrapper  # type: ignore

    return decorator


def retry_with_circuit_breaker(
    circuit_breaker: CircuitBreaker,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Combined retry and circuit breaker decorator.

    Retries failed calls with exponential backoff, but respects the circuit
    breaker state. If the circuit is open, raises CircuitBreakerError immediately.

    Args:
        circuit_breaker: CircuitBreaker instance to use
        max_attempts: Maximum retry attempts
        base_delay: Initial retry delay
        max_delay: Maximum retry delay
        exceptions: Exception types to retry on

    Usage:
        todoist_circuit = CircuitBreaker("todoist")

        @retry_with_circuit_breaker(todoist_circuit, max_attempts=3)
        def fetch_todoist():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check circuit breaker first
            if not circuit_breaker.allow_request():
                reset_time = circuit_breaker.get_reset_time()
                raise CircuitBreakerError(circuit_breaker.name, reset_time or datetime.now())

            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    circuit_breaker.record_success()
                    return result
                except exceptions as e:
                    last_exception = e
                    circuit_breaker.record_failure()

                    if attempt == max_attempts:
                        logger.warning(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Check if circuit just opened
                    if not circuit_breaker.allow_request():
                        logger.warning(
                            f"{func.__name__}: circuit opened after {attempt} failures"
                        )
                        raise CircuitBreakerError(
                            circuit_breaker.name,
                            circuit_breaker.get_reset_time() or datetime.now()
                        )

                    # Calculate delay
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay = delay * (0.5 + random.random() * 0.5)  # Add jitter

                    logger.debug(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed. "
                        f"Retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry state")

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# Pre-configured Circuit Breakers for Common Services
# =============================================================================

# Circuit breakers for external APIs (can be imported and used directly)
todoist_circuit = CircuitBreaker("todoist", failure_threshold=3, reset_timeout_seconds=60)
linear_circuit = CircuitBreaker("linear", failure_threshold=3, reset_timeout_seconds=60)
telegram_circuit = CircuitBreaker("telegram", failure_threshold=5, reset_timeout_seconds=120)
slack_circuit = CircuitBreaker("slack", failure_threshold=5, reset_timeout_seconds=120)
weather_circuit = CircuitBreaker("weather", failure_threshold=3, reset_timeout_seconds=300)


def get_circuit_status() -> dict[str, dict]:
    """Get status of all circuit breakers."""
    circuits = [
        todoist_circuit, linear_circuit, telegram_circuit,
        slack_circuit, weather_circuit
    ]

    return {
        cb.name: {
            "state": cb.state.value,
            "failure_count": cb._failure_count,
            "failure_threshold": cb.failure_threshold,
            "reset_time": cb.get_reset_time().isoformat() if cb.get_reset_time() else None
        }
        for cb in circuits
    }
