# Design: Help Tooltips ❔ + Customizable Telegram Notifications

## Feature 1: Help Tooltips (❔)

**Goal:** Add a "?" icon next to each configuration setting that shows a description popup when clicked.

**Implementation:**
1. Create helper `_show_help_popup(title, description)` in `TradingBotGUI`:
   - Opens a `tk.Toplevel` with title, description text (wrapped), and a Close button
   - Centered on parent window, modal (grab_set)

2. Add help descriptions as new translation keys prefixed with `help_`:
   - `help_leverage`, `help_min_usdt`, `help_margin`, `help_tp_count`, `help_breakeven`
   - `help_entry_mode`, `help_max_deviation`, `help_timeout_limit`, `help_dca`, `help_dca_parts`
   - `help_tp_distribution`, `help_tp_pesos`, `help_trailing`, `help_trailing_activation`, `help_trailing_distance`
   - `help_max_positions`, `help_capital_pct`
   - `help_language`, `help_autostart`
   - `help_api_enabled`, `help_api_key`, `help_api_secret`, `help_api_passphrase`

3. In `setup_risk_tab()`: After each label/widget pair, add a `ttk.Button(text="❔", width=2)` that calls `_show_help_popup`
4. In `setup_settings_tab()` and `setup_apis_tab()`: Same pattern

**UI Layout:**
```
Apalancamiento (X): [5] ❔    ← button
```

**Files modified:** `ui/main_window.py`, `utils/translations.py`

## Feature 2: Customizable Telegram Notifications

**Goal:** Let users select which Telegram notifications they receive.

**Implementation:**

### Data Model
In `TelegramNotifier`, add `_enabled_notifications: Dict[str, bool]`:
```python
DEFAULT_NOTIFICATION_PREFS = {
    "trade_open": True,
    "trade_closed": True,
    "tp_hit": True,
    "trailing_activated": True,
    "health_change": True,
    "circuit_breaker": True,
    "system_error": True,
    "daily_report": True,
}
```

### Notifier Changes
Each notify_* method checks the preference before sending:
```python
async def notify_trade_open(self, position: Position):
    if not self._enabled_notifications.get("trade_open", True):
        return
    # ... existing code
```

### UI Changes
In `setup_telegram_tab()`, add a new section "Notificaciones Seleccionables":
- 8 checkboxes, each with i18n label
- On toggle, save to settings.json
- Load from settings on init

### Persistence
- Settings key: `notification_preferences` in `settings.json`
- Loaded in `TelegramNotifier.__init__()` (passed from main.py/engine.py)
- Saved when user toggles any checkbox

### Files modified
- `services/notifier.py` — Add _enabled_notifications + checks
- `ui/main_window.py` — Add checkboxes section in Telegram tab, save handler
- `utils/translations.py` — Add labels for each notification type
- `core/engine.py` — Pass notification prefs to notifier on init (minimal change)

## Files not modified
- `services/notifier.py` — Major changes
- `ui/main_window.py` — Major changes (both features)
- `utils/translations.py` — New keys (both features)
- `core/engine.py` — Minimal (pass prefs)
