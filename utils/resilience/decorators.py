"""Decoradores de resiliencia: @retry, @circuit_breaker, @timeout, @log_errors."""

import asyncio
import functools
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, Type

from utils.resilience.retry_service import RetryService
from utils.resilience.circuit_breaker import CircuitBreaker
from utils.resilience.retry_service import MaxRetriesExceeded

logger = logging.getLogger("TradingBot")

KNOWN_EXCHANGE_IDS = {"bitget", "bingx", "binance", "bybit", "okx", "kucoin", "mexc", "phemex", "blofin"}


# ─── TIMEOUT DECORATOR ───────────────────────────────────────────────

def timeout_decorator(
    seconds: float = 30.0,
    timeout_message: str = "Operation timed out",
):
    """
    Decorador que aplica un timeout a una función async.

    Uso:
        @timeout_decorator(seconds=15)
        async def fetch_ticker(exchange_id, symbol):
            ...
    """
    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=seconds
                )
            except asyncio.TimeoutError:
                safe_args = tuple(str(a) if not isinstance(a, str) else a[:50] for a in args)
                safe_kwargs = {k: v if not isinstance(v, str) else v[:50] for k, v in kwargs.items()}
                logger.error(
                    f"⏰ Timeout ({seconds}s) en {func.__name__} "
                    f"args={safe_args}, kwargs={safe_kwargs}"
                )
                raise
        return wrapper
    return decorator


# ─── RETRY DECORATOR ─────────────────────────────────────────────────

def _extract_exchange_id(args: tuple, kwargs: dict) -> str:
    """
    Extrae el exchange_id de los argumentos de la función decorada.

    Para métodos bound de ExchangeService: args=(self, exchange_id, ...)
    Para funciones sueltas: args=(exchange_id, ...)
    Para execute_signal: args=(self, signal, config, exchange_id)
    """
    if 'exchange_id' in kwargs:
        return kwargs['exchange_id']
    for arg in args:
        if isinstance(arg, str) and arg in KNOWN_EXCHANGE_IDS:
            return arg
    for arg in reversed(args):
        if isinstance(arg, str) and not arg.startswith("/") and "/" not in arg[:10]:
            return arg
    return "unknown"


def retry_decorator(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Decorador que reintenta una función async con backoff exponencial.

    El exchange_id se extrae de los argumentos de la función decorada.

    Uso:
        @retry_decorator(max_retries=3, base_delay=1.0)
        async def get_balance(exchange_id, ...):
            ...
    """
    retry_service = RetryService(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
        retry_on=retry_on,
    )

    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            exchange_id = _extract_exchange_id(args, kwargs)
            return await retry_service.execute(
                lambda: func(*args, **kwargs),
                exchange_id=exchange_id,
                operation=func.__name__,
            )
        return wrapper
    return decorator


# ─── CIRCUIT BREAKER DECORATOR ────────────────────────────────────

def circuit_breaker_decorator_dynamic(
    resolver: Callable[[str], CircuitBreaker],
):
    """
    Decorador que resuelve el circuit breaker dinámicamente por exchange_id.

    Uso:
        def get_cb(exchange_id):
            return _circuit_breakers[exchange_id]

        @circuit_breaker_decorator_dynamic(resolver=get_cb)
        async def get_balance(exchange_id, ...):
            ...
    """
    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            exchange_id = _extract_exchange_id(args, kwargs)
            cb = resolver(exchange_id)
            cb.call(exchange_id)
            try:
                result = await func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                raise
        return wrapper
    return decorator


# ─── LOG ERRORS DECORATOR ────────────────────────────────────────────

def log_errors_decorator(
    context: Optional[Dict[str, Any]] = None,
):
    """
    Decorador que captura errores y los loguea con contexto estructurado.

    Uso:
        @log_errors_decorator(context={"module": "exchange_service"})
        async def execute_signal(signal, config, exchange_id):
            ...
    """
    ctx = context or {}

    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                exchange_id = _extract_exchange_id(args, kwargs)

                logger.error(
                    f"❌ Error en {func.__name__}: {e} "
                    f"[exchange={exchange_id}, duration={duration_ms:.0f}ms]"
                )
                raise
        return wrapper
    return decorator
