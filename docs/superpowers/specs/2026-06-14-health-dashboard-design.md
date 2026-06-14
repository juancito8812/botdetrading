# Dashboard de Salud de Exchanges — Spec de Diseño

**Fecha:** 14/06/2026
**Proyecto:** MiBotTrading
**Estado:** Aprobado ✅

---

## Resumen

Mejorar la sección de salud del dashboard actual (`ui/main_window.py`) para mostrar información más completa del estado de los exchanges, incluyendo indicadores visuales LED, estado del circuit breaker, y última vez que estuvieron OK.

## Cambios Propuestos

### Archivo a modificar

- `ui/main_window.py` — solo la función `refresh_health()` y sus helpers

### No se modifican

- `utils/resilience/health_monitor.py` — ya provee toda la info necesaria via `get_summary()`
- `services/notifier.py` — no tocar
- `core/engine.py` — no tocar

## Diseño de Cards de Salud

Cada exchange se muestra como una card (LabelFrame) con la siguiente información:

```
┌─────────────────────┐
│  BITGET  🟢         │  ← Exchange name + LED indicator
├─────────────────────┤
│  ✅ Healthy         │  ← Status text with color
│  ⏱  120ms          │  ← Avg latency
│  ⚠  0 fallos       │  ← Consecutive failures count
│  🔒 CB: Cerrado     │  ← Circuit breaker state with icon
│  🕐  14/06 15:30    │  ← Last OK timestamp
└─────────────────────┘
```

### Componentes visuales por card

| Elemento | Fuente de datos | Formato |
|----------|----------------|---------|
| LED indicator | `data["status"]` | 🟢 healthy / 🟡 degraded / 🔴 down / ⚪ unknown |
| Status text | `data["status"]` | Texto traducido con i18n |
| Latencia | `data["avg_latency_ms"]` | `{n:.0f}ms` o `-` si 0 |
| Fallos | `data["consecutive_failures"]` | `N fallos` o `✓` si 0 |
| Circuit breaker | `data["circuit_breaker_state"]` | 🔒 closed / 🔓 open / ⚠️ half_open |
| Última vez OK | `data["last_ok_time"]` | Timestamp formateado o `Nunca` |

### Mapeo de colores

| Estado | LED | Texto status | CB closed | CB open |
|--------|-----|-------------|-----------|---------|
| healthy | 🟢 `#00cc00` | Verde | 🔒 Verde | - |
| degraded | 🟡 `#ccaa00` | Amarillo | - | - |
| down | 🔴 `#ff4444` | Rojo | - | 🔓 Rojo |
| half_open | - | - | - | ⚠️ Amarillo |

### Layout

- Las cards se organizan horizontalmente con `pack(side='left', fill='y', padx=4, pady=2)` dentro de `self.health_container`
- Si hay más exchanges de los que caben en una fila, Tkinter hace wrap automático
- El contenedor se reconstruye completamente en cada `refresh_health()` (ya es el comportamiento actual)

### Auto-refresh

- No se necesita lógica nueva — el auto-refresh ya existe en `_dash_auto_tick()` que llama a `refresh_health()` cada 30s
- Solo hay que asegurar que el botón "Refresh Health" existente siga funcionando

## Traducciones

Se agregan las siguientes claves a `utils/translations.py`:

| Clave | Español | Inglés |
|-------|---------|--------|
| `health_cb_closed` | Cerrado | Closed |
| `health_cb_open` | Abierto | Open |
| `health_cb_half_open` | Medio abierto | Half-open |
| `health_last_ok` | Última vez OK | Last OK |
| `health_never` | Nunca | Never |
| `health_failures` | fallos | failures |
| `health_latency` | Latencia | Latency |

## Pruebas

- No se requieren tests unitarios nuevos para este cambio (solo UI)
- Verificar manualmente que las cards se rendericen correctamente
- Verificar que el auto-refresh funcione

---

## Self-Review

- ✅ Sin placeholders (TBD/TODO)
- ✅ Consistencia interna: diseño coincide con datos disponibles
- ✅ Scope enfocado: solo mejorar sección existente, no crear nueva pestaña
- ✅ Sin ambigüedad: cada elemento visual tiene fuente de datos y formato específicos
