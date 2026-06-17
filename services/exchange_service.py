import asyncio
import logging
import threading
import ccxt.async_support as ccxt_async
from typing import Dict, Optional, Any
from utils.config import EXCHANGES_DEFAULTS, load_api_creds
from utils.resilience.decorators import (
    retry_decorator, circuit_breaker_decorator_dynamic,
    timeout_decorator, log_errors_decorator,
)
from utils.resilience.circuit_breaker import CircuitBreaker

logger = logging.getLogger("TradingBot")

# Circuit breakers por exchange
_circuit_breakers = {}

def _get_circuit_breaker(exchange_id: str) -> CircuitBreaker:
    if exchange_id not in _circuit_breakers:
        _circuit_breakers[exchange_id] = CircuitBreaker(
            name=exchange_id,
            failure_threshold=5,
            reset_timeout=60,
        )
        from utils.config import DATA_DIR
        cb_file = DATA_DIR / "resilience" / f"cb_{exchange_id}.json"
        if cb_file.exists():
            try:
                _circuit_breakers[exchange_id].load(str(cb_file))
            except Exception as e:
                logger.warning("No se pudo cargar CB desde disco para %s: %s", exchange_id, e)
    return _circuit_breakers[exchange_id]

class ExchangeService:
    def __init__(self):
        self.clients: Dict[str, Any] = {}
        self.failed_exchanges = set()
        self._clients_lock = threading.Lock()

    async def _ensure_event_loop(self, exchange_id: str) -> bool:
        with self._clients_lock:
            if exchange_id in self.clients:
                return True
            creds = load_api_creds()
            ex_creds = creds["exchanges"].get(exchange_id, {})
            needs_create = ex_creds.get("enabled")
        if needs_create:
            client = await self._create_client_impl(exchange_id, ex_creds)
            with self._clients_lock:
                if client:
                    self.clients[exchange_id] = client
                return exchange_id in self.clients
        return False

    @timeout_decorator(seconds=20)
    async def create_client(self, exchange_id: str, creds: Dict[str, Any]) -> Optional[Any]:
        """Crea e inicializa un cliente de CCXT."""
        with self._clients_lock:
            if exchange_id in self.clients:
                try:
                    await self.clients[exchange_id].close()
                except Exception as e:
                    logger.warning("Error cerrando cliente existente: %s", e)
                del self.clients[exchange_id]

        client = await self._create_client_impl(exchange_id, creds)

        with self._clients_lock:
            if client:
                self.clients[exchange_id] = client
                self.failed_exchanges.discard(exchange_id)
        return client

    async def _create_client_impl(self, exchange_id: str, creds: Dict[str, Any]) -> Optional[Any]:
        """Crea el cliente CCXT (sin lock, llamar desde el event loop correcto)."""
        try:
            exchange_class = getattr(ccxt_async, exchange_id)
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
                except Exception as e: logger.warning("Error cargando time difference para BingX: %s", e)
                
            return client
            
        except Exception as e:
            logger.error(f"Error inicializando {exchange_id}: {e}")
            with self._clients_lock:
                self.failed_exchanges.add(exchange_id)
            return None

    async def close_all(self):
        from utils.config import DATA_DIR
        cb_dir = DATA_DIR / "resilience"
        cb_dir.mkdir(parents=True, exist_ok=True)
        for ex_id, cb in _circuit_breakers.items():
            cb.persist(str(cb_dir / f"cb_{ex_id}.json"))
        with self._clients_lock:
            clients = list(self.clients.items())
        for ex_id, client in clients:
            try:
                await asyncio.wait_for(client.close(), timeout=5)
            except Exception as e:
                logger.warning("Error cerrando cliente %s: %s", ex_id, e)
        with self._clients_lock:
            self.clients.clear()

    @circuit_breaker_decorator_dynamic(resolver=_get_circuit_breaker)
    @retry_decorator(max_retries=3, base_delay=1.0)
    @timeout_decorator(seconds=30)
    @log_errors_decorator(context={"module": "exchange_service"})
    async def get_balance(self, exchange_id: str) -> float:
        with self._clients_lock:
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
            if isinstance(usdt, dict):
                free = usdt.get('free')
                if free is not None:
                    logger.info(f"💰 Balance {exchange_id}: disponible={free}, total={usdt.get('total', 'N/A')}")
                    return float(free)
                avail = usdt.get('available')
                if avail is not None:
                    logger.info(f"💰 Balance {exchange_id}: disponible={avail}")
                    return float(avail)
                total = usdt.get('total')
                if total is not None:
                    logger.info(f"💰 Balance {exchange_id}: total={total} (sin free)")
                    return float(total)
            try:
                return float(usdt)
            except (TypeError, ValueError):
                pass
            return 0.0
        except Exception as e:
            logger.error(f"Error balance {exchange_id}: {e}")
            return 0.0

    @circuit_breaker_decorator_dynamic(resolver=_get_circuit_breaker)
    @retry_decorator(max_retries=2, base_delay=1.0)
    @timeout_decorator(seconds=30)
    async def get_ticker_price(self, exchange_id: str, market_symbol: str) -> float:
        with self._clients_lock:
            client = self.clients.get(exchange_id)
            if not client:
                logger.warning("Cliente no disponible para %s en get_ticker_price", exchange_id)
                return 0.0
        try:
            ticker = await client.fetch_ticker(market_symbol)
            return float(ticker['last'])
        except RuntimeError as e:
            if "Event loop is closed" in str(e) or "event loop" in str(e).lower():
                logger.warning("Event loop error en %s, eliminando y recreando...", exchange_id)
                with self._clients_lock:
                    self.clients.pop(exchange_id, None)
                for _ in range(3):
                    creds = load_api_creds()
                    ex_creds = creds["exchanges"].get(exchange_id, {})
                    if not ex_creds.get("enabled"):
                        break
                    new_client = await self._create_client_impl(exchange_id, ex_creds)
                    if new_client:
                        with self._clients_lock:
                            self.clients[exchange_id] = new_client
                        try:
                            ticker = await new_client.fetch_ticker(market_symbol)
                            return float(ticker['last'])
                        except RuntimeError:
                            continue
                    await asyncio.sleep(1)
                logger.error("No se pudo recuperar cliente %s tras event loop error", exchange_id)
                return 0.0
            raise

    @circuit_breaker_decorator_dynamic(resolver=_get_circuit_breaker)
    @retry_decorator(max_retries=2, base_delay=1.0)
    @timeout_decorator(seconds=30)
    async def set_leverage(self, exchange_id: str, market_symbol: str, leverage: int, margin_mode: str = 'cross', side: str = 'LONG'):
        with self._clients_lock:
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
                params['side'] = side.upper()
            
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

    @circuit_breaker_decorator_dynamic(resolver=_get_circuit_breaker)
    @retry_decorator(max_retries=2, base_delay=1.0)
    async def get_market_symbol(self, exchange_id: str, symbol_base: str) -> Optional[str]:
        with self._clients_lock:
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
        with self._clients_lock:
            client = self.clients.get(exchange_id)
            if not client: return None
        try:
            positions = await client.fetch_positions([market_symbol])
            for p in positions:
                if p['symbol'] == market_symbol:
                    return p
            return None
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("Event loop error en fetch_position para %s", exchange_id)
                with self._clients_lock:
                    client = self.clients.pop(exchange_id, None)
                if client:
                    try:
                        await client.close()
                    except Exception:
                        pass
            return None
        except Exception as e:
            logger.error("Error consultando posición en %s: %s", exchange_id, e)
            return None

    @retry_decorator(max_retries=2, base_delay=1.0)
    @timeout_decorator(seconds=30)
    async def cancel_order(self, exchange_id: str, market_symbol: str, order_id: str):
        with self._clients_lock:
            client = self.clients.get(exchange_id)
            if not client: return False
        try:
            await client.cancel_order(order_id, market_symbol)
            return True
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("Event loop error en cancel_order para %s", exchange_id)
                with self._clients_lock:
                    client = self.clients.pop(exchange_id, None)
                if client:
                    try:
                        await client.close()
                    except Exception:
                        pass
            return False
        except Exception as e:
            logger.debug("Error cancelando orden %s en %s: %s", order_id, exchange_id, e)
            return False

# Instancia global
exchange_service = ExchangeService()
