"""
Servicio de TG Scraping + Backtesting para señales de trading.

Scrapea el historial completo de mensajes de canales de Telegram,
parsea las señales de trading y verifica si se cumplieron
usando precios históricos de CoinGecko.
"""
import asyncio
import json
import logging
import time
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

import aiohttp
from aiohttp import ClientTimeout

from core.parser import parse_trading_signal
from models.data_classes import Signal
from utils.config import DATA_DIR

logger = logging.getLogger("TradingBot")

# ─── Archivo de persistencia ────────────────────────────────────────────────
SCRAPING_RESULTS_FILE = DATA_DIR / "tg_scraping_results.json"

# ─── Timeouts ────────────────────────────────────────────────────────────────
COINGECKO_TIMEOUT = ClientTimeout(total=20)

# ─── CoinGecko ID mapping ────────────────────────────────────────────────────
# Mapeo de símbolos comunes a IDs de CoinGecko
SYMBOL_TO_COINGECKO_ID: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "DOGE": "dogecoin",
    "LINK": "chainlink",
    "MATIC": "matic-network",
    "UNI": "uniswap",
    "SHIB": "shiba-inu",
    "LTC": "litecoin",
    "BCH": "bitcoin-cash",
    "ATOM": "cosmos",
    "NEAR": "near",
    "OP": "optimism",
    "ARB": "arbitrum",
    "APT": "aptos",
    "FIL": "filecoin",
    "SUI": "sui",
    "PEPE": "pepe",
    "INJ": "injective-protocol",
    "TIA": "celestia",
    "SEI": "sei-network",
    "WIF": "dogwifcoin",
    "RUNE": "thorchain",
    "FTM": "fantom",
    "ALGO": "algorand",
    "AAVE": "aave",
    "AXS": "axie-infinity",
    "SAND": "the-sandbox",
    "MANA": "decentraland",
    "EGLD": "elrond-erd-2",
    "KSM": "kusama",
    "COMP": "compound-governance-token",
    "CRV": "curve-dao-token",
    "YFI": "yearn-finance",
    "MKR": "maker",
    "SNX": "synthetix-network-token",
    "ZEC": "zcash",
    "DASH": "dash",
    "XMR": "monero",
    "EOS": "eos",
    "TRX": "tron",
    "VET": "vechain",
    "THETA": "theta-token",
    "ICP": "internet-computer",
    "FET": "fetch-ai",
    "GRT": "the-graph",
    "RNDR": "render-token",
    "HBAR": "hedera-hashgraph",
    "STX": "stacks",
}


# ─── Modelos de datos ───────────────────────────────────────────────────────

@dataclass
class ScrapedSignal:
    """Señal scrapeada de un canal de Telegram."""
    id: str  # hash único del mensaje
    channel_id: int
    channel_name: str
    symbol: str
    direction: str
    entry_min: Optional[float]
    entry_max: Optional[float]
    stop_loss: Optional[float]
    targets: List[float]
    raw_text: str
    timestamp: float
    date_str: str

    @classmethod
    def from_signal(cls, signal: Signal, channel_id: int, channel_name: str,
                    msg_id: int, timestamp: float) -> "ScrapedSignal":
        """Crea un ScrapedSignal a partir de un Signal parseado."""
        raw = f"{channel_id}_{msg_id}"
        uid = hashlib.md5(raw.encode()).hexdigest()[:12]
        dt = datetime.fromtimestamp(timestamp)
        return cls(
            id=uid,
            channel_id=channel_id,
            channel_name=channel_name,
            symbol=signal.simbolo,
            direction=signal.direccion,
            entry_min=signal.entry_min,
            entry_max=signal.entry_max,
            stop_loss=signal.stop_loss,
            targets=signal.targets,
            raw_text=signal.raw_text,
            timestamp=timestamp,
            date_str=dt.strftime("%Y-%m-%d %H:%M"),
        )


@dataclass
class BacktestResult:
    """Resultado del backtesting para una señal."""
    signal_id: str
    entry_reached: bool
    sl_hit: bool
    tps_reached: List[bool]
    best_tp_reached: int  # índice del mejor TP alcanzado (0 = ninguno)
    status: str  # 'win', 'loss', 'pending', 'error'
    entry_date: Optional[str] = None
    sl_date: Optional[str] = None
    tp_dates: List[str] = field(default_factory=list)
    error_msg: str = ""


@dataclass
class ChannelInfo:
    """Información de un canal scrapeado."""
    channel_id: int
    channel_name: str
    signal_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    last_scrape: Optional[float] = None


