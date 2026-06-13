# Sistema de Notificaciones Telegram — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar un sistema de notificaciones vía Telegram para eventos de trading, alertas del sistema y reportes periódicos.

**Architecture:** Clase `TelegramNotifier` que usa el cliente Telethon existente. Se integra mediante hooks directos en `engine.py` (trading), `health_monitor.py` (sistema) y una tarea programada en `main.py` (reportes diarios).

**Tech Stack:** Python 3.10+, Telethon (ya instalado), pytest. Sin nuevas dependencias.

---

## Estructura de Archivos

**NUEVOS:**
- `services/notifier.py` — TelegramNotifier: servicio principal de notificaciones
- `tests/test_notifier.py` — Tests unitarios

**MODIFICADOS:**
- `core/engine.py` — Añadir notificaciones en execute_signal() y watchdog()
- `utils/resilience/health_monitor.py` — Añadir callback `on_status_change`
- `main.py` — Inicializar TelegramNotifier y conectar

---

### Task 1: TelegramNotifier — Servicio Principal

**Files:**
- Create: `services/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write tests for the notifier**

```python
# tests/test_notifier.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.notifier import TelegramNotifier
from models.data_classes import Position


@pytest.fixture
def mock_telegram():
    client = AsyncMock()
    return client


@pytest.fixture
def notifier(mock_telegram):
    return TelegramNotifier(
        telegram_client=mock_telegram,
        chat_id="test_chat",
        enabled=True,
    )


@pytest.mark.asyncio
async def test_send_message(notifier, mock_telegram):
    """Enviar un mensaje básico."""
    result = await notifier.send_message("Hello from bot!")
    assert result is True
    mock_telegram.send_message.assert_called_once_with("test_chat", "Hello from bot!")


@pytest.mark.asyncio
async def test_disabled_notifier(mock_telegram):
    """Notificador deshabilitado no envía mensajes."""
    n = TelegramNotifier(telegram_client=mock_telegram, chat_id="test", enabled=False)
    result = await n.send_message("test")
    assert result is False
    mock_telegram.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_notify_trade_open(notifier, mock_telegram):
    """Notificación de apertura de posición."""
    pos = Position(
        exchange_id="bitget",
        symbol="BTC/USDT",
        market_symbol="BTC/USDT:USDT",
        side="Buy",
        entry_price=67432.50,
        amount=0.025,
        leverage=5,
        sl_order_id="sl123",
        tp_order_ids=["tp1", "tp2"],
    )
    await notifier.notify_trade_open(pos)
    args = mock_telegram.send_message.call_args[0]
    assert "🚀" in args[1]
    assert "LONG" in args[1] or "Buy" in args[1]
    assert "BTC/USDT" in args[1]
    assert "67432" in args[1]
    assert "5x" in args[1]


@pytest.mark.asyncio
async def test_notify_trade_closed(notifier, mock_telegram):
    """Notificación de cierre de posición."""
    pos = Position(
        exchange_id="bingx",
        symbol="ETH/USDT",
        market_symbol="ETH/USDT",
        side="Buy",
        entry_price=3450.0,
        amount=0.1,
        leverage=5,
        pnl=85.20,
    )
    await notifier.notify_trade_closed(pos)
    args = mock_telegram.send_message.call_args[0]
    assert "✅" in args[1] or "POSICIÓN" in args[1]
    assert "ETH/USDT" in args[1]


@pytest.mark.asyncio
async def test_notify_health_change(notifier, mock_telegram):
    """Notificación de cambio de salud."""
    await notifier.notify_health_change("bitget", "degraded", 3, 1234.0)
    args = mock_telegram.send_message.call_args[0]
    assert "bitget" in args[1]
    assert "DEGRADED" in args[1].upper() or "degraded" in args[1]


@pytest.mark.asyncio
async def test_notify_circuit_breaker(notifier, mock_telegram):
    """Notificación de circuit breaker."""
    await notifier.notify_circuit_breaker("bingx", "open", 60.0)
    args = mock_telegram.send_message.call_args[0]
    assert "bingx" in args[1]
    assert "OPEN" in args[1].upper() or "open" in args[1]


@pytest.mark.asyncio
async def test_send_daily_report(notifier, mock_telegram):
    """Reporte diario con posiciones y balances."""
    positions = [
        Position(
            exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
            side="Buy", entry_price=67000, amount=0.1, leverage=5, pnl=45.20,
        ),
        Position(
            exchange_id="bingx", symbol="ETH/USDT", market_symbol="ETH/USDT",
            side="Sell", entry_price=3400, amount=0.5, leverage=5, pnl=-12.0,
        ),
    ]
    balances = {"bitget": 678.90, "bingx": 555.66}
    await notifier.send_daily_report(positions, balances)
    args = mock_telegram.send_message.call_args[0]
    assert "Reporte" in args[1]
    assert "BTC/USDT" in args[1]
    assert "678.90" in args[1]


