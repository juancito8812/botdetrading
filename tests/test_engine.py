"""Tests para core/engine.py — TradingEngine (lógica de trading)."""

import asyncio
import json
import os
import tempfile
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from models.data_classes import Signal, Position


# ─── Helpers ─────────────────────────────────────────────────────────────────

SAMPLE_CONFIG = {
    "apalancamiento": 10,
    "modo_margen": "cross",
    "porcentaje_capital": {"bitget": 5.0, "bingx": 5.0},
    "cantidad_minima_usdt": 10.0,
    "cooldown_segundos": 30,
    "entrada_modalidad": "auto",
    "desviacion_maxima_porcentaje": 3.0,
    "timeout_orden_limit_minutos": 10,
    "dca_habilitado": True,
    "dca_partes": 3,
    "trailing_stop_habilitado": True,
    "trailing_activacion_porcentaje": 1.5,
    "trailing_distancia_porcentaje": 0.8,
    "auto_breakeven": True,
    "tp_distribucion": "progresivo",
    "tp_pesos": [50, 25, 15, 10],
}


def _sig(symbol="BTCUSDT", direction="Buy", entry_min=67000, entry_max=68000,
         stop_loss=66000, targets=None):
    """Crea un Signal de prueba."""
    return Signal(
        simbolo=symbol,
        direccion=direction,
        entry_min=entry_min,
        entry_max=entry_max,
        stop_loss=stop_loss,
        targets=targets or [69000, 70000, 71000],
    )


def _mock_client():
    """Crea un mock de cliente CCXT."""
    client = MagicMock()
    client.amount_to_precision = MagicMock(return_value="0.01")
    client.price_to_precision = MagicMock(return_value="67000.0")
    client.markets = {
        "BTC/USDT": {"swap": True, "future": False},
        "ETH/USDT": {"swap": True, "future": False},
    }
    return client


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _is_duplicate
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def engine():
    from core.engine import TradingEngine
    eng = TradingEngine()
    eng.processed_signals = {}
    return eng


def test_is_duplicate_new_signal(engine):
    """Señal nueva no es duplicada."""
    assert engine._is_duplicate("BTC", "Buy", "bitget", 30) is False


def test_is_duplicate_within_cooldown(engine):
    """Misma señal dentro del cooldown es duplicada."""
    engine._is_duplicate("BTC", "Buy", "bitget", 30)
    assert engine._is_duplicate("BTC", "Buy", "bitget", 30) is True


def test_is_duplicate_after_cooldown(engine):
    """Misma señal después del cooldown no es duplicada (simulado con timestamp antiguo)."""
    engine.processed_signals[("BTC", "Buy", "bitget")] = time.time() - 60
    assert engine._is_duplicate("BTC", "Buy", "bitget", 30) is False


def test_is_duplicate_different_exchange(engine):
    """Misma señal en distinto exchange no es duplicada."""
    engine._is_duplicate("BTC", "Buy", "bitget", 30)
    assert engine._is_duplicate("BTC", "Buy", "bingx", 30) is False


def test_is_duplicate_different_side(engine):
    """Misma señal con distinto lado no es duplicada."""
    engine._is_duplicate("BTC", "Buy", "bitget", 30)
    assert engine._is_duplicate("BTC", "Sell", "bitget", 30) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _calculate_tp_amounts
# ═══════════════════════════════════════════════════════════════════════════════

def test_calc_tp_amounts_empty_targets(engine):
    """Sin targets retorna lista vacía."""
    assert engine._calculate_tp_amounts(100.0, [], SAMPLE_CONFIG) == []


def test_calc_tp_amounts_equal(engine):
    """Distribución 'igual' divide equitativamente."""
    config = {**SAMPLE_CONFIG, "tp_distribucion": "igual"}
    result = engine._calculate_tp_amounts(100.0, [69000, 70000, 71000], config)
    assert len(result) == 3
    assert all(abs(v - 33.33) < 0.01 for v in result)  # 33.33 cada uno