# ─── Persistencia ───────────────────────────────────────────────────────────

def _load_results() -> dict:
    """Carga resultados de scraping desde disco."""
    if not SCRAPING_RESULTS_FILE.exists():
        return {"signals": [], "results": {}, "last_scrape": None}
    try:
        with open(SCRAPING_RESULTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"signals": [], "results": {}, "last_scrape": None}


def _save_results(signals: List[dict], results: dict, last_scrape: Optional[float] = None):
    """Guarda resultados de scraping a disco."""
    data = {
        "signals": signals,
        "results": results,
        "last_scrape": last_scrape or time.time(),
    }
    try:
        SCRAPING_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SCRAPING_RESULTS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error guardando resultados de scraping: {e}")


def load_saved_signals() -> tuple:
    """Carga señales guardadas.
    Retorna (signals_list, results_dict)."""
    data = _load_results()
    signals = data.get("signals", [])
    results = data.get("results", {})
    return signals, results


# ─── CoinGecko helper ───────────────────────────────────────────────────────

async def _get_coingecko_prices(coin_id: str, from_ts: float, to_ts: float) -> List[float]:
    """Obtiene precios históricos de CoinGecko para un rango de tiempo."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {
        "vs_currency": "usd",
        "from": int(from_ts),
        "to": int(to_ts),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=COINGECKO_TIMEOUT) as resp:
                if resp.status == 429:
                    logger.warning(f"CoinGecko rate limit para {coin_id}")
                    return []
                if resp.status != 200:
                    logger.warning(f"CoinGecko error {resp.status} para {coin_id}")
                    return []
                data = await resp.json()
                prices = data.get("prices", [])
                return [p[1] for p in prices]  # [timestamp, price] -> price
    except asyncio.TimeoutError:
        logger.warning(f"CoinGecko timeout para {coin_id}")
        return []
    except Exception as e:
        logger.debug(f"Error obteniendo precios CoinGecko para {coin_id}: {e}")
        return []


def _symbol_to_coingecko_id(symbol: str) -> Optional[str]:
    """Convierte un símbolo (ej: BTC) a ID de CoinGecko."""
    return SYMBOL_TO_COINGECKO_ID.get(symbol.upper())


# ─── Scraping ───────────────────────────────────────────────────────────────

async def scrape_channel(client, channel_id: int, limit: int = 1000) -> tuple:
    """Scrapea mensajes de un canal de Telegram y extrae señales de trading.
    
    Args:
        client: Cliente Telethon conectado
        channel_id: ID del canal a scrapear
        limit: Máximo de mensajes a obtener
        
    Returns:
        (channel_name, list_of_ScrapedSignal)
    """
    signals_found: List[ScrapedSignal] = []
    channel_name = str(channel_id)

    try:
        # Obtener entidad del canal
        entity = await client.get_entity(channel_id)
        channel_name = getattr(entity, 'title', str(channel_id))
        logger.info(f"📡 Scrapeando canal: {channel_name} (ID: {channel_id})")

        # Obtener mensajes
        messages = await client.get_messages(entity, limit=limit)

        for msg in messages:
            if not msg.text:
                continue

            text = msg.text.strip()
            if not text:
                continue

            # Parsear señal
            signal = parse_trading_signal(text)
            if signal:
                ts = msg.date.timestamp() if msg.date else time.time()
                scraped = ScrapedSignal.from_signal(
                    signal, channel_id, channel_name,
                    msg.id, ts
                )
                signals_found.append(scraped)

        logger.info(f"   → {len(signals_found)} señales encontradas en {channel_name}")

    except ValueError as e:
        logger.warning(f"⚠️ No se pudo acceder al canal {channel_id}: {e}")
    except Exception as e:
        logger.error(f"Error scrapeando canal {channel_id}: {e}")

    return channel_name, signals_found


async def scrape_all_channels(client, channels: Set[int],
                               limit: int = 500) -> tuple:
    """Scrapea todos los canales configurados.
    
    Args:
        client: Cliente Telethon conectado
        channels: Set de IDs de canales
        limit: Máximo de mensajes por canal
        
    Returns:
        (list_of_ScrapedSignal_dicts, dict_of_results)
    """
    all_signals: List[ScrapedSignal] = []
    seen_ids: Set[str] = set()

    for cid in channels:
        try:
            channel_name, signals = await scrape_channel(client, cid, limit)
            for s in signals:
                if s.id not in seen_ids:
                    seen_ids.add(s.id)
                    all_signals.append(s)
        except Exception as e:
            logger.error(f"Error scrapeando canal {cid}: {e}")

    # Ejecutar backtesting para todas las señales
    results = await run_backtest_batch(all_signals)

    # Guardar a disco
    signals_dicts = [asdict(s) for s in all_signals]
    results_dict = {k: asdict(v) for k, v in results.items()}
    _save_results(signals_dicts, results_dict)

    return signals_dicts, results_dict


# ─── Backtesting ────────────────────────────────────────────────────────────

async def run_single_backtest(scraped: ScrapedSignal) -> BacktestResult:
    """Ejecuta backtesting para una señal individual."""
    coin_id = _symbol_to_coingecko_id(scraped.symbol)
    if not coin_id:
        return BacktestResult(
            signal_id=scraped.id,
            entry_reached=False, sl_hit=False,
            tps_reached=[], best_tp_reached=0,
            status="pending",
            error_msg=f"Sin mapping CoinGecko para {scraped.symbol}"
        )

    # Ventana de 7 días después de la señal
    from_ts = scraped.timestamp
    to_ts = from_ts + (7 * 86400)

    prices = await _get_coingecko_prices(coin_id, from_ts, to_ts)
    if not prices:
        return BacktestResult(
            signal_id=scraped.id,
            entry_reached=False, sl_hit=False,
            tps_reached=[], best_tp_reached=0,
            status="error",
            error_msg=f"Sin datos de precio para {scraped.symbol}"
        )

    # Determinar precios relevantes según dirección
    if scraped.direction.lower() == "buy":
        entry_min = scraped.entry_min or 0
        entry_max = scraped.entry_max or float('inf')
        sl = scraped.stop_loss or 0
        targets = scraped.targets  # Targets LONG: ascendentes

        entry_reached = any(entry_min <= p <= entry_max for p in prices)
        sl_hit = any(p <= sl for p in prices)
        tps_reached = [any(p >= t for p in prices) for t in targets]

    else:  # Sell / Short
        entry_min = scraped.entry_min or float('inf')
        entry_max = scraped.entry_max or 0
        sl = scraped.stop_loss or float('inf')
        targets = scraped.targets  # Targets SHORT: descendentes

        entry_reached = any(entry_max >= p >= entry_min for p in prices)
        sl_hit = any(p >= sl for p in prices)
        tps_reached = [any(p <= t for p in prices) for t in targets]

    # Determinar mejor TP alcanzado
    best_tp = 0
    for i, reached in enumerate(tps_reached):
        if reached:
            best_tp = i + 1

    # Estado final
    if sl_hit and best_tp == 0:
        status = "loss"
    elif best_tp >= 1:
        status = "win"
    elif entry_reached and not sl_hit:
        status = "win"  # Entró pero no tocó SL ni targets aún
    else:
        status = "pending"

    result = BacktestResult(
        signal_id=scraped.id,
        entry_reached=entry_reached,
        sl_hit=sl_hit,
        tps_reached=tps_reached,
        best_tp_reached=best_tp,
        status=status,
    )

    return result


async def run_backtest_batch(signals: List[ScrapedSignal]) -> Dict[str, BacktestResult]:
    """Ejecuta backtesting para un lote de señales."""
    results = {}
    batch_size = 5  # CoinGecko rate limit: procesar de a pocos

    for i in range(0, len(signals), batch_size):
        batch = signals[i:i + batch_size]
        tasks = [run_single_backtest(s) for s in batch]
        batch_results = await asyncio.gather(*tasks)

        for s, r in zip(batch, batch_results):
            results[s.id] = r

        # Pequeña pausa para evitar rate limiting
        if i + batch_size < len(signals):
            await asyncio.sleep(1.5)

    logger.info(f"✅ Backtesting completado: {len(results)} señales procesadas")
    return results


# ─── Estadísticas ───────────────────────────────────────────────────────────

def get_channel_stats(signals: List[dict], results: dict) -> Dict[int, ChannelInfo]:
    """Calcula estadísticas por canal a partir de datos guardados."""
    channels: Dict[int, ChannelInfo] = {}

    for s in signals:
        cid = s.get("channel_id", 0)
        cname = s.get("channel_name", str(cid))
        sid = s.get("id", "")

        if cid not in channels:
            channels[cid] = ChannelInfo(channel_id=cid, channel_name=cname)

        channels[cid].signal_count += 1

        # Verificar resultado
        bt = results.get(sid, {})
        status = bt.get("status", "") if isinstance(bt, dict) else getattr(bt, "status", "")
        if status == "win":
            channels[cid].win_count += 1
        elif status == "loss":
            channels[cid].loss_count += 1

    return channels
