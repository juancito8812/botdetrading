"""Servicio de notificaciones vía Telegram."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from models.data_classes import Position, PositionStatus

logger = logging.getLogger("TradingBot")


# Preferencias por defecto de notificaciones
DEFAULT_NOTIFICATION_PREFS = {
    "trade_open": True,
    "trade_closed": True,
    "tp_hit": True,
    "trailing_activated": True,
    "health_change": True,
    "circuit_breaker": True,
    "system_error": True,
    "daily_report": True,
    "sl_hit": True,
    "signal_received": True,
    "limit_filled": True,
}


class TelegramNotifier:
    """
    Envía notificaciones formateadas a Telegram.

    Reusa el cliente Telethon existente. Se integra mediante hooks
    en engine.py, health_monitor.py y main.py.

    IMPORTANTE: Telegram con cuentas de usuario (no bot) SOLO puede enviar a:
      - Tu propio chat ("Mensajes Guardados") — siempre funciona
      - Otros usuarios que HAYAN INICIADO conversación contigo primero
      - Grupos donde la cuenta del bot SEA MIEMBRO
      - Canales donde la cuenta del bot SEA MIEMBRO/ADMIN
    """

    # Rate limiting: mínimo 2s entre notificaciones
    _MIN_INTERVAL = 2.0

    def __init__(
        self,
        telegram_client: Any,
        chat_id: str,
        enabled: bool = True,
        notification_prefs: Optional[Dict[str, bool]] = None,
    ):
        self.client = telegram_client
        self.chat_id = chat_id
        self.enabled = enabled
        self._enabled_notifications: Dict[str, bool] = (
            notification_prefs if notification_prefs else dict(DEFAULT_NOTIFICATION_PREFS)
        )
        self.history: List[str] = []
        self._resolved_entity = None
        self._last_send_time = 0.0
        self._cached_chat_id: Optional[str] = None

    def is_notification_enabled(self, notif_type: str) -> bool:
        """Verifica si un tipo de notificación está habilitado."""
        return self._enabled_notifications.get(notif_type, True)

    def set_notification_prefs(self, prefs: Dict[str, bool]):
        """Actualiza las preferencias de notificaciones."""
        self._enabled_notifications.update(prefs)

    def get_notification_prefs(self) -> Dict[str, bool]:
        """Retorna copia de las preferencias actuales."""
        return dict(self._enabled_notifications)

    def _add_to_history(self, text: str):
        """Agrega una entrada al historial (max 20)."""
        timestamp = datetime.now().strftime("%H:%M")
        self.history.append(f"[{timestamp}] {text}")
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def get_recent(self, count: int = 20) -> List[str]:
        """Retorna las últimas N notificaciones."""
        return self.history[-count:]

    async def _notify(self, notif_type: str, msg: str, history: str) -> bool:
        """Helper: check pref -> send -> add history. Retorna True si envió."""
        if not self.is_notification_enabled(notif_type):
            return False
        ok = await self.send_message(msg)
        if ok:
            self._add_to_history(history)
        return ok

    async def _resolve_chat_id(self) -> Any:
        """
        Convierte self.chat_id al tipo correcto y resuelve la entidad.

        Retorna la entidad resuelta (int o Entity) para usar en send_message.
        Si self.chat_id cambió (ej: usuario lo modificó en settings.json),
        invalida la caché automáticamente.
        """
        raw: Union[int, str] = self.chat_id
        if isinstance(raw, str) and raw.isdigit():
            raw = int(raw)
        elif isinstance(raw, str) and raw.startswith('-') and raw[1:].isdigit():
            raw = int(raw)

        # Invalidar caché si el chat_id cambió
        if self._cached_chat_id is not None and self._cached_chat_id != self.chat_id:
            self._resolved_entity = None
            self._cached_chat_id = None

        # Si ya tenemos la entidad resuelta en caché, la retornamos
        if self._resolved_entity is not None:
            return self._resolved_entity

        # Intentar resolver la entidad (obtener error claro si no existe/accesible)
        try:
            entity = await self.client.get_entity(raw)
            self._resolved_entity = entity
            self._cached_chat_id = self.chat_id
            return entity
        except ValueError as e:
            err_msg = str(e).lower()
            if "cannot find any entity" in err_msg or "no user has" in err_msg:
                logger.error(
                    f"Telegram no encuentra la entidad con ID '{raw}'. "
                    f"Para enviar a OTRO USUARIO: esa cuenta debe escribirte PRIMERO. "
                    f"Para enviar a un GRUPO: la cuenta del bot debe ser MIEMBRO del grupo."
                )
            raise

    async def send_message(self, text: str) -> bool:
        """
        Envía un mensaje de texto a Telegram con rate limiting.

        - Mínimo {_MIN_INTERVAL}s entre mensajes para evitar rate limit de Telegram.
        - NOTA: El error 'event loop must not change' de Telethon es intermitente
          y el mensaje se envía igual. La reconexión la maneja main.py.
        """
        if not self.enabled:
            return False

        # Rate limiting: esperar si se envió hace poco
        now = time.time()
        elapsed = now - self._last_send_time
        if elapsed < self._MIN_INTERVAL:
            await asyncio.sleep(self._MIN_INTERVAL - elapsed)

        try:
            entity = await self._resolve_chat_id()
            await self.client.send_message(entity, text)
            self._last_send_time = time.time()
            return True
        except ValueError as e:
            err_str = str(e).lower()
            if "cannot find any entity" in err_str or "no user has" in err_str:
                logger.error(
                    f"❌ No se puede enviar el mensaje. "
                    f"La entidad con ID '{self.chat_id}' no es accesible.\n"
                    f"   📌 Para OTRO USUARIO: esa cuenta debe escribirte PRIMERO en Telegram.\n"
                    f"   📌 Para un GRUPO: agrega la cuenta del bot al grupo."
                )
            else:
                logger.error(f"Error enviando notificación: {e}")
            return False
        except Exception as e:
            error_str = str(e).lower()
            if "event loop" in error_str and "must not change" in error_str:
                logger.debug(f"Telethon event loop warning (el mensaje probablemente llegó): {e}")
            else:
                logger.error(f"Error enviando notificación: {e}")
            return False

    async def notify_trade_open(self, position: Position):
        side_emoji = "🚀" if position.side.lower() == "buy" else "🔻"
        side_text = "LONG" if position.side.lower() == "buy" else "SHORT"
        size_usdt = position.amount * position.entry_price * position.leverage
        if position.sl_price and position.sl_price > 0:
            sl_text = f"${position.sl_price:,.2f}"
        elif position.sl_order_id:
            sl_text = "Colocado"
        else:
            sl_text = "Sin SL"
        tp_count = len(position.tp_order_ids) if position.tp_order_ids else 0

        msg = (
            f"{side_emoji} {side_text} ABIERTA\n"
            f"Exchange: {position.exchange_id}\n"
            f"Símbolo: {position.symbol}\n"
            f"Entrada: ${position.entry_price:,.2f}\n"
            f"Tamaño: ${size_usdt:,.2f}\n"
            f"Apalancamiento: {position.leverage}x\n"
            f"SL: {sl_text}\n"
            f"TPs: {tp_count} niveles"
        )
        await self._notify("trade_open", msg, f"{side_emoji} {side_text} ABIERTA {position.symbol}")

    async def notify_trade_closed(self, position: Position):
        side_text = "LONG" if position.side.lower() == "buy" else "SHORT"
        pnl_val = position.pnl if position.pnl is not None else 0.0
        # Usar el monto original (entry_filled_amount) si existe, para PnL% correcto tras TP parcial
        original_amount = max(position.amount, position.entry_filled_amount) or position.amount
        entry_val = position.entry_price * original_amount if position.entry_price and original_amount > 0 else 0
        pnl_pct = (pnl_val / entry_val) * 100 if entry_val > 0 else 0.0
        emoji = "✅" if pnl_val >= 0 else "❌"
        exit_p = position.exit_price if position.exit_price else position.entry_price
        duration = ""
        if position.close_time and position.open_time:
            mins = int((position.close_time - position.open_time) / 60)
            hours = mins // 60
            mins = mins % 60
            if hours > 0:
                duration = f"Duración: {hours}h {mins}min\n"
            else:
                duration = f"Duración: {mins}min\n"

        msg = (
            f"{emoji} POSICIÓN CERRADA\n"
            f"Exchange: {position.exchange_id}\n"
            f"Símbolo: {position.symbol}\n"
            f"Side: {side_text}\n"
            f"Entrada: ${position.entry_price:,.2f}\n"
            f"Salida: ${exit_p:,.2f}\n"
            f"PnL: ${pnl_val:+.2f} ({pnl_pct:+.2f}%)\n"
            f"{duration}"
        )
        await self._notify("trade_closed", msg, f"{emoji} CERRADA {position.symbol} ${pnl_val:+.2f}")

    async def notify_tp_hit(self, position: Position, tp_number: int, tp_price: Optional[float] = None, tp_pnl: Optional[float] = None):
        price_str = f" a ${tp_price:,.2f}" if tp_price else ""
        pnl_line = f"\nPnL: ${tp_pnl:+.2f}" if tp_pnl is not None else ""
        msg = (
            f"🎯 TP{tp_number} alcanzado{price_str}\n"
            f"Símbolo: {position.symbol}\n"
            f"Exchange: {position.exchange_id}{pnl_line}"
        )
        await self._notify("tp_hit", msg, f"🎯 TP{tp_number} {position.symbol}")

    async def notify_sl_hit(self, position: Position):
        loss = position.pnl if position.pnl is not None else 0.0
        exit_p = position.exit_price if position.exit_price else position.entry_price
        msg = (
            f"🛑 STOP LOSS EJECUTADO\n"
            f"Exchange: {position.exchange_id}\n"
            f"Símbolo: {position.symbol}\n"
            f"Entrada: ${position.entry_price:,.2f}\n"
            f"Salida: ${exit_p:,.2f}\n"
            f"Pérdida: ${loss:+.2f}"
        )
        await self._notify("sl_hit", msg, f"🛑 SL {position.symbol} ${loss:+.2f}")


    async def notify_signal_received(self, signal, exchange_id: str, action: str):
        msg = (
            f"📡 Señal recibida\n"
            f"Símbolo: {signal.symbol}\n"
            f"Dirección: {signal.direccion}\n"
            f"Exchange: {exchange_id}\n"
            f"Acción: {action}"
        )
        await self._notify("signal_received", msg, f"📡 {signal.symbol} {action}")


    async def notify_limit_filled(self, position: Position):
        msg = (
            f"✅ Orden LIMIT llenada\n"
            f"Exchange: {position.exchange_id}\n"
            f"Símbolo: {position.symbol}\n"
            f"Entrada: ${position.entry_price:,.2f}\n"
            f"Cantidad: {position.amount}"
        )
        await self._notify("limit_filled", msg, f"✅ LIMIT {position.symbol}")


    async def notify_dca_executed(self, exchange_id: str, market_symbol: str, price: float):
        """Notifica que una orden DCA se ejecutó."""
        msg = (
            f"📊 DCA ejecutado\n"
            f"Exchange: {exchange_id}\n"
            f"Símbolo: {market_symbol}\n"
            f"Precio: ${price:,.2f}"
        )
        await self._notify("limit_filled", msg, f"📊 DCA {market_symbol}")


    async def notify_trailing_activated(self, position: Position):
        """Notifica que el trailing stop se activó."""
        msg = (
            f"🔝 Trailing Stop activado\n"
            f"Símbolo: {position.symbol}\n"
            f"Exchange: {position.exchange_id}\n"
            f"Precio entrada: ${position.entry_price:,.2f}"
        )
        await self._notify("trailing_activated", msg, f"🔝 Trailing {position.symbol}")

    async def notify_health_change(
        self, exchange: str, status: str,
        consecutive_failures: int = 0, avg_latency_ms: float = 0.0,
    ):
        """Notifica cambio en el estado de salud de un exchange."""
        emoji = "✅" if status == "healthy" else ("⚠️" if status == "degraded" else "🔴")
        msg = (
            f"{emoji} Health Monitor - {exchange}\n"
            f"Estado: {status.upper()}\n"
            f"Fallos consecutivos: {consecutive_failures}\n"
            f"Latencia: {avg_latency_ms:.0f}ms"
        )
        await self._notify("health_change", msg, f"{emoji} {exchange}: {status.upper()}")

    async def notify_circuit_breaker(
        self, exchange: str, state: str, retry_after: float = 0.0,
    ):
        """Notifica cambio de estado en el circuit breaker."""
        msg = (
            f"🔴 Circuit Breaker - {exchange}\n"
            f"Estado: {state.upper()}\n"
            f"Reintentar en: {retry_after:.0f}s"
        )
        await self._notify("circuit_breaker", msg, f"🔴 CB {exchange}: {state.upper()}")

    async def notify_error(self, module: str, error_message: str):
        """Notifica un error crítico del sistema."""
        await self._notify("system_error",
            f"❌ Error en {module}\n{error_message[:200]}",
            f"❌ Error en {module}")

    async def send_daily_report(
        self, positions: List[Position], balances: Dict[str, float],
    ):
        """Envía un reporte diario con posiciones abiertas y balances."""
        if not self.is_notification_enabled("daily_report"):
            return
        today = datetime.now().strftime("%d/%m/%Y")
        lines = [f"📊 Reporte Diario — {today}", "━" * 25]

        open_positions = [p for p in positions if p.status == PositionStatus.OPEN]
        lines.append(f"Posiciones abiertas: {len(open_positions)}")

        total_pnl = sum(p.pnl or 0.0 for p in positions)
        lines.append(f"PnL total: ${total_pnl:+.2f}")
        lines.append("")

        if open_positions:
            lines.append("Posiciones:")
            for p in open_positions:
                side = "LONG" if p.side.lower() == "buy" else "SHORT"
                lines.append(f"  {p.exchange_id} {p.symbol} {side}")
            lines.append("")

        lines.append("Balances:")
        if balances:
            for ex, bal in balances.items():
                lines.append(f"  {ex}: ${bal:.2f}")
        else:
            lines.append("  (sin datos - exchanges no conectados)")

        ok = await self.send_message("\n".join(lines))
        if ok:
            self._add_to_history("📊 Reporte diario enviado")
