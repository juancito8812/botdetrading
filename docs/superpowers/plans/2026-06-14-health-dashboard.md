# Dashboard de Salud — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar las cards de salud de exchanges en el dashboard con LED indicator, circuit breaker state y última vez OK.

**Architecture:** Solo se modifican 2 archivos: `ui/main_window.py` (función `refresh_health()`) y `utils/translations.py` (6 nuevas claves de traducción). El layout de las cards se reconstruye completamente en cada refresh (comportamiento existente).

**Tech Stack:** Python 3.14, Tkinter, health_monitor.get_summary()

---

### Task 1: Agregar traducciones

**Files:**
- Modify: `utils/translations.py` — agregar 6 nuevas claves i18n

- [ ] **Step 1: Agregar claves en español e inglés**

Encontrar en `utils/translations.py` los diccionarios `es` y `en`, agregar las nuevas claves al final de cada uno:

```python
# En el diccionario 'es':
"health_cb_closed": "Cerrado",
"health_cb_open": "Abierto",
"health_cb_half_open": "Medio abierto",
"health_last_ok": "Última vez OK",
"health_never": "Nunca",
"health_failures": "fallos",
"health_latency": "Latencia",

# En el diccionario 'en':
"health_cb_closed": "Closed",
"health_cb_open": "Open",
"health_cb_half_open": "Half-open",
"health_last_ok": "Last OK",
"health_never": "Never",
"health_failures": "failures",
"health_latency": "Latency",
```

- [ ] **Step 2: Verificar que las traducciones no rompen nada**

Run: `python -c "from utils.translations import i18n; print(i18n.t('health_cb_closed')); print('OK')"`
Expected: `Cerrado\nOK`

---

### Task 2: Mejorar refresh_health() en main_window.py

**Files:**
- Modify: `ui/main_window.py` — función `refresh_health()` (~líneas 195-265)

La función actual:

```python
def refresh_health(self):
    try:
        summary = health_monitor.get_summary()
        if not summary:
            for ex_id in list(exchange_service.clients.keys()):
                health_monitor.add_exchange(ex_id)
            summary = health_monitor.get_summary()

        for child in self.health_container.winfo_children():
            child.destroy()

        if not summary:
            lbl = ttk.Label(self.health_container, text=i18n.t("dash_health_unknown"), foreground="gray")
            lbl.pack(side='left', padx=10, pady=2)
            return

        for ex_id in sorted(summary.keys()):
            data = summary[ex_id]
            status = data.get("status", "unknown")
            failures = data.get("consecutive_failures", 0)
            latency = data.get("avg_latency_ms", 0.0)

            if status == "healthy":
                status_text = i18n.t("dash_health_healthy")
                fg_color = "#00cc00"
            elif status == "degraded":
                status_text = i18n.t("dash_health_degraded")
                fg_color = "#ccaa00"
            elif status == "down":
                status_text = i18n.t("dash_health_down")
                fg_color = "#ff4444"
            else:
                status_text = i18n.t("dash_health_unknown")
                fg_color = "gray"

            card = ttk.LabelFrame(self.health_container, text=ex_id.upper(), padding=3)
            card.pack(side='left', padx=4, pady=2, fill='y')

            status_lbl = ttk.Label(card, text=status_text, foreground=fg_color, font=("", 10, "bold"))
            status_lbl.pack(anchor='w', padx=2)

            latency_text = f"{latency:.0f}ms" if latency > 0 else "-"
            ttk.Label(card, text=f"⏱ {latency_text}", font=("", 8)).pack(anchor='w', padx=2)

            fail_text = f"{failures} {i18n.t('dash_health_failures')}" if failures > 0 else "✓"
            fail_color = "#ff4444" if failures > 0 else "#00cc00"
            ttk.Label(card, text=f"⚠ {fail_text}", foreground=fail_color, font=("", 8)).pack(anchor='w', padx=2)
    except Exception as e:
        logger.warning(f"Error actualizando health en UI: {e}")
```

Reemplazar con la versión mejorada que agrega:

1. **LED indicator** junto al nombre del exchange (LabelFrame text)
2. **Circuit breaker state** con icono y color
3. **Última vez OK** formateada como timestamp legible
4. Función helper `_format_timestamp()` para formatear last_ok_time

