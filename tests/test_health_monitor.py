import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from utils.resilience.health_monitor import (
    HealthMonitor, ExchangeHealth, HealthStatus,
)


def test_health_initial_state():
    """ExchangeHealth comienza con estado healthy."""
    health = ExchangeHealth(exchange_id="bitget")
    assert health.status == HealthStatus.HEALTHY
    assert health.consecutive_failures == 0
    assert health.latencies_ms == []


def test_health_record_success():
    """Registrar un éxito resetea fallos y añade latencia."""
    health = ExchangeHealth(exchange_id="bitget")
    health.record_success(latency_ms=150.0)
    assert health.status == HealthStatus.HEALTHY
    assert health.consecutive_failures == 0
    assert len(health.latencies_ms) == 1
    assert health.avg_latency_ms == 150.0


def test_health_record_failure():
    """Fallos consecutivos cambian el estado."""
    health = ExchangeHealth(exchange_id="bitget", degraded_after=2, down_after=5)
    health.record_failure()
    assert health.status == HealthStatus.HEALTHY
    health.record_failure()
    assert health.status == HealthStatus.DEGRADED
    health.record_failure()
    health.record_failure()
    health.record_failure()
    assert health.status == HealthStatus.DOWN


def test_health_recovery():
    """Un éxito después de fallos recupera el estado."""
    health = ExchangeHealth(exchange_id="bitget", degraded_after=2, down_after=5)
    for _ in range(3):
        health.record_failure()
    assert health.status == HealthStatus.DEGRADED

    health.record_success(latency_ms=100)
    assert health.status == HealthStatus.HEALTHY
    assert health.consecutive_failures == 0


@pytest.mark.asyncio
async def test_health_monitor_add_exchange():
    """HealthMonitor añade exchanges correctamente."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    monitor.add_exchange("bingx")

    assert "bitget" in monitor.get_summary()
    assert "bingx" in monitor.get_summary()


@pytest.mark.asyncio
async def test_health_monitor_check():
    """HealthMonitor ejecuta health checks."""
    monitor = HealthMonitor(check_interval=0.1)

    mock_check = AsyncMock(return_value=True)
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")

    await monitor._check_single_exchange("bitget")
    mock_check.assert_called_once()


def test_health_to_dict():
    """ExchangeHealth se puede serializar a dict."""
    health = ExchangeHealth(exchange_id="bitget")
    health.record_success(latency_ms=100.0)
    health.record_success(latency_ms=200.0)

    data = health.to_dict()
    assert data["exchange_id"] == "bitget"
    assert data["status"] == "healthy"
    assert data["avg_latency_ms"] == 150.0
