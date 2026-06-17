"""Circuit breaker con estados closed/open/half-open."""

import time
import logging
from enum import Enum
from typing import Optional


class CircuitBreakerOpenError(Exception):
    """Circuit breaker bloqueando requests."""
    def __init__(self, exchange_id: str, retry_after: float = 0.0):
        self.exchange_id = exchange_id
        self.retry_after = retry_after
        super().__init__(f"[{exchange_id}] Circuit breaker OPEN, retry after {retry_after}s")

logger = logging.getLogger("TradingBot")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker para operaciones de exchange.

    Estados:
        CLOSED: Normal. Pasan todas las requests.
        OPEN: Bloquea requests después de N fallos consecutivos.
        HALF_OPEN: Después del timeout, permite 1 request de prueba.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_requests: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_requests = half_open_max_requests

        self._state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.half_open_requests = 0

    @property
    def state(self) -> CircuitState:
        """Retorna el estado actual, evaluando si debe pasar a HALF_OPEN."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.reset_timeout:
                logger.info(f"🔓 Circuit breaker {self.name}: OPEN → HALF_OPEN")
                self._state = CircuitState.HALF_OPEN
                self.half_open_requests = 0
        return self._state

    def call(self, exchange_id: str) -> bool:
        """
        Verifica si se permite una llamada. Lanza CircuitBreakerOpenError si está abierto.

        Returns: True si la llamada está permitida.
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            remaining = self.reset_timeout - (time.time() - self.last_failure_time)
            raise CircuitBreakerOpenError(exchange_id, max(0, remaining))

        if current_state == CircuitState.HALF_OPEN:
            if self.half_open_requests >= self.half_open_max_requests:
                raise CircuitBreakerOpenError(exchange_id, self.reset_timeout)
            self.half_open_requests += 1

        return True

    def record_success(self):
        """Registra un éxito. Resetea el contador de fallos."""
        self.failure_count = 0
        self.half_open_requests = 0
        if self._state != CircuitState.CLOSED:
            logger.info(f"🔒 Circuit breaker {self.name}: → CLOSED")
            self._state = CircuitState.CLOSED

    def record_failure(self):
        """Registra un fallo. Abre el circuito si se supera el umbral."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"🔴 Circuit breaker {self.name}: HALF_OPEN → OPEN")
            self._state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            logger.warning(
                f"🔴 Circuit breaker {self.name}: CLOSED → OPEN "
                f"({self.failure_count} fallos)"
            )
            self._state = CircuitState.OPEN


