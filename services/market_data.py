"""Servicio de datos de mercado vía CoinGecko API (sin API key necesaria)."""
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
import time
from typing import Optional

logger = logging.getLogger("TradingBot")

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
TIMEOUT = ClientTimeout(total=15)

# Cache simple con TTL de 60s para evitar rate limiting (429)
_cache = {}
_cache_ttl = 60

# Sesión HTTP reutilizable para connection pooling
_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


def invalidate_cache():
    """Limpia el caché de CoinGecko."""
    _cache.clear()


def _get_from_cache(key: str):
    """Retorna dato del caché si no ha expirado."""
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _cache_ttl:
        return entry["data"]
    return None


def _set_cache(key: str, data):
    """Guarda dato en caché con timestamp."""
    _cache[key] = {"data": data, "ts": time.time()}


async def fetch_top20() -> list:
    """
    Obtiene las top 20 criptomonedas desde CoinGecko.
    Retorna lista de dicts con: symbol, name, price, change_24h, volume, market_cap.
    """
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 20,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h"
    }
    # Verificar caché primero
    cached = _get_from_cache("top20")
    if cached is not None:
        return cached

    try:
        session = await _get_session()
        async with session.get(url, params=params, timeout=TIMEOUT) as resp:
            if resp.status == 429:
                logger.warning("CoinGecko rate limited (429), usando caché")
                return _get_from_cache("top20") or []
            if resp.status != 200:
                logger.error(f"CoinGecko error {resp.status}, usando caché")
                return _get_from_cache("top20") or []
            data = await resp.json()
            results = []
            for coin in data:
                symbol = coin.get("symbol", "").upper()
                change = coin.get("price_change_percentage_24h")
                results.append({
                    "symbol": symbol,
                    "name": coin.get("name", symbol),
                    "price": coin.get("current_price", 0) or 0,
                    "change_24h": change if change is not None else 0,
                    "volume": coin.get("total_volume", 0) or 0,
                    "market_cap": coin.get("market_cap", 0) or 0,
                    "image": coin.get("image", ""),
                })
            _set_cache("top20", results)
            return results
    except asyncio.TimeoutError:
        logger.warning("CoinGecko timeout, usando caché")
        return _get_from_cache("top20") or []
    except Exception as e:
        logger.error(f"Error fetching CoinGecko top20: {e}")
        return []


async def fetch_market_indices() -> dict:
    """
    Obtiene datos globales del mercado desde CoinGecko.
    Retorna dict con: total_market_cap, btc_dominance, eth_dominance.
    """
    # Verificar caché primero
    cached = _get_from_cache("indices")
    if cached is not None:
        return cached

    indices = {
        "btc_dominance": 0,
        "eth_dominance": 0,
        "total_market_cap": 0,
        "total_volume_24h": 0,
        "market_cap_change_24h": 0,
        "btc_price": 0,
        "eth_price": 0,
    }
    
    try:
        # Global data de CoinGecko
        session = await _get_session()
        url = f"{COINGECKO_BASE}/global"
        async with session.get(url, timeout=TIMEOUT) as resp:
            if resp.status == 429:
                logger.warning("CoinGecko rate limited (429) en global data")
                return _get_from_cache("indices") or indices
            if resp.status == 200:
                data = await resp.json()
                gdata = data.get("data", {})
                indices["total_market_cap"] = gdata.get("total_market_cap", {}).get("usd", 0) or 0
                indices["total_volume_24h"] = gdata.get("total_volume", {}).get("usd", 0) or 0
                indices["btc_dominance"] = gdata.get("market_cap_percentage", {}).get("btc", 0) or 0
                indices["eth_dominance"] = gdata.get("market_cap_percentage", {}).get("eth", 0) or 0
                indices["market_cap_change_24h"] = gdata.get("market_cap_change_percentage_24h_usd", 0) or 0
            else:
                return _get_from_cache("indices") or indices
    except asyncio.TimeoutError:
        logger.warning("CoinGecko timeout en global data")
        return _get_from_cache("indices") or indices
    except Exception as e:
        logger.error(f"Error fetching global data: {e}")
        return _get_from_cache("indices") or indices

    # Obtener precios de BTC y ETH para referencia
    try:
        session = await _get_session()
        url = f"{COINGECKO_BASE}/simple/price"
        params = {"ids": "bitcoin,ethereum", "vs_currencies": "usd", "include_24hr_change": "true"}
        async with session.get(url, params=params, timeout=TIMEOUT) as resp:
            if resp.status == 429:
                logger.warning("CoinGecko rate limited (429) en precios")
            elif resp.status == 200:
                data = await resp.json()
                indices["btc_price"] = data.get("bitcoin", {}).get("usd", 0) or 0
                indices["eth_price"] = data.get("ethereum", {}).get("usd", 0) or 0
            else:
                logger.warning(f"CoinGecko error {resp.status} en precios, usando caché")
                return _get_from_cache("indices") or indices
    except asyncio.TimeoutError:
        logger.warning("CoinGecko timeout en precios BTC/ETH")
    except Exception as e:
        logger.error(f"Error fetching BTC/ETH price: {e}")

    _set_cache("indices", indices)
    return indices