```python
    def _format_timestamp(self, timestamp: Optional[float]) -> str:
        """Formatea un timestamp UNIX a hora legible o 'Nunca'."""
        if not timestamp:
            return i18n.t("health_never")
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        return dt.strftime("%d/%m %H:%M")

    def refresh_health(self):
        """Actualiza los indicadores de salud de exchanges desde health_monitor."""
        try:
            summary = health_monitor.get_summary()
            if not summary:
                for ex_id in list(exchange_service.clients.keys()):
                    health_monitor.add_exchange(ex_id)
                summary = health_monitor.get_summary()

            for child in self.health_container.winfo_children():
                child.destroy()

            if not summary:
                lbl = ttk.Label(self.health_container, text=i18n.t("dash_health_unknown"), foreground="gray")
                lbl.pack(side='left', padx=10, pady=2)
                return

            for ex_id in sorted(summary.keys()):
                data = summary[ex_id]
                status = data.get("status", "unknown")
                failures = data.get("consecutive_failures", 0)
                latency = data.get("avg_latency_ms", 0.0)
                cb_state = data.get("circuit_breaker_state", "closed")
                last_ok = data.get("last_ok_time", None)

                # LED y color según estado
                if status == "healthy":
                    led = "🟢"
                    status_text = i18n.t("dash_health_healthy")
                    fg_color = "#00cc00"
                elif status == "degraded":
                    led = "🟡"
                    status_text = i18n.t("dash_health_degraded")
                    fg_color = "#ccaa00"
                elif status == "down":
                    led = "🔴"
                    status_text = i18n.t("dash_health_down")
                    fg_color = "#ff4444"
                else:
                    led = "⚪"
                    status_text = i18n.t("dash_health_unknown")
                    fg_color = "gray"

                # Circuit breaker state
                if cb_state == "closed":
                    cb_icon = "🔒"
                    cb_text = i18n.t("health_cb_closed")
                    cb_color = "#00cc00"
                elif cb_state == "open":
                    cb_icon = "🔓"
                    cb_text = i18n.t("health_cb_open")
                    cb_color = "#ff4444"
                elif cb_state == "half_open":
                    cb_icon = "⚠️"
                    cb_text = i18n.t("health_cb_half_open")
                    cb_color = "#ccaa00"
                else:
                    cb_icon = "?"
                    cb_text = cb_state
                    cb_color = "gray"

                # Card con LED en el título
                card = ttk.LabelFrame(self.health_container, text=f"{led} {ex_id.upper()}", padding=3)
                card.pack(side='left', padx=4, pady=2, fill='y')

                # Status
                status_lbl = ttk.Label(card, text=status_text, foreground=fg_color, font=("", 10, "bold"))
                status_lbl.pack(anchor='w', padx=2)

                # Latencia
                latency_text = f"{latency:.0f}ms" if latency > 0 else "-"
                ttk.Label(card, text=f"⏱ {i18n.t('health_latency')}: {latency_text}", font=("", 8)).pack(anchor='w', padx=2)

                # Fallos
                fail_text = f"{failures} {i18n.t('health_failures')}" if failures > 0 else "✓ 0"
                fail_color = "#ff4444" if failures > 0 else "#00cc00"
                ttk.Label(card, text=f"⚠ {fail_text}", foreground=fail_color, font=("", 8)).pack(anchor='w', padx=2)

                # Circuit breaker
                ttk.Label(card, text=f"{cb_icon} CB: {cb_text}", foreground=cb_color, font=("", 8)).pack(anchor='w', padx=2)

                # Última vez OK
                last_ok_text = self._format_timestamp(last_ok)
                ttk.Label(card, text=f"🕐 {i18n.t('health_last_ok')}: {last_ok_text}", font=("", 8)).pack(anchor='w', padx=2)

        except Exception as e:
            logger.warning(f"Error actualizando health en UI: {e}")
```

También agregar el import de `datetime` al inicio del archivo si no existe:

```python
from datetime import datetime
```

- [ ] **Step 1: Agregar import de `datetime` en `ui/main_window.py`**

Buscar `from utils.helpers import ...` o similar y agregar `from datetime import datetime`

- [ ] **Step 2: Agregar método `_format_timestamp()` antes de `refresh_health()`**

Insertar el método helper justo antes de `refresh_health()`.

- [ ] **Step 3: Reemplazar `refresh_health()` con la versión mejorada**

Reemplazar el cuerpo completo de `refresh_health()` con el código mejorado.

---

### Task 3: Verificar que el código funciona

**Files:**
- Test: Ejecutar los tests existentes para asegurar que no se rompió nada

- [ ] **Step 1: Ejecutar tests existentes**

Run: `python -m pytest tests/ -v`
Expected: Todos los tests pasan (72 tests ✅)

- [ ] **Step 2: Verificar que la UI importa correctamente**

Run: `python -c "from ui.main_window import TradingBotGUI; print('UI import OK')"`
Expected: `UI import OK` (puede fallar si Tkinter no está disponible en la terminal, pero el código debe ser sintácticamente válido)

---

## Resumen de archivos modificados

| Archivo | Cambio |
|---------|--------|
| `utils/translations.py` | +7 claves i18n (es + en) |
| `ui/main_window.py` | `refresh_health()` mejorado + `_format_timestamp()` + `from datetime import datetime` |
