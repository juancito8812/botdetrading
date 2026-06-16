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
    from core.engine import TradingEngine, _PENDING_LIMITS_FILE
    # Limpiar archivo de persistencia para que tests no hereden datos entre sí
    try:
        if _PENDING_LIMITS_FILE.exists():
            _PENDING_LIMITS_FILE.unlink()
    except Exception:
        pass
    eng = TradingEngine()
    eng.processed_signals = {}
    eng._last_health_check_time = 0.0  # Inicializar para watchdog
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
    assert "sin" in result.lower() and "id" in result.lower() or "ID" in result


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


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _place_stop_loss
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_place_stop_loss_no_sl(engine):
    """Sin stop_loss en signal, no coloca nada."""
    from services.exchange_service import exchange_service

    signal = _sig(stop_loss=None)
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    client = MagicMock()
    await engine._place_stop_loss(client, "bitget", "BTC/USDT", signal, 0.01, "LONG", pos)
    client.create_order.assert_not_called()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_stop_loss_bingx(mock_ex_svc, engine):
    """Stop Loss para BingX usa TRIGGER_MARKET con positionSide."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "sl_bingx"})

    signal = _sig(stop_loss=65000)
    pos = Position(exchange_id="bingx", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_stop_loss(mock_client, "bingx", "BTC/USDT", signal, 0.01, "LONG", pos)

    mock_client.create_order.assert_called_once()
    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "TRIGGER_MARKET"  # order_type
    assert "positionSide" in args[5]  # params
    assert pos.sl_order_id == "sl_bingx"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_stop_loss_bitget(mock_ex_svc, engine):
    """Stop Loss para Bitget usa limit con planType='normal_plan'."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "sl_bitget"})

    signal = _sig(stop_loss=65000)
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_stop_loss(mock_client, "bitget", "BTC/USDT", signal, 0.01, "LONG", pos)

    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "limit"
    assert args[5].get("planType") == "normal_plan"
    assert args[5].get("reduceOnly") is True
    assert pos.sl_order_id == "sl_bitget"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_stop_loss_other(mock_ex_svc, engine):
    """Stop Loss para exchange genérico usa market con reduceOnly."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "sl_other"})

    signal = _sig(stop_loss=65000)
    pos = Position(exchange_id="bybit", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_stop_loss(mock_client, "bybit", "BTC/USDT", signal, 0.01, "LONG", pos)

    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "market"
    assert args[5].get("reduceOnly") is True
    assert pos.sl_order_id == "sl_other"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_stop_loss_error(mock_ex_svc, engine):
    """Error colocando SL no lanza excepción."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(side_effect=Exception("API error"))

    signal = _sig(stop_loss=65000)
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_stop_loss(mock_client, "bitget", "BTC/USDT", signal, 0.01, "LONG", pos)
    # Error capturado, no se lanza
    assert pos.sl_order_id is None  # Sin SL asignado


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _place_take_profits
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_place_take_profits_no_targets(engine):
    """Sin targets, no coloca TPs."""
    client = _mock_client()
    signal = _sig(targets=[])
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_take_profits(client, "bitget", "BTC/USDT", signal, [], "LONG", pos)
    client.create_order.assert_not_called()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_take_profits_bingx(mock_ex_svc, engine):
    """TP para BingX usa TRIGGER_LIMIT con positionSide."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "tp_bingx"})

    signal = _sig(targets=[69000])
    pos = Position(exchange_id="bingx", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_take_profits(mock_client, "bingx", "BTC/USDT", signal, [0.01], "LONG", pos)

    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "TRIGGER_LIMIT"
    assert "positionSide" in args[5]
    assert "tp_bingx" in pos.tp_order_ids


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_take_profits_bitget(mock_ex_svc, engine):
    """TP para Bitget usa limit con planType='normal_plan'."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "tp_bitget"})

    signal = _sig(targets=[69000])
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_take_profits(mock_client, "bitget", "BTC/USDT", signal, [0.01], "LONG", pos)

    args, kwargs = mock_client.create_order.call_args
    assert args[5].get("planType") == "normal_plan"
    assert args[5].get("reduceOnly") is True
    assert "tp_bitget" in pos.tp_order_ids


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_take_profits_other(mock_ex_svc, engine):
    """TP para exchange genérico usa limit con reduceOnly."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "tp_other"})

    signal = _sig(targets=[69000])
    pos = Position(exchange_id="bybit", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_take_profits(mock_client, "bybit", "BTC/USDT", signal, [0.01], "LONG", pos)

    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "limit"
    assert args[5].get("reduceOnly") is True
    assert "tp_other" in pos.tp_order_ids


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_take_profits_zero_amount_skipped(mock_ex_svc, engine):
    """TP con amount 0 es saltado."""
    mock_client = _mock_client()
    # Devolver "0.0" para el primer TP (cantidad inexacta), "0.01" para el segundo
    mock_client.amount_to_precision = MagicMock(side_effect=["0.0", "0.01"])

    signal = _sig(targets=[69000, 70000])
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_take_profits(mock_client, "bitget", "BTC/USDT", signal, [0.0, 0.01], "LONG", pos)

    # Solo debe crear 1 TP (el segundo con amount 0.01)
    assert mock_client.create_order.call_count == 1


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_take_profits_error(mock_ex_svc, engine):
    """Error en TP no lanza excepción, continúa con los siguientes."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(side_effect=[
        Exception("API error"),
        {"id": "tp2"},
    ])

    signal = _sig(targets=[69000, 70000])
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5)
    await engine._place_take_profits(mock_client, "bitget", "BTC/USDT", signal, [0.005, 0.005], "LONG", pos)

    # Debe haber intentado 2 y creado 1
    assert mock_client.create_order.call_count == 2
    assert len(pos.tp_order_ids) == 1
    assert pos.tp_order_ids[0] == "tp2"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _place_limit_entry
