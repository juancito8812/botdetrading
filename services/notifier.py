"""Servicio de notificaciones vía Telegram."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from models.data_classes import Position

logger = logging.getLogger("TradingBot")


class TelegramNotifier:
    """
    Envía notificaciones formateadas a Telegram.

    Reusa el cliente Telethon existente. Se integra mediante hooks
    en engine.py, health_monitor.py y main.py.
    """

    def __init__(
        self,
        telegram_client: Any,
        chat_id: str,
        enabled: bool = True,
    ):
        self.client = telegram_client
        self.chat_id = chat_id
        self.enabled = enabled
        self.history: List[str] = []

    def _add_to_history(self, text: str):
        """Agrega una entrada al historial (max 20)."""
        timestamp = datetime.now().strftime("%H:%M")
        self.history.append(f"[{timestamp}] {text}")
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def get_recent(self, count: int = 20) -> List[str]:
        """Retorna las últimas N notificaciones."""
        return self.history[-count:]

    async def send_message(self, text: str) -> bool:
        """Envía un mensaje de texto a Telegram."""
        if not self.enabled:
            return False
        try:
            await self.client.send_message(self.chat_id, text)
            return True
        except Exception as e:
            logger.error(f"Error enviando notificación: {e}")
            return False

    async def notify_trade_open(self, position: Position):
        """Notifica apertura de una posición."""
        side_emoji = "🚀" if position.side.lower() == "buy" else "🔻"
        side_text = "LONG" if position.side.lower() == "buy" else "SHORT"
        sl_text = f"${position.entry_price}" if position.sl_order_id else "Sin SL"
        tp_count = len(position.tp_order_ids) if position.tp_order_ids else 0

        msg = (
            f"{side_emoji} {side_text} ABIERTA\n"
            f"Exchange: {position.exchange_id}\n"
            f"Símbolo: {position.symbol}\n"
            f"Entrada: ${position.entry_price:,.2f}\n"
            f"Cantidad: {position.amount}\n"
            f"Apalancamiento: {position.leverage}x\n"
            f"SL: {sl_text}\n"
            f"TPs: {tp_count} niveles"
        )
        await self.send_message(msg)
        self._add_to_history(f"{side_emoji} {side_text} ABIERTA {position.symbol}")

    async def notify_trade_closed(self, position: Position):
        """Notifica cierre de una posición."""
        side_text = "LONG" if position.side.lower() == "buy" else "SHORT"
        pnl_str = f"{position.pnl:+.2f}" if position.pnl else "0.00"
        emoji = "✅" if position.pnl and position.pnl >= 0 else "❌"

        msg = (
            f"{emoji} POSICIÓN CERRADA\n"
            f"Exchange: {position.exchange_id}\n"
            f"Símbolo: {position.symbol}\n"
            f"Side: {side_text}\n"
            f"Entrada: ${position.entry_price:,.2f}\n"
            f"PnL: ${pnl_str}"
        )
        await self.send_message(msg)
        emoji_closed = "✅" if position.pnl and position.pnl >= 0 else "❌"
        self._add_to_history(f"{emoji_closed} CERRADA {position.symbol} ${position.pnl:+.2f}" if position.pnl else f"❌ CERRADA {position.symbol}")

    async def notify_tp_hit(self, position: Position, tp_number: int):
        """Notifica que se alcanzó un Take Profit."""
        msg = (
            f"🎯 TP{tp_number} alcanzado\n"
            f"Símbolo: {position.symbol}\n"
            f"Exchange: {position.exchange_id}\n"
            f"Precio entrada: ${position.entry_price:,.2f}"
        )
        await self.send_message(msg)
        self._add_to_history(f"🎯 TP{tp_number} {position.symbol}")

    async def notify_trailing_activated(self, position: Position):
        """Notifica que el trailing stop se activó."""
        msg = (
            f"🔝 Trailing Stop activado\n"
            f"Símbolo: {position.symbol}\n"
            f"Exchange: {position.exchange_id}\n"
            f"Precio entrada: ${position.entry_price:,.2f}"
        )
        await self.send_message(msg)
        self._add_to_history(f"🔝 Trailing {position.symbol}")

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
        await self.send_message(msg)
        emoji_h = "✅" if status == "healthy" else ("⚠️" if status == "degraded" else "🔴")
        self._add_to_history(f"{emoji_h} {exchange}: {status.upper()}")

    async def notify_circuit_breaker(
        self, exchange: str, state: str, retry_after: float = 0.0,
    ):
        """Notifica cambio de estado en el circuit breaker."""
        msg = (
            f"🔴 Circuit Breaker - {exchange}\n"
            f"Estado: {state.upper()}\n"
            f"Reintentar en: {retry_after:.0f}s"
        )
        await self.send_message(msg)
        self._add_to_history(f"🔴 CB {exchange}: {state.upper()}")

    async def notify_error(self, module: str, error_message: str):
        """Notifica un error crítico del sistema."""
        msg = (
            f"❌ Error en {module}\n"
            f"{error_message[:200]}"
        )
        await self.send_message(msg)
        self._add_to_history(f"❌ Error en {module}")

    async def send_daily_report(
        self, positions: List[Position], balances: Dict[str, float],
    ):
        """Envía un reporte diario con posiciones abiertas y balances."""
        today = datetime.now().strftime("%d/%m/%Y")
        lines = [f"📊 Reporte Diario — {today}", "━" * 25]

        open_positions = [p for p in positions if p.status == "open"]
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
        for ex, bal in balances.items():
            lines.append(f"  {ex}: ${bal:.2f}")

        await self.send_message("\n".join(lines))
        self._add_to_history("📊 Reporte diario enviado")
