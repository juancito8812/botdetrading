import asyncio
import logging
import ccxt.async_support as ccxt_async
from typing import Dict, Optional, Any
from utils.config import EXCHANGES_DEFAULTS
from utils.resilience.decorators import (
    retry_decorator, circuit_breaker_decorator_dynamic,
    timeout_decorator, log_errors_decorator,
)
from utils.resilience.circuit_breaker import CircuitBreaker

logger = logging.getLogger("TradingBot")

# Circuit breakers por exchange
_circuit_breakers = {}

def _get_circuit_breaker(exchange_id: str) -> CircuitBreaker:
    """Obtiene o crea un circuit breaker para un exchange."""
    if exchange_id not in _circuit_breakers:
        _circuit_breakers[exchange_id] = CircuitBreaker(
            name=exchange_id,
            failure_threshold=5,
            reset_timeout=60,
        )
    return _circuit_breakers[exchange_id]

class ExchangeService:
    def __init__(self):
        self.clients: Dict[str, Any] = {}
        self.failed_exchanges = set()

    @retry_decorator(max_retries=2, base_delay=2.0)
    @timeout_decorator(seconds=60)
    async def create_client(self, exchange_id: str, creds: Dict[str, Any]) -> Optional[Any]:
        """Crea e inicializa un cliente de CCXT."""
        # Limpiar cliente previo si existe para evitar conflictos de loop
        if exchange_id in self.clients:
            try: await self.clients[exchange_id].close()
            except: pass
            del self.clients[exchange_id]

        try:
            exchange_class = getattr(ccxt_async, exchange_id)
            # ... rest of config ...
            config = {
                'apiKey': creds["api_key"],
                'secret': creds["secret"],
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {
                    'defaultType': EXCHANGES_DEFAULTS[exchange_id]["default_type"],
                    'adjustForTimeDifference': True,
                    'fetchCurrencies': False,
                }
            }
            if EXCHANGES_DEFAULTS[exchange_id]["needs_passphrase"] and creds.get("passphrase"):
                config['password'] = creds["passphrase"]
            
            client = exchange_class(config)
            await client.load_markets()
            
            if exchange_id == "bingx":
                try: await client.load_time_difference()
                except: pass
                
            self.clients[exchange_id] = client
            self.failed_exchanges.discard(exchange_id)
            return client
            
        except Exception as e:
            logger.error(f"Error inicializando {exchange_id}: {e}")
            self.failed_exchanges.add(exchange_id)
            return None

    async def close_all(self):
        # Persistir estado de circuit breakers
        from utils.config import DATA_DIR
        cb_dir = DATA_DIR / "resilience"
        cb_dir.mkdir(parents=True, exist_ok=True)
        for ex_id, cb in _circuit_breakers.items():
            cb.persist(str(cb_dir / f"cb_{ex_id}.json"))
        for client in self.clients.values():
            try: await asyncio.wait_for(client.close(), timeout=5)
            except: pass
        self.clients.clear()

    @retry_decorator(max_retries=3, base_delay=1.0)
    @circuit_breaker_decorator_dynamic(resolver=_get_circuit_breaker)
    @timeout_decorator(seconds=30)
    @log_errors_decorator(context={"module": "exchange_service"})
    async def get_balance(self, exchange_id: str) -> float:
        client = self.clients.get(exchange_id)
        if not client: return 0.0
        try:
            params = {}
            if exchange_id in ["binance", "bybit", "okx"]:
                params["type"] = "future"
            elif exchange_id in ["bingx", "bitget"]:
                params["type"] = "swap"
            
            balance = await client.fetch_balance(params=params)
            usdt = balance.get('USDT', {})
            return float(usdt.get('free') or usdt.get('available') or usdt.get('total') or 0.0)
        except Exception as e:
            logger.error(f"Error balance {exchange_id}: {e}")
            return 0.0

    @retry_decorator(max_retries=3, base_delay=1.0)
    @circuit_breaker_decorator_dynamic(resolver=_get_circuit_breaker)
    @timeout_decorator(seconds=15)
    async def get_ticker_price(self, exchange_id: str, market_symbol: str) -> float:
        client = self.clients.get(exchange_id)
        if not client: return 0.0
        ticker = await client.fetch_ticker(market_symbol)
        return float(ticker['last'])

    @retry_decorator(max_retries=2, base_delay=1.0)
    @circuit_breaker_decorator_dynamic(resolver=_get_circuit_breaker)
    @timeout_decorator(seconds=30)
    async def set_leverage(self, exchange_id: str, market_symbol: str, leverage: int, margin_mode: str = 'cross', side: str = 'LONG'):
        client = self.clients.get(exchange_id)
        if not client: return
        try:
            # 1. Configurar Modo de Margen
            try:
                await client.set_margin_mode(margin_mode.upper(), market_symbol)
            except Exception as e:
                logger.debug(f"Nota: No se pudo cambiar margen en {exchange_id}: {e}")

            # 2. Configurar Apalancamiento
            params = {}
            if exchange_id == "bingx":
                params['side'] = side.upper() # BingX requiere side
            
            await client.set_leverage(leverage, market_symbol, params)
            
            # 3. Forzar Modo de Posición para Bitget
            if exchange_id == "bitget":
                try:
                    await client.set_position_mode(False, market_symbol)
                except Exception as e:
                    logger.debug(f"Nota: No se pudo cambiar modo posicion en Bitget: {e}")

            logger.info(f"⚙️ {exchange_id}: Configuración completada para {market_symbol}")
        except Exception as e:
            logger.warning(f"⚠️ {exchange_id}: No se pudo configurar apalancamiento/margen: {e}")

    async def get_market_symbol(self, exchange_id: str, symbol_base: str) -> Optional[str]:
        """Busca el símbolo de mercado completo para un símbolo base dado."""
        client = self.clients.get(exchange_id)
        if not client or not client.markets:
            return None
        
        symbol_upper = symbol_base.upper().strip()
        
        # Patrones a buscar
        patterns = [
            f"{symbol_upper}/USDT",
            f"{symbol_upper}/USDT:USDT",
            f"{symbol_upper}USDT",
        ]
        
        for pattern in patterns:
            if pattern in client.markets:
                market = client.markets[pattern]
                if market.get('swap', False) or market.get('future', False):
                    return pattern
        
        # Búsqueda flexible: buscar cualquier mercado que contenga el símbolo base
        for sym, market in client.markets.items():
            if symbol_upper in sym and ('USDT' in sym) and (market.get('swap', False) or market.get('future', False)):
                logger.info(f"🔍 Símbolo encontrado por búsqueda flexible: {sym} para {symbol_base}")
                return sym
        
        logger.warning(f"❌ No se encontró símbolo de mercado para {symbol_base} en {exchange_id}")
        return None

    @retry_decorator(max_retries=2, base_delay=1.0)
    @timeout_decorator(seconds=30)
    async def fetch_position(self, exchange_id: str, market_symbol: str) -> Optional[Dict[str, Any]]:
        client = self.clients.get(exchange_id)
        if not client: return None
        try:
            positions = await client.fetch_positions([market_symbol])
            for p in positions:
                if p['symbol'] == market_symbol:
                    return p
            return None
        except Exception as e:
            logger.error(f"Error consultando posición en {exchange_id}: {e}")
            return None

    @retry_decorator(max_retries=2, base_delay=1.0)
    @timeout_decorator(seconds=30)
    async def cancel_order(self, exchange_id: str, market_symbol: str, order_id: str):
        client = self.clients.get(exchange_id)
        if not client: return False
        try:
            await client.cancel_order(order_id, market_symbol)
            return True
        except Exception as e:
            logger.debug(f"Error cancelando orden {order_id} en {exchange_id}: {e}")
            return False

# Instancia global
exchange_service = ExchangeService()
