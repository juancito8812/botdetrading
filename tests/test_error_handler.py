import pytest
from utils.resilience.error_handler import (
    ExchangeConnectionError, RateLimitExceeded, OrderRejected,
    InsufficientBalance, PositionNotFound, CircuitBreakerOpenError,
    MaxRetriesExceeded, ResilienceError,
)


def test_error_hierarchy():
    """Todos los errores heredan de ResilienceError."""
    assert issubclass(ExchangeConnectionError, ResilienceError)
    assert issubclass(RateLimitExceeded, ResilienceError)
    assert issubclass(OrderRejected, ResilienceError)
    assert issubclass(InsufficientBalance, ResilienceError)
    assert issubclass(PositionNotFound, ResilienceError)
    assert issubclass(CircuitBreakerOpenError, ResilienceError)
    assert issubclass(MaxRetriesExceeded, ResilienceError)


def test_error_message():
    """Los errores incluyen exchange_id y mensaje."""
    err = ExchangeConnectionError("bitget", "Connection refused")
    assert err.exchange_id == "bitget"
    assert "Connection refused" in str(err)


def test_error_with_cause():
    """Los errores pueden tener una causa (otra excepción)."""
    cause = ValueError("original error")
    err = MaxRetriesExceeded("bingx", "fetch_balance", cause)
    assert err.__cause__ is cause


def test_circuit_breaker_error():
    """CircuitBreakerOpenError incluye estado y timeout."""
    err = CircuitBreakerOpenError("bitget", 60.0)
    assert "open" in str(err).lower()
    assert err.exchange_id == "bitget"
