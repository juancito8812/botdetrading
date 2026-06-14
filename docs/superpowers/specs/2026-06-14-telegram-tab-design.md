# Pestaña Telegram — Spec de Diseño

**Fecha:** 14/06/2026
**Proyecto:** MiBotTrading
**Estado:** Aprobado ✅

---

## Resumen

Crear una pestaña unificada de Telegram que agrupe: estado de conexión, credenciales, canales, notificaciones recientes y controles.

## Cambios Propuestos

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `ui/main_window.py` | Nueva pestaña `tab_telegram`, mover credenciales + canales aquí, nuevo historial de notis |
| `utils/translations.py` | ~10 nuevas claves i18n |
| `services/notifier.py` | Agregar `history` (array) y método `get_recent()` |
| `main.py` | Exponer estado de Telegram a la GUI via callback/referencia |

## Diseño de la Pestaña

```
┌──────────────────────────────────────────────┐
│  📱 TELEGRAM                                 │
├──────────────────────────────────────────────┤
│                                              │
│  ┌─── CONEXIÓN ──────────────────────────┐   │
│  │  ● Conectado como: Juan (@juancito)   │   │
│  │  📱 +584161234567                     │   │
│  │  🆔 Chat ID: 123456789                │   │
│  │  🔔 Notificaciones: ACTIVADAS [Toggle]│   │
│  │  [🔌 Desconectar] [📨 Enviar Test]   │   │
│  └────────────────────────────────────────┘   │
│                                              │
│  ┌─── CREDENCIALES ──────────────────────┐   │
│  │  API ID:    [____________]            │   │
│  │  API Hash:  [____________]            │   │
│  │  Teléfono:  [____________]            │   │
│  │  [💾 Guardar]                         │   │
│  └────────────────────────────────────────┘   │
│                                              │
│  ┌─── CANALES ───────────────────────────┐   │
│  │  ID: [_________] [➕ Añadir]          │   │
│  │  ├─ -100123456789                     │   │
│  │  ├─ -100987654321                     │   │
│  │  └─ [❌ Eliminar seleccionado]        │   │
│  └────────────────────────────────────────┘   │
│                                              │
│  ┌─── ÚLTIMAS NOTIFICACIONES ────────────┐   │
│  │  14:30 🚀 BTC LONG ABIERTA            │   │
│  │  14:25 🎯 TP1 alcanzado ETH           │   │
│  │  14:20 ⚠️ Bitget degradado            │   │
│  │  14:15 📊 Reporte diario enviado       │   │
│  │  [🔄 Refrescar]                       │   │
│  └────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

## Detalle de cada sección

### 1. Conexión
- Estado: label con LED 🟢🟡🔴 según estado de `telegram_client.is_connected()`
- Nombre de usuario: desde `client.get_me()`
- Chat ID: desde `NOTIFICATION_CHAT_ID` o `me.id`
- Toggle notificaciones: checkbox que modifica `notifier.enabled`
- Botón "Desconectar": llama a `client.disconnect()`
- Botón "Enviar Test": llama a `notifier.send_message("🧪 Test desde UI")`

### 2. Credenciales
- API_ID, API_HASH, Phone (movido desde `setup_apis_tab()`)
- Botón Guardar → `save_api_creds()`

### 3. Canales
- Listbox + campo ID + botones (movido desde `setup_channels_tab()`)
- Se elimina la pestaña `tab_canales` (ahora está aquí)

### 4. Últimas Notificaciones
- Listbox con las últimas 20 notificaciones enviadas
- Fuente: `notifier.history` (nuevo array en `TelegramNotifier`)
- Cada entrada: `[HH:MM] [emoji] texto`
- Botón Refrescar

## Cambios en services/notifier.py

Agregar en `TelegramNotifier`:

```python
class TelegramNotifier:
    def __init__(self, ...):
        ...
        self.history: List[str] = []  # Nuevo

    def _add_to_history(self, text: str):
        """Agrega una entrada al historial (max 20)."""
        timestamp = datetime.now().strftime("%H:%M")
        self.history.append(f"[{timestamp}] {text}")
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def get_recent(self, count: int = 20) -> List[str]:
        """Retorna las últimas N notificaciones."""
        return self.history[-count:]
```

Llamar `self._add_to_history(...)` en cada método de notificación.

## Cambios en main.py

- Agregar referencia a `TradingBotApp.telegram_client` y `TradingBotApp.notifier` para que la UI pueda acceder al estado
- Pasar referencia de la app a la GUI para acceso a estado

## Traducciones necesarias

| Clave | Español | Inglés |
|-------|---------|--------|
| `tab_telegram` | 📱 Telegram | 📱 Telegram |
| `tg_connection` | Conexión | Connection |
| `tg_connected_as` | Conectado como | Connected as |
| `tg_chat_id` | Chat ID | Chat ID |
| `tg_notifications` | Notificaciones | Notifications |
| `tg_disconnect` | Desconectar | Disconnect |
| `tg_send_test` | Enviar Test | Send Test |
| `tg_recent_notifications` | Últimas Notificaciones | Recent Notifications |
| `tg_no_notifications` | Sin notificaciones | No notifications |

## Auto-Review

- ✅ Sin placeholders
- ✅ Consistencia: fuentes de datos existen
- ✅ Scope enfocado: solo la pestaña Telegram, sin tocar lógica de trading
- ✅ Sin ambigüedad