@pytest.mark.asyncio
async def test_send_message_error(notifier, mock_telegram):
    """Error al enviar mensaje no lanza excepción."""
    mock_telegram.send_message.side_effect = Exception("Network error")
    result = await notifier.send_message("test")
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**

```python
# services/notifier.py
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
        sl_text = f"${position.sl_order_id}" if position.sl_order_id else "Sin SL"
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

    async def notify_tp_hit(self, position: Position, tp_number: int):
        """Notifica que se alcanzó un Take Profit."""
        msg = (
            f"🎯 TP{tp_number} alcanzado\n"
            f"Símbolo: {position.symbol}\n"
            f"Exchange: {position.exchange_id}\n"
            f"Precio entrada: ${position.entry_price:,.2f}"
        )
        await self.send_message(msg)

    async def notify_trailing_activated(self, position: Position):
        """Notifica que el trailing stop se activó."""
        msg = (
            f"🔝 Trailing Stop activado\n"
            f"Símbolo: {position.symbol}\n"
            f"Exchange: {position.exchange_id}\n"
            f"Precio entrada: ${position.entry_price:,.2f}"
        )
        await self.send_message(msg)

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

    async def notify_error(self, module: str, error_message: str):
        """Notifica un error crítico del sistema."""
        msg = (
            f"❌ Error en {module}\n"
            f"{error_message[:200]}"
        )
        await self.send_message(msg)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add services/notifier.py tests/test_notifier.py
git commit -m "feat(notifications): add TelegramNotifier service with trade, health, and report notifications"
```

---

### Task 2: Integrar Notificaciones en TradingEngine

**Files:**
- Modify: `core/engine.py`

- [ ] **Step 1: Añadir notificador al engine y notificar eventos de trading**

Añadir en `core/engine.py`:

```python
# Al inicio, después de imports existentes
from services.notifier import TelegramNotifier

# En la clase TradingEngine, añadir al __init__:
    def __init__(self):
        ...código existente...
        self.notifier: Optional[TelegramNotifier] = None
```

En `execute_signal()`, después de `pos_manager.add_position(new_pos)` y el log de éxito:

```python
            pos_manager.add_position(new_pos)
            logger.info(f"✅ Ejecución completa en {exchange_id} a {entry_price}")

            # Notificar apertura de posición
            if self.notifier:
                await self.notifier.notify_trade_open(new_pos)
```

En `watchdog()`, donde se detecta que una posición se cerró (contracts == 0):

```python
                            if contracts == 0:
                                pos.status = "closed"
                                pos_manager.save()
                                logger.info(f"🔒 Posición {pos.symbol} en {pos.exchange_id} cerrada")
                                # Notificar cierre
                                if self.notifier:
                                    await self.notifier.notify_trade_closed(pos)
                                continue
```

En `watchdog()`, donde se detecta TP1 alcanzado:

```python
                                        if order.get('status') == 'closed' or order.get('filled', 0) > 0:
                                            pos.tp1_hit = True
                                            pos_manager.save()
                                            logger.info(f"🎯 TP1 alcanzado para {pos.symbol} en {pos.exchange_id}")
                                            if self.notifier:
                                                await self.notifier.notify_tp_hit(pos, 1)
                                            break
```

En `_check_trailing_stop()`, donde trailing_activated cambia a True:

```python
            if gain_pct >= activacion_pct and not pos.trailing_activated:
                pos.trailing_activated = True
                logger.info(f"🔝 Trailing activado para {pos.symbol} (ganancia: {gain_pct:.2f}%)")
                if self.trading_engine.notifier:  # Nota: acceso a engine desde método interno
                    await self.trading_engine.notifier.notify_trailing_activated(pos)
```

**Nota:** `_check_trailing_stop` es un método de instancia de `TradingEngine`, así que `self.notifier` está disponible directamente.

- [ ] **Step 2: Commit**

```bash
git add core/engine.py
git commit -m "feat(notifications): integrate trade notifications in engine (open, close, TP, trailing)"
```

---

### Task 3: Integrar Notificaciones en HealthMonitor

**Files:**
- Modify: `utils/resilience/health_monitor.py`

- [ ] **Step 1: Añadir callback on_status_change al HealthMonitor**

En `utils/resilience/health_monitor.py`:

```python
# En la clase HealthMonitor, añadir al __init__:
    def __init__(self, check_interval: float = 60.0):
        ...código existente...
        self.on_status_change: Optional[Callable] = None  # callback(exchange_id, status, failures, latency)
```

