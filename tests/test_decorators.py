import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from utils.resilience.decorators import (
    timeout_decorator, retry_decorator, log_errors_decorator,
    circuit_breaker_decorator_dynamic,
)
from utils.resilience.retry_service import MaxRetriesExceeded
from utils.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


@pytest.mark.asyncio
async def test_retry_decorator_success():
    """@retry_decorator ejecuta con éxito al primer intento."""
    mock_func = AsyncMock(return_value="ok")

    decorated = retry_decorator(max_retries=2, base_delay=0.01)(mock_func)

    result = await decorated("test_exchange")
    assert result == "ok"
    mock_func.assert_called_once()


@pytest.mark.asyncio
async def test_retry_decorator_retries():
    """@retry_decorator reintenta en fallos transitorios."""
    mock_func = AsyncMock(side_effect=[
        ConnectionError("fail1"),
        ConnectionError("fail2"),
        "success",
    ])

    decorated = retry_decorator(max_retries=3, base_delay=0.01)(mock_func)

    result = await decorated("test_exchange")
    assert result == "success"
    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_retry_decorator_exhausted():
    """@retry_decorator lanza MaxRetriesExceeded."""
    mock_func = AsyncMock(side_effect=ConnectionError("always fails"))

    decorated = retry_decorator(max_retries=2, base_delay=0.01)(mock_func)

    with pytest.raises(MaxRetriesExceeded):
        await decorated("test_exchange")


@pytest.mark.asyncio
async def test_circuit_breaker_decorator_dynamic():
    """@circuit_breaker_decorator_dynamic lanza error cuando está abierto."""
    cbs = {"test_cb": CircuitBreaker(name="test_cb", failure_threshold=2, reset_timeout=0.05)}
    cbs["test_cb"].record_failure()
    cbs["test_cb"].record_failure()

    def resolver(eid):
        return cbs[eid]

    mock_func = AsyncMock(return_value="ok")
    decorated = circuit_breaker_decorator_dynamic(resolver=resolver)(mock_func)

    with pytest.raises(CircuitBreakerOpenError):
        await decorated("test_exchange")


@pytest.mark.asyncio
async def test_circuit_breaker_decorator_dynamic():
    """@circuit_breaker_decorator_dynamic resuelve CB por exchange_id."""
    cbs = {
        "exchange_a": CircuitBreaker(name="a", failure_threshold=2, reset_timeout=60),
        "exchange_b": CircuitBreaker(name="b", failure_threshold=1, reset_timeout=60),
    }
    def resolver(eid):
        return cbs[eid]

    # exchange_b tiene threshold 1, ya está abierto
    cbs["exchange_b"].record_failure()

    mock_func = AsyncMock(return_value="ok")

    # exchange_a funciona bien
    decorated_a = circuit_breaker_decorator_dynamic(resolver=resolver)(mock_func)
    result = await decorated_a("exchange_a")
    assert result == "ok"

    # exchange_b está abierto
    decorated_b = circuit_breaker_decorator_dynamic(resolver=resolver)(mock_func)
    with pytest.raises(CircuitBreakerOpenError):
        await decorated_b("exchange_b")


@pytest.mark.asyncio
async def test_timeout_decorator():
    """@timeout_decorator lanza TimeoutError si la función excede el tiempo."""
    async def slow_func(*args, **kwargs):
        await asyncio.sleep(1.0)

    decorated = timeout_decorator(seconds=0.05)(slow_func)

    with pytest.raises(asyncio.TimeoutError):
        await decorated("test_exchange")


@pytest.mark.asyncio
async def test_timeout_decorator_success():
    """@timeout_decorator no interfiere si la función termina a tiempo."""
    mock_func = AsyncMock(return_value="fast")

    decorated = timeout_decorator(seconds=5.0)(mock_func)

    result = await decorated("test_exchange")
    assert result == "fast"


@pytest.mark.asyncio
async def test_log_errors_decorator(caplog):
    """@log_errors_decorator captura errores y los loguea."""
    import logging
    caplog.set_level(logging.ERROR)

    mock_func = AsyncMock(side_effect=ValueError("test error"))

    decorated = log_errors_decorator(context={"module": "test"})(mock_func)

    with pytest.raises(ValueError):
        await decorated("test_exchange")

    assert "test error" in caplog.text
