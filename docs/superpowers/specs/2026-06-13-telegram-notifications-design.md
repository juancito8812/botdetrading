# Sistema de Notificaciones Telegram para MiBotTrading

**Fecha:** 2026-06-13
**Estado:** Aprobado
**Versión:** 1.0

## Resumen

Sistema de notificaciones vía Telegram para alertar al usuario sobre eventos de trading, cambios en la salud del sistema, y reportes periódicos. Reusa el cliente Telethon existente para enviar mensajes.

## Arquitectura

```
┌─────────────────────────────────────────────┐
│  TelegramNotifier                           │
│  ├── send_message(text) → Telegram          │
│  ├── notify_trade_open(position)            │
│  ├── notify_trade_closed(position, pnl)     │
│  ├── notify_tp_hit(position, tp_num)        │
│  ├── notify_sl_hit(position)                │
│  ├── notify_trailing_activated(position)    │
│  ├── notify_dca_executed(exchange, symbol)  │
│  ├── notify_health_change(exchange, status) │
│  ├── notify_circuit_breaker(exchange, state)│
│  ├── notify_error(module, error)            │
│  └── send_daily_report(positions, balances) │
├─────────────────────────────────────────────┤
│  Integración:                                │
│  engine.py → execute_signal                 │
│  engine.py → watchdog (TP1, cierre, trail)  │
│  health_monitor.py → on_status_change       │
│  main.py → inicialización + tarea diaria    │
└─────────────────────────────────────────────┘
```

## Componentes

### 1. TelegramNotifier (`services/notifier.py`)

Clase principal que envía mensajes formateados a Telegram.

```python
class TelegramNotifier:
    def __init__(self, telegram_client, chat_id: str, enabled: bool = True):
        self.client = telegram_client  # Telethon client (ya conectado)
        self.chat_id = chat_id         # ID de Telegram destino
        self.enabled = enabled         # Se puede deshabilitar desde config

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
```

### 2. Formato de Mensajes

**Apertura de posición:**
```
🚀 LONG ABIERTA
Exchange: Bitget
Símbolo: BTC/USDT
Entrada: $67,432.50
Cantidad: 0.025 BTC
Apalancamiento: 5x
SL: $66,200.00
TPs: $68,500 → $69,800 → $71,000
```

**Cierre de posición:**
```
✅ POSICIÓN CERRADA
Exchange: BingX
Símbolo: ETH/USDT
Side: LONG
Entrada: $3,450
Salida: $3,620
PnL: +$85.20 (+4.93%)
Duración: 2h 35m
```

**Health change:**
```
⚠️ Health Monitor - Bitget
Estado: DEGRADED
Fallos consecutivos: 3
Latencia: 1,234ms
```

**Circuit breaker:**
```
🔴 Circuit Breaker - BingX
Estado: OPEN
Bloqueado por: 60s
Motivo: 5 fallos consecutivos
```

**Reporte diario:**
```
📊 Reporte Diario — 13/06/2026
━━━━━━━━━━━━━━━━━━━━━
Posiciones abiertas: 3
PnL no realizado: +$45.20

Exchanges:
Bitget: $678.90
BingX: $555.66
━━━━━━━━━━━━━━━━━━━━━
```

### 3. Puntos de Integración

| Archivo | Método/Lugar | Notificación |
|---------|-------------|--------------|
| `core/engine.py` | `execute_signal()` → posición creada | `notify_trade_open` |
| `core/engine.py` | `watchdog()` → TP1 hit detectado | `notify_tp_hit` |
| `core/engine.py` | `watchdog()` → posición cerrada (contracts=0) | `notify_trade_closed` |
| `core/engine.py` | `_check_trailing_stop()` → trailing activado | `notify_trailing_activated` |
| `utils/resilience/health_monitor.py` | `record_failure()` → status change | `notify_health_change` (via callback) |
| `utils/resilience/health_monitor.py` | `record_success()` → recovery | `notify_health_change` (via callback) |
| `main.py` | Tarea asíncrona cada 24h | `send_daily_report` |

### 4. Configuración

Variable de entorno (`.env`):
```env
# Opcional: ID de Telegram para recibir notificaciones
# Si no se configura, las notificaciones se envían al propio usuario
NOTIFICATION_CHAT_ID=
```

Si `NOTIFICATION_CHAT_ID` está vacío, se usa el ID del usuario autenticado en Telegram (`get_me().id`).

## Archivos

- **Nuevo:** `services/notifier.py`
- **Nuevo:** `tests/test_notifier.py`
- **Modificado:** `core/engine.py`
- **Modificado:** `utils/resilience/health_monitor.py`
- **Modificado:** `main.py`

## Tests

| Test | Descripción |
|------|-------------|
| `test_send_message` | Enviar mensaje con mock del cliente Telegram |
| `test_notify_trade_open` | Formato correcto del mensaje de apertura |
| `test_notify_trade_closed` | Formato correcto del mensaje de cierre |
| `test_notify_health_change` | Formato correcto del mensaje de salud |
| `test_notify_circuit_breaker` | Formato correcto del mensaje de CB |
| `test_send_daily_report` | Formato correcto del reporte diario |
| `test_disabled_notifier` | No envía si enabled=False |
| `test_send_message_error` | Manejo de errores de Telegram |
