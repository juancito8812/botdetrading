"""Tests para services/exchange_service.py — ExchangeService (clients CCXT)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from services.exchange_service import (
    ExchangeService, exchange_service,
    _get_circuit_breaker, _circuit_breakers,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _mock_client():
    """Crea un mock de cliente CCXT con métodos async comunes."""
    client = MagicMock()
    client.load_markets = AsyncMock()
    client.load_time_difference = AsyncMock()
    client.close = AsyncMock()
    client.markets = {
        "BTC/USDT": {"swap": True, "future": False},
        "ETH/USDT": {"swap": True, "future": False},
        "BTC/USDT:USDT": {"swap": True, "future": False},
    }
    client.fetch_balance = AsyncMock(return_value={
        "USDT": {"free": 500.0, "available": 500.0, "total": 500.0},
    })
    client.fetch_ticker = AsyncMock(return_value={"last": 67500.0})
    client.set_margin_mode = AsyncMock()
    client.set_leverage = AsyncMock()
    client.set_position_mode = AsyncMock()
    client.fetch_positions = AsyncMock(return_value=[
        {"symbol": "BTC/USDT", "contracts": 0.01, "entryPrice": 67000.0},
    ])
    client.cancel_order = AsyncMock(return_value=None)
    return client


def _mock_ccxt_exchange(config: dict = None):
    """Crea una clase mock de exchange CCXT que retorna un cliente mock."""
    client = _mock_client()
    cls = MagicMock(return_value=client)
    if config:
        cls.return_value = _mock_client_with_config(config)
    return cls, client


def _mock_client_with_config(config: dict):
    """Crea mock client con fetch_balance personalizado."""
    client = _mock_client()
    client.fetch_balance = AsyncMock(return_value=config.get("balance", {
        "USDT": {"free": 500.0, "available": 500.0, "total": 500.0},
    }))
    return client


def _mock_creds(exchange_id: str = "bitget", enabled: bool = True, needs_passphrase: bool = True):
    """Crea credenciales mock para un exchange."""
    from utils.config import EXCHANGES_DEFAULTS
    creds = {"exchanges": {}, "telegram": {"API_ID": "123", "API_HASH": "abc", "PHONE_NUMBER": "+000"}}

    needs_pp = EXCHANGES_DEFAULTS.get(exchange_id, {}).get("needs_passphrase", False)
    creds["exchanges"][exchange_id] = {
        "api_key": "test_key",
        "secret": "test_secret",
        "passphrase": "test_pass" if needs_pp else "",
        "enabled": enabled,
    }
    return creds


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_state():
    """Limpia circuit breakers y estado global antes de cada test."""
    _circuit_breakers.clear()
    exchange_service.clients.clear()
    exchange_service.failed_exchanges.clear()


@pytest.fixture
def svc():
    """Crea una instancia fresca de ExchangeService."""
    return ExchangeService()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _get_circuit_breaker (module-level)
# ═══════════════════════════════════════════════════════════════════════════════

def test_get_circuit_breaker_creates_new():
    """_get_circuit_breaker crea un nuevo CB para un exchange desconocido."""
    cb = _get_circuit_breaker("nonexistent")
    assert cb is not None
    assert cb.name == "nonexistent"
    assert cb.failure_threshold == 5
    assert cb.reset_timeout == 60


def test_get_circuit_breaker_returns_existing():
    """_get_circuit_breaker retorna el CB existente si ya fue creado."""
    cb1 = _get_circuit_breaker("bitget")
    cb2 = _get_circuit_breaker("bitget")
    assert cb1 is cb2  # Misma instancia


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: __init__
# ═══════════════════════════════════════════════════════════════════════════════

def test_init_empty():
    """ExchangeService comienza con clients vacío y sin exchanges fallidos."""
    s = ExchangeService()
    assert s.clients == {}
    assert s.failed_exchanges == set()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _ensure_event_loop
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ensure_loop_client_exists(svc):
    """Cliente existente con loop vivo retorna True."""
    svc.clients["bitget"] = _mock_client()
    result = await svc._ensure_event_loop("bitget")
    assert result is True


@pytest.mark.asyncio
async def test_ensure_loop_no_client(svc):
    """Sin cliente retorna False."""
    result = await svc._ensure_event_loop("nonexistent")
    assert result is False


@pytest.mark.asyncio
@patch("services.exchange_service.ccxt_async")
@patch("services.exchange_service.load_api_creds")
async def test_ensure_loop_closed_recreates(mock_load_creds, mock_ccxt, svc):
    """Loop cerrado recrea el cliente automáticamente."""
    mock_client = _mock_client()
    mock_ccxt.bitget = MagicMock(return_value=mock_client)
    mock_load_creds.return_value = _mock_creds("bitget")

    # Agregar cliente cuyo loop está cerrado
    dead_client = MagicMock()
    dead_client.close = AsyncMock()
    svc.clients["bitget"] = dead_client

    # Parchear asyncio.get_running_loop para que lance RuntimeError
    with patch("asyncio.get_running_loop", side_effect=RuntimeError("Event loop is closed")):
        result = await svc._ensure_event_loop("bitget")

    assert result is True
    assert svc.clients["bitget"] is mock_client  # Reemplazado
    dead_client.close.assert_awaited_once()


@pytest.mark.asyncio
@patch("services.exchange_service.load_api_creds")
async def test_ensure_loop_closed_recreate_fails(mock_load_creds, svc):
    """Si recrear el cliente falla, retorna False."""
    dead_client = MagicMock()
    dead_client.close = AsyncMock()
    svc.clients["bitget"] = dead_client

    with patch("asyncio.get_running_loop", side_effect=RuntimeError("Event loop is closed")):
        result = await svc._ensure_event_loop("bitget")

    assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: create_client
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("services.exchange_service.ccxt_async")
async def test_create_client_success(mock_ccxt, svc):
    """create_client inicializa cliente CCXT correctamente."""
    mock_client = _mock_client()
    mock_ccxt.bitget = MagicMock(return_value=mock_client)

    creds = {"api_key": "key", "secret": "secret", "passphrase": "pass", "enabled": True}
    result = await svc.create_client("bitget", creds)

    assert result is mock_client
    assert "bitget" in svc.clients
    assert "bitget" not in svc.failed_exchanges
    mock_client.load_markets.assert_awaited_once()


@pytest.mark.asyncio
@patch("services.exchange_service.ccxt_async")
async def test_create_client_no_passphrase(mock_ccxt, svc):
    """create_client para exchange sin passphrase funciona igual."""
    mock_client = _mock_client()
    mock_ccxt.binance = MagicMock(return_value=mock_client)

    creds = {"api_key": "key", "secret": "secret", "passphrase": "", "enabled": True}
    result = await svc.create_client("binance", creds)

    assert result is mock_client
    assert "binance" in svc.clients


@pytest.mark.asyncio
@patch("services.exchange_service.ccxt_async")
async def test_create_client_ccxt_error(mock_ccxt, svc):
    """Error en CCXT retorna None y agrega a failed_exchanges."""
    mock_ccxt.bitget = MagicMock(side_effect=ValueError("Invalid exchange"))

    creds = {"api_key": "key", "secret": "secret", "passphrase": "pass", "enabled": True}
    result = await svc.create_client("bitget", creds)

    assert result is None
    assert "bitget" in svc.failed_exchanges


@pytest.mark.asyncio
@patch("services.exchange_service.ccxt_async")
async def test_create_client_replaces_existing(mock_ccxt, svc):
    """create_client reemplaza un cliente existente."""
    old_client = MagicMock()
    old_client.close = AsyncMock()
    svc.clients["bitget"] = old_client

    new_client = _mock_client()
    mock_ccxt.bitget = MagicMock(return_value=new_client)

    creds = {"api_key": "key", "secret": "secret", "passphrase": "pass", "enabled": True}
    result = await svc.create_client("bitget", creds)

    assert result is new_client
    old_client.close.assert_awaited_once()


@pytest.mark.asyncio
@patch("services.exchange_service.ccxt_async")
async def test_create_client_bingx_loads_time(mock_ccxt, svc):
    """BingX adicionalmente llama load_time_difference."""
    mock_client = _mock_client()
    mock_ccxt.bingx = MagicMock(return_value=mock_client)

    creds = {"api_key": "key", "secret": "secret", "passphrase": "", "enabled": True}
    result = await svc.create_client("bingx", creds)

    assert result is mock_client
    mock_client.load_time_difference.assert_awaited_once()


@pytest.mark.asyncio
@patch("services.exchange_service.ccxt_async")
async def test_create_client_bingx_load_time_fails_gracefully(mock_ccxt, svc):
    """Si load_time_difference falla en BingX, no impide crear el cliente."""
    mock_client = _mock_client()
    mock_client.load_time_difference = AsyncMock(side_effect=ConnectionError("timeout"))
    mock_ccxt.bingx = MagicMock(return_value=mock_client)

    creds = {"api_key": "key", "secret": "secret", "passphrase": "", "enabled": True}
    result = await svc.create_client("bingx", creds)

    assert result is mock_client
    assert "bingx" in svc.clients


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: close_all
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_close_all_closes_clients(svc):
    """close_all cierra todos los clientes y limpia el dict."""
    client_a = _mock_client()
    client_b = _mock_client()
    svc.clients["bitget"] = client_a
    svc.clients["bingx"] = client_b

    await svc.close_all()

    assert svc.clients == {}
    client_a.close.assert_awaited_once()
    client_b.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_all_no_clients(svc):
    """close_all sin clientes no lanza error."""
    await svc.close_all()  # No debe lanzar


@pytest.mark.asyncio
async def test_close_all_client_close_error_graceful(svc):
    """Error cerrando un cliente no impide cerrar los demás."""
    client_ok = _mock_client()
    client_err = _mock_client()
    client_err.close = AsyncMock(side_effect=ConnectionError("close failed"))
    svc.clients["ok"] = client_ok
    svc.clients["err"] = client_err

    await svc.close_all()

    assert svc.clients == {}
    client_ok.close.assert_awaited_once()
    client_err.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_all_persists_circuit_breakers(svc):
    """close_all persiste el estado de circuit breakers."""
    # Primero poblar circuit breakers
    cb_bitget = _get_circuit_breaker("bitget")
    cb_bingx = _get_circuit_breaker("bingx")

    with patch.object(cb_bitget, "persist") as mock_persist_1, \
         patch.object(cb_bingx, "persist") as mock_persist_2:
        svc.clients["bitget"] = _mock_client()
        await svc.close_all()

        mock_persist_1.assert_called_once()
        mock_persist_2.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: get_balance
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_balance_success(svc):
    """get_balance retorna el balance free de USDT."""
    client = _mock_client()
    svc.clients["bitget"] = client
    balance = await svc.get_balance("bitget")
    assert balance == 500.0
    client.fetch_balance.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_balance_no_client(svc):
    """get_balance sin cliente retorna 0.0."""
    balance = await svc.get_balance("nonexistent")
    assert balance == 0.0


@pytest.mark.asyncio
async def test_get_balance_error(svc):
    """get_balance con error retorna 0.0."""
    client = _mock_client()
    client.fetch_balance = AsyncMock(side_effect=ConnectionError("API error"))
    svc.clients["bitget"] = client
    balance = await svc.get_balance("bitget")
    assert balance == 0.0


@pytest.mark.asyncio
async def test_get_balance_exchange_params(svc):
    """get_balance usa params correctos según exchange."""
    for ex, expected_type in [("binance", "future"), ("bybit", "future"),
                               ("bingx", "swap"), ("bitget", "swap")]:
        client = _mock_client()
        svc.clients[ex] = client
        await svc.get_balance(ex)
        _, kwargs = client.fetch_balance.await_args
        assert kwargs["params"]["type"] == expected_type, f"{ex} esperaba type={expected_type}"
        svc.clients.clear()


@pytest.mark.asyncio
async def test_get_balance_unknown_exchange(svc):
    """Exchange desconocido no pasa params.type."""
    client = _mock_client()
    svc.clients["unknown_ex"] = client
    await svc.get_balance("unknown_ex")
    _, kwargs = client.fetch_balance.await_args
    assert "params" not in kwargs or kwargs["params"] == {}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: get_ticker_price
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_ticker_price_success(svc):
    """get_ticker_price retorna el last price del ticker."""
    client = _mock_client()
    svc.clients["bitget"] = client
    price = await svc.get_ticker_price("bitget", "BTC/USDT")
    assert price == 67500.0
    client.fetch_ticker.assert_awaited_once_with("BTC/USDT")


@pytest.mark.asyncio
async def test_get_ticker_price_no_client(svc):
    """get_ticker_price sin cliente retorna 0.0."""
    price = await svc.get_ticker_price("nonexistent", "BTC/USDT")
    assert price == 0.0


@pytest.mark.asyncio
async def test_get_ticker_price_runtime_error_ensures_loop(svc):
    """RuntimeError en fetch_ticker llama a _ensure_event_loop y relanza."""
    client = _mock_client()
    client.fetch_ticker = AsyncMock(side_effect=RuntimeError("Event loop is closed"))
    svc.clients["bitget"] = client

    with patch.object(svc, "_ensure_event_loop", new=AsyncMock(return_value=True)) as mock_ensure:
        with pytest.raises(RuntimeError):
            await svc.get_ticker_price("bitget", "BTC/USDT")
        # El decorador @retry_decorator puede reintentar, así que verificamos que
        # _ensure_event_loop fue llamado AL MENOS una vez
        assert mock_ensure.await_count >= 1
        mock_ensure.assert_awaited_with("bitget")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: set_leverage
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_set_leverage_success(svc):
    """set_leverage configura margen y apalancamiento."""
    client = _mock_client()
    svc.clients["bitget"] = client
    await svc.set_leverage("bitget", "BTC/USDT", 10, "cross", "LONG")

    client.set_margin_mode.assert_awaited_once_with("CROSS", "BTC/USDT")
    client.set_leverage.assert_awaited_once_with(10, "BTC/USDT", {})


@pytest.mark.asyncio
async def test_set_leverage_no_client(svc):
    """set_leverage sin cliente no hace nada."""
    await svc.set_leverage("nonexistent", "BTC/USDT", 10)  # No debe lanzar


@pytest.mark.asyncio
async def test_set_leverage_bingx_side_param(svc):
    """BingX pasa side como parámetro a set_leverage."""
    client = _mock_client()
    svc.clients["bingx"] = client
    await svc.set_leverage("bingx", "BTC/USDT", 10, "cross", "LONG")

    client.set_leverage.assert_awaited_once_with(10, "BTC/USDT", {"side": "LONG"})


@pytest.mark.asyncio
async def test_set_leverage_bitget_position_mode(svc):
    """Bitget llama a set_position_mode después de set_leverage."""
    client = _mock_client()
    svc.clients["bitget"] = client
    await svc.set_leverage("bitget", "BTC/USDT", 10, "cross", "LONG")

    client.set_position_mode.assert_awaited_once_with(False, "BTC/USDT")


@pytest.mark.asyncio
async def test_set_leverage_margin_mode_error_graceful(svc):
    """Error en set_margin_mode no impide configurar leverage."""
    client = _mock_client()
    client.set_margin_mode = AsyncMock(side_effect=ValueError("not supported"))
    svc.clients["bitget"] = client

    await svc.set_leverage("bitget", "BTC/USDT", 10)
    client.set_leverage.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_leverage_error_graceful(svc):
    """Error general en set_leverage se loguea pero no se lanza."""
    client = _mock_client()
    client.set_leverage = AsyncMock(side_effect=ConnectionError("API error"))
    svc.clients["bitget"] = client

    await svc.set_leverage("bitget", "BTC/USDT", 10)  # No debe lanzar


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: get_market_symbol
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_market_symbol_exact_match(svc):
    """get_market_symbol encuentra símbolo exacto swap/future."""
    client = _mock_client()
    svc.clients["bitget"] = client
    symbol = await svc.get_market_symbol("bitget", "BTC")
    assert symbol == "BTC/USDT"


@pytest.mark.asyncio
async def test_get_market_symbol_no_client(svc):
    """get_market_symbol sin cliente retorna None."""
    symbol = await svc.get_market_symbol("nonexistent", "BTC")
    assert symbol is None


@pytest.mark.asyncio
async def test_get_market_symbol_no_markets(svc):
    """get_market_symbol sin markets cargados retorna None."""
    client = MagicMock()
    client.markets = None
    svc.clients["bitget"] = client
    symbol = await svc.get_market_symbol("bitget", "BTC")
    assert symbol is None


@pytest.mark.asyncio
async def test_get_market_symbol_no_match(svc):
    """get_market_symbol sin coincidencia retorna None."""
    client = _mock_client()
    svc.clients["bitget"] = client
    symbol = await svc.get_market_symbol("bitget", "NONEXISTENT")
    assert symbol is None


@pytest.mark.asyncio
async def test_get_market_symbol_flexible_match(svc):
    """get_market_symbol encuentra por búsqueda flexible."""
    client = MagicMock()
    client.markets = {
        "BTCPERP/USDT": {"swap": True, "future": False},
    }
    svc.clients["bitget"] = client

    symbol = await svc.get_market_symbol("bitget", "BTC")
    assert symbol == "BTCPERP/USDT"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: fetch_position
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fetch_position_found(svc):
    """fetch_position retorna la posición cuando existe."""
    client = _mock_client()
    svc.clients["bitget"] = client
    pos = await svc.fetch_position("bitget", "BTC/USDT")
    assert pos is not None
    assert pos["symbol"] == "BTC/USDT"
    client.fetch_positions.assert_awaited_once_with(["BTC/USDT"])


@pytest.mark.asyncio
async def test_fetch_position_not_found(svc):
    """fetch_position retorna None cuando no hay posición para ese símbolo."""
    client = _mock_client()
    client.fetch_positions = AsyncMock(return_value=[
        {"symbol": "ETH/USDT", "contracts": 0.1},
    ])
    svc.clients["bitget"] = client
    pos = await svc.fetch_position("bitget", "BTC/USDT")
    assert pos is None


@pytest.mark.asyncio
async def test_fetch_position_no_client(svc):
    """fetch_position sin cliente retorna None."""
    pos = await svc.fetch_position("nonexistent", "BTC/USDT")
    assert pos is None


@pytest.mark.asyncio
async def test_fetch_position_error(svc):
    """fetch_position con error retorna None."""
    client = _mock_client()
    client.fetch_positions = AsyncMock(side_effect=ConnectionError("API error"))
    svc.clients["bitget"] = client
    pos = await svc.fetch_position("bitget", "BTC/USDT")
    assert pos is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: cancel_order
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cancel_order_success(svc):
    """cancel_order retorna True en éxito."""
    client = _mock_client()
    svc.clients["bitget"] = client
    result = await svc.cancel_order("bitget", "BTC/USDT", "order_123")
    assert result is True
    client.cancel_order.assert_awaited_once_with("order_123", "BTC/USDT")


@pytest.mark.asyncio
async def test_cancel_order_no_client(svc):
    """cancel_order sin cliente retorna False."""
    result = await svc.cancel_order("nonexistent", "BTC/USDT", "order_123")
    assert result is False


@pytest.mark.asyncio
async def test_cancel_order_failure(svc):
    """cancel_order con error retorna False."""
    client = _mock_client()
    client.cancel_order = AsyncMock(side_effect=ConnectionError("cancel failed"))
    svc.clients["bitget"] = client
    result = await svc.cancel_order("bitget", "BTC/USDT", "order_123")
    assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Instancia global
# ═══════════════════════════════════════════════════════════════════════════════

def test_global_instance():
    """exchange_service es una instancia de ExchangeService."""
    from services.exchange_service import exchange_service
    assert isinstance(exchange_service, ExchangeService)
