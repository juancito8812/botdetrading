"""Circuit breaker con estados closed/open/half-open."""

import time
import json
import logging
from enum import Enum
from typing import Optional

from utils.resilience.error_handler import CircuitBreakerOpenError

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

    def persist(self, filepath: str):
        """Guarda el estado actual a un archivo JSON."""
        data = {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
        }
        try:
            with open(filepath, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error persistiendo circuit breaker {self.name}: {e}")

    def load(self, filepath: str):
        """Carga el estado desde un archivo JSON."""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            self.name = data.get("name", self.name)
            self._state = CircuitState(data.get("state", "closed"))
            self.failure_count = data.get("failure_count", 0)
            self.last_failure_time = data.get("last_failure_time", 0.0)
        except Exception as e:
            logger.error(f"Error cargando circuit breaker {self.name}: {e}")
