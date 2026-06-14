# Positions Tab Enhancement Design

## Overview
Improve the positions tab: show only active positions, add actions (close, modify SL/TP, detail popup), and add CSV export to Reports tab.

## Sections

### 1. Positions Tab (Active Only)
**File:** `ui/main_window.py` — `setup_positions_tab()` + helpers

- **Columns**: Exchange, Symbol, Side (🚀/🔻), Entry Price, Amount, Leverage, PnL, SL, TPs, Actions
- **Only open positions**: closed/failed positions are filtered out
- **PnL coloring**: green for positive, red for negative
- **Actions column**: two buttons per row — ✏️ Modify (popup), ❌ Close
- **Scrollbars**: vertical + horizontal on Treeview
- **Auto-width**: columns sized to fit content

### 2. Modify SL/TP Popup
**File:** `ui/main_window.py` — new method `_open_modify_popup()`

- Toplevel window with:
  - Exchange + Symbol info
  - Entry for new SL price
  - Entry + Add button for new TP
  - List of current TPs with status
  - Save / Cancel buttons
- On save: cancel old SL order, place new SL order via exchange_service

### 3. Close Position Action
**File:** `ui/main_window.py` — new method `_close_position()`

- Confirmation dialog before closing
- Creates opposite market order to close position
- Updates position status in pos_manager
- Shows success/error message

### 4. CSV Export in Reports Tab
**File:** `ui/main_window.py` — add button + method in `setup_reports_tab()`

- Button: "📥 Export CSV" in the recent trades section
- Saves `trades_YYYY-MM-DD.csv` in project directory
- Columns: Exchange, Symbol, Side, Entry Price, Amount, Leverage, PnL, Status, Open Time
- Includes ALL positions (not just filtered view)

## Data Sources
| Feature | Source |
|---------|--------|
| Position list | `pos_manager.get_open_positions()` |
| Close position | `exchange_service.create_order()` opposite side market order |
| Modify SL | `exchange_service.cancel_order()` + `exchange_service.create_order()` |
| CSV export | `pos_manager.get_all_positions()` |

## Files Modified
- `ui/main_window.py` — rewrite setup_positions_tab, add modify popup, close action, CSV export
- `utils/translations.py` — ~15 new keys for actions, popup, CSV