En `ExchangeHealth.record_failure()`, después de cambiar el estado:

```python
    def record_failure(self):
        old_status = self.status
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.down_after:
            self.status = HealthStatus.DOWN
        elif self.consecutive_failures >= self.degraded_after:
            self.status = HealthStatus.DEGRADED
        return old_status != self.status  # Retorna True si el estado cambió
```

En `ExchangeHealth.record_success()`, después de cambiar el estado:

```python
    def record_success(self, latency_ms: float = 0.0):
        old_status = self.status
        self.consecutive_failures = 0
        self.last_ok_time = time.time()
        self.status = HealthStatus.HEALTHY
        ...
        return old_status != self.status
```

En `HealthMonitor._check_single_exchange()`, invocar callback si hay cambio:

```python
    async def _check_single_exchange(self, exchange_id: str):
        ...código existente...
        try:
            ok = await self._health_check_func(exchange_id)
            latency_ms = (time.time() - start) * 1000
            if ok:
                changed = health.record_success(latency_ms)
                if changed and self.on_status_change:
                    await self.on_status_change(exchange_id, "healthy", 0, health.avg_latency_ms)
            else:
                changed = health.record_failure()
                if changed and self.on_status_change:
                    await self.on_status_change(exchange_id, health.status.value,
                                                health.consecutive_failures, health.avg_latency_ms)
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            changed = health.record_failure()
            if changed and self.on_status_change:
                await self.on_status_change(exchange_id, health.status.value,
                                            health.consecutive_failures, health.avg_latency_ms)
```

- [ ] **Step 2: Commit**

```bash
git add utils/resilience/health_monitor.py
git commit -m "feat(notifications): add on_status_change callback to HealthMonitor"
```

---

### Task 4: Conectar Todo en main.py + Reporte Diario

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Inicializar notificador y conectarlo en main.py**

En `main.py`, dentro de `main_async()`:

```python
    # Después de inicializar exchanges y antes del bucle de Telegram
    from services.notifier import TelegramNotifier
    
    # Inicializar notificador
    notifier = None
    if self.telegram_client:
        notification_chat_id = os.getenv("NOTIFICATION_CHAT_ID", "").strip()
        if not notification_chat_id and self.telegram_client:
            # Si no hay chat_id configurado, usar el propio usuario
            try:
                me = await self.telegram_client.get_me()
                notification_chat_id = str(me.id)
            except Exception:
                pass
        
        if notification_chat_id:
            notifier = TelegramNotifier(
                telegram_client=self.telegram_client,
                chat_id=notification_chat_id,
                enabled=True,
            )
            logger.info(f"🔔 Notificador inicializado (chat_id: {notification_chat_id})")
    
    # Conectar notificador al engine
    trading_engine.notifier = notifier
    
    # Conectar notificador al health monitor via callback
    if notifier:
        async def health_callback(exchange, status, failures, latency):
            await notifier.notify_health_change(exchange, status, failures, latency)
        health_monitor.on_status_change = health_callback
```

También añadir la tarea de reporte diario al inicio del watchdog o como tarea separada:

```python
    # Tarea de reporte diario (se ejecuta en el watchdog)
    # En TradingEngine.watchdog(), añadir al inicio:
    self._last_daily_report = 0  # timestamp del último reporte
```

Y dentro del watchdog, al inicio del bucle:

```python
    # Reporte diario cada 24h
    if self.notifier and now - self._last_daily_report > 86400:
        self._last_daily_report = now
        open_positions = pos_manager.get_open_positions()
        from services.exchange_service import exchange_service
        balances = {}
        for ex_id in exchange_service.clients:
            bal = await exchange_service.get_balance(ex_id)
            balances[ex_id] = bal
        await self.notifier.send_daily_report(pos_manager.get_all_positions(), balances)
```

Añadir import en `main.py`:
```python
import os
from dotenv import load_dotenv
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat(notifications): wire TelegramNotifier in main.py with daily report task"
```

---

### Task 5: Ejecutar Tests y Verificar

**Files:** (ninguno, solo verificación)

- [ ] **Step 1: Run ALL tests**

Run: `python -m pytest tests/ -v`
Expected: All 63+ existing tests + new notifier tests = ~73+ tests PASS

- [ ] **Step 2: Verificación final**
  - [x] TelegramNotifier creado con todas las notificaciones del spec
  - [x] Tests unitarios del notifier
  - [x] Integración en engine.py (apertura, cierre, TP, trailing)
  - [x] Integración en health_monitor.py (callback de cambios de estado)
  - [x] Conexión en main.py (inicialización, daily report)
  - [x] Sin nuevas dependencias