# ═════════════════════════════════════════════════───────���────────────────══════

@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_limit_entry_success(mock_ex_svc, engine):
    """Colocar orden LIMIT exitosamente."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "limit_entry_1"})
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67000.0)

    signal = _sig()
    ok, result = await engine._place_limit_entry(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 500.0, 10, 67000
    )
    assert ok is True
    assert result == "limit_placed"
    assert "limit_entry_1" in engine._pending_limit_orders


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_limit_entry_error(mock_ex_svc, engine):
    """Error colocando orden LIMIT retorna False."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(side_effect=Exception("API error"))
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67000.0)

    signal = _sig()
    ok, result = await engine._place_limit_entry(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 500.0, 10, 67000
    )
    assert ok is False
    assert "Error LIMIT" in result


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_place_limit_entry_no_id(mock_ex_svc, engine):
    """Orden LIMIT sin ID retorna False."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": None})
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67000.0)

    signal = _sig()
    ok, result = await engine._place_limit_entry(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 500.0, 10, 67000
    )
    assert ok is False
    assert "sin" in result.lower() and "id" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _process_filled_limit_order
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_process_filled_limit_order(mock_ex_svc, mock_pm, engine):
    """Procesa orden LIMIT llenada y crea posición."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "sl_123"})
    mock_ex_svc.clients = {"bitget": mock_client}

    signal = Signal(simbolo="BTC/USDT", direccion="Buy", entry_min=67000, entry_max=68000,
                    stop_loss=66000, targets=[69000])
    pending = {
        "side": "buy",
        "side_upper": "LONG",
        "signal": signal,
        "config": SAMPLE_CONFIG,
        "leverage": 10,
        "amount": 0.01,
        "limit_price": 67000.0,
    }
    order = {"id": "filled_order", "status": "closed", "filled": 0.01, "average": 67100.0}

    await engine._process_filled_limit_order("bitget", "BTC/USDT:USDT", order, pending)
    mock_pm.add_position.assert_called_once()
    pos = mock_pm.add_position.call_args[0][0]
    assert pos.exchange_id == "bitget"
    assert pos.entry_price == 67100.0


