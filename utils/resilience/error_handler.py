"""Taxonomía de errores del sistema de trading."""

from typing import Optional


class ResilienceError(Exception):
    """Error base del sistema de resiliencia."""
    def __init__(self, exchange_id: str, message: str = ""):
        self.exchange_id = exchange_id
        super().__init__(f"[{exchange_id}] {message}" if message else f"[{exchange_id}]")


class ExchangeConnectionError(ResilienceError):
    """Error de conexión con el exchange."""
    pass


class RateLimitExceeded(ResilienceError):
    """Rate limit alcanzado."""
    pass


class OrderRejected(ResilienceError):
    """Orden rechazada por el exchange."""
    pass


class InsufficientBalance(ResilienceError):
    """Saldo insuficiente."""
    pass


class PositionNotFound(ResilienceError):
    """Posición no encontrada."""
    pass


class CircuitBreakerOpenError(ResilienceError):
    """Circuit breaker bloqueando requests."""
    def __init__(self, exchange_id: str, retry_after: float = 0.0):
        self.retry_after = retry_after
        super().__init__(exchange_id, f"Circuit breaker OPEN, retry after {retry_after}s")


class MaxRetriesExceeded(ResilienceError):
    """Se agotaron los reintentos."""
    def __init__(self, exchange_id: str, operation: str, cause: Optional[Exception] = None):
        msg = f"Max retries exceeded for {operation}"
        self.operation = operation
        super().__init__(exchange_id, msg)
        if cause:
            self.__cause__ = cause
