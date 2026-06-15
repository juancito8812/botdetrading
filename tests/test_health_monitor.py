import asyncio
import pytest
import time
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch

from utils.resilience.health_monitor import (
    HealthMonitor, ExchangeHealth, HealthStatus,
)


# ─── ExchangeHealth Tests ────────────────────────────────────────────────────


def test_health_initial_state():
    """ExchangeHealth comienza con estado healthy."""
    health = ExchangeHealth(exchange_id="bitget")
    assert health.status == HealthStatus.HEALTHY
    assert health.consecutive_failures == 0
    assert health.latencies_ms == []


def test_health_record_success():
    """Registrar un éxito resetea fallos y añade latencia."""
    health = ExchangeHealth(exchange_id="bitget")
    changed = health.record_success(latency_ms=150.0)
    assert changed is False  # mismo estado
    assert health.status == HealthStatus.HEALTHY
    assert health.consecutive_failures == 0
    assert len(health.latencies_ms) == 1
    assert health.avg_latency_ms == 150.0


def test_health_record_failure():
    """Fallos consecutivos cambian el estado."""
    health = ExchangeHealth(exchange_id="bitget", degraded_after=2, down_after=5)
    changed = health.record_failure()
    assert changed is False  # HEALTHY -> HEALTHY (aún no cruza umbral)
    assert health.status == HealthStatus.HEALTHY
    health.record_failure()
    assert health.status == HealthStatus.DEGRADED
    health.record_failure()
    health.record_failure()
    health.record_failure()
    assert health.status == HealthStatus.DOWN


def test_health_recovery_returns_changed():
    """record_success retorna True cuando había estado diferente."""
    health = ExchangeHealth(exchange_id="bitget", degraded_after=2, down_after=5)
    for _ in range(3):
        health.record_failure()
    assert health.status == HealthStatus.DEGRADED

    changed = health.record_success(latency_ms=100)
    assert changed is True  # DEGRADED -> HEALTHY
    assert health.status == HealthStatus.HEALTHY
    assert health.consecutive_failures == 0


def test_health_record_failure_returns_changed():
    """record_failure retorna True cuando cambia el estado."""
    health = ExchangeHealth(exchange_id="bitget", degraded_after=1, down_after=2)
    # Primer fallo: HEALTHY -> DEGRADED (cruza degraded_after=1)
    changed1 = health.record_failure()
    assert changed1 is True
    assert health.status == HealthStatus.DEGRADED

    # Segundo fallo: DEGRADED -> DOWN (cruza down_after=2)
    changed2 = health.record_failure()
    assert changed2 is True
    assert health.status == HealthStatus.DOWN

    # Tercer fallo: DOWN -> DOWN (sin cambio)
    changed3 = health.record_failure()
    assert changed3 is False
    assert health.status == HealthStatus.DOWN


def test_health_latency_max_entries():
    """ExchangeHealth mantiene máximo MAX_LATENCIES (5) entradas."""
    health = ExchangeHealth(exchange_id="bitget")
    for i in range(10):
        health.record_success(latency_ms=float(i * 10))
    assert len(health.latencies_ms) == 5
    # Últimas 5: 50,60,70,80,90 -> avg=70
    assert health.avg_latency_ms == pytest.approx(70.0)


def test_health_no_latency_avg():
    """Sin latencias, avg_latency_ms retorna 0.0."""
    health = ExchangeHealth(exchange_id="bitget")
    assert health.avg_latency_ms == 0.0


def test_health_last_ok_time_on_success():
    """record_success actualiza last_ok_time."""
    health = ExchangeHealth(exchange_id="bitget")
    before = time.time()
    health.record_success()
    assert health.last_ok_time is not None
    assert health.last_ok_time >= before


# ─── HealthMonitor Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_monitor_add_exchange():
    """HealthMonitor añade exchanges correctamente."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    monitor.add_exchange("bingx")

    assert "bitget" in monitor.get_summary()
    assert "bingx" in monitor.get_summary()


@pytest.mark.asyncio
async def test_health_monitor_add_exchange_duplicate():
    """Añadir exchange duplicado no crea entrada extra."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    monitor.add_exchange("bitget")  # duplicado
    assert len(monitor.get_summary()) == 1


@pytest.mark.asyncio
async def test_health_monitor_remove_exchange():
    """HealthMonitor elimina exchanges."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    monitor.add_exchange("bingx")
    monitor.remove_exchange("bitget")
    assert "bitget" not in monitor.get_summary()
    assert "bingx" in monitor.get_summary()


@pytest.mark.asyncio
async def test_health_monitor_remove_nonexistent():
    """Eliminar exchange que no existe no falla."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.remove_exchange("nonexistent")  # No debe lanzar


