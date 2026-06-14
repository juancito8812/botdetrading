# Positions Tab Enhancement Implementation Plan

**Goal:** Enhance positions tab (active only, actions, modify popup) + CSV export in Reports tab.

---

### Task 1: Add translations

**File:** `utils/translations.py`

Add to both es/en dictionaries:

```
positions_only_active: "Solo activas" / "Active only"
positions_col_leverage: "Leverage" / "Leverage"
positions_col_sl: "SL" / "SL"
positions_col_tps: "TPs" / "TPs"
positions_col_actions: "Acción" / "Actions"
positions_close: "❌ Cerrar" / "❌ Close"
positions_modify: "✏️ Modificar" / "✏️ Modify"
positions_close_confirm: "¿Cerrar posición?" / "Close position?"
positions_close_confirm_msg: "¿Estás seguro de cerrar {symbol} en {exchange}?" / "Are you sure you want to close {symbol} on {exchange}?"
positions_close_success: "Posición cerrada" / "Position closed"
positions_close_error: "Error al cerrar" / "Error closing"
positions_modify_title: "Modificar SL/TP" / "Modify SL/TP"
positions_sl_label: "Stop Loss:" / "Stop Loss:"
positions_tp_label: "Nuevo TP:" / "New TP:"
positions_tp_add: "➕ Añadir" / "➕ Add"
positions_tp_current: "TPs actuales:" / "Current TPs:"
positions_save: "💾 Guardar" / "💾 Save"
positions_sl_updated: "SL actualizado" / "SL updated"
positions_tp_added: "TP agregado" / "TP added"
export_csv: "📥 Exportar CSV" / "📥 Export CSV"
export_csv_success: "CSV exportado" / "CSV exported"
export_csv_error: "Error exportando CSV" / "Error exporting CSV"
```

### Task 2: Rewrite setup_positions_tab()

**File:** `ui/main_window.py`

Replace `setup_positions_tab()` and `update_positions_list()` with:
- Treeview with columns: ex, sym, side, price, amount, leverage, pnl, sl, tps, actions
- Only open positions from `pos_manager.get_open_positions()`
- PnL coloring (green/red)
- Scrollbars (vertical + horizontal)
- Actions column with ✏️ and ❌ buttons using treeview click binding

### Task 3: Add modify popup + close action

**File:** `ui/main_window.py`

- `_open_modify_popup(position)`: Toplevel with SL entry, TP entry + add button, current TPs list, save/cancel
- `_close_position(position)`: Confirmation dialog, creates opposite market order, updates status

### Task 4: Add CSV export to Reports tab

**File:** `ui/main_window.py`

- Add "📥 Export CSV" button in `setup_reports_tab()` filter_row
- `_export_csv()`: writes all positions to `trades_YYYY-MM-DD.csv`
