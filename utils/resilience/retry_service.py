"""Servicio de reintentos con backoff exponencial y jitter."""

import asyncio
import random
import logging
from typing import (
    Awaitable, Callable, Optional, Tuple, Type,
)

from utils.resilience.error_handler import (
    MaxRetriesExceeded, RateLimitExceeded, ExchangeConnectionError,
)

logger = logging.getLogger("TradingBot")


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    Calcula el tiempo de espera para un reintento.

    Fórmula: delay = min(base_delay * backoff_factor^attempt, max_delay)
    Con jitter: delay *= random.uniform(0.5, 1.5)
    """
    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
    if jitter:
        delay *= random.uniform(0.5, 1.5)
    return delay


class RetryService:
    """
    Servicio de reintentos con backoff exponencial y jitter.

    Uso:
        retry = RetryService(max_retries=3, base_delay=1.0)
        result = await retry.execute(some_async_func)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retry_on: Optional[Tuple[Type[Exception], ...]] = None,
        on_retry: Optional[Callable] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retry_on = retry_on or (
            ConnectionError, TimeoutError, asyncio.TimeoutError,
            ExchangeConnectionError, RateLimitExceeded,
        )
        # Excepciones que NUNCA se reintentan (fallo fatal)
        self._never_retry = (RuntimeError, asyncio.CancelledError)
        self.on_retry = on_retry

    async def execute(
        self,
        func: Callable[..., Awaitable],
        *args,
        exchange_id: str = "unknown",
        operation: str = "unknown",
        **kwargs,
    ):
        """
        Ejecuta una función async con reintentos.

        Args:
            func: Función asíncrona a ejecutar
            exchange_id: Identificador del exchange (para logging)
            operation: Nombre de la operación (para logging)

        Returns:
            El resultado de la función

        Raises:
            MaxRetriesExceeded: Si se agotan los reintentos
        """
        last_exc = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exc = e

                if not self._is_retryable(e):
                    raise

                if attempt < self.max_retries:
                    delay = calculate_backoff(
                        attempt, self.base_delay, self.max_delay,
                        self.backoff_factor, self.jitter,
                    )
                    logger.warning(
                        f"🔄 Reintento {attempt + 1}/{self.max_retries} "
                        f"para {exchange_id}/{operation} "
                        f"en {delay:.1f}s. Error: {e}"
                    )

                    if self.on_retry:
                        self.on_retry(e, attempt)

                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"❌ Se agotaron los reintentos ({self.max_retries}) "
                        f"para {exchange_id}/{operation}: {e}"
                    )
                    raise MaxRetriesExceeded(exchange_id, operation, e) from e

        raise MaxRetriesExceeded(exchange_id, operation, last_exc)

    def _is_retryable(self, exc: Exception) -> bool:
        """Determina si una excepción es reintentable."""
        if isinstance(exc, self._never_retry):
            return False
        return isinstance(exc, self.retry_on)