def test_calc_tp_amounts_progresivo(engine):
    """Distribución 'progresivo' usa pesos 50/25/15/10."""
    config = {**SAMPLE_CONFIG, "tp_distribucion": "progresivo", "tp_pesos": [50, 25, 15, 10]}
    result = engine._calculate_tp_amounts(100.0, [69000, 70000, 71000, 72000], config)
    assert len(result) == 4
    assert abs(result[0] - 50.0) < 0.01  # 50% del total
    assert abs(result[1] - 25.0) < 0.01  # 25% del total
    assert abs(result[2] - 15.0) < 0.01  # 15% del total
    assert abs(result[3] - 10.0) < 0.01  # 10% del total


def test_calc_tp_amounts_progresivo_mas_targets_que_pesos(engine):
    """Si hay más targets que pesos, el último peso se repite."""
    config = {**SAMPLE_CONFIG, "tp_distribucion": "progresivo", "tp_pesos": [60, 30, 10]}
    result = engine._calculate_tp_amounts(100.0, [69000, 70000, 71000, 72000], config)
    assert len(result) == 4
    # Pesos: 60 + 30 + 10 + 10 = 110
    assert abs(result[0] - 54.55) < 0.02
    assert abs(result[3] - 9.09) < 0.02


def test_calc_tp_amounts_progresivo_menos_targets_que_pesos(engine):
    """Si hay menos targets que pesos, se trunca."""
    config = {**SAMPLE_CONFIG, "tp_distribucion": "progresivo", "tp_pesos": [50, 25, 15, 10]}
    result = engine._calculate_tp_amounts(100.0, [69000, 70000], config)
    assert len(result) == 2
    # Pesos: 50 + 25 = 75
    assert abs(result[0] - 66.67) < 0.02
    assert abs(result[1] - 33.33) < 0.02


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: stop_watchdog
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_stop_watchdog_no_task(engine):
    """stop_watchdog sin tarea activa no falla."""
    engine.stop_watchdog()  # Debe ser seguro llamarlo sin tarea
    assert engine._watchdog_task is None


@pytest.mark.asyncio
async def test_stop_watchdog_cancels_running(engine):
    """stop_watchdog cancela la tarea activa."""
    async def dummy():
        try:
            await asyncio.sleep(999)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(dummy())
    engine._watchdog_task = task
    assert not task.done()

    engine.stop_watchdog()
    assert engine._watchdog_task is None
    # Esperar a que la cancelación se procese
    await asyncio.sleep(0.01)
    assert task.done()
    assert task.cancelled()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _pending_limit_orders persistence
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def engine_with_temp_file():
    """Crea un engine con _PENDING_LIMITS_FILE temporal."""
    from core import engine as engine_module

    # Guardar ruta original y reemplazar
    original_path = engine_module._PENDING_LIMITS_FILE
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    engine_module._PENDING_LIMITS_FILE = type(original_path)(tmp.name)

    eng = engine_module.TradingEngine()
    eng._pending_limit_orders = {}

    yield eng

    # Cleanup
    engine_module._PENDING_LIMITS_FILE = original_path
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


def test_save_and_load_pending_limits(engine_with_temp_file):
    """Guardar y cargar órdenes LIMIT pendientes funciona correctamente."""
    eng = engine_with_temp_file
    test_data = {
        "order_123": {
            "exchange_id": "bitget",
            "market_symbol": "BTC/USDT",
            "amount": 0.01,
            "limit_price": 67000.0,
            "side": "buy",
            "timestamp": time.time(),
        }
    }
    eng._pending_limit_orders = test_data
    eng._save_pending_limits()

    # Crear nuevo engine que debería cargar los datos
    from core.engine import TradingEngine
    eng2 = TradingEngine()
    assert "order_123" in eng2._pending_limit_orders
    assert eng2._pending_limit_orders["order_123"]["exchange_id"] == "bitget"


