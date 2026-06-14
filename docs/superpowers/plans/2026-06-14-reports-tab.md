# Reports Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a trading reports/statistics tab to the GUI.

**Architecture:** New `setup_reports_tab()` method in `main_window.py` plus helper methods. Data sourced from existing `pos_manager.get_all_positions()` and `exchange_service.get_balance()`. Pure Tkinter (no external deps).

**Tech Stack:** Python, Tkinter, existing Position model, existing pos_manager/exchange_service singletons.

---

### Task 1: Add translation keys

**Files:**
- Modify: `utils/translations.py`

- [ ] **Add 15 new keys to both es/en dictionaries**

In `es`:
```python
"tab_reportes": "📊 Reportes",
"reports_summary": "Resumen General",
"reports_total_trades": "Total Trades",
"reports_win_rate": "Win Rate",
"reports_total_pnl": "PnL Total",
"reports_best_trade": "Mejor Trade",
"reports_worst_trade": "Peor Trade",
"reports_open": "Abiertas",
"reports_closed": "Cerradas",
"reports_per_exchange": "Performance por Exchange",
"reports_recent": "Últimos Trades",
"reports_col_exchange": "Exchange",
"reports_col_trades": "Trades",
"reports_col_winpct": "Win %",
"reports_col_pnl": "PnL",
"reports_col_balance": "Balance",
"reports_col_symbol": "Símbolo",
"reports_col_side": "Side",
"reports_col_status": "Estado",
"reports_col_time": "Apertura",
"reports_filter_all": "Todas",
"reports_filter_open": "Abiertas",
"reports_filter_closed": "Cerradas",
```

In `en`:
```python
"tab_reportes": "📊 Reports",
"reports_summary": "General Summary",
"reports_total_trades": "Total Trades",
"reports_win_rate": "Win Rate",
"reports_total_pnl": "Total PnL",
"reports_best_trade": "Best Trade",
"reports_worst_trade": "Worst Trade",
"reports_open": "Open",
"reports_closed": "Closed",
"reports_per_exchange": "Performance by Exchange",
"reports_recent": "Recent Trades",
"reports_col_exchange": "Exchange",
"reports_col_trades": "Trades",
"reports_col_winpct": "Win %",
"reports_col_pnl": "PnL",
"reports_col_balance": "Balance",
"reports_col_symbol": "Symbol",
"reports_col_side": "Side",
"reports_col_status": "Status",
"reports_col_time": "Open Time",
"reports_filter_all": "All",
"reports_filter_open": "Open",
"reports_filter_closed": "Closed",
```

- [ ] **Verify keys are added correctly**

Run: `python -c "from utils.translations import i18n; print(i18n.t('tab_reportes')); i18n.set_language('en'); print(i18n.t('tab_reportes'))"`
Expected: `📊 Reportes` / `📊 Reports`

- [ ] **Commit**

```bash
git add utils/translations.py
git commit -m "feat: add translations for reports tab"
```

### Task 2: Add reports tab to main_window.py

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Create frame in `__init__`**

After `self.tab_telegram = ...`, add:
```python
self.tab_reportes = ttk.Frame(self.notebook)
```
After `self.notebook.add(self.tab_telegram, ...)`, add:
```python
self.notebook.add(self.tab_reportes, text=i18n.t("tab_reportes"))
```
Update `self.last_tab_index = 7` (was 6, now 7 with the new tab).

- [ ] **Add setup call in `__init__`**

After `self.setup_telegram_tab()`, add:
```python
self.setup_reports_tab()
```

- [ ] **Add language change handler in `_on_language_change`**

After `self.notebook.tab(self.tab_telegram, ...)`, add:
```python
self.notebook.tab(self.tab_reportes, text=i18n.t("tab_reportes"))
```

### Task 3: Implement setup_reports_tab()

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Write the `setup_reports_tab()` method**

This creates 3 sections in a scrollable frame:

```python
def setup_reports_tab(self):
    canvas = tk.Canvas(self.tab_reportes)
    scrollbar = ttk.Scrollbar(self.tab_reportes, orient="vertical", command=canvas.yview)
    scrollable = ttk.Frame(canvas)
    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # ─── Summary ────────────────────────
    summary_frame = ttk.LabelFrame(scrollable, text=i18n.t("reports_summary"), padding=10)
    summary_frame.pack(fill='x', padx=10, pady=5)
    self.reports_summary_labels = {}
    metrics = [
        ("total_trades", i18n.t("reports_total_trades")),
        ("win_rate", i18n.t("reports_win_rate")),
        ("total_pnl", i18n.t("reports_total_pnl")),
        ("best_trade", i18n.t("reports_best_trade")),
        ("worst_trade", i18n.t("reports_worst_trade")),
        ("open_count", i18n.t("reports_open")),
        ("closed_count", i18n.t("reports_closed")),
    ]
    for i, (key, label) in enumerate(metrics):
        col = i % 4
        row = i // 4
        ttk.Label(summary_frame, text=f"{label}:", font=("", 9, "bold")).grid(row=row, column=col*2, sticky='e', padx=2, pady=1)
        lbl = ttk.Label(summary_frame, text="--", font=("", 9))
        lbl.grid(row=row, column=col*2+1, sticky='w', padx=2, pady=1)
        self.reports_summary_labels[key] = lbl

    # ─── Performance by Exchange ─────────
    ex_frame = ttk.LabelFrame(scrollable, text=i18n.t("reports_per_exchange"), padding=10)
    ex_frame.pack(fill='x', padx=10, pady=5)

    columns_ex = ("exchange", "trades", "winpct", "pnl", "balance")
    self.tree_reports_ex = ttk.Treeview(ex_frame, columns=columns_ex, show='headings', height=6)
    col_texts_ex = [
        i18n.t("reports_col_exchange"),
        i18n.t("reports_col_trades"),
        i18n.t("reports_col_winpct"),
        i18n.t("reports_col_pnl"),
        i18n.t("reports_col_balance"),
    ]
    widths_ex = {"exchange": 100, "trades": 70, "winpct": 70, "pnl": 100, "balance": 100}
    for col, text in zip(columns_ex, col_texts_ex):
        self.tree_reports_ex.heading(col, text=text)
        self.tree_reports_ex.column(col, width=widths_ex.get(col, 80), anchor='center')
    self.tree_reports_ex.pack(fill='x')

    # ─── Recent Trades ──────────────────
    trades_frame = ttk.LabelFrame(scrollable, text=i18n.t("reports_recent"), padding=10)
    trades_frame.pack(fill='both', expand=True, padx=10, pady=5)

    filter_row = ttk.Frame(trades_frame)
    filter_row.pack(fill='x', pady=2)
    self.reports_filter_var = tk.StringVar(value="all")
    filters = [
        ("all", i18n.t("reports_filter_all")),
        ("open", i18n.t("reports_filter_open")),
        ("closed", i18n.t("reports_filter_closed")),
    ]
    for val, text in filters:
        ttk.Radiobutton(filter_row, text=text, variable=self.reports_filter_var, value=val,
                        command=self.refresh_reports).pack(side='left', padx=5)
    ttk.Button(filter_row, text=i18n.t("dash_refresh"), command=self.refresh_reports).pack(side='right', padx=5)

    columns_tr = ("symbol", "side", "pnl", "status", "open_time")
    self.tree_reports_tr = ttk.Treeview(trades_frame, columns=columns_tr, show='headings', height=14)
    col_texts_tr = [
        i18n.t("reports_col_symbol"),
        i18n.t("reports_col_side"),
        i18n.t("reports_col_pnl"),
        i18n.t("reports_col_status"),
        i18n.t("reports_col_time"),
    ]
    widths_tr = {"symbol": 120, "side": 70, "pnl": 100, "status": 80, "open_time": 140}
    for col, text in zip(columns_tr, col_texts_tr):
        self.tree_reports_tr.heading(col, text=text)
        self.tree_reports_tr.column(col, width=widths_tr.get(col, 100), anchor='center')
    self.tree_reports_tr.pack(fill='both', expand=True)

    # Initial load
    self.refresh_reports()
```

### Task 4: Implement refresh_reports() and helpers

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Write `refresh_reports()` method**