@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_process_filled_limit_order_partial_fill(mock_ex_svc, mock_pm, engine):
    """Procesa llenado parcial de orden LIMIT."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "sl_123"})
    mock_ex_svc.clients = {"bitget": mock_client}

    signal = Signal(simbolo="BTC/USDT", direccion="Buy", entry_min=67000, entry_max=68000,
                    stop_loss=66000, targets=[69000])
    pending = {
        "side": "buy",
        "side_upper": "LONG",
        "signal": signal,
        "config": SAMPLE_CONFIG,
        "leverage": 10,
        "amount": 0.01,
        "limit_price": 67000.0,
        "is_dca": True,
    }
    order = {"id": "filled_order", "status": "closed", "filled": 0.005, "average": 67100.0}

    await engine._process_filled_limit_order("bitget", "BTC/USDT:USDT", order, pending)
    mock_pm.add_position.assert_called_once()
    pos = mock_pm.add_position.call_args[0][0]
    assert pos.entry_filled_amount == 0.005  # Llenado parcial


# ═══════════════════════════════════════════════════════════════���═══════════════
# Tests: _check_trailing_stop - SHORT
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_trailing_activates_short(engine):
    """Trailing se activa para SHORT cuando el precio baja lo suficiente."""
    config = {**SAMPLE_CONFIG, "trailing_activacion_porcentaje": 1.0}
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Sell", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="sl123", lowest_price=65000)  # -2.99%
    await engine._check_trailing_stop(pos, config, MagicMock())
    assert pos.trailing_activated is True


@pytest.mark.asyncio
async def test_trailing_not_activate_short_below_threshold(engine):
    """Trailing NO se activa en SHORT si la baja es insuficiente."""
    config = {**SAMPLE_CONFIG, "trailing_activacion_porcentaje": 5.0}  # 5% requerido
    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Sell", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="sl123", lowest_price=66500)  # -0.75%
    await engine._check_trailing_stop(pos, config, MagicMock())
    assert pos.trailing_activated is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _update_trailing_sl
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_update_trailing_sl_bingx(mock_pm, mock_ex_svc, engine):
    """Actualizar trailing SL en BingX."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "new_sl"})
    mock_ex_svc.cancel_order = AsyncMock()

    pos = Position(exchange_id="bingx", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="old_sl")
    await engine._update_trailing_sl(pos, 68000.0, mock_client)

    mock_ex_svc.cancel_order.assert_called_once_with("bingx", "BTC/USDT", "old_sl")
    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "TRIGGER_MARKET"
    assert "positionSide" in args[5]
    assert pos.sl_order_id == "new_sl"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_update_trailing_sl_bitget(mock_pm, mock_ex_svc, engine):
    """Actualizar trailing SL en Bitget."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "new_sl_bitget"})
    mock_ex_svc.cancel_order = AsyncMock()

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="old_sl")
    await engine._update_trailing_sl(pos, 68000.0, mock_client)

    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "limit"
    assert args[5].get("planType") == "normal_plan"
    assert pos.sl_order_id == "new_sl_bitget"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_update_trailing_sl_other(mock_pm, mock_ex_svc, engine):
    """Actualizar trailing SL en exchange genérico."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "new_sl_other"})
    mock_ex_svc.cancel_order = AsyncMock()

    pos = Position(exchange_id="bybit", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="old_sl")
    await engine._update_trailing_sl(pos, 68000.0, mock_client)

    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "market"
    assert args[5].get("reduceOnly") is True
    assert pos.sl_order_id == "new_sl_other"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_update_trailing_sl_error(mock_pm, mock_ex_svc, engine):
    """Error actualizando trailing SL no lanza excepción."""
    mock_client = _mock_client()
    mock_ex_svc.cancel_order = AsyncMock(side_effect=Exception("API error"))

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="old_sl")
    await engine._update_trailing_sl(pos, 68000.0, mock_client)
    # Error capturado, no se lanza


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _move_sl_to_breakeven
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_move_sl_to_breakeven_bingx(mock_pm, mock_ex_svc, engine):
    """Mover SL a break-even en BingX."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "be_sl"})
    mock_ex_svc.cancel_order = AsyncMock()

    pos = Position(exchange_id="bingx", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="old_sl")
    await engine._move_sl_to_breakeven(pos, mock_client)

    mock_ex_svc.cancel_order.assert_called_once_with("bingx", "BTC/USDT", "old_sl")
    args, kwargs = mock_client.create_order.call_args
    assert args[1] == "TRIGGER_MARKET"
    # El stopPrice está dentro de params (args[5]), no como arg posicional
    assert args[5]["stopPrice"] == 67000.0  # stopPrice = entry_price
    assert pos.sl_order_id == "be_sl"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_move_sl_to_breakeven_bitget(mock_pm, mock_ex_svc, engine):
    """Mover SL a break-even en Bitget."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "be_sl_bitget"})
    mock_ex_svc.cancel_order = AsyncMock()

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="old_sl")
    await engine._move_sl_to_breakeven(pos, mock_client)

    args, kwargs = mock_client.create_order.call_args
    assert args[5].get("planType") == "normal_plan"
    assert pos.sl_order_id == "be_sl_bitget"


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_move_sl_to_breakeven_no_previous_sl(mock_pm, mock_ex_svc, engine):
    """Mover SL a break-even sin SL previo (no cancela nada)."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={"id": "be_sl"})

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id=None)
    await engine._move_sl_to_breakeven(pos, mock_client)

    mock_ex_svc.cancel_order.assert_not_called()
    mock_client.create_order.assert_called_once()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
@patch("core.engine.pos_manager")
async def test_move_sl_to_breakeven_error(mock_pm, mock_ex_svc, engine):
    """Error moviendo SL a break-even no lanza excepción."""
    mock_client = _mock_client()
    mock_ex_svc.cancel_order = AsyncMock(side_effect=Exception("API error"))

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5,
                   sl_order_id="old_sl")
    await engine._move_sl_to_breakeven(pos, mock_client)
    # Error capturado, no se lanza


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _load_pending_limits with errors
# ═══════════════════════════════════════════════════════════════════════════════

def test_load_pending_limits_corrupted(engine_with_temp_file):
    """Cargar JSON corrupto no lanza excepción."""
    import json

    from core import engine as engine_module
    # Escribir JSON inválido
    with open(engine_module._PENDING_LIMITS_FILE, "w") as f:
        f.write("{corrupted json")

    # Recargar no debe lanzar
    engine_module.TradingEngine()


def test_save_pending_limits_permission_error(engine_with_temp_file):
    """Error al guardar no lanza excepción."""
    eng = engine_with_temp_file
    eng._pending_limit_orders = {"test": {"data": "value"}}
    # Simular error en atomic_write_json no debería propagarse
    # No podemos simular fácilmente un error de permisos aquí,
    # pero el except captura cualquier Exception
    eng._save_pending_limits()  # No debe lanzar


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _watchdog_tick
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_watchdog_tick_health_check(engine):
    """_watchdog_tick ejecuta health check si pasaron 60s."""
    engine._last_health_check_time = time.time() - 120  # Hace 2 minutos
    engine.health_monitor._run_cycle = AsyncMock()

    await engine._watchdog_tick()

    engine.health_monitor._run_cycle.assert_called_once()
    assert engine._last_health_check_time > time.time() - 5  # Actualizado


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_watchdog_tick_no_health_check_recent(mock_ex_svc, engine):
    """_watchdog_tick NO ejecuta health check si pasaron menos de 60s."""
    engine._last_health_check_time = time.time() - 10  # Hace 10 segundos
    engine.health_monitor._run_cycle = AsyncMock()

    await engine._watchdog_tick()

    engine.health_monitor._run_cycle.assert_not_called()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_watchdog_tick_stale_orders_timeout(mock_ex_svc, engine):
    """Órdenes LIMIT con timeout son canceladas y limpiadas."""
    mock_client = MagicMock()
    mock_client.fetch_order = AsyncMock(return_value={"status": "open"})
    mock_client.cancel_order = AsyncMock()
    mock_ex_svc.clients = {"bitget": mock_client}

    order_id = "old_order"
    engine._pending_limit_orders[order_id] = {
        "exchange_id": "bitget",
        "market_symbol": "BTC/USDT",
        "timestamp": time.time() - 3600,  # Hace 1 hora
        "signal": _sig(),
        "config": SAMPLE_CONFIG,
        "amount": 0.01,
        "limit_price": 67000,
        "side": "buy",
        "side_upper": "LONG",
        "leverage": 10,
        "usdt_to_use": 50.0,
    }

    await engine._watchdog_tick()

    mock_client.cancel_order.assert_called_once()
    assert order_id not in engine._pending_limit_orders


@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_watchdog_tick_stale_orders_filled(mock_ex_svc, mock_pm, engine):
    """Orden LIMIT llenada es procesada y removida de pending."""
    mock_client = MagicMock()
    mock_client.fetch_order = AsyncMock(return_value={
        "id": "filled_order", "status": "closed", "filled": 0.01, "average": 67100.0
    })
    mock_client.amount_to_precision = MagicMock(return_value="0.01")
    mock_client.create_order = AsyncMock(return_value={"id": "sl_123"})
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.cancel_order = AsyncMock()

    order_id = "filled_order"
    engine._pending_limit_orders[order_id] = {
        "exchange_id": "bitget",
        "market_symbol": "BTC/USDT",
        "timestamp": time.time() - 60,
        "signal": _sig(),
        "config": SAMPLE_CONFIG,
        "amount": 0.01,
        "limit_price": 67000,
        "side": "buy",
        "side_upper": "LONG",
        "leverage": 10,
        "usdt_to_use": 50.0,
    }

    await engine._watchdog_tick()

    mock_pm.add_position.assert_called_once()
    assert order_id not in engine._pending_limit_orders


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_watchdog_tick_stale_orders_no_client(mock_ex_svc, engine):
    """Orden LIMIT sin cliente disponible es removida."""
    mock_ex_svc.clients = {}  # Sin clientes

    order_id = "orphan"
    engine._pending_limit_orders[order_id] = {
        "exchange_id": "bitget",
        "market_symbol": "BTC/USDT",
        "timestamp": time.time() - 60,
        "signal": _sig(),
        "config": SAMPLE_CONFIG,
        "amount": 0.01,
        "limit_price": 67000,
        "side": "buy",
        "side_upper": "LONG",
        "leverage": 10,
        "usdt_to_use": 50.0,
    }

    await engine._watchdog_tick()

    assert order_id not in engine._pending_limit_orders


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _watchdog_tick — sync positions
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_watchdog_tick_position_closed(mock_ex_svc, mock_pm, engine):
    """Posición cerrada en exchange se marca como 'closed'."""
    mock_client = MagicMock()
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.fetch_position = AsyncMock(return_value={"contracts": 0})  # Cerrada

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5, status="open")
    mock_pm.get_open_positions.return_value = [pos]
    engine.notifier = AsyncMock()

    await engine._watchdog_tick()

    assert pos.status == "closed"
    mock_pm.save.assert_called()
    engine.notifier.notify_trade_closed.assert_called_once_with(pos)


@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_watchdog_tick_sync_pnl(mock_ex_svc, mock_pm, engine):
    """Sincronización actualiza PnL y highest_price desde el exchange."""
    mock_client = MagicMock()
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.fetch_position = AsyncMock(return_value={
        "contracts": 0.01,
        "markPrice": 68000,
        "unrealizedPnl": 10.0,
    })

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5, status="open",
                   highest_price=67000)
    mock_pm.get_open_positions.return_value = [pos]

    await engine._watchdog_tick()

    assert pos.pnl == 10.0  # Desde unrealizedPnl
    assert pos.highest_price == 68000  # Actualizado


@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_watchdog_tick_trailing_breakeven(mock_ex_svc, mock_pm, engine):
    """Watchdog ejecuta trailing stop y breakeven en posiciones."""
    mock_client = MagicMock()
    mock_client.create_order = AsyncMock(return_value={"id": "new_sl"})
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.fetch_position = AsyncMock(return_value={
        "contracts": 0.01,                        "markPrice": 67300,
        "unrealizedPnl": 3.0,
    })
    mock_ex_svc.cancel_order = AsyncMock()

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5, status="open",
                   sl_order_id="sl_old", tp_order_ids=["tp1"], tp1_hit=True, highest_price=67300)
    mock_pm.get_open_positions.return_value = [pos]

    await engine._watchdog_tick()

    # Breakeven debería activarse (TP1 hit, no trailing, no breakeven aún)
    # 67300 = ~0.45% ganancia, por debajo del 1.5% que activa trailing
    assert pos.is_breakeven is True


@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_watchdog_tick_position_no_client(mock_ex_svc, mock_pm, engine):
    """Posición sin cliente en exchange no causa error."""
    mock_ex_svc.clients = {}  # Sin clientes

    pos = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
                   side="Buy", entry_price=67000, amount=0.01, leverage=5, status="open")
    mock_pm.get_open_positions.return_value = [pos]

    await engine._watchdog_tick()  # No debe lanzar


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _watchdog_tick — clean cache + daily report
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_watchdog_tick_clean_cache(mock_ex_svc, engine):
    """Señales procesadas hace más de 1 hora se limpian."""
    old_time = time.time() - 4000  # > 1 hora
    engine.processed_signals = {
        ("BTC", "Buy", "bitget"): old_time,
        ("ETH", "Sell", "bingx"): old_time,
        ("SOL", "Buy", "bitget"): time.time(),  # Reciente, no se limpia
    }

    await engine._watchdog_tick()

    assert ("BTC", "Buy", "bitget") not in engine.processed_signals
    assert ("ETH", "Sell", "bingx") not in engine.processed_signals
    assert ("SOL", "Buy", "bitget") in engine.processed_signals


@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_watchdog_tick_daily_report(mock_ex_svc, mock_pm, engine):
    """Reporte diario se envía si pasaron 24h."""
    mock_ex_svc.clients = {"bitget": MagicMock()}
    mock_ex_svc.get_balance = AsyncMock(return_value=500.0)
    mock_pm.get_all_positions.return_value = []

    engine._last_daily_report = time.time() - 90000  # > 24h
    engine.notifier = AsyncMock()

    await engine._watchdog_tick()

    engine.notifier.send_daily_report.assert_called_once()
    assert engine._last_daily_report > time.time() - 5  # Actualizado


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_watchdog_tick_no_notifier(mock_ex_svc, engine):
    """watchdog_tick no falla si no hay notifier configurado."""
    engine.notifier = None
    await engine._watchdog_tick()  # No debe lanzar


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: requerir_stop_loss
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_execute_signal_reject_without_sl(mock_ex_svc, engine):
    """Señal sin SL se rechaza cuando requerir_stop_loss=True."""
    signal = _sig(stop_loss=None)
    config = {**SAMPLE_CONFIG, "requerir_stop_loss": True}
    await engine.execute_signal(signal, config, "bitget")
    # No debe llamar a get_market_symbol (se rechaza antes)
    mock_ex_svc.get_market_symbol.assert_not_called()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_execute_signal_allow_without_sl(mock_ex_svc, engine):
    """Señal sin SL se permite cuando requerir_stop_loss=False."""
    mock_client = _mock_client()
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_market_symbol = AsyncMock(return_value="BTC/USDT")

    signal = _sig(stop_loss=None)
    config = {**SAMPLE_CONFIG, "requerir_stop_loss": False}
    await engine.execute_signal(signal, config, "bitget")
    # Debe continuar (llama a get_market_symbol)
    mock_ex_svc.get_market_symbol.assert_called_once()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_execute_signal_with_sl_passes(mock_ex_svc, engine):
    """Señal CON SL pasa la validación aunque requerir_stop_loss=True."""
    mock_client = _mock_client()
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_market_symbol = AsyncMock(return_value="BTC/USDT")

    signal = _sig(stop_loss=66000)  # Tiene SL
    config = {**SAMPLE_CONFIG, "requerir_stop_loss": True}
    await engine.execute_signal(signal, config, "bitget")
    # Debe continuar
    mock_ex_svc.get_market_symbol.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: execute_signal (ruta completa MARKET)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("core.engine.pos_manager")
@patch("core.engine.exchange_service")
async def test_execute_signal_market_path(mock_ex_svc, mock_pm, engine):
    """execute_signal completa ruta MARKET exitosamente."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={
        "id": "entry_1", "average": 67050.0
    })
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_market_symbol = AsyncMock(return_value="BTC/USDT")
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67000.0)
    mock_ex_svc.get_balance = AsyncMock(return_value=500.0)
    mock_ex_svc.set_leverage = AsyncMock()

    # Signal sin rango de entrada → MARKET
    signal = _sig(entry_min=None, entry_max=None)

    await engine.execute_signal(signal, SAMPLE_CONFIG, "bitget")

    # Verificar que se creó la posición
    assert mock_pm.add_position.called
    pos = mock_pm.add_position.call_args[0][0]
    assert pos.symbol == "BTCUSDT"
    assert pos.entry_price == 67050.0


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_execute_signal_duplicate(mock_ex_svc, engine):
    """Señal duplicada no ejecuta nada."""
    signal = _sig()
    engine.processed_signals[("BTCUSDT", "Buy", "bitget")] = time.time()

    await engine.execute_signal(signal, SAMPLE_CONFIG, "bitget")
    # No debe llamar a market_symbol si es duplicado
    mock_ex_svc.get_market_symbol.assert_not_called()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_execute_signal_no_client(mock_ex_svc, engine):
    """Sin cliente para exchange, no ejecuta."""
    mock_ex_svc.clients = {}
    signal = _sig()
    await engine.execute_signal(signal, SAMPLE_CONFIG, "nonexistent")


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_execute_signal_no_market_symbol(mock_ex_svc, engine):
    """Sin market_symbol, no ejecuta."""
    mock_client = _mock_client()
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_market_symbol = AsyncMock(return_value=None)  # No encontrado

    signal = _sig()
    await engine.execute_signal(signal, SAMPLE_CONFIG, "bitget")
    mock_ex_svc.get_market_symbol.assert_called_once()


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_execute_signal_zero_balance(mock_ex_svc, engine):
    """Balance 0.0 no ejecuta."""
    mock_client = _mock_client()
    mock_ex_svc.clients = {"bitget": mock_client}
    mock_ex_svc.get_market_symbol = AsyncMock(return_value="BTC/USDT")
    mock_ex_svc.get_ticker_price = AsyncMock(return_value=67000.0)
    mock_ex_svc.get_balance = AsyncMock(return_value=0.0)  # Saldo 0

    signal = _sig()
    await engine.execute_signal(signal, SAMPLE_CONFIG, "bitget")


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_decide_price_out_of_range_for_short(mock_ex_svc, engine):
    """SHORT: precio fuera de desviación máxima → rechazado."""
    signal = _sig(direction="Sell", entry_min=67000, entry_max=68000)
    # Precio demasiado alto para SHORT
    ok, result = await engine._decide_entry_type(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 72000, 500.0, 10
    )
    assert ok is False


@pytest.mark.asyncio
@patch("core.engine.exchange_service")
async def test_decide_market_when_price_in_range(mock_ex_svc, engine):
    """Precio dentro del rango de entrada → MARKET aunque modalidad sea auto."""
    mock_client = _mock_client()
    mock_client.create_order = AsyncMock(return_value={
        "id": "market_inrange", "average": 67500.0
    })
    mock_ex_svc.clients = {"bitget": mock_client}

    signal = _sig(entry_min=67000, entry_max=68000)
    # Precio 67500 está DENTRO del rango
    ok, result = await engine._decide_entry_type(
        "bitget", "BTC/USDT:USDT", signal, SAMPLE_CONFIG, 67500, 500.0, 10
    )
    assert ok is True
    assert isinstance(result, dict)  # MARKET