def test_save_pending_limits_empty(engine_with_temp_file):
    """Guardar diccionario vacío no causa error."""
    eng = engine_with_temp_file
    eng._pending_limit_orders = {}
    eng._save_pending_limits()  # No debe lanzar


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _check_trailing_stop
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_trailing_disabled(engine):
    """Trailing no se activa si está deshabilitado."""
    config = {**SAMPLE_CONFIG, "trailing_stop_habilitado": False}
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="sl123", highest_price=68000)
    await engine._check_trailing_stop(pos, config, MagicMock())
    assert pos.trailing_activated is False


@pytest.mark.asyncio
async def test_trailing_no_sl(engine):
    """Trailing no se activa si no hay SL."""
    config = {**SAMPLE_CONFIG}
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id=None, highest_price=68000)
    await engine._check_trailing_stop(pos, config, MagicMock())
    assert pos.trailing_activated is False


@pytest.mark.asyncio
async def test_trailing_activates_long(engine):
    """Trailing se activa para LONG cuando la ganancia supera el umbral."""
    config = {**SAMPLE_CONFIG, "trailing_activacion_porcentaje": 1.0}
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="sl123", highest_price=68000)  # +1.49%
    await engine._check_trailing_stop(pos, config, MagicMock())
    assert pos.trailing_activated is True


@pytest.mark.asyncio
async def test_trailing_not_activate_below_threshold(engine):
    """Trailing NO se activa si la ganancia está por debajo del umbral."""
    config = {**SAMPLE_CONFIG, "trailing_activacion_porcentaje": 5.0}  # 5% requerido
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="sl123", highest_price=67500)  # +0.75%
    await engine._check_trailing_stop(pos, config, MagicMock())
    assert pos.trailing_activated is False


