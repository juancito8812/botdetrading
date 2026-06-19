import asyncio
import json
import logging
import time
from typing import Optional, List, Dict, Any
from models.data_classes import Signal, Position, PositionStatus
from services.exchange_service import exchange_service, _circuit_breakers
from core.manager import pos_manager
from utils.config import load_risk_config, load_api_creds, DATA_DIR
from utils.resilience.health_monitor import HealthMonitor
from utils.resilience.decorators import log_errors_decorator
from services.notifier import TelegramNotifier
from utils.helpers import atomic_write_json

logger = logging.getLogger("TradingBot")

# Archivo de persistencia para órdenes LIMIT pendientes
_PENDING_LIMITS_FILE = DATA_DIR / "pending_limits.json"

# Instancia global de HealthMonitor
health_monitor = HealthMonitor(check_interval=60.0)

class TradingEngine:
    def __init__(self):
        self.active_tasks = set()
        self.processed_signals = {}  # {(symbol, side): timestamp}
        self._dedup_lock = asyncio.Lock()
        self._pending_limit_orders: Dict[str, Any] = {}  # {order_id: {exchange_id, market_symbol, signal_data}}
        self._watchdog_task: Optional[asyncio.Task] = None
        self.health_monitor = health_monitor
        self._health_check_task = None
        self.notifier: Optional[TelegramNotifier] = None
        self._last_daily_report = 0.0  # timestamp del último reporte diario
        self._last_health_check_time = 0.0  # timestamp del último health check
        # Cargar órdenes LIMIT pendientes desde disco
        self._load_pending_limits()
        self._added_exchanges: set = set()

    def _signal_to_dict(self, signal: 'Signal') -> dict:
        """Convierte un objeto Signal a dict para serialización JSON."""
        return {
            "symbol": signal.symbol,
            "direccion": signal.direccion,
            "entry_min": signal.entry_min,
            "entry_max": signal.entry_max,
            "stop_loss": signal.stop_loss,
            "targets": list(signal.targets) if signal.targets else [],
            "raw_text": signal.raw_text,
        }

    def _signal_from_dict(self, data: dict) -> 'Signal':
        """Reconstruye un objeto Signal desde un dict."""
        return Signal(
            symbol=data.get("symbol", ""),
            direccion=data.get("direccion", ""),
            entry_min=data.get("entry_min"),
            entry_max=data.get("entry_max"),
            stop_loss=data.get("stop_loss"),
            targets=data.get("targets", []),
            raw_text=data.get("raw_text", ""),
        )

    def _load_pending_limits(self):
        """Carga órdenes LIMIT pendientes desde archivo (persistencia entre reinicios)."""
        try:
            if _PENDING_LIMITS_FILE.exists():
                with open(_PENDING_LIMITS_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for order_id, pending in data.items():
                        if isinstance(pending.get("signal"), dict):
                            pending["signal"] = self._signal_from_dict(pending["signal"])
                        # Reiniciar timestamp para que no expiren inmediatamente al recargar
                        pending["timestamp"] = time.time()
                    self._pending_limit_orders = data
                    logger.info(f"📂 Cargadas {len(data)} órdenes LIMIT pendientes desde disco")
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron cargar órdenes LIMIT pendientes: {e}")

    def _save_pending_limits(self):
        """Persiste órdenes LIMIT pendientes a disco."""
        try:
            # Convertir signals a dict antes de serializar
            serializable = {}
            for oid, pending in self._pending_limit_orders.items():
                entry = dict(pending)
                if isinstance(entry.get("signal"), Signal):
                    entry["signal"] = self._signal_to_dict(entry["signal"])
                serializable[oid] = entry
            atomic_write_json(_PENDING_LIMITS_FILE, serializable, indent=2, default=str)
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron persistir órdenes LIMIT: {e}")

    def _calculate_usdt_amount(self, balance: float, risk_pct: float,
                                 min_usdt: float,
                                 exchange_id: str = "") -> tuple:
        """
        Calcula la cantidad de USDT a usar según balance y % de riesgo.
        Retorna (usdt_to_use, error_msg_or_None).
        """
        usdt_to_use = balance * (risk_pct / 100.0)
        if usdt_to_use < min_usdt:
            if balance >= min_usdt:
                usdt_to_use = min_usdt
            else:
                return 0.0, f"Saldo insuficiente ({balance} < {min_usdt})"
        return usdt_to_use, None

    def _get_exchange_params(self, exchange_id: str, side_upper: str,
                             config: dict) -> dict:
        """Retorna parámetros específicos del exchange para órdenes."""
        params = {}
        if exchange_id == "bingx":
            params['positionSide'] = side_upper
        elif exchange_id == "bitget":
            params['tdMode'] = config.get("modo_margen", "cross")
        return params

    def _create_exchange_order(self, exchange_id, side_upper, stop_price, is_tp=False):
        if exchange_id == "bingx":
            order_type = 'TRIGGER_LIMIT' if is_tp else 'TRIGGER_MARKET'
            price = stop_price if is_tp else None
            params = {'stopPrice': stop_price, 'positionSide': side_upper}
        elif exchange_id == "bitget":
            order_type = 'limit'
            price = stop_price
            params = {'stopPrice': stop_price, 'planType': 'normal_plan', 'reduceOnly': True}
        else:
            order_type = 'limit' if is_tp else 'stop'
            price = stop_price if is_tp else None
            params = {'stopPrice': stop_price, 'reduceOnly': True}
        return order_type, price, params

    def _validate_price_deviation(self, price: float, entry_min: float,
                                   entry_max: float, side: str,
                                   max_deviation: float) -> tuple:
        """
        Valida si el precio actual está dentro de la desviación máxima del rango.
        Retorna (is_valid, reason_if_not).
        """
        if side == 'buy':
            if price > entry_max and entry_max > 0:
                deviation = ((price - entry_max) / entry_max) * 100
                if deviation > max_deviation:
                    return False, f"Precio {deviation:.1f}% sobre el rango de entrada"
            elif price < entry_min and entry_min > 0:
                deviation = ((entry_min - price) / entry_min) * 100
                if deviation > max_deviation:
                    return False, f"Precio {deviation:.1f}% bajo el rango de entrada"
        else:  # Sell / Short
            if price < entry_min and entry_min > 0:
                deviation = ((entry_min - price) / entry_min) * 100
                if deviation > max_deviation:
                    return False, f"Precio {deviation:.1f}% bajo el rango de entrada"
            elif price > entry_max and entry_max > 0:
                deviation = ((price - entry_max) / entry_max) * 100
                if deviation > max_deviation:
                    return False, f"Precio {deviation:.1f}% sobre el rango de entrada"
        return True, ""

    async def _is_duplicate(self, symbol, side, exchange_id, cooldown=30):
        async with self._dedup_lock:
            key = (symbol, side, exchange_id)
            now = time.time()
            if key in self.processed_signals:
                if now - self.processed_signals[key] < cooldown:
                    return True
            self.processed_signals[key] = now
            return False

    @log_errors_decorator(context={"module": "trading_engine"})
    async def execute_signal(self, signal: Signal, config: dict, exchange_id: str):
        """Orquesta la ejecución de una señal en un exchange específico."""
        task = asyncio.current_task()
        if task:
            self.active_tasks.add(task)

        cooldown = config.get("cooldown_segundos", 30)
        if await self._is_duplicate(signal.symbol, signal.direccion, exchange_id, cooldown):
            logger.info(f"⏭️ Señal duplicada ignorada en {exchange_id}: {signal.symbol} {signal.direccion}")
            if self.notifier:
                action = "Rechazada"
                await self.notifier.notify_signal_received(signal, exchange_id, action)
            return

        # Validación: rechazar señales sin Stop Loss si está configurado
        if config.get("requerir_stop_loss", True) and signal.stop_loss is None:
            logger.warning(f"⛔ Señal {signal.symbol} rechazada: SL requerido pero no encontrado")
            if self.notifier:
                action = "Rechazada"
                await self.notifier.notify_signal_received(signal, exchange_id, action)
            return

        client = exchange_service.clients.get(exchange_id)
        if not client:
            logger.error(f"Cliente no disponible para {exchange_id}")
            return

        market_symbol = await exchange_service.get_market_symbol(exchange_id, signal.symbol)
        if not market_symbol:
            logger.error(f"Símbolo {signal.symbol} no encontrado en {exchange_id}")
            return

        try:
            # 1. Obtener datos de mercado y balance
            price = await exchange_service.get_ticker_price(exchange_id, market_symbol)
            balance = await exchange_service.get_balance(exchange_id)

            if balance <= 0:
                logger.error(f"Saldo insuficiente en {exchange_id}: {balance}")
                return

            # 2. Configurar Apalancamiento y Margen
            leverage = int(config.get("apalancamiento", 10))
            margin_mode = config.get("modo_margen", "cross")
            side_upper = 'LONG' if signal.direccion.lower() == 'buy' else 'SHORT'
            await exchange_service.set_leverage(exchange_id, market_symbol, leverage, margin_mode, side_upper)

            # 3. Determinar modalidad de entrada (#1, #3 - Entrada LIMIT o validación de precio)
            entry_ok, decision = await self._decide_entry_type(
                exchange_id, market_symbol, signal, config, price, balance, leverage
            )
            if not entry_ok:
                logger.info(f"⏭️ Señal descartada en {exchange_id}: {decision}")
                return

            # Si la decisión fue una orden LIMIT, la ejecutó _decide_entry_type
            # y estamos esperando que se llene (posición pending)
            if decision == "limit_placed":
                logger.info(f"⏳ Orden LIMIT/DCA colocada en {exchange_id}, esperando llenado...")
                if self.notifier:
                    await self.notifier.notify_signal_received(signal, exchange_id, "LIMIT colocada")
                return

            # Si llegamos aquí, fue MARKET, continuar con SL/TP
            result = decision  # dict con datos de la orden ejecutada
            if not result:
                return

            entry_price = result["entry_price"]
            amount = result["amount"]
            entry_order_id = result.get("order_id")

            new_pos = Position(
                exchange_id=exchange_id,
                symbol=signal.symbol,
                market_symbol=market_symbol,
                side=signal.direccion,
                entry_price=entry_price,
                amount=amount,
                leverage=leverage,
                sl_price=signal.stop_loss or 0.0,
                highest_price=entry_price if signal.direccion.lower() == 'buy' else 0.0,
                lowest_price=entry_price if signal.direccion.lower() == 'sell' else float('inf'),
                entry_order_ids=[entry_order_id] if entry_order_id else []
            )

            # 5. Colocar Stop Loss (SL)
            await self._place_stop_loss(client, exchange_id, market_symbol, signal, amount, side_upper, new_pos)

            # 6. Colocar Take Profits (TP) con distribución personalizada (#5)
            tp_amounts = self._calculate_tp_amounts(amount, signal.targets, config)
            await self._place_take_profits(
                client, exchange_id, market_symbol, signal, tp_amounts, side_upper, new_pos
            )

            pos_manager.add_position(new_pos)
            logger.info(f"✅ Ejecución completa en {exchange_id} a {entry_price}")

            # Notificar apertura de posición
            if self.notifier:
                await self.notifier.notify_trade_open(new_pos)
            if self.notifier:
                action = "Ejecutada"
                await self.notifier.notify_signal_received(signal, exchange_id, action)

        except Exception as e:
            logger.error(f"Error fatal ejecutando señal en {exchange_id}: {e}", exc_info=True)
        finally:
            self.active_tasks.discard(task)

    async def _decide_entry_type(
        self, exchange_id: str, market_symbol: str,
        signal: Signal, config: dict, price: float,
        balance: float, leverage: int
    ) -> tuple:
        """
        Decide si usar MARKET, LIMIT o rechazar la señal.
        Retorna (ok, resultado).
        - ok=False → señal descartada
        - resultado="limit_placed" → se colocó LIMIT, pendiente
        - resultado=dict → orden MARKET ejecutada
        """
        modalidad = config.get("entrada_modalidad", "auto")
        desviacion_max = float(config.get("desviacion_maxima_porcentaje", 3.0))
        side = signal.direccion.lower()

        # Si la señal NO tiene rango de entrada, siempre MARKET
        if signal.entry_min is None and signal.entry_max is None:
            return await self._execute_market_entry(
                exchange_id, market_symbol, signal, config, price, balance, leverage
            )

        entry_min_val = signal.entry_min or 0.0
        entry_max_val = signal.entry_max or 0.0

        # #3 Validación de precio - ¿está el precio dentro de un rango aceptable?
        is_valid, reason = self._validate_price_deviation(
            price, entry_min_val, entry_max_val, side, desviacion_max
        )
        if not is_valid:
            logger.warning(
                f"⚠️ {reason}: precio={price:.2f}, rango=({entry_min_val}-{entry_max_val})"
            )
            return False, reason

        # Decidir MARKET vs LIMIT
        in_range = entry_min_val <= price <= entry_max_val

        if modalidad == "market" or in_range:
            # El precio ya está en rango → MARKET
            return await self._execute_market_entry(
                exchange_id, market_symbol, signal, config, price, balance, leverage
            )
        elif modalidad == "limit" or modalidad == "auto":
            # Colocar orden LIMIT en el borde del rango
            # Long → queremos comprar barato → LIMIT en entry_min_val
            # Short → queremos vender caro → LIMIT en entry_max_val
            limit_price = entry_min_val if side == 'buy' else entry_max_val
            dca_enabled = config.get("dca_habilitado", True)
            dca_parts = int(config.get("dca_partes", 3))

            if dca_enabled and dca_parts > 1 and entry_min_val > 0 and entry_max_val > 0 and entry_min_val != entry_max_val:
                # #2 DCA: múltiples órdenes escalonadas
                emin = signal.entry_min or 0.0
                emax = signal.entry_max or 0.0
                return await self._place_dca_orders(
                    exchange_id, market_symbol, signal, config, balance, leverage,
                    emin, emax, side, dca_parts
                )
            else:
                # Orden LIMIT única
                return await self._place_limit_entry(
                    exchange_id, market_symbol, signal, config, balance, leverage,
                    limit_price
                )

        # Fallback: MARKET
        return await self._execute_market_entry(
            exchange_id, market_symbol, signal, config, price, balance, leverage
        )

    async def _execute_market_entry(
        self, exchange_id, market_symbol, signal, config, price, balance, leverage
    ) -> tuple:
        """Ejecuta una orden MARKET de entrada."""
        client = exchange_service.clients.get(exchange_id)
        if not client:
            return False, "Cliente no disponible"

        side = signal.direccion.lower()
        side_upper = 'LONG' if side == 'buy' else 'SHORT'

        pct_por_exchange = config.get("porcentaje_capital", {})
        if isinstance(pct_por_exchange, dict):
            risk_pct = float(pct_por_exchange.get(exchange_id, 5.0))
        else:
            risk_pct = float(pct_por_exchange)
        min_usdt = float(config.get("cantidad_minima_usdt", 1.0))

        usdt_to_use, err = self._calculate_usdt_amount(balance, risk_pct, min_usdt, exchange_id)
        logger.info(f"📐 {exchange_id}: balance={balance:.2f}, risk={risk_pct}%, usdt={usdt_to_use:.2f}")
        if err:
            return False, err

        amount = (usdt_to_use * leverage) / price
        amount = float(client.amount_to_precision(market_symbol, amount))

        params = self._get_exchange_params(exchange_id, side_upper, config)

        logger.info(f"🚀 Enviando orden MARKET {side} en {exchange_id} para {market_symbol}")
        order = await client.create_order(market_symbol, 'market', side, amount, None, params)

        if not order.get('id'):
            logger.error(f"❌ Orden MARKET no devolvió ID en {exchange_id}")
            return False, "Orden sin ID"

        entry_price = float(order.get('average', price) or price)
        logger.info(f"✅ Entrada MARKET ejecutada en {exchange_id} a {entry_price}")

        return True, {
            "entry_price": entry_price,
            "amount": amount,
            "order_id": order.get('id')
        }

    async def _place_limit_entry(
        self, exchange_id, market_symbol, signal, config, balance, leverage, limit_price
    ) -> tuple:
        """Coloca una orden LIMIT de entrada."""
        client = exchange_service.clients.get(exchange_id)
        if not client:
            return False, "Cliente no disponible"

        side = signal.direccion.lower()
        side_upper = 'LONG' if side == 'buy' else 'SHORT'

        pct_por_exchange = config.get("porcentaje_capital", {})
        if isinstance(pct_por_exchange, dict):
            risk_pct = float(pct_por_exchange.get(exchange_id, 5.0))
        else:
            risk_pct = float(pct_por_exchange)
        min_usdt = float(config.get("cantidad_minima_usdt", 1.0))

        usdt_to_use, err = self._calculate_usdt_amount(balance, risk_pct, min_usdt, exchange_id)
        if err:
            return False, err

        amount = (usdt_to_use * leverage) / limit_price
        amount = float(client.amount_to_precision(market_symbol, amount))

        params = self._get_exchange_params(exchange_id, side_upper, config)

        logger.info(
            f"⏳ Colocando orden LIMIT {side} en {exchange_id} "
            f"para {market_symbol} a {limit_price}"
        )
        try:
            order = await client.create_order(
                market_symbol, 'limit', side, amount, limit_price, params
            )
            if not order.get('id'):
                logger.error(f"❌ Orden LIMIT no devolvió ID en {exchange_id}")
                return False, "Orden LIMIT sin ID"

            order_id = order.get('id')
            self._pending_limit_orders[order_id] = {
                "exchange_id": exchange_id,
                "market_symbol": market_symbol,
                "signal": self._signal_to_dict(signal),
                "config": config,
                "amount": amount,
                "limit_price": limit_price,
                "side": side,
                "side_upper": side_upper,
                "leverage": leverage,
                "usdt_to_use": usdt_to_use,
                "timestamp": time.time()
            }
            self._save_pending_limits()  # Persistir inmediatamente
            logger.info(f"✅ Orden LIMIT colocada: {order_id} a {limit_price}")
            return True, "limit_placed"
        except Exception as e:
            logger.error(f"❌ Error colocando orden LIMIT en {exchange_id}: {e}")
            return False, f"Error LIMIT: {e}"

    async def _place_dca_orders(
        self, exchange_id, market_symbol, signal, config, balance, leverage,
        entry_min, entry_max, side, dca_parts
    ) -> tuple:
        """Coloca múltiples órdenes LIMIT escalonadas (DCA)."""
        client = exchange_service.clients.get(exchange_id)
        if not client:
            return False, "Cliente no disponible"

        step = (entry_max - entry_min) / (dca_parts + 1)
        prices = [entry_min + step * (i + 1) for i in range(dca_parts)]
        if side == 'sell':
            prices.reverse()

        pct_por_exchange = config.get("porcentaje_capital", {})
        if isinstance(pct_por_exchange, dict):
            risk_pct = float(pct_por_exchange.get(exchange_id, 5.0))
        else:
            risk_pct = float(pct_por_exchange)
        min_usdt = float(config.get("cantidad_minima_usdt", 1.0))

        total_usdt, err = self._calculate_usdt_amount(balance, risk_pct, min_usdt, exchange_id)
        logger.info(f"📐 DCA {exchange_id}: balance={balance:.2f}, risk={risk_pct}%, total={total_usdt:.2f} USDT, min={min_usdt}")
        if err:
            return False, f"Saldo insuficiente para DCA"
        usdt_per_order = total_usdt / dca_parts

        if usdt_per_order < min_usdt:
            if total_usdt >= min_usdt * dca_parts:
                usdt_per_order = min_usdt
            else:
                logger.warning(f"DCA: {total_usdt:.2f} USDT total < mínimo {min_usdt}x{dca_parts}, usando {usdt_per_order:.2f}/orden")

        price_now = await exchange_service.get_ticker_price(exchange_id, market_symbol)
        base_amount = (usdt_per_order * leverage) / price_now
        base_amount = float(client.amount_to_precision(market_symbol, base_amount))

        side_upper = 'LONG' if side == 'buy' else 'SHORT'
        params = self._get_exchange_params(exchange_id, side_upper, config)

        placed_count = 0
        for i, limit_price in enumerate(prices):
            try:
                limit_price_prec = float(client.price_to_precision(market_symbol, limit_price))
                logger.info(
                    f"⏳ DCA {i+1}/{dca_parts}: LIMIT {side} {market_symbol} "
                    f"a {limit_price_prec} en {exchange_id}"
                )
                order = await client.create_order(
                    market_symbol, 'limit', side, base_amount,
                    limit_price_prec, params
                )
                if order.get('id'):
                    order_id = order.get('id')
                    self._pending_limit_orders[order_id] = {
                        "exchange_id": exchange_id,
                        "market_symbol": market_symbol,
                        "signal": self._signal_to_dict(signal),
                        "config": config,
                        "amount": base_amount,
                        "limit_price": limit_price_prec,
                        "side": side,
                        "side_upper": side_upper,
                        "leverage": leverage,
                        "usdt_to_use": usdt_per_order,
                        "timestamp": time.time(),
                        "is_dca": True,
                    }
                    placed_count += 1
            except Exception as e:
                logger.warning(f"⚠️ DCA {i+1} falló en {exchange_id}: {e}")

        if placed_count > 0:
            self._save_pending_limits()  # Persistir DCA
            logger.info(f"✅ {placed_count}/{dca_parts} órdenes DCA colocadas en {exchange_id}")
            return True, "limit_placed"
        return False, "No se pudo colocar ninguna orden DCA"

    async def _place_stop_loss(
        self, client, exchange_id, market_symbol, signal, amount, side_upper, new_pos
    ):
        """Coloca Stop Loss."""
        if not signal.stop_loss:
            return

        side = signal.direccion.lower()
        sl_side = 'sell' if side == 'buy' else 'buy'
        sl_amount = float(client.amount_to_precision(market_symbol, amount))

        try:
            order_type, price, params = self._create_exchange_order(exchange_id, side_upper, signal.stop_loss)
            sl_order = await client.create_order(market_symbol, order_type, sl_side, sl_amount, price, params)

            new_pos.sl_order_id = sl_order.get('id')
            logger.info(f"🛑 Stop Loss colocado a {signal.stop_loss}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo colocar SL en {exchange_id}: {e}")

    def _calculate_tp_amounts(self, total_amount: float, targets: List[float], config: dict) -> List[float]:
        """#5 Calcula la cantidad por TP según la distribución configurada."""
        if not targets:
            return []

        distribucion = config.get("tp_distribucion", "progresivo")
        n_targets = len(targets)

        if distribucion == "igual":
            amount_step = total_amount / n_targets
            return [amount_step] * n_targets

        else:
            pesos = config.get("tp_pesos", [50, 25, 15, 10])
            if len(pesos) < n_targets:
                pesos = pesos + [pesos[-1]] * (n_targets - len(pesos))
            pesos = pesos[:n_targets]
            total_peso = sum(pesos)
            return [(total_amount * p / total_peso) for p in pesos]

    async def _place_take_profits(
        self, client, exchange_id, market_symbol, signal, tp_amounts, side_upper, new_pos
    ):
        """#5 Coloca Take Profits con cantidades personalizadas."""
        if not signal.targets or not tp_amounts:
            return

        side = signal.direccion.lower()
        tp_side = 'sell' if side == 'buy' else 'buy'

        total_tp = sum(tp_amounts)

        for i, target in enumerate(signal.targets):
            if i >= len(tp_amounts):
                break
            tp_amount = float(client.amount_to_precision(market_symbol, tp_amounts[i]))
            if tp_amount <= 0:
                continue

            try:
                order_type, price, params = self._create_exchange_order(exchange_id, side_upper, target, is_tp=True)
                tp_order = await client.create_order(market_symbol, order_type, tp_side, tp_amount, price, params)
                new_pos.tp_order_ids.append(tp_order.get('id'))
                pct_str = f" ({(tp_amounts[i]/total_tp*100):.0f}%)" if total_tp > 0 else ""
                logger.info(f"🎯 Target {i+1} colocado a {target}{pct_str}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo colocar TP{i+1} en {exchange_id}: {e}")

    async def _process_filled_limit_order(self, exchange_id, market_symbol, order, pending):
        """Procesa una orden LIMIT que se llenó. Crea posición + SL/TP."""
        side = pending["side"]
        side_upper = pending["side_upper"]
        # Reconstruir Signal si vino como dict desde disco
        raw_signal = pending["signal"]
        if isinstance(raw_signal, dict):
            signal: Signal = self._signal_from_dict(raw_signal)
        else:
            signal: Signal = raw_signal
        config = pending["config"]
        leverage = pending["leverage"]
        amount = pending["amount"]

        # Verificar si el llenado es parcial
        filled = float(order.get('filled', amount))
        if filled <= 0:
            filled = amount

        entry_price = float(order.get('average', pending["limit_price"]))
        logger.info(f"✅ Orden LIMIT llenada en {exchange_id} a {entry_price}, filled={filled}")

        new_pos = Position(
            exchange_id=exchange_id,
            symbol=signal.symbol,
            market_symbol=market_symbol,
            side=signal.direccion,
            entry_price=entry_price,
            amount=filled,
            leverage=leverage,
            sl_price=signal.stop_loss or 0.0,
            highest_price=entry_price if side == 'buy' else 0.0,
            lowest_price=entry_price if side == 'sell' else float('inf'),
            entry_order_ids=[order.get('id')],
            entry_filled_amount=filled
        )

        client = exchange_service.clients.get(exchange_id)
        if client:
            await self._place_stop_loss(client, exchange_id, market_symbol, signal, filled, side_upper, new_pos)
            tp_amounts = self._calculate_tp_amounts(filled, signal.targets, config)
            await self._place_take_profits(client, exchange_id, market_symbol, signal, tp_amounts, side_upper, new_pos)

        pos_manager.add_position(new_pos)
        if self.notifier:
            await self.notifier.notify_limit_filled(new_pos)
        logger.info(f"✅ Posición creada desde orden LIMIT en {exchange_id}")

        # Notificar si fue una orden DCA que se ejecutó
        if pending.get("is_dca") and self.notifier:
            await self.notifier.notify_dca_executed(
                exchange_id, market_symbol, entry_price
            )

    async def _check_stale_limit_orders(self, config: dict, now: float):
        """Revisa órdenes LIMIT pendientes: timeout, llenadas, canceladas."""
        stale_orders = []
        for order_id, pending in list(self._pending_limit_orders.items()):
            elapsed = now - pending["timestamp"]
            timeout_min = int(config.get("timeout_orden_limit_minutos", 30))
            exchange_id = pending["exchange_id"]
            market_symbol = pending["market_symbol"]

            client = exchange_service.clients.get(exchange_id)
            if not client:
                # Si el exchange no está conectado, esperar al próximo ciclo
                continue

            try:
                order = await client.fetch_order(order_id, market_symbol)
                status = order.get('status', '')
                if status == 'closed':
                    # Eliminar del dict ANTES de procesar para evitar duplicados
                    self._pending_limit_orders.pop(order_id, None)
                    await self._process_filled_limit_order(exchange_id, market_symbol, order, pending)
                    # No agregar a stale_orders — ya se eliminó arriba
                elif status == 'canceled' or status == 'expired':
                    logger.info(f"❌ Orden LIMIT {order_id} cancelada/expirada en {exchange_id}")
                    stale_orders.append(order_id)
                elif elapsed > timeout_min * 60:
                    logger.warning(f"⏰ Timeout de orden LIMIT {order_id} en {exchange_id}")
                    try:
                        await client.cancel_order(order_id, market_symbol)
                    except Exception as e:
                        logger.warning(f"⚠️ Error cancelando orden LIMIT {order_id} en {exchange_id}: {e}")
                    stale_orders.append(order_id)
            except Exception:
                logger.warning(f"Error fetching order {order_id}", exc_info=True)
                if elapsed > timeout_min * 60:
                    try:
                        await client.cancel_order(order_id, market_symbol)
                        logger.info(f"✅ Orden LIMIT cancelada (timeout fetch): {order_id}")
                    except Exception as cancel_err:
                        logger.warning(f"⚠️ No se pudo cancelar orden huérfana {order_id}: {cancel_err}")
                    stale_orders.append(order_id)

        for oid in stale_orders:
            self._pending_limit_orders.pop(oid, None)
        if stale_orders:
            self._save_pending_limits()
        return stale_orders

    async def _sync_positions(self, config: dict):
        """Sincroniza posiciones abiertas con exchange: PnL, trailing, breakeven."""
        open_positions = pos_manager.get_open_positions()
        for pos in open_positions:
            client = exchange_service.clients.get(pos.exchange_id)
            if not client:
                continue

            try:
                position_data = await exchange_service.fetch_position(
                    pos.exchange_id, pos.market_symbol
                )

                if position_data:
                    contracts = position_data.get('contracts')
                    if contracts is None:
                        contracts = position_data.get('size')
                    if contracts is None:
                        contracts = position_data.get('amount', 0)
                    contracts = float(contracts)
                else:
                    continue

                exit_price = float(position_data.get('markPrice', 0)) or pos.entry_price

                if contracts == 0:
                    pos.exit_price = exit_price
                    pos.close_time = time.time()
                    pos.status = PositionStatus.CLOSED
                    pos_manager.save()
                    logger.info(f"🔒 Posición {pos.symbol} en {pos.exchange_id} cerrada")
                    if self.notifier:
                        # Solo notificar SL si realmente fue SL (no TP, no liquidación)
                        if pos.sl_order_id and not pos.tp1_hit:
                            await self.notifier.notify_sl_hit(pos)
                        else:
                            await self.notifier.notify_trade_closed(pos)
                    continue

                if 0 < contracts < pos.amount:
                    logger.info(f"📉 Posición {pos.symbol} reducida de {pos.amount} a {contracts} (TP parcial)")
                    pos.amount = contracts
                    if pos.sl_order_id:
                        sl_side = 'sell' if pos.side.lower() == 'buy' else 'buy'
                        sl_amount = float(client.amount_to_precision(pos.market_symbol, contracts))
                        side_upper = 'LONG' if pos.side.lower() == 'buy' else 'SHORT'
                        await exchange_service.cancel_order(pos.exchange_id, pos.market_symbol, pos.sl_order_id)
                        order_type, price, params = self._create_exchange_order(pos.exchange_id, side_upper, pos.sl_price)
                        sl_order = await client.create_order(pos.market_symbol, order_type, sl_side, sl_amount, price, params)
                        pos.sl_order_id = sl_order.get('id')
                    pos_manager.save()

                mark_price = float(position_data.get('markPrice', 0))
                if mark_price > 0:
                    if pos.side.lower() == 'buy':
                        if mark_price > pos.highest_price:
                            pos.highest_price = mark_price
                    else:
                        if pos.lowest_price == 0 or mark_price < pos.lowest_price:
                            pos.lowest_price = mark_price

                contracts = float(position_data.get('contracts', pos.amount))
                contract_size = 1.0
                if client and client.markets and pos.market_symbol in client.markets:
                    market_info = client.markets[pos.market_symbol]
                    raw_size = market_info.get('contractSize', 1.0)
                    if raw_size:
                        contract_size = float(raw_size)
                unrealized_pnl = position_data.get('unrealizedPnl')
                if unrealized_pnl is not None:
                    pos.pnl = float(unrealized_pnl)
                elif mark_price > 0 and contracts > 0:
                    if pos.side.lower() == 'buy':
                        pos.pnl = (mark_price - pos.entry_price) * contracts * contract_size
                    else:
                        pos.pnl = (pos.entry_price - mark_price) * contracts * contract_size

                await self._check_tp1_hit(pos, client)

                if config.get("auto_breakeven", True) and not pos.is_breakeven and pos.tp1_hit and not pos.trailing_activated:
                    logger.info(f"🔄 Moving SL to break-even for {pos.symbol}")
                    await self._move_sl_to_breakeven(pos, client)
                    pos.is_breakeven = True
                    pos_manager.save()

                await self._check_trailing_stop(pos, config, client)

            except Exception as e:
                logger.debug(f"Watchdog: Error verificando posición {pos.symbol}: {e}")

    async def _check_tp1_hit(self, pos, client):
        """Verifica si TP1 fue alcanzado. Solo revisa el primer TP."""
        if not pos.tp1_hit and pos.tp_order_ids:
            tp1_id = pos.tp_order_ids[0]  # Solo TP1
            try:
                order = await client.fetch_order(tp1_id, pos.market_symbol)
                if order.get('status') == 'closed' or order.get('filled', 0) > 0:
                    pos.tp1_hit = True
                    pos_manager.save()
                    logger.info(f"🎯 TP1 alcanzado para {pos.symbol} en {pos.exchange_id}")
                    if self.notifier:
                        await self.notifier.notify_tp_hit(pos, 1)
            except Exception as e:
                logger.warning(f"⚠️ Error fetching TP1 order for {pos.symbol}: {e}")

    async def _sync_failed_exchanges(self):
        """Reintenta conexión con exchanges fallidos."""
        failed_snapshot = list(exchange_service.failed_exchanges)
        creds = load_api_creds()
        for ex_id in failed_snapshot:
            logger.info(f"🔄 Reintentando conexión con {ex_id}...")
            ex_creds = creds["exchanges"].get(ex_id, {})
            if ex_creds.get("enabled"):
                await exchange_service.create_client(ex_id, ex_creds)

    def _clean_old_signals(self, now: float):
        """Limpia señales procesadas antiguas (> 1 hora)."""
        stale_keys = [k for k, v in self.processed_signals.items() if now - v > 3600]
        for k in stale_keys:
            del self.processed_signals[k]
        if stale_keys:
            logger.debug(f"🧹 Limpiadas {len(stale_keys)} señales antiguas del caché")

    async def cancel_pending_tasks(self):
        """Cancela todas las tareas de ejecución de señales pendientes."""
        tasks = list(self.active_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.active_tasks.clear()
        logger.info("⏹️ Tareas pendientes canceladas")

    def stop_watchdog(self):
        """Cancela el watchdog si está corriendo."""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            self._watchdog_task = None
            logger.info("⏹️ Watchdog detenido")

    async def _watchdog_tick(self):
        """Una iteración del watchdog. Extraída para testing."""
        config = load_risk_config()
        now = time.time()

        # 0. Health check periódico (cada 60s)
        if now - self._last_health_check_time >= 60:
            self._last_health_check_time = now
            await self.health_monitor._run_cycle()

        # 1. Revisar órdenes LIMIT pendientes
        await self._check_stale_limit_orders(config, now)

        # 2. Sincronizar posiciones abiertas
        await self._sync_positions(config)

        for ex_id in list(exchange_service.clients.keys()):
            if ex_id not in self._added_exchanges:
                self.health_monitor.add_exchange(ex_id)
                self._added_exchanges.add(ex_id)
        self.health_monitor.sync_circuit_breaker_states(_circuit_breakers)

        # 3. Reintentar exchanges fallidos
        await self._sync_failed_exchanges()

        # 4. Limpiar señales procesadas antiguas
        self._clean_old_signals(now)

        # 5. Reporte diario (cada 24h, solo si pasó 24h desde el último envío)
        if self.notifier and self._last_daily_report > 0 and now - self._last_daily_report > 86400:
            self._last_daily_report = now
            all_positions = pos_manager.get_all_positions()
            balances = {}
            for ex_id in list(exchange_service.clients.keys()):
                try:
                    bal = await exchange_service.get_balance(ex_id)
                    balances[ex_id] = bal
                except Exception:
                    balances[ex_id] = 0.0
            await self.notifier.send_daily_report(all_positions, balances)

    async def watchdog(self):
        """Vigila órdenes pendientes, sincroniza estados y monitorea salud."""
        self.health_monitor.set_health_check_func(self._health_check_exchange)
        self._last_health_check_time = time.time()
        consecutive_errors = 0
        max_consecutive_errors = 5
        while True:
            try:
                await self._watchdog_tick()
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error en watchdog ({consecutive_errors}/{max_consecutive_errors}): {e}", exc_info=True)
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical("Demasiados errores consecutivos en watchdog, deteniendo")
                    break
            await asyncio.sleep(30)

    async def _check_trailing_stop(self, pos: Position, config: dict, client):
        """#4 Trailing stop: mueve el SL cuando el precio se mueve a favor."""
        if not config.get("trailing_stop_habilitado", True):
            return
        if not pos.sl_order_id:
            return
        # No usar trailing si ya se activó break-even (son mutuamente excluyentes)
        if pos.is_breakeven:
            return

        activacion_pct = float(config.get("trailing_activacion_porcentaje", 1.5))
        distancia_pct = float(config.get("trailing_distancia_porcentaje", 0.8))

        if pos.side.lower() == 'buy':
            # Para LONG: el precio sube, trailing se activa si ganancia > X%
            if pos.highest_price <= 0:
                return
            gain_pct = ((pos.highest_price - pos.entry_price) / pos.entry_price) * 100
            if gain_pct >= activacion_pct and not pos.trailing_activated:
                pos.trailing_activated = True
                logger.info(f"🔝 Trailing activado para {pos.symbol} (ganancia: {gain_pct:.2f}%)")
                if self.notifier:
                    await self.notifier.notify_trailing_activated(pos)

            if pos.trailing_activated:
                new_sl = pos.highest_price * (1 - distancia_pct / 100)
                if new_sl > pos.entry_price:
                    await self._update_trailing_sl(pos, new_sl, client)
        else:
            # Para SHORT: el precio baja, trailing se activa si ganancia > X%
            if pos.lowest_price <= 0 or pos.lowest_price == float('inf'):
                return
            gain_pct = ((pos.entry_price - pos.lowest_price) / pos.entry_price) * 100
            if gain_pct >= activacion_pct and not pos.trailing_activated:
                pos.trailing_activated = True
                logger.info(f"🔝 Trailing activado para {pos.symbol} (ganancia: {gain_pct:.2f}%)")
                if self.notifier:
                    await self.notifier.notify_trailing_activated(pos)

            if pos.trailing_activated:
                new_sl = pos.lowest_price * (1 + distancia_pct / 100)
                if new_sl < pos.entry_price:
                    await self._update_trailing_sl(pos, new_sl, client)

    async def _update_trailing_sl(self, pos: Position, new_sl: float, client):
        """Actualiza el SL a una nueva posición (trailing)."""
        try:
            # Cancelar SL anterior
            sl_id = pos.sl_order_id or ""
            await exchange_service.cancel_order(
                pos.exchange_id, pos.market_symbol, sl_id
            )

            sl_side = 'sell' if pos.side.lower() == 'buy' else 'buy'
            sl_amount = float(client.amount_to_precision(pos.market_symbol, pos.amount))
            side_upper = 'LONG' if pos.side.lower() == 'buy' else 'SHORT'

            order_type, price, params = self._create_exchange_order(pos.exchange_id, side_upper, new_sl)
            sl_order = await client.create_order(pos.market_symbol, order_type, sl_side, sl_amount, price, params)

            pos.sl_order_id = sl_order.get('id')
            pos_manager.save()
            logger.info(f"🔄 Trailing SL movido a {new_sl:.4f} para {pos.symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Error moviendo trailing SL: {e}")

    async def _health_check_exchange(self, exchange_id: str) -> bool:
        """
        Función de health check para un exchange.
        Usa los mercados disponibles del exchange para probar conectividad,
        fallback a símbolos hardcodeados.
        """
        # Primero intentar usar mercados reales del exchange
        client = exchange_service.clients.get(exchange_id)
        if client and client.markets:
            # Buscar un mercado USDT swap/future activo
            for sym, market in client.markets.items():
                if 'USDT' in sym and (market.get('swap') or market.get('future')):
                    try:
                        price = await exchange_service.get_ticker_price(exchange_id, sym)
                        if price > 0:
                            return True
                    except Exception:
                        continue

        # Fallback a símbolos hardcodeados comunes
        symbols_to_try = ["BTC/USDT", "BTC/USDT:USDT", "BTCUSDT", "ETH/USDT", "ETH/USDT:USDT"]
        for sym in symbols_to_try:
            try:
                price = await exchange_service.get_ticker_price(exchange_id, sym)
                if price > 0:
                    return True
            except Exception:
                continue
        return False

    async def _move_sl_to_breakeven(self, pos: Position, client):
        """Mueve el SL al precio de entrada."""
        try:
            if pos.sl_order_id:
                await exchange_service.cancel_order(
                    pos.exchange_id, pos.market_symbol, pos.sl_order_id
                )

            sl_side = 'sell' if pos.side.lower() == 'buy' else 'buy'
            side_upper = 'LONG' if pos.side.lower() == 'buy' else 'SHORT'

            order_type, price, params = self._create_exchange_order(pos.exchange_id, side_upper, pos.entry_price)
            sl_order = await client.create_order(pos.market_symbol, order_type, sl_side, pos.amount, price, params)

            pos.sl_order_id = sl_order.get('id')
            pos_manager.save()
            logger.info(f"✅ SL movido a break-even ({pos.entry_price}) para {pos.symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Error moviendo SL a break-even: {e}")


# Instancia global
trading_engine = TradingEngine()