import asyncio
import pytest
from utils.resilience.retry_service import RetryService, calculate_backoff, MaxRetriesExceeded


@pytest.mark.asyncio
async def test_retry_success_first_try():
    """No reintenta si la función tiene éxito al primer intento."""
    retry = RetryService(max_retries=3, base_delay=0.01)
    call_count = 0

    async def success_func():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await retry.execute(success_func)
    assert result == "ok"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_after_failures():
    """Reintenta después de fallos transitorios."""
    retry = RetryService(max_retries=3, base_delay=0.01)
    call_count = 0

    async def fail_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("temporary error")
        return "recovered"

    result = await retry.execute(fail_then_succeed)
    assert result == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exhausted():
    """Lanza MaxRetriesExceeded cuando se agotan los reintentos."""
    retry = RetryService(max_retries=2, base_delay=0.01)

    async def always_fails():
        raise ConnectionError("persistent error")

    with pytest.raises(MaxRetriesExceeded) as exc_info:
        await retry.execute(always_fails)
    assert exc_info.value.exchange_id


@pytest.mark.asyncio
async def test_retry_on_specific_exceptions():
    """Solo reintenta en las excepciones especificadas."""
    retry = RetryService(max_retries=2, base_delay=0.01, retry_on=(ConnectionError,))

    async def raises_value_error():
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        await retry.execute(raises_value_error)


@pytest.mark.asyncio
async def test_retry_rate_limit():
    """Reintenta en excepción temporal."""
    retry = RetryService(max_retries=2, base_delay=0.01)
    call_count = 0

    async def rate_limited():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("rate limited")
        return "ok"

    result = await retry.execute(rate_limited)
    assert result == "ok"
    assert call_count == 2


def test_calculate_backoff_values():
    """Verifica que los backoffs son exponenciales."""
    delays_no_jitter = []
    for attempt in range(3):
        delay = calculate_backoff(attempt, base_delay=1.0, max_delay=30.0,
                                  backoff_factor=2.0, jitter=False)
        delays_no_jitter.append(delay)
    assert delays_no_jitter[0] == 1.0
    assert delays_no_jitter[1] == 2.0
    assert delays_no_jitter[2] == 4.0

    # Con jitter, deben tener variación
    delays_with_jitter = []
    for attempt in range(3):
        delay = calculate_backoff(attempt, base_delay=1.0, max_delay=30.0,
                                  backoff_factor=2.0, jitter=True)
        delays_with_jitter.append(delay)
    # Con jitter los valores varían, pero deben estar en un rango esperado
    for d in delays_with_jitter:
        assert 0 < d <= 30.0


@pytest.mark.asyncio
async def test_on_retry_callback():
    """El callback on_retry se invoca en cada reintento."""
    callback_calls = []

    def on_retry_cb(exc, attempt):
        callback_calls.append((attempt, str(exc)))

    retry = RetryService(max_retries=2, base_delay=0.01, on_retry=on_retry_cb)

    async def always_fails():
        raise ConnectionError("fail")

    with pytest.raises(MaxRetriesExceeded):
        await retry.execute(always_fails)

    assert len(callback_calls) == 2  # 2 reintentos