@pytest.mark.asyncio
async def test_trailing_skipped_if_breakeven(engine):
    """Trailing no se activa si ya está en break-even."""
    config = {**SAMPLE_CONFIG, "trailing_activacion_porcentaje": 1.0}
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="sl123", is_breakeven=True, highest_price=68000)
    await engine._check_trailing_stop(pos, config, MagicMock())
    assert pos.trailing_activated is False  # Breakeven gana


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _execute_market_entry
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_market_entry_no_client(engine):
    """Sin cliente, retorna error."""
    signal = _sig()
    result = await engine._execute_market_entry(
        "nonexistent", "BTC/USDT", signal, SAMPLE_CONFIG, 67000, 500.0, 10
    )
    assert result == (False, "Cliente no disponible")


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_market_entry_insufficient_balance(mock_ex_svc, engine):
    """Saldo insuficiente retorna error."""
    mock_client = _mock_client()
    mock_ex_svc.clients = {"bitget": mock_client}

    signal = _sig()
    result = await engine._execute_market_entry(
        "bitget", "BTC/USDT", signal, SAMPLE_CONFIG, 67000, 1.0, 10
    )
    assert result[0] is False
    assert "insuficiente" in result[1].lower()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_market_entry_success(mock_ex_svc, engine):
    """Orden MARKET ejecutada exitosamente retorna dict con entry data."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={
        "id": "order_abc", "average": 67050.0
    })
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_market_symbol = AsyncMock(return_value="BTC/USDT")
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67000.0)
    mock_ex_svc.get_balance = AsyncMock(return_value=500.0)
    mock_ex_svc.set_leverage = AsyncMock()

    signal = _sig()
    ok, result = await engine._execute_market_entry(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 67000, 500.0, 10
    )
    assert ok is True
    assert isinstance(result, dict)
    assert result["entry_price"] == 67050.0
    assert "order_id" in result
    assert result["amount"] == 0.01


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_market_entry_order_no_id(mock_ex_svc, engine):
    """Orden MARKET sin ID retorna error."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": None})
    mock_ex_svc.clients = {"bitget": mock_client}

    signal = _sig()
    ok, result = await engine._execute_market_entry(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 67000, 500.0, 10
    )
    assert ok is False
    assert "sin ID" in result.lower() or "ID" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _decide_entry_type (lógica de decisión)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_decide_market_no_entry_range(mock_ex_svc, engine):
    """Señal sin rango de entrada → siempre MARKET."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={
        "id": "market_1", "average": 67050.0
    })
    mock_ex_svc.clients = {"bitget": mock_client}

    signal = _sig(entry_min=None, entry_max=None)
    ok, result = await engine._decide_entry_type(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 67000, 500.0, 10
    )
    assert ok is True
    assert isinstance(result, dict)  # Es MARKET
    assert result["entry_price"] == 67050.0


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_decide_price_above_max_deviation(mock_ex_svc, engine):
    """Precio muy por encima del rango → rechazado."""
    signal = _sig(entry_min=67000, entry_max=68000)
    # Precio actual mucho más alto que el rango
    ok, result = await engine._decide_entry_type(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 75000, 500.0, 10
    )
    assert ok is False
    assert "desviación" in result.lower() or "sobre" in result.lower()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_decide_price_below_max_deviation(mock_ex_svc, engine):
    """Precio muy por debajo del rango (LONG) → rechazado."""
    signal = _sig(entry_min=67000, entry_max=68000)
    # Precio actual mucho más bajo que el rango
    ok, result = await engine._decide_entry_type(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 60000, 500.0, 10
    )
    assert ok is False
    assert "bajo" in result.lower()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_decide_limit_entry_placed(mock_ex_svc, engine):
    """Modalidad LIMIT con precio fuera de rango → coloca orden y retorna limit_placed."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "limit_1"})
    mock_client.amount_to_precision = MagicMock(return_value="0.01")
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67000.0)

    # Precio (69000) FUERA del rango de entrada (67000-68000) pero dentro de desviación máx (3%)
    config = {**SAMPLE_CONFIG, "entrada_modalidad": "limit", "dca_habilitado": False}
    signal = _sig()  # entry 67000-68000
    ok, result = await engine._decide_entry_type(
        "bitget", "BTC/USDT:USDT", signal, config, 69000, 500.0, 10
    )
    assert ok is True
    assert result == "limit_placed"
    # Verificar que se agregó a pending
    assert len(engine._pending_limit_orders) == 1


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_decide_dca_placed(mock_ex_svc, engine):
    """DCA habilitado con precio fuera de rango → coloca múltiples órdenes."""
    mock_client = _mock_client()
    # IDs distintos para cada orden DCA
    mock_client.create_order = AsyncMock(side_effect=[
        {"id": "dca_001"},
        {"id": "dca_002"},
        {"id": "dca_003"},
    ])
    mock_client.amount_to_precision = MagicMock(return_value="0.01")
    mock_client.price_to_precision = MagicMock(return_value="67500.0")
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67500.0)

    # Precio (68500) FUERA del rango (67000-68000), dentro de desviación máx → DCA
    # Balance alto para que alcance para 3 órdenes DCA (min 10 USDT cada una)
    config = {**SAMPLE_CONFIG, "entrada_modalidad": "auto", "dca_habilitado": True, "dca_partes": 3}
    signal = _sig(entry_min=67000, entry_max=68000)
    ok, result = await engine._decide_entry_type(
        "bitget", "BTC/USDT:USDT", signal, config, 68500, 5000.0, 10
    )
    assert ok is True
    assert result == "limit_placed"
    # Verificar que se crearon 3 órdenes DCA
    assert len(engine._pending_limit_orders) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _health_check_exchange
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_health_check_with_real_markets(mock_ex_svc, engine):
    """Health check usa mercados reales del exchange primero."""
    mock_client = _mock_client()
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(side_effect=lambda ex, sym:
        67500.0 if sym == "BTC/USDT" else 0.0)

    result = await engine._health_check_exchange("bitget")
    assert result is True


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_health_check_fallback_symbols(mock_ex_svc, engine):
    """Health check usa fallback si exchange no tiene markets."""
    mock_client = MagicMock()
    mock_client.markets = {}  # Sin mercados cargados
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67500.0)

    result = await engine._health_check_exchange("bitget")
    assert result is True


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_health_check_all_fail(mock_ex_svc, engine):
    """Si todos los símbolos fallan, retorna False."""
    mock_client = MagicMock()
    mock_client.markets = {}
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=0.0)

    result = await engine._health_check_exchange("bitget")
    assert result is False
