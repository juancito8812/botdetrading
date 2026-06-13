import time
import pytest
import json
import os
from utils.resilience.circuit_breaker import (
    CircuitBreaker, CircuitState,
)
from utils.resilience.error_handler import CircuitBreakerOpenError


def test_initial_state():
    """Circuit breaker comienza en CLOSED."""
    cb = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=0.1)
    assert cb.state == CircuitState.CLOSED


def test_open_after_threshold():
    """Se abre después de N fallos consecutivos."""
    cb = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=60)
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_success_resets_counter():
    """Un éxito resetea el contador de fallos."""
    cb = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.failure_count == 0
    assert cb.state == CircuitState.CLOSED


def test_half_open_after_timeout():
    """Después del timeout, pasa a HALF_OPEN."""
    cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN


def test_half_open_success_closes():
    """Un éxito en HALF_OPEN vuelve a CLOSED."""
    cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_half_open_failure_reopens():
    """Un fallo en HALF_OPEN vuelve a OPEN."""
    cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_call_raises_when_open():
    """Llamar cuando está OPEN lanza CircuitBreakerOpenError."""
    cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=60)
    cb.record_failure()
    cb.record_failure()

    with pytest.raises(CircuitBreakerOpenError):
        cb.call("test_exchange")


def test_call_succeeds_when_closed():
    """Llamar cuando está CLOSED devuelve True."""
    cb = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=60)
    assert cb.call("test_exchange") is True


def test_persist_and_load(tmp_path):
    """El estado se puede guardar y cargar."""
    cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=60)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    filepath = os.path.join(tmp_path, "circuit_state.json")
    cb.persist(filepath)

    cb2 = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=60)
    cb2.load(filepath)
    assert cb2.state == CircuitState.OPEN
    assert cb2.failure_count == 2


def test_call_when_open_with_context():
    """CircuitBreakerOpenError incluye exchange y retry_after."""
    cb = CircuitBreaker(name="bitget", failure_threshold=2, reset_timeout=60)
    cb.record_failure()
    cb.record_failure()

    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        cb.call("bitget")
    assert exc_info.value.exchange_id == "bitget"
    assert exc_info.value.retry_after > 0
