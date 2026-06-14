"""Tests para services/market_data.py — CoinGecko cache + API."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from services.market_data import (
    fetch_top20, fetch_market_indices,
    invalidate_cache, _cache, _get_from_cache, _set_cache, _cache_ttl,
)

# ─── Sample data ────────────────────────────────────────────────────────────

SAMPLE_COINS = [
    {
        "symbol": "BTC",
        "name": "Bitcoin",
        "current_price": 67432.50,
        "price_change_percentage_24h": 2.5,
        "total_volume": 30000000000,
        "market_cap": 1320000000000,
        "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
    },
    {
        "symbol": "ETH",
        "name": "Ethereum",
        "current_price": 3450.0,
        "price_change_percentage_24h": -1.2,
        "total_volume": 15000000000,
        "market_cap": 420000000000,
        "image": "https://assets.coingecko.com/coins/images/279/large/ethereum.png",
    },
]

SAMPLE_GLOBAL_DATA = {
    "data": {
        "total_market_cap": {"usd": 2500000000000},
        "total_volume": {"usd": 80000000000},
        "market_cap_percentage": {"btc": 52.3, "eth": 17.1},
        "market_cap_change_percentage_24h_usd": -1.2,
    }
}

SAMPLE_PRICE_DATA = {
    "bitcoin": {"usd": 67432.50},
    "ethereum": {"usd": 3450.0},
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_mock_response(status: int = 200, json_data=None, exc=None):
    """Crea un mock de respuesta HTTP de aiohttp.

    - Si se pasa exc, `json()` y `__aenter__` lanzarán esa excepción.
    - Caso normal: resp.json() retorna json_data, status=status.
    """
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(side_effect=([exc] if exc else None))
    if json_data is not None and not exc:
        resp.json = AsyncMock(return_value=json_data)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    return resp


def _make_mock_session(get_side_effect=None):
    """Crea un mock de aiohttp.ClientSession.

    session.get(url, ...) NO es awaitable — se usa dentro de ``async with``,
    por lo que side_effect debe ser una función sincrónica que retorne
    un objeto con __aenter__/__aexit__.
    """
    session = MagicMock()
    if get_side_effect:
        session.get = MagicMock(side_effect=get_side_effect)
    else:
        session.get = MagicMock(return_value=_make_mock_response())
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


def _success_resp():
    return _make_mock_response(status=200, json_data=SAMPLE_COINS)


class _TimeoutSentinel:
    """Usado para señalar 'lanzar TimeoutError' en side_effect sincrónico."""


def _timeout_err():
    """Side effect que lanza TimeoutError (función sincrónica)."""
    raise asyncio.TimeoutError()


def _conn_err():
    """Side effect que lanza ConnectionError."""
    raise ConnectionError("Network unreachable")


def setup_function():
    """Limpia el caché global antes de cada test."""
    invalidate_cache()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests de utilidades de caché
# ═══════════════════════════════════════════════════════════════════════════════

def test_invalidate_cache():
    """invalidate_cache limpia todo el caché."""
    _cache["test"] = {"data": 123, "ts": time.time()}
    assert len(_cache) == 1
    invalidate_cache()
    assert len(_cache) == 0


def test_set_and_get_cache():
    """_set_cache guarda y _get_from_cache recupera antes del TTL."""
    _set_cache("mykey", {"foo": "bar"})
    result = _get_from_cache("mykey")
    assert result == {"foo": "bar"}


def test_get_cache_expired():
    """_get_from_cache retorna None si el dato expiró."""
    _cache["expired"] = {"data": "old", "ts": time.time() - _cache_ttl - 10}
    result = _get_from_cache("expired")
    assert result is None


def test_get_cache_missing():
    """_get_from_cache retorna None si la clave no existe."""
    result = _get_from_cache("nonexistent")
    assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: fetch_top20
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fetch_top20_success():
    """fetch_top20 retorna datos formateados correctamente desde la API."""
    resp = _make_mock_response(status=200, json_data=SAMPLE_COINS)
    session = _make_mock_session(get_side_effect=lambda *a, **kw: resp)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_top20()

    assert len(result) == 2
    assert result[0]["symbol"] == "BTC"
    assert result[0]["name"] == "Bitcoin"
    assert result[0]["price"] == 67432.50
    assert result[0]["change_24h"] == 2.5
    assert result[0]["volume"] == 30000000000
    assert result[0]["market_cap"] == 1320000000000
    assert result[0]["image"] == SAMPLE_COINS[0]["image"]
    assert result[1]["symbol"] == "ETH"
    assert result[1]["change_24h"] == -1.2


@pytest.mark.asyncio
async def test_fetch_top20_cache_hit():
    """Segunda llamada usa caché en vez de hacer HTTP request."""
    call_count = 0

    def side_effect(*a, **kw):
        nonlocal call_count
        call_count += 1
        return _make_mock_response(status=200, json_data=SAMPLE_COINS)

    session = _make_mock_session(get_side_effect=side_effect)

    with patch("aiohttp.ClientSession", return_value=session):
        result1 = await fetch_top20()
        assert len(result1) == 2
        assert call_count == 1

        result2 = await fetch_top20()
        assert len(result2) == 2
        assert call_count == 1  # No llamó a la API


@pytest.mark.asyncio
async def test_fetch_top20_cache_invalidation():
    """Después de invalidate_cache(), la llamada va a la API de nuevo."""
    call_count = 0

    def side_effect(*a, **kw):
        nonlocal call_count
        call_count += 1
        return _make_mock_response(status=200, json_data=SAMPLE_COINS)

    session = _make_mock_session(get_side_effect=side_effect)

    with patch("aiohttp.ClientSession", return_value=session):
        await fetch_top20()
        assert call_count == 1

        invalidate_cache()

        await fetch_top20()
        assert call_count == 2  # Llamó a la API otra vez


@pytest.mark.asyncio
async def test_fetch_top20_429_with_cache():
    """429 con caché disponible retorna datos cacheados."""
    responses = [
        _make_mock_response(status=200, json_data=SAMPLE_COINS),
        _make_mock_response(status=429),
    ]

    def side_effect(*a, **kw):
        return responses.pop(0)

    session = _make_mock_session(get_side_effect=side_effect)

    with patch("aiohttp.ClientSession", return_value=session):
        result1 = await fetch_top20()
        assert len(result1) == 2

        result2 = await fetch_top20()  # 429 pero hay caché
        assert len(result2) == 2
        assert result2[0]["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_fetch_top20_429_no_cache():
    """429 sin caché retorna lista vacía."""
    resp = _make_mock_response(status=429)
    session = _make_mock_session(get_side_effect=lambda *a, **kw: resp)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_top20()

    assert result == []


@pytest.mark.asyncio
async def test_fetch_top20_non_200():
    """Status code no-200 retorna lista vacía."""
    resp = _make_mock_response(status=500)
    session = _make_mock_session(get_side_effect=lambda *a, **kw: resp)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_top20()

    assert result == []


@pytest.mark.asyncio
async def test_fetch_top20_timeout_with_cache():
    """Timeout con caché disponible retorna datos cacheados."""
    # Primera llamada: éxito → llena caché
    success_session = _make_mock_session(
        get_side_effect=lambda *a, **kw: _make_mock_response(
            status=200, json_data=SAMPLE_COINS
        )
    )
    # Segunda llamada: timeout
    timeout_session = _make_mock_session(get_side_effect=_timeout_err)

    sessions = [success_session, timeout_session]

    with patch("aiohttp.ClientSession") as mock_cls:
        mock_cls.side_effect = lambda: sessions.pop(0)

        result1 = await fetch_top20()
        assert len(result1) == 2

        result2 = await fetch_top20()  # Timeout pero viene de caché
        assert len(result2) == 2
        assert result2[0]["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_fetch_top20_timeout_no_cache():
    """Timeout sin caché retorna lista vacía."""
    session = _make_mock_session(get_side_effect=_timeout_err)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_top20()

    assert result == []


@pytest.mark.asyncio
async def test_fetch_top20_exception():
    """Excepción genérica retorna lista vacía."""
    session = _make_mock_session(get_side_effect=_conn_err)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_top20()

    assert result == []


@pytest.mark.asyncio
async def test_fetch_top20_none_values():
    """Valores nulos en la API se convierten a 0."""
    coins_with_none = [
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "current_price": None,
            "price_change_percentage_24h": None,
            "total_volume": None,
            "market_cap": None,
            "image": "",
        }
    ]
    resp = _make_mock_response(status=200, json_data=coins_with_none)
    session = _make_mock_session(get_side_effect=lambda *a, **kw: resp)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_top20()

    assert len(result) == 1
    assert result[0]["price"] == 0
    assert result[0]["change_24h"] == 0
    assert result[0]["volume"] == 0
    assert result[0]["market_cap"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: fetch_market_indices
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fetch_market_indices_success():
    """fetch_market_indices retorna todos los índices correctamente."""
    global_resp = _make_mock_response(status=200, json_data=SAMPLE_GLOBAL_DATA)
    price_resp = _make_mock_response(status=200, json_data=SAMPLE_PRICE_DATA)
    responses = [global_resp, price_resp]

    def side_effect(*a, **kw):
        return responses.pop(0)

    session = _make_mock_session(get_side_effect=side_effect)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_market_indices()

    assert result["btc_dominance"] == 52.3
    assert result["eth_dominance"] == 17.1
    assert result["total_market_cap"] == 2500000000000
    assert result["total_volume_24h"] == 80000000000
    assert result["market_cap_change_24h"] == -1.2
    assert result["btc_price"] == 67432.50
    assert result["eth_price"] == 3450.0


@pytest.mark.asyncio
async def test_fetch_market_indices_cache():
    """Segunda llamada a market_indices usa caché."""
    call_count = 0

    def side_effect(*a, **kw):
        nonlocal call_count
        call_count += 1
        if "global" in str(a):
            return _make_mock_response(status=200, json_data=SAMPLE_GLOBAL_DATA)
        return _make_mock_response(status=200, json_data=SAMPLE_PRICE_DATA)

    session = _make_mock_session(get_side_effect=side_effect)

    with patch("aiohttp.ClientSession", return_value=session):
        result1 = await fetch_market_indices()
        assert result1["btc_dominance"] == 52.3
        assert call_count == 2  # global + price

        result2 = await fetch_market_indices()
        assert result2["btc_dominance"] == 52.3
        assert call_count == 2  # No llamó a la API


@pytest.mark.asyncio
async def test_fetch_market_indices_429_global():
    """429 en global data retorna fallback (índices = 0) y PRICE NO se ejecuta."""
    # La función RETORNA en el 429 con los fallback values,
    # nunca llega al endpoint de price.
    rate_limit_resp = _make_mock_response(status=429)
    price_resp = _make_mock_response(status=200, json_data=SAMPLE_PRICE_DATA)
    responses = [rate_limit_resp, price_resp]

    def side_effect(*a, **kw):
        return responses.pop(0)

    session = _make_mock_session(get_side_effect=side_effect)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_market_indices()

    # global falló (429) → retorna fallback con valores 0
    # El price endpoint NO se ejecuta porque la función ya retornó
    assert result["btc_dominance"] == 0
    assert result["total_market_cap"] == 0
    assert result["btc_price"] == 0
    assert result["eth_price"] == 0

    # price_resp nunca se consumió
    assert len(responses) == 1


@pytest.mark.asyncio
async def test_fetch_market_indices_timeout_global():
    """Timeout en global data retorna fallback con valores 0."""
    session = _make_mock_session(get_side_effect=_timeout_err)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_market_indices()

    assert result["btc_dominance"] == 0
    assert result["eth_dominance"] == 0
    assert result["total_market_cap"] == 0
    assert result["btc_price"] == 0
    assert result["eth_price"] == 0


@pytest.mark.asyncio
async def test_fetch_market_indices_timeout_price_but_global_ok():
    """Timeout en price no impide retornar índices globales."""
    global_resp = _make_mock_response(status=200, json_data=SAMPLE_GLOBAL_DATA)

    def side_effect(*a, **kw):
        # Primera llamada: /global → éxito
        # Segunda llamada: /simple/price → timeout
        if not hasattr(side_effect, "call_num"):
            side_effect.call_num = 0
        side_effect.call_num += 1
        if side_effect.call_num == 1:
            return global_resp
        raise asyncio.TimeoutError()

    session = _make_mock_session(get_side_effect=side_effect)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await fetch_market_indices()

    assert result["btc_dominance"] == 52.3  # Global OK
    assert result["total_market_cap"] == 2500000000000  # Global OK
    assert result["btc_price"] == 0  # Price timed out
    assert result["eth_price"] == 0  # Price timed out
