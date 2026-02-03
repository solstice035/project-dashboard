"""
Tests for resilience module - retry decorator and circuit breaker.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from resilience import (
    retry, CircuitBreaker, CircuitState, CircuitBreakerError,
    retry_with_circuit_breaker, get_circuit_status
)


class TestRetryDecorator:
    """Tests for @retry decorator."""

    def test_retry_success_first_attempt(self):
        """Should succeed on first attempt without retrying."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeed()

        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failures(self):
        """Should succeed after transient failures."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient failure")
            return "success"

        result = fail_then_succeed()

        assert result == "success"
        assert call_count == 3

    def test_retry_exhausts_attempts(self):
        """Should raise after exhausting all attempts."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("persistent failure")

        with pytest.raises(ValueError, match="persistent failure"):
            always_fail()

        assert call_count == 3

    def test_retry_only_catches_specified_exceptions(self):
        """Should only retry on specified exception types."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retried")

        with pytest.raises(TypeError):
            raise_type_error()

        assert call_count == 1  # Not retried

    def test_retry_on_retry_callback(self):
        """Should call on_retry callback for each retry."""
        retries = []

        def on_retry(exception, attempt):
            retries.append((str(exception), attempt))

        @retry(max_attempts=3, base_delay=0.01, on_retry=on_retry)
        def fail_twice():
            if len(retries) < 2:
                raise ValueError("failing")
            return "success"

        result = fail_twice()

        assert result == "success"
        assert len(retries) == 2
        assert retries[0][1] == 1
        assert retries[1][1] == 2


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_circuit_starts_closed(self):
        """Circuit should start in closed state."""
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request()

    def test_circuit_opens_after_threshold(self):
        """Circuit should open after reaching failure threshold."""
        cb = CircuitBreaker("test", failure_threshold=3)

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.allow_request()

    def test_circuit_resets_on_success(self):
        """Success should reset failure count."""
        cb = CircuitBreaker("test", failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_circuit_half_open_after_timeout(self):
        """Circuit should transition to half-open after reset timeout."""
        cb = CircuitBreaker("test", failure_threshold=2, reset_timeout_seconds=0)

        cb.record_failure()
        cb.record_failure()
        # Check internal state to avoid triggering auto-transition
        assert cb._state == CircuitState.OPEN

        # With 0 timeout, accessing state property should trigger transition to half-open
        time.sleep(0.01)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request()  # One test request allowed

    def test_circuit_closes_on_half_open_success(self):
        """Success in half-open should close the circuit."""
        cb = CircuitBreaker("test", failure_threshold=2, reset_timeout_seconds=0)

        cb.record_failure()
        cb.record_failure()
        time.sleep(0.01)

        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_circuit_reopens_on_half_open_failure(self):
        """Failure in half-open should reopen the circuit."""
        cb = CircuitBreaker("test", failure_threshold=2, reset_timeout_seconds=0)

        cb.record_failure()
        cb.record_failure()
        # Check internal state first before triggering transition
        assert cb._state == CircuitState.OPEN
        time.sleep(0.01)

        # Access state to trigger OPEN -> HALF_OPEN transition
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        # Failure in HALF_OPEN should reopen - check internal state
        assert cb._state == CircuitState.OPEN

    def test_circuit_manual_reset(self):
        """Manual reset should close the circuit."""
        cb = CircuitBreaker("test", failure_threshold=2)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_circuit_protect_decorator(self):
        """@protect decorator should integrate with function."""
        cb = CircuitBreaker("test", failure_threshold=2)
        call_count = 0

        @cb.protect
        def protected_func():
            nonlocal call_count
            call_count += 1
            return "result"

        result = protected_func()
        assert result == "result"
        assert call_count == 1

    def test_circuit_protect_raises_on_open(self):
        """@protect should raise CircuitBreakerError when open."""
        cb = CircuitBreaker("test", failure_threshold=2)

        @cb.protect
        def protected_func():
            raise ValueError("fail")

        # Open the circuit
        with pytest.raises(ValueError):
            protected_func()
        with pytest.raises(ValueError):
            protected_func()

        # Now circuit is open, should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError) as exc:
            protected_func()

        assert exc.value.service_name == "test"


class TestRetryWithCircuitBreaker:
    """Tests for combined retry with circuit breaker."""

    def test_retry_respects_circuit_breaker(self):
        """Should not retry when circuit is open."""
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=60)
        call_count = 0

        @retry_with_circuit_breaker(cb, max_attempts=3, base_delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        # First call - fails and opens circuit, decorator raises CircuitBreakerError
        # (because after first failure, circuit opens with threshold=1, and decorator
        # checks allow_request() which returns False, so it raises CircuitBreakerError)
        with pytest.raises(CircuitBreakerError):
            failing_func()

        # Circuit still open - should raise CircuitBreakerError immediately
        with pytest.raises(CircuitBreakerError):
            failing_func()

        # Only 1 call because circuit opened after first failure
        assert call_count == 1

    def test_retry_records_success(self):
        """Should record success with circuit breaker."""
        cb = CircuitBreaker("test", failure_threshold=3)

        @retry_with_circuit_breaker(cb, max_attempts=3, base_delay=0.01)
        def succeed():
            return "success"

        result = succeed()
        assert result == "success"
        assert cb._failure_count == 0


class TestGetCircuitStatus:
    """Tests for get_circuit_status function."""

    def test_returns_all_circuits(self):
        """Should return status for all pre-configured circuits."""
        status = get_circuit_status()

        assert "todoist" in status
        assert "linear" in status
        assert "telegram" in status
        assert "slack" in status
        assert "weather" in status

    def test_status_contains_state(self):
        """Each circuit status should contain state info."""
        status = get_circuit_status()

        for name, info in status.items():
            assert "state" in info
            assert "failure_count" in info
            assert "failure_threshold" in info