```python
def refresh_reports(self):
    from core.manager import pos_manager
    from services.exchange_service import exchange_service
    import threading, asyncio

    all_positions = pos_manager.get_all_positions()
    closed = [p for p in all_positions if p.status == "closed"]
    open_pos = [p for p in all_positions if p.status == "open"]

    # ─── Summary ───
    total = len(all_positions)
    closed_count = len(closed)
    open_count = len(open_pos)
    win_count = sum(1 for p in closed if p.pnl and p.pnl > 0)
    win_rate = (win_count / closed_count * 100) if closed_count > 0 else 0.0
    total_pnl = sum(p.pnl or 0.0 for p in all_positions)

    best = max(closed, key=lambda p: p.pnl or 0) if closed else None
    worst = min(closed, key=lambda p: p.pnl or 0) if closed else None

    self.reports_summary_labels["total_trades"].config(text=str(total))
    self.reports_summary_labels["win_rate"].config(
        text=f"{win_rate:.1f}% ({win_count}/{closed_count})" if closed_count > 0 else "N/A")
    pnl_text = f"${total_pnl:+.2f}"
    self.reports_summary_labels["total_pnl"].config(text=pnl_text,
        foreground="#00cc00" if total_pnl >= 0 else "#ff4444")
    self.reports_summary_labels["best_trade"].config(
        text=f"{best.symbol} ${best.pnl:+.2f}" if best else "--")
    self.reports_summary_labels["worst_trade"].config(
        text=f"{worst.symbol} ${worst.pnl:+.2f}" if worst else "--")
    self.reports_summary_labels["open_count"].config(text=str(open_count))
    self.reports_summary_labels["closed_count"].config(text=str(closed_count))

    # ─── Per Exchange ───
    for item in self.tree_reports_ex.get_children():
        self.tree_reports_ex.delete(item)

    ex_data = {}
    for p in all_positions:
        if p.exchange_id not in ex_data:
            ex_data[p.exchange_id] = {"trades": 0, "wins": 0, "pnl": 0.0}
        ex_data[p.exchange_id]["trades"] += 1
        if p.pnl:
            ex_data[p.exchange_id]["pnl"] += p.pnl
            if p.pnl > 0:
                ex_data[p.exchange_id]["wins"] += 1

    for ex_id, data in sorted(ex_data.items(), key=lambda x: x[1]["pnl"], reverse=True):
        winpct = (data["wins"] / data["trades"] * 100) if data["trades"] > 0 else 0
        self.tree_reports_ex.insert("", tk.END, values=(
            ex_id.upper(), data["trades"], f"{winpct:.0f}%",
            f"${data['pnl']:+.2f}", "--"))

    # Fetch balances async
    def _fetch_balances():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for ex_id in list(ex_data.keys()):
            if ex_id in exchange_service.clients:
                try:
                    bal = loop.run_until_complete(exchange_service.get_balance(ex_id))
                    self.root.after(0, lambda e=ex_id, b=bal: self._update_ex_balance(e, b))
                except Exception:
                    pass
        loop.close()
    threading.Thread(target=_fetch_balances, daemon=True).start()

    # ─── Recent Trades (filtered) ───
    for item in self.tree_reports_tr.get_children():
        self.tree_reports_tr.delete(item)

    filter_val = self.reports_filter_var.get()
    if filter_val == "open":
        filtered = open_pos
    elif filter_val == "closed":
        filtered = closed
    else:
        filtered = all_positions

    # Sort by open_time descending (most recent first)
    filtered_sorted = sorted(filtered, key=lambda p: p.open_time, reverse=True)[:50]

    for p in filtered_sorted:
        pnl_str = f"${p.pnl:+.2f}" if p.pnl else "$0.00"
        side_emoji = "🚀" if p.side.lower() == "buy" else "🔻"
        side_text = "LONG" if p.side.lower() == "buy" else "SHORT"
        tags = ()
        if p.pnl and p.pnl > 0:
            tags = ("profit",)
        elif p.pnl and p.pnl < 0:
            tags = ("loss",)
        self.tree_reports_tr.insert("", tk.END, values=(
            p.symbol, f"{side_emoji} {side_text}", pnl_str,
            p.status.upper(), p.open_time), tags=tags)

    self.tree_reports_tr.tag_configure("profit", foreground="#00cc00")
    self.tree_reports_tr.tag_configure("loss", foreground="#ff4444")

def _update_ex_balance(self, exchange_id: str, balance: float):
    for item in self.tree_reports_ex.get_children():
        values = self.tree_reports_ex.item(item, "values")
        if values and values[0] == exchange_id.upper():
            self.tree_reports_ex.item(item, values=(
                values[0], values[1], values[2], values[3], f"${balance:.2f}"))
            break
```

- [ ] **Verify no syntax errors**

Run: `python -c "import ast; ast.parse(open('ui/main_window.py').read()); print('OK')"`
Expected: OK

- [ ] **Run tests to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: All 72 tests pass

### Task 5: Final verification

- [ ] **Code review**
Spawn code-reviewer-deepseek-flash to verify changes
- [ ] **Final commit + push**

```bash
git add ui/main_window.py utils/translations.py docs/superpowers/specs/2026-06-14-reports-tab-design.md docs/superpowers/plans/2026-06-14-reports-tab.md
git commit -m "feat: add trading reports tab with summary, per-exchange stats, and trade history"
git push origin master
```
