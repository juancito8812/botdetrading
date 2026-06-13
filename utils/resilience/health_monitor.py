"""Monitor de salud de conexiones a exchanges."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Awaitable, Any

from utils.resilience.error_handler import ExchangeConnectionError

logger = logging.getLogger("TradingBot")


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


MAX_LATENCIES = 5


@dataclass
class ExchangeHealth:
    """Estado de salud de un exchange."""
    exchange_id: str
    status: HealthStatus = HealthStatus.HEALTHY
    last_ok_time: Optional[float] = None
    consecutive_failures: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    degraded_after: int = 3
    down_after: int = 6
    circuit_breaker_state: str = "closed"

    def record_success(self, latency_ms: float = 0.0):
        """Registra un health check exitoso."""
        self.consecutive_failures = 0
        self.last_ok_time = time.time()
        self.status = HealthStatus.HEALTHY

        self.latencies_ms.append(latency_ms)
        if len(self.latencies_ms) > MAX_LATENCIES:
            self.latencies_ms = self.latencies_ms[-MAX_LATENCIES:]

    def record_failure(self):
        """Registra un health check fallido."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.down_after:
            self.status = HealthStatus.DOWN
        elif self.consecutive_failures >= self.degraded_after:
            self.status = HealthStatus.DEGRADED

    @property
    def avg_latency_ms(self) -> float:
        """Latencia promedio de las últimas mediciones."""
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a dict para persistencia."""
        return {
            "exchange_id": self.exchange_id,
            "status": self.status.value,
            "last_ok_time": self.last_ok_time,
            "consecutive_failures": self.consecutive_failures,
            "avg_latency_ms": self.avg_latency_ms,
        }


class HealthMonitor:
    """
    Monitorea periódicamente la salud de las conexiones a exchanges.

    Se ejecuta como tarea asíncrona y se integra con el watchdog existente.
    """

    def __init__(self, check_interval: float = 60.0):
        self.check_interval = check_interval
        self._health_map: Dict[str, ExchangeHealth] = {}
        self._health_check_func: Optional[Callable[..., Awaitable[bool]]] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def set_health_check_func(self, func: Callable[..., Awaitable[bool]]):
        """Establece la función de health check (debe aceptar exchange_id como arg)."""
        self._health_check_func = func

    def add_exchange(self, exchange_id: str):
        """Añade un exchange al monitoreo."""
        if exchange_id not in self._health_map:
            self._health_map[exchange_id] = ExchangeHealth(exchange_id=exchange_id)
            logger.info(f"📡 HealthMonitor: añadido {exchange_id}")

    def remove_exchange(self, exchange_id: str):
        """Elimina un exchange del monitoreo."""
        self._health_map.pop(exchange_id, None)

    def get_health(self, exchange_id: str) -> Optional[ExchangeHealth]:
        """Retorna la salud de un exchange."""
        return self._health_map.get(exchange_id)

    def get_summary(self) -> Dict[str, Dict[str, Any]]:
        """Retorna un resumen de salud de todos los exchanges."""
        return {
            eid: health.to_dict()
            for eid, health in self._health_map.items()
        }

    async def _check_single_exchange(self, exchange_id: str):
        """Ejecuta un health check para un exchange específico."""
        if not self._health_check_func:
            return

        health = self._health_map.get(exchange_id)
        if not health:
            return

        start = time.time()
        try:
            ok = await self._health_check_func(exchange_id)
            latency_ms = (time.time() - start) * 1000
            if ok:
                health.record_success(latency_ms)
            else:
                health.record_failure()
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            health.record_failure()
            logger.warning(
                f"⚠️ Health check falló para {exchange_id}: {e} "
                f"(latencia: {latency_ms:.0f}ms)"
            )

    async def _run_cycle(self):
        """Ejecuta un ciclo completo de health checks."""
        for exchange_id in list(self._health_map.keys()):
            await self._check_single_exchange(exchange_id)

        for eid, health in self._health_map.items():
            if health.status != HealthStatus.HEALTHY:
                logger.warning(
                    f"📊 {eid}: {health.status.value} "
                    f"({health.consecutive_failures} fallos, "
                    f"latencia: {health.avg_latency_ms:.0f}ms)"
                )

    async def start(self):
        """Inicia el monitoreo periódico."""
        if self._running:
            return
        self._running = True
        logger.info(f"📡 HealthMonitor iniciado (intervalo: {self.check_interval}s)")

        while self._running:
            await self._run_cycle()
            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Detiene el monitoreo."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def persist(self, filepath: str):
        """Guarda el historial de salud a un archivo JSON."""
        try:
            data = {
                eid: health.to_dict()
                for eid, health in self._health_map.items()
            }
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error persistiendo health data: {e}")