@pytest.mark.asyncio
async def test_health_monitor_get_health():
    """get_health retorna ExchangeHealth o None."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    health = monitor.get_health("bitget")
    assert health is not None
    assert health.exchange_id == "bitget"
    assert monitor.get_health("nonexistent") is None


@pytest.mark.asyncio
async def test_health_monitor_check_success():
    """Health check exitoso registra latencia y estado."""
    monitor = HealthMonitor(check_interval=0.1)

    mock_check = AsyncMock(return_value=True)
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")

    await monitor._check_single_exchange("bitget")
    mock_check.assert_called_once()
    health = monitor.get_health("bitget")
    assert health.status == HealthStatus.HEALTHY
    assert len(health.latencies_ms) == 1


@pytest.mark.asyncio
async def test_health_monitor_check_failure():
    """Health check fallido incrementa fallos consecutivos."""
    monitor = HealthMonitor(check_interval=0.1)

    mock_check = AsyncMock(return_value=False)
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")

    await monitor._check_single_exchange("bitget")
    health = monitor.get_health("bitget")
    assert health.consecutive_failures == 1


@pytest.mark.asyncio
async def test_health_monitor_check_exception():
    """Health check que lanza excepción cuenta como fallo."""
    monitor = HealthMonitor(check_interval=0.1)

    mock_check = AsyncMock(side_effect=ConnectionError("timeout"))
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")

    await monitor._check_single_exchange("bitget")
    health = monitor.get_health("bitget")
    assert health.consecutive_failures == 1


@pytest.mark.asyncio
async def test_health_monitor_check_none_func():
    """Sin health_check_func, _check_single_exchange no falla."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    await monitor._check_single_exchange("bitget")  # No debe lanzar


@pytest.mark.asyncio
async def test_health_monitor_check_nonexistent_exchange():
    """Check para exchange no registrado no falla."""
    monitor = HealthMonitor(check_interval=0.1)
    mock_check = AsyncMock(return_value=True)
    monitor.set_health_check_func(mock_check)
    await monitor._check_single_exchange("nonexistent")  # No debe lanzar
    mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_on_status_change_called():
    """on_status_change se llama cuando el estado cambia."""
    monitor = HealthMonitor(check_interval=0.1)
    on_change = AsyncMock()
    monitor.on_status_change = on_change

    mock_check = AsyncMock(return_value=False)
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")
    # Override degraded_after para que el primer fallo cambie a DEGRADED
    monitor.get_health("bitget").degraded_after = 1

    await monitor._check_single_exchange("bitget")
    on_change.assert_called_once()
    args = on_change.call_args[0]
    assert args[0] == "bitget"
    assert args[1] == "degraded"
    assert args[2] == 1  # consecutive_failures


@pytest.mark.asyncio
async def test_on_status_change_not_called_no_change():
    """on_status_change NO se llama si el estado no cambia."""
    monitor = HealthMonitor(check_interval=0.1)
    on_change = AsyncMock()
    monitor.on_status_change = on_change

    mock_check = AsyncMock(return_value=True)  # ya es healthy, no cambia
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")

    await monitor._check_single_exchange("bitget")
    on_change.assert_not_called()


@pytest.mark.asyncio
async def test_run_cycle_calls_all():
    """_run_cycle ejecuta health check para todos los exchanges."""
    monitor = HealthMonitor(check_interval=0.1)
    mock_check = AsyncMock(return_value=True)
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")
    monitor.add_exchange("bingx")

    await monitor._run_cycle()
    assert mock_check.call_count == 2


@pytest.mark.asyncio
async def test_sync_circuit_breaker_states():
    """sync_circuit_breaker_states actualiza el estado de CB en health."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")

    cb_bitget = MagicMock()
    cb_bitget.state.value = "open"
    cbs = {"bitget": cb_bitget}

    monitor.sync_circuit_breaker_states(cbs)
    assert monitor.get_health("bitget").circuit_breaker_state == "open"


@pytest.mark.asyncio
async def test_sync_circuit_breaker_states_no_health():
    """sync_circuit_breaker_states no falla si exchange no está en health_map."""
    monitor = HealthMonitor(check_interval=0.1)
    cb = MagicMock()
    cb.state.value = "open"
    monitor.sync_circuit_breaker_states({"nonexistent": cb})  # No debe lanzar


@pytest.mark.asyncio
async def test_start_stops_loop():
    """start y stop controlan el loop correctamente."""
    monitor = HealthMonitor(check_interval=0.05)

    mock_check = AsyncMock(return_value=True)
    monitor.set_health_check_func(mock_check)
    monitor.add_exchange("bitget")

    # Iniciar el monitor en una tarea y esperar un ciclo
    task = asyncio.create_task(monitor.start())
    await asyncio.sleep(0.06)  # Esperar un ciclo
    await monitor.stop()
    await task

    assert monitor._running is False
    assert mock_check.called


@pytest.mark.asyncio
async def test_start_already_running():
    """start no hace nada si ya está corriendo."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor._running = True
    await monitor.start()  # No debe lanzar ni reiniciar
    assert monitor._running is True


def test_persist(tmp_path):
    """persist guarda health data a JSON."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    monitor.get_health("bitget").record_success(latency_ms=100.0)

    filepath = os.path.join(tmp_path, "health.json")
    monitor.persist(filepath)

    with open(filepath) as f:
        data = json.load(f)
    assert "bitget" in data
    assert data["bitget"]["status"] == "healthy"


def test_persist_empty():
    """persist con health_map vacío no falla."""
    monitor = HealthMonitor(check_interval=0.1)
    with patch("builtins.open", MagicMock()):
        monitor.persist("/fake/path.json")  # No debe lanzar


@pytest.mark.asyncio
async def test_get_summary():
    """get_summary retorna dict con resumen de todos los exchanges."""
    monitor = HealthMonitor(check_interval=0.1)
    monitor.add_exchange("bitget")
    monitor.add_exchange("bingx")

    summary = monitor.get_summary()
    assert len(summary) == 2
    assert "bitget" in summary
    assert "bingx" in summary
    assert summary["bitget"]["status"] == "healthy"
