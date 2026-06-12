import asyncio
import logging
import time
from typing import Optional, List
from models.data_classes import Signal, Position
from services.exchange_service import exchange_service
from core.manager import pos_manager
from utils.config import load_risk_config

logger = logging.getLogger("TradingBot")

class TradingEngine:
    def __init__(self):
        self.active_tasks = set()
        self.processed_signals = {}  # {(symbol, side): timestamp}
        self._pending_limit_orders = {}  # {order_id: {exchange_id, market_symbol, signal_data}}

    def _is_duplicate(self, symbol, side, exchange_id, cooldown=30):
        key = (symbol, side, exchange_id)
        now = time.time()
        if key in self.processed_signals:
            if now - self.processed_signals[key] < cooldown:
                return True
        self.processed_signals[key] = now
        return False

    async def execute_signal(self, signal: Signal, config: dict, exchange_id: str):
        """Orquesta la ejecución de una señal en un exchange específico."""
        cooldown = config.get("cooldown_segundos", 30)
        if self._is_duplicate(signal.simbolo, signal.direccion, exchange_id, cooldown):
            logger.info(f"⏭️ Señal duplicada ignorada en {exchange_id}: {signal.simbolo} {signal.direccion}")
            return

        client = exchange_service.clients.get(exchange_id)
        if not client:
            logger.error(f"Cliente no disponible para {exchange_id}")
            return

        market_symbol = await exchange_service.get_market_symbol(exchange_id, signal.simbolo)
        if not market_symbol:
            logger.error(f"Símbolo {signal.simbolo} no encontrado en {exchange_id}")
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
                logger.info(f"⏳ Orden LIMIT colocada en {exchange_id}, esperando llenado...")
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
                symbol=signal.simbolo,
                market_symbol=market_symbol,
                side=signal.direccion,
                entry_price=entry_price,
                amount=amount,
                leverage=leverage,
                highest_price=entry_price if signal.direccion.lower() == 'buy' else 0.0,
                lowest_price=entry_price if signal.direccion.lower() == 'sell' else float('inf'),
                entry_order_ids=[entry_order_id] if entry_order_id else []
            )

            # 5. Colocar Stop Loss (SL)
            await self._place_stop_loss(client, exchange_id, market_symbol, signal, amount, side_upper, new_pos)

            # 6. Colocar Take Profits (TP) con distribución personalizada (#5)
            amount_remaining = amount
            tp_amounts = self._calculate_tp_amounts(amount, signal.targets, config)
            await self._place_take_profits(
                client, exchange_id, market_symbol, signal, tp_amounts, side_upper, new_pos
            )

            pos_manager.add_position(new_pos)
            logger.info(f"✅ Ejecución completa en {exchange_id} a {entry_price}")

        except Exception as e:
            logger.error(f"Error fatal ejecutando señal en {exchange_id}: {e}", exc_info=True)

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
        if side == 'buy':
            if price > entry_max_val:
                deviation = ((price - entry_max_val) / entry_max_val) * 100
                if deviation > desviacion_max:
                    logger.warning(
                        f"⚠️ Precio demasiado alto ({price:.2f}) vs entrada "
                        f"({entry_min_val}-{entry_max_val}). "
                        f"Desviación: {deviation:.1f}% "
                        f"(máx: {desviacion_max}%)"
                    )
                    return (
                        False,
                        f"Precio {deviation:.1f}% sobre el rango de entrada"
                    )
            elif price < entry_min_val and entry_min_val > 0:
                deviation = ((entry_min_val - price) / entry_min_val) * 100
                if deviation > desviacion_max:
                    logger.warning(
                        f"⚠️ Precio demasiado bajo ({price:.2f}) vs entrada "
                        f"({entry_min_val}-{entry_max_val}). "
                        f"Desviación: {deviation:.1f}% "
                        f"(máx: {desviacion_max}%)"
                    )
                    return (
                        False,
                        f"Precio {deviation:.1f}% bajo el rango de entrada"
                    )
        else:  # Sell / Short
            if price < entry_min_val and entry_min_val > 0:
                deviation = ((entry_min_val - price) / entry_min_val) * 100
                if deviation > desviacion_max:
                    return (
                        False,
                        f"Precio {deviation:.1f}% bajo el rango de entrada"
                    )
            elif price > entry_max_val and entry_max_val > 0:
                deviation = ((price - entry_max_val) / entry_max_val) * 100
                if deviation > desviacion_max:
                    return (
                        False,
                        f"Precio {deviation:.1f}% sobre el rango de entrada"
                    )

        # Decidir MARKET vs LIMIT
        in_range = (
            entry_min_val <= price <= entry_max_val
        ) if entry_min_val and entry_max_val else False

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
        risk_pct = float(pct_por_exchange.get(exchange_id, 5.0))
        usdt_to_use = balance * (risk_pct / 100.0)

        min_usdt = float(config.get("cantidad_minima_usdt", 10.0))
        if usdt_to_use < min_usdt:
            if balance >= min_usdt:
                usdt_to_use = min_usdt
            else:
                return False, f"Saldo insuficiente ({balance} < {min_usdt})"

        amount = (usdt_to_use * leverage) / price
        amount = float(client.amount_to_precision(market_symbol, amount))

        params = {}
        if exchange_id == "bingx":
            params['positionSide'] = side_upper
        elif exchange_id == "bitget":
            params['tdMode'] = config.get("modo_margen", "cross")

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
        risk_pct = float(pct_por_exchange.get(exchange_id, 5.0))
        usdt_to_use = balance * (risk_pct / 100.0)

        min_usdt = float(config.get("cantidad_minima_usdt", 10.0))
        if usdt_to_use < min_usdt:
            if balance >= min_usdt:
                usdt_to_use = min_usdt
            else:
                return False, f"Saldo insuficiente ({balance} < {min_usdt})"

        price_now = await exchange_service.get_ticker_price(exchange_id, market_symbol)
        amount = (usdt_to_use * leverage) / price_now
        amount = float(client.amount_to_precision(market_symbol, amount))

        params = {}
        if exchange_id == "bingx":
            params['positionSide'] = side_upper
        elif exchange_id == "bitget":
            params['tdMode'] = config.get("modo_margen", "cross")

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
                "signal": signal,
                "config": config,
                "amount": amount,
                "limit_price": limit_price,
                "side": side,
                "side_upper": side_upper,
                "leverage": leverage,
                "usdt_to_use": usdt_to_use,
                "timestamp": time.time()
            }
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
        risk_pct = float(pct_por_exchange.get(exchange_id, 5.0))
        total_usdt = balance * (risk_pct / 100.0)
        usdt_per_order = total_usdt / dca_parts

        min_usdt = float(config.get("cantidad_minima_usdt", 10.0))
        if usdt_per_order < min_usdt:
            if total_usdt >= min_usdt * dca_parts:
                usdt_per_order = min_usdt
            else:
                return False, f"Saldo insuficiente para DCA"

        price_now = await exchange_service.get_ticker_price(exchange_id, market_symbol)
        base_amount = (usdt_per_order * leverage) / price_now
        base_amount = float(client.amount_to_precision(market_symbol, base_amount))

        params = {}
        side_upper = 'LONG' if side == 'buy' else 'SHORT'
        if exchange_id == "bingx":
            params['positionSide'] = side_upper
        elif exchange_id == "bitget":
            params['tdMode'] = config.get("modo_margen", "cross")

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
                        "signal": signal,
                        "config": config,
                        "amount": base_amount,
                        "limit_price": limit_price_prec,
                        "side": side,
                        "side_upper": side_upper,
                        "leverage": leverage,
                        "usdt_to_use": usdt_per_order,
                        "timestamp": time.time()
                    }
                    placed_count += 1
            except Exception as e:
                logger.warning(f"⚠️ DCA {i+1} falló en {exchange_id}: {e}")

        if placed_count > 0:
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
            if exchange_id == "bingx":
                sl_order = await client.create_order(
                    market_symbol, 'TRIGGER_MARKET', sl_side, sl_amount, None, {
                        'stopPrice': signal.stop_loss,
                        'positionSide': side_upper
                    }
                )
            elif exchange_id == "bitget":
                sl_order = await client.create_order(
                    market_symbol, 'limit', sl_side, sl_amount, signal.stop_loss, {
                        'stopPrice': signal.stop_loss,
                        'planType': 'normal_plan',
                        'reduceOnly': True
                    }
                )
            else:
                sl_order = await client.create_order(
                    market_symbol, 'market', sl_side, sl_amount, None, {
                        'stopPrice': signal.stop_loss,
                        'reduceOnly': True
                    }
                )

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

        elif distribucion == "progresivo":
            pesos = config.get("tp_pesos", [50, 25, 15, 10])
            # Ajustar cantidad de pesos al número de targets
            if len(pesos) < n_targets:
                pesos = pesos + [pesos[-1]] * (n_targets - len(pesos))
            pesos = pesos[:n_targets]

            total_peso = sum(pesos)
            return [(total_amount * p / total_peso) for p in pesos]

        # "personalizado" - usar pesos exactos
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

        for i, target in enumerate(signal.targets):
            if i >= len(tp_amounts):
                break
            tp_amount = float(client.amount_to_precision(market_symbol, tp_amounts[i]))
            if tp_amount <= 0:
                continue

            try:
                if exchange_id == "bingx":
                    tp_order = await client.create_order(
                        market_symbol, 'TRIGGER_LIMIT', tp_side, tp_amount, target, {
                            'stopPrice': target,
                            'positionSide': side_upper
                        }
                    )
                elif exchange_id == "bitget":
                    tp_order = await client.create_order(
                        market_symbol, 'limit', tp_side, tp_amount, target, {
                            'stopPrice': target,
                            'planType': 'normal_plan',
                            'reduceOnly': True
                        }
                    )
                else:
                    tp_order = await client.create_order(
                        market_symbol, 'limit', tp_side, tp_amount, target, {
                            'stopPrice': target,
                            'reduceOnly': True
                        }
                    )
                new_pos.tp_order_ids.append(tp_order.get('id'))
                logger.info(f"🎯 Target {i+1} colocado a {target} ({(tp_amounts[i]/sum(tp_amounts)*100):.0f}%)")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo colocar TP{i+1} en {exchange_id}: {e}")

    async def _process_filled_limit_order(self, exchange_id, market_symbol, order, pending):
        """Procesa una orden LIMIT que se llenó. Crea posición + SL/TP."""
        from models.data_classes import Signal

        side = pending["side"]
        side_upper = pending["side_upper"]
        signal: Signal = pending["signal"]
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
            symbol=signal.simbolo,
            market_symbol=market_symbol,
            side=signal.direccion,
            entry_price=entry_price,
            amount=filled,
            leverage=leverage,
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
        logger.info(f"✅ Posición creada desde orden LIMIT en {exchange_id}")

    async def watchdog(self):
        """Vigila órdenes pendientes y sincroniza estados."""
        while True:
            try:
                config = load_risk_config()
                now = time.time()

                # 0. Revisar órdenes LIMIT pendientes (#1 timeout)
                stale_orders = []
                for order_id, pending in list(self._pending_limit_orders.items()):
                    elapsed = now - pending["timestamp"]
                    timeout_min = int(config.get("timeout_orden_limit_minutos", 10))
                    exchange_id = pending["exchange_id"]
                    market_symbol = pending["market_symbol"]

                    client = exchange_service.clients.get(exchange_id)
                    if not client:
                        stale_orders.append(order_id)
                        continue

                    try:
                        order = await client.fetch_order(order_id, market_symbol)
                        status = order.get('status', '')
                        if status == 'closed':
                            await self._process_filled_limit_order(exchange_id, market_symbol, order, pending)
                            stale_orders.append(order_id)
                        elif status == 'canceled' or status == 'expired':
                            logger.info(f"❌ Orden LIMIT {order_id} cancelada/expirada en {exchange_id}")
                            stale_orders.append(order_id)
                        elif elapsed > timeout_min * 60:
                            # Timeout: cancelar orden LIMIT
                            logger.warning(f"⏰ Timeout de orden LIMIT {order_id} en {exchange_id}")
                            try:
                                await client.cancel_order(order_id, market_symbol)
                            except Exception:
                                pass
                            stale_orders.append(order_id)
                    except Exception:
                        if elapsed > timeout_min * 60:
                            stale_orders.append(order_id)

                for oid in stale_orders:
                    self._pending_limit_orders.pop(oid, None)

                # 1. Sincronizar posiciones abiertas
                open_positions = pos_manager.get_open_positions()
                for pos in open_positions:
                    client = exchange_service.clients.get(pos.exchange_id)
                    if not client:
                        continue

                    try:
                        # Verificar estado de la posición
                        position_data = await exchange_service.fetch_position(
                            pos.exchange_id, pos.market_symbol
                        )

                        if position_data:
                            contracts = float(position_data.get('contracts', 0))
                            if contracts == 0:
                                pos.status = "closed"
                                pos_manager.save()
                                logger.info(f"🔒 Posición {pos.symbol} en {pos.exchange_id} cerrada")
                                continue

                            # Actualizar precio más alto/bajo para trailing (#4)
                            mark_price = float(position_data.get('markPrice', 0))
                            if mark_price > 0:
                                if pos.side.lower() == 'buy':
                                    if mark_price > pos.highest_price:
                                        pos.highest_price = mark_price
                                else:
                                    if pos.lowest_price == 0 or mark_price < pos.lowest_price:
                                        pos.lowest_price = mark_price

                            # #4 Trailing stop automático
                            await self._check_trailing_stop(pos, config, client)

                            # Auto Breakeven (existente)
                            if config.get("auto_breakeven", True) and not pos.is_breakeven and pos.tp1_hit:
                                logger.info(f"🔄 Moviendo SL a break-even para {pos.symbol}")
                                await self._move_sl_to_breakeven(pos, client)
                                pos.is_breakeven = True
                                pos_manager.save()

                            # Verificar TP1 hit
                            if not pos.tp1_hit and pos.tp_order_ids:
                                for tp_id in pos.tp_order_ids:
                                    try:
                                        order = await client.fetch_order(tp_id, pos.market_symbol)
                                        if order.get('status') == 'closed' or order.get('filled', 0) > 0:
                                            pos.tp1_hit = True
                                            pos_manager.save()
                                            logger.info(f"🎯 TP1 alcanzado para {pos.symbol} en {pos.exchange_id}")
                                            break
                                    except Exception:
                                        pass

                    except Exception as e:
                        logger.debug(f"Watchdog: Error verificando posición {pos.symbol}: {e}")

                # 2. Reintentar exchanges fallidos
                failed_snapshot = list(exchange_service.failed_exchanges)
                for ex_id in failed_snapshot:
                    logger.info(f"🔄 Reintentando conexión con {ex_id}...")
                    from utils.config import load_api_creds
                    creds = load_api_creds()
                    ex_creds = creds["exchanges"].get(ex_id, {})
                    if ex_creds.get("enabled"):
                        await exchange_service.create_client(ex_id, ex_creds)

                # 3. Limpiar señales procesadas antiguas (> 1 hora)
                stale_keys = [k for k, v in self.processed_signals.items() if now - v > 3600]
                for k in stale_keys:
                    del self.processed_signals[k]
                if stale_keys:
                    logger.debug(f"🧹 Limpiadas {len(stale_keys)} señales antiguas del caché")

            except Exception as e:
                logger.error(f"Error en watchdog: {e}", exc_info=True)

            await asyncio.sleep(30)  # Cada 30 segundos

    async def _check_trailing_stop(self, pos: Position, config: dict, client):
        """#4 Trailing stop: mueve el SL cuando el precio se mueve a favor."""
        if not config.get("trailing_stop_habilitado", True):
            return
        if not pos.sl_order_id:
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

            if pos.exchange_id == "bingx":
                sl_order = await client.create_order(
                    pos.market_symbol, 'TRIGGER_MARKET', sl_side, sl_amount, None, {
                        'stopPrice': new_sl,
                        'positionSide': side_upper
                    }
                )
            elif pos.exchange_id == "bitget":
                sl_order = await client.create_order(
                    pos.market_symbol, 'limit', sl_side, sl_amount, new_sl, {
                        'stopPrice': new_sl,
                        'planType': 'normal_plan',
                        'reduceOnly': True
                    }
                )
            else:
                sl_order = await client.create_order(
                    pos.market_symbol, 'market', sl_side, sl_amount, None, {
                        'stopPrice': new_sl,
                        'reduceOnly': True
                    }
                )

            pos.sl_order_id = sl_order.get('id')
            pos_manager.save()
            logger.info(f"🔄 Trailing SL movido a {new_sl:.4f} para {pos.symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Error moviendo trailing SL: {e}")

    async def _move_sl_to_breakeven(self, pos: Position, client):
        """Mueve el SL al precio de entrada."""
        try:
            if pos.sl_order_id:
                await exchange_service.cancel_order(
                    pos.exchange_id, pos.market_symbol, pos.sl_order_id
                )

            sl_side = 'sell' if pos.side.lower() == 'buy' else 'buy'
            side_upper = 'LONG' if pos.side.lower() == 'buy' else 'SHORT'

            if pos.exchange_id == "bingx":
                sl_order = await client.create_order(
                    pos.market_symbol, 'TRIGGER_MARKET', sl_side, pos.amount, None, {
                        'stopPrice': pos.entry_price,
                        'positionSide': side_upper
                    }
                )
            elif pos.exchange_id == "bitget":
                sl_order = await client.create_order(
                    pos.market_symbol, 'limit', sl_side, pos.amount, pos.entry_price, {
                        'stopPrice': pos.entry_price,
                        'planType': 'normal_plan',
                        'reduceOnly': True
                    }
                )
            else:
                sl_order = await client.create_order(
                    pos.market_symbol, 'market', sl_side, pos.amount, None, {
                        'stopPrice': pos.entry_price,
                        'reduceOnly': True
                    }
                )

            pos.sl_order_id = sl_order.get('id')
            pos_manager.save()
            logger.info(f"✅ SL movido a break-even ({pos.entry_price}) para {pos.symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Error moviendo SL a break-even: {e}")


# Instancia global
trading_engine = TradingEngine()