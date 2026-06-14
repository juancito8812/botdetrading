# Reports / Statistics Tab

## Overview
New tab in the TradingBot GUI that shows trading performance metrics, per-exchange breakdown, and recent trade history — all computed from existing `Position` data in `pos_manager`.

## Sections

### 1. Summary Bar (top)
Key metrics in a single-line LabelFrame:
- Total trades (open + closed)
- Win rate (% and fraction: e.g. "68.1% (32/47)")
- Total PnL (colored green/red)
- Best trade ($ and symbol)
- Worst trade ($ and symbol)
- Open / Closed counts

### 2. Performance by Exchange (Treeview table)
Columns: Exchange | Trades | Win % | PnL | Balance
- Rows: one per exchange that has ever had a position
- Balance fetched from `exchange_service.get_balance()`
- Sorted by PnL descending

### 3. Recent Trades (Treeview list)
Columns: Symbol | Side | PnL | Status | Open Time
- Filter dropdown: All / Open / Closed
- Sorted by `open_time` descending (most recent first)
- Row coloring: green for positive PnL, red for negative

## Data Sources
| Section | Source | Notes |
|---------|--------|-------|
| Summary, Per Exchange, History | `pos_manager.get_all_positions()` | `Position` objects with exchange_id, symbol, side, entry_price, amount, pnl, status, open_time |
| Balances | `exchange_service.get_balance(ex_id)` | Async per-exchange |

## Files Modified
- `ui/main_window.py` — new methods: `setup_reports_tab()`, `refresh_reports()`, `_calc_summary_stats()`, `_populate_exchange_table()`, `_populate_trades_table()`
- `utils/translations.py` — ~15 new keys for tab title, column headers, labels

## Dependencies
None. Pure Tkinter (Labels, Treeview, Combobox for filter).
