import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import threading
import logging

from utils.config import (
    load_api_creds, save_api_creds, load_risk_config, save_risk_config,
    load_channels, save_channels, EXCHANGES_DEFAULTS
)
from utils.translations import i18n
from utils.settings_manager import (
    load_settings, save_settings,
    is_autostart_enabled, enable_autostart, disable_autostart
)
from services.exchange_service import exchange_service
from services.market_data import fetch_top20, fetch_market_indices
from core.manager import pos_manager
from utils.logger import logger


class GuiHandler(logging.Handler):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        if hasattr(self.app, 'root'):
            self.app.root.after(0, lambda: self.app.agregar_log(msg))


class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        # Inicializar idioma desde settings
        i18n.current_lang = self.settings.get("language", "es")
        self.root.title(i18n.t("app_title"))
        self.root.geometry("1200x850")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Crear pestañas
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_apis = ttk.Frame(self.notebook)
        self.tab_riesgo = ttk.Frame(self.notebook)
        self.tab_canales = ttk.Frame(self.notebook)
        self.tab_test = ttk.Frame(self.notebook)
        self.tab_posiciones = ttk.Frame(self.notebook)
        self.tab_saldos = ttk.Frame(self.notebook)
        self.tab_consola = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_dashboard, text=i18n.t("tab_dashboard"))
        self.notebook.add(self.tab_apis, text=i18n.t("tab_apis"))
        self.notebook.add(self.tab_riesgo, text=i18n.t("tab_riesgo"))
        self.notebook.add(self.tab_canales, text=i18n.t("tab_canales"))
        self.notebook.add(self.tab_test, text=i18n.t("tab_test"))
        self.notebook.add(self.tab_posiciones, text=i18n.t("tab_posiciones"))
        self.notebook.add(self.tab_saldos, text=i18n.t("tab_saldos"))
        self.notebook.add(self.tab_consola, text=i18n.t("tab_consola"))
        self.notebook.add(self.tab_settings, text=i18n.t("tab_settings"))

        # Pestaña de consola debe ir al final (la usan otras tabs)
        self.last_tab_index = 8

        # Inicializar UI de pestañas
        self.setup_dashboard_tab()
        self.setup_apis_tab()
        self.setup_risk_tab()
        self.setup_channels_tab()
        self.setup_test_tab()
        self.setup_positions_tab()
        self.setup_balances_tab()
        self.setup_console_tab()
        self.setup_settings_tab()

        # Configurar Logs
        self.setup_logging_bridge()

        # Listener para cambio de idioma
        i18n.add_listener(self._on_language_change)

        logger.info("Interfaz gráfica cargada correctamente.")

    def setup_logging_bridge(self):
        handler = GuiHandler(self)
        logging.getLogger("TradingBot").addHandler(handler)

    def agregar_log(self, msg):
        if hasattr(self, 'consola_text'):
            self.consola_text.config(state=tk.NORMAL)
            self.consola_text.insert(tk.END, msg + "\n")
            self.consola_text.see(tk.END)
            self.consola_text.config(state=tk.DISABLED)

    def _on_language_change(self):
        """Actualiza la UI cuando cambia el idioma."""
        self.root.title(i18n.t("app_title"))
        self.notebook.tab(self.tab_dashboard, text=i18n.t("tab_dashboard"))
        self.notebook.tab(self.tab_apis, text=i18n.t("tab_apis"))
        self.notebook.tab(self.tab_riesgo, text=i18n.t("tab_riesgo"))
        self.notebook.tab(self.tab_canales, text=i18n.t("tab_canales"))
        self.notebook.tab(self.tab_test, text=i18n.t("tab_test"))
        self.notebook.tab(self.tab_posiciones, text=i18n.t("tab_posiciones"))
        self.notebook.tab(self.tab_saldos, text=i18n.t("tab_saldos"))
        self.notebook.tab(self.tab_consola, text=i18n.t("tab_consola"))
        self.notebook.tab(self.tab_settings, text=i18n.t("tab_settings"))

    # ==================== TAB: DASHBOARD ====================
    def setup_dashboard_tab(self):
        frame = self.tab_dashboard

        # Top controls
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill='x', padx=10, pady=5)

        self.dash_btn = ttk.Button(top_frame, text=i18n.t("dash_refresh"), command=self.refresh_dashboard)
        self.dash_btn.pack(side='left', padx=5)

        self.dash_status = ttk.Label(top_frame, text="")
        self.dash_status.pack(side='left', padx=10)

        # --- Indices Frame ---
        indices_frame = ttk.LabelFrame(frame, text=i18n.t("dash_indices"), padding=5)
        indices_frame.pack(fill='x', padx=10, pady=2)
        
        self.indices_labels = {}
        indices_data = [
            ("btc_price", "BTC:"),
            ("eth_price", "ETH:"),
            ("total_mcap", "Total MCap:"),
            ("volume_24h", "Vol 24h:"),
            ("btc_dominance", "BTC Dom:"),
            ("eth_dominance", "ETH Dom:"),
            ("mcap_change", "MCap 24h:"),
        ]
        for i, (key, label) in enumerate(indices_data):
            lbl = ttk.Label(indices_frame, text=f"{label} --")
            lbl.grid(row=0, column=i, padx=8, pady=2)
            self.indices_labels[key] = lbl
        
        ttk.Label(indices_frame, text=i18n.t("dash_source"), foreground="gray", font=("", 8)).grid(row=0, column=len(indices_data), padx=10)

        # Treeview for crypto data
        columns = ("rank", "symbol", "name", "price", "change", "volume", "market_cap")
        self.dash_tree = ttk.Treeview(frame, columns=columns, show='headings', height=18)

        col_texts = [
            i18n.t("dash_col_rank"),
            i18n.t("dash_col_symbol"),
            i18n.t("dash_col_name"),
            i18n.t("dash_col_price"),
            i18n.t("dash_col_change"),
            i18n.t("dash_col_volume"),
            i18n.t("dash_col_market_cap"),
        ]
        widths = {"rank": 40, "symbol": 80, "name": 140, "price": 120, "change": 100, "volume": 140, "market_cap": 140}
        for col, text in zip(columns, col_texts):
            self.dash_tree.heading(col, text=text)
            self.dash_tree.column(col, width=widths.get(col, 100), anchor='center')
        self.dash_tree.column("name", anchor='w')

        # Tree + scrollbars
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.dash_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.dash_tree.xview)
        self.dash_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.dash_tree.pack(side='top', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')

        # Auto-refresh button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=5)
        self.dash_auto_btn = ttk.Button(btn_frame, text="▶ Auto-Refresh (60s)", command=self.toggle_dash_auto_refresh)
        self.dash_auto_btn.pack(side='left', padx=5)

        self.dash_auto_active = False
        self.dash_auto_job = None

    def refresh_dashboard(self):
        self.dash_status.config(text=i18n.t("dash_loading"))
        self.dash_btn.config(state='disabled')

        for item in self.dash_tree.get_children():
            self.dash_tree.delete(item)

        def _fetch():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                coins, indices = loop.run_until_complete(self._fetch_dash_data())
                loop.close()
                self.root.after(0, lambda: self._populate_dashboard(coins, indices))
            except Exception as e:
                self.root.after(0, lambda: self.dash_status.config(text=f"{i18n.t('dash_error')}: {str(e)[:60]}"))
            finally:
                self.root.after(0, lambda: self.dash_btn.config(state='normal'))

        threading.Thread(target=_fetch, daemon=True).start()

    async def _fetch_dash_data(self) -> tuple:
        """Obtiene datos de CoinGecko: top 20 coins + índices de mercado."""
        coins_task = asyncio.create_task(fetch_top20())
        indices_task = asyncio.create_task(fetch_market_indices())
        coins = await coins_task
        indices = await indices_task
        return coins, indices

    def _populate_dashboard(self, coins: list, indices: dict):
        self.dash_status.config(text=f"{len(coins)} criptos cargadas | CoinGecko")

        # Actualizar índices
        def fmt_currency(val):
            if val >= 1e12:
                return f"${val/1e12:.2f}T"
            elif val >= 1e9:
                return f"${val/1e9:.2f}B"
            elif val >= 1e6:
                return f"${val/1e6:.2f}M"
            else:
                return f"${val:,.0f}"

        indices_map = {
            "btc_price": f"BTC: ${indices.get('btc_price', 0):,.0f}",
            "eth_price": f"ETH: ${indices.get('eth_price', 0):,.0f}",
            "total_mcap": f"MCap: {fmt_currency(indices.get('total_market_cap', 0))}",
            "volume_24h": f"Vol: {fmt_currency(indices.get('total_volume_24h', 0))}",
            "btc_dominance": f"BTC Dom: {indices.get('btc_dominance', 0):.1f}%",
            "eth_dominance": f"ETH Dom: {indices.get('eth_dominance', 0):.1f}%",
            "mcap_change": f"MCap 24h: {indices.get('market_cap_change_24h', 0):+.2f}%",
        }
        for key, text in indices_map.items():
            if key in self.indices_labels:
                self.indices_labels[key].config(text=text)

        # Color MCap change
        mcap_change = indices.get('market_cap_change_24h', 0)
        if mcap_change >= 0:
            self.indices_labels["mcap_change"].config(foreground="#00ff00")
        else:
            self.indices_labels["mcap_change"].config(foreground="#ff4444")

        # Poblar tree
        for i, coin in enumerate(coins):
            rank = i + 1
            symbol = coin.get("symbol", "?")
            name = coin.get("name", symbol)
            price = coin.get("price", 0)
            change = coin.get("change_24h", 0)
            volume = coin.get("volume", 0)
            market_cap = coin.get("market_cap", 0)

            change_str = f"{change:+.2f}%" if change else "0.00%"
            tags = ()
            if change > 0:
                tags = ("up",)
            elif change < 0:
                tags = ("down",)

            self.dash_tree.insert("", tk.END, values=(
                rank,
                symbol,
                name,
                f"${price:,.2f}" if price else "N/A",
                change_str,
                f"${volume:,.0f}" if volume else "N/A",
                f"${market_cap:,.0f}" if market_cap else "N/A",
            ), tags=tags)

        self.dash_tree.tag_configure("up", foreground="#00ff00")
        self.dash_tree.tag_configure("down", foreground="#ff4444")

    def toggle_dash_auto_refresh(self):
        if self.dash_auto_active:
            self.dash_auto_active = False
            self.dash_auto_btn.config(text="▶ Auto-Refresh (60s)")
            if self.dash_auto_job:
                self.root.after_cancel(self.dash_auto_job)
                self.dash_auto_job = None
        else:
            self.dash_auto_active = True
            self.dash_auto_btn.config(text="⏹ Stop Auto-Refresh")
            self._dash_auto_tick()

    def _dash_auto_tick(self):
        if not self.dash_auto_active:
            return
        self.refresh_dashboard()
        self.dash_auto_job = self.root.after(60000, self._dash_auto_tick)

    # ==================== TAB: SETTINGS ====================
    def setup_settings_tab(self):
        frame = self.tab_settings

        # --- Language ---
        lang_frame = ttk.LabelFrame(frame, text=i18n.t("settings_title"), padding=10)
        lang_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(lang_frame, text=i18n.t("settings_language")).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.lang_var = tk.StringVar(value=self.settings.get("language", "es"))
        lang_combo = ttk.Combobox(lang_frame, textvariable=self.lang_var, values=["es", "en"], state="readonly", width=10)
        lang_combo.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        lang_combo.bind('<<ComboboxSelected>>', self._on_lang_selected)

        ttk.Label(lang_frame, text=i18n.t("settings_restart_hint"), foreground="gray").grid(row=1, column=0, columnspan=2, pady=5)

        # --- Auto-start ---
        autostart_frame = ttk.LabelFrame(frame, text=i18n.t("settings_autostart"), padding=10)
        autostart_frame.pack(fill='x', padx=10, pady=10)

        self.autostart_var = tk.BooleanVar(value=self.settings.get("start_with_windows", False))
        ttk.Checkbutton(
            autostart_frame,
            text=i18n.t("settings_autostart_desc"),
            variable=self.autostart_var,
            command=self._on_autostart_toggle
        ).pack(anchor='w', pady=5)

        ttk.Label(autostart_frame, text=i18n.t("settings_autostart_info"), wraplength=700, foreground="gray").pack(anchor='w', pady=5)

        autostart_status_frame = ttk.Frame(autostart_frame)
        autostart_status_frame.pack(fill='x', pady=5)

        self.autostart_status_label = ttk.Label(autostart_status_frame, text="")
        self.autostart_status_label.pack(side='left', padx=5)

        # Buttons for manual task management
        btn_frame = ttk.Frame(autostart_frame)
        btn_frame.pack(fill='x', pady=5)

        self.btn_install_task = ttk.Button(btn_frame, text=i18n.t("settings_install_task"), command=self._install_autostart_task)
        self.btn_install_task.pack(side='left', padx=5)

        self.btn_remove_task = ttk.Button(btn_frame, text=i18n.t("settings_uninstall_task"), command=self._remove_autostart_task)
        self.btn_remove_task.pack(side='left', padx=5)

        self._update_autostart_status()

    def _on_lang_selected(self, event=None):
        lang = self.lang_var.get()
        self.settings["language"] = lang
        save_settings(self.settings)
        i18n.set_language(lang)

    def _on_autostart_toggle(self):
        if self.autostart_var.get():
            self._install_autostart_task()
        else:
            self._remove_autostart_task()

    def _install_autostart_task(self):
        success, msg = enable_autostart()
        if success:
            self.settings["start_with_windows"] = True
            save_settings(self.settings)
            self.autostart_var.set(True)
        self._update_autostart_status()
        messagebox.showinfo("Auto-start", msg)

    def _remove_autostart_task(self):
        success, msg = disable_autostart()
        if success:
            self.settings["start_with_windows"] = False
            save_settings(self.settings)
            self.autostart_var.set(False)
        self._update_autostart_status()
        messagebox.showinfo("Auto-start", msg)

    def _update_autostart_status(self):
        enabled = is_autostart_enabled()
        if enabled:
            self.autostart_status_label.config(text="\u2705 " + i18n.t("settings_autostart_enabled"), foreground="green")
        else:
            self.autostart_status_label.config(text="\u274c " + i18n.t("settings_autostart_disabled"), foreground="red")

    # ==================== TAB: APIs ====================
    def setup_apis_tab(self):
        canvas = tk.Canvas(self.tab_apis)
        scrollbar = ttk.Scrollbar(self.tab_apis, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.exchange_widgets = {}
        creds = load_api_creds()

        ttk.Button(scrollable, text=i18n.t("btn_save_all"), command=self.save_apis).pack(pady=10, padx=10, fill='x')

        for ex_id, info in EXCHANGES_DEFAULTS.items():
            frame = ttk.LabelFrame(scrollable, text=f"Exchange: {info['name']}", padding=10)
            frame.pack(fill='x', padx=10, pady=5)

            widgets = {}
            enabled_var = tk.BooleanVar(value=creds["exchanges"].get(ex_id, {}).get("enabled", False))
            ttk.Checkbutton(frame, text=i18n.t("apis_enabled"), variable=enabled_var).grid(row=0, column=1, sticky='w')
            widgets["enabled"] = enabled_var

            ttk.Label(frame, text=i18n.t("apis_api_key")).grid(row=1, column=0, sticky='e')
            key_entry = ttk.Entry(frame, width=50, show="*")
            key_entry.insert(0, creds["exchanges"].get(ex_id, {}).get("api_key", ""))
            key_entry.grid(row=1, column=1, padx=5, pady=2)
            widgets["api_key"] = key_entry

            ttk.Label(frame, text=i18n.t("apis_secret")).grid(row=2, column=0, sticky='e')
            sec_entry = ttk.Entry(frame, width=50, show="*")
            sec_entry.insert(0, creds["exchanges"].get(ex_id, {}).get("secret", ""))
            sec_entry.grid(row=2, column=1, padx=5, pady=2)
            widgets["secret"] = sec_entry

            if info["needs_passphrase"]:
                ttk.Label(frame, text=i18n.t("apis_passphrase")).grid(row=3, column=0, sticky='e')
                pass_entry = ttk.Entry(frame, width=50, show="*")
                pass_entry.insert(0, creds["exchanges"].get(ex_id, {}).get("passphrase", ""))
                pass_entry.grid(row=3, column=1, padx=5, pady=2)
                widgets["passphrase"] = pass_entry

            self.exchange_widgets[ex_id] = widgets

        # Telegram
        tg_frame = ttk.LabelFrame(scrollable, text=i18n.t("apis_telegram"), padding=10)
        tg_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(tg_frame, text="API_ID:").grid(row=0, column=0, sticky='e')
        self.entry_api_id = ttk.Entry(tg_frame, width=30)
        self.entry_api_id.insert(0, creds["telegram"].get("API_ID", ""))
        self.entry_api_id.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(tg_frame, text="API_HASH:").grid(row=1, column=0, sticky='e')
        self.entry_api_hash = ttk.Entry(tg_frame, width=50)
        self.entry_api_hash.insert(0, creds["telegram"].get("API_HASH", ""))
        self.entry_api_hash.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(tg_frame, text="Phone (+...):").grid(row=2, column=0, sticky='e')
        self.entry_phone = ttk.Entry(tg_frame, width=30)
        self.entry_phone.insert(0, creds["telegram"].get("PHONE_NUMBER", ""))
        self.entry_phone.grid(row=2, column=1, padx=5, pady=2)

    def save_apis(self):
        new_creds = {"exchanges": {}, "telegram": {}}
        new_creds["telegram"] = {
            "API_ID": self.entry_api_id.get().strip(),
            "API_HASH": self.entry_api_hash.get().strip(),
            "PHONE_NUMBER": self.entry_phone.get().strip()
        }
        for ex_id, w in self.exchange_widgets.items():
            new_creds["exchanges"][ex_id] = {
                "api_key": w["api_key"].get().strip(),
                "secret": w["secret"].get().strip(),
                "passphrase": w["passphrase"].get().strip() if "passphrase" in w else "",
                "enabled": w["enabled"].get()
            }
        save_api_creds(new_creds)
        messagebox.showinfo(i18n.t("save"), i18n.t("apis_save_success"))

    # ==================== TAB: Riesgo ====================
    def setup_risk_tab(self):
        canvas = tk.Canvas(self.tab_riesgo)
        scrollbar = ttk.Scrollbar(self.tab_riesgo, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        config = load_risk_config()

        # --- Configuración General ---
        gen_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_title"), padding=10)
        gen_frame.pack(fill='x', padx=10, pady=10)

        row = 0
        ttk.Label(gen_frame, text=i18n.t("risk_leverage")).grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.spin_lev = ttk.Spinbox(gen_frame, from_=1, to=100, width=10)
        self.spin_lev.set(config.get("apalancamiento", 10))
        self.spin_lev.grid(row=row, column=1, sticky='w')
        row += 1

        ttk.Label(gen_frame, text=i18n.t("risk_min_usdt")).grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.entry_min_usdt = ttk.Entry(gen_frame, width=12)
        self.entry_min_usdt.insert(0, str(config.get("cantidad_minima_usdt", 10.0)))
        self.entry_min_usdt.grid(row=row, column=1, sticky='w')
        row += 1

        ttk.Label(gen_frame, text=i18n.t("risk_margin")).grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.margin_var = tk.StringVar(value=config.get("modo_margen", "cross"))
        ttk.Radiobutton(gen_frame, text=i18n.t("risk_margin_cross"), variable=self.margin_var, value="cross").grid(row=row, column=1, sticky='w')
        ttk.Radiobutton(gen_frame, text=i18n.t("risk_margin_isolated"), variable=self.margin_var, value="isolated").grid(row=row, column=2, sticky='w')
        row += 1

        ttk.Label(gen_frame, text=i18n.t("risk_tp_count")).grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.spin_tp_count = ttk.Spinbox(gen_frame, from_=1, to=10, width=10)
        self.spin_tp_count.set(config.get("tp_count", 5))
        self.spin_tp_count.grid(row=row, column=1, sticky='w')
        row += 1

        self.be_var = tk.BooleanVar(value=config.get("auto_breakeven", True))
        ttk.Checkbutton(gen_frame, text=i18n.t("risk_breakeven"), variable=self.be_var).grid(row=row, column=0, columnspan=3, pady=5, sticky='w')
        row += 1

        # --- Modo de Entrada ---
        entrada_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_entry_mode"), padding=10)
        entrada_frame.pack(fill='x', padx=10, pady=5)

        self.entry_mode_var = tk.StringVar(value=config.get("entrada_modalidad", "auto"))
        ttk.Radiobutton(entrada_frame, text=i18n.t("risk_entry_auto"), variable=self.entry_mode_var, value="auto").pack(anchor='w', pady=2)
        ttk.Radiobutton(entrada_frame, text=i18n.t("risk_entry_market"), variable=self.entry_mode_var, value="market").pack(anchor='w', pady=2)
        ttk.Radiobutton(entrada_frame, text=i18n.t("risk_entry_limit"), variable=self.entry_mode_var, value="limit").pack(anchor='w', pady=2)

        param_frame = ttk.Frame(entrada_frame)
        param_frame.pack(fill='x', pady=5)
        ttk.Label(param_frame, text=i18n.t("risk_max_deviation")).pack(side='left')
        self.entry_max_dev = ttk.Entry(param_frame, width=6)
        self.entry_max_dev.insert(0, str(config.get("desviacion_maxima_porcentaje", 3.0)))
        self.entry_max_dev.pack(side='left', padx=5)

        param_frame2 = ttk.Frame(entrada_frame)
        param_frame2.pack(fill='x', pady=5)
        ttk.Label(param_frame2, text=i18n.t("risk_timeout_limit")).pack(side='left')
        self.entry_timeout_limit = ttk.Entry(param_frame2, width=6)
        self.entry_timeout_limit.insert(0, str(config.get("timeout_orden_limit_minutos", 10)))
        self.entry_timeout_limit.pack(side='left', padx=5)

        # --- DCA ---
        dca_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_dca"), padding=10)
        dca_frame.pack(fill='x', padx=10, pady=5)

        self.dca_var = tk.BooleanVar(value=config.get("dca_habilitado", True))
        ttk.Checkbutton(dca_frame, text=i18n.t("risk_dca"), variable=self.dca_var).pack(anchor='w', pady=2)

        dca_row = ttk.Frame(dca_frame)
        dca_row.pack(fill='x', pady=2)
        ttk.Label(dca_row, text=i18n.t("risk_dca_parts")).pack(side='left')
        self.spin_dca_parts = ttk.Spinbox(dca_row, from_=2, to=10, width=5)
        self.spin_dca_parts.set(config.get("dca_partes", 3))
        self.spin_dca_parts.pack(side='left', padx=5)

        # --- Distribución de TPs ---
        tp_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_tp_distribution"), padding=10)
        tp_frame.pack(fill='x', padx=10, pady=5)

        self.tp_dist_var = tk.StringVar(value=config.get("tp_distribucion", "progresivo"))
        ttk.Radiobutton(tp_frame, text=i18n.t("risk_tp_equal"), variable=self.tp_dist_var, value="igual").pack(anchor='w', pady=2)
        ttk.Radiobutton(tp_frame, text=i18n.t("risk_tp_progressive"), variable=self.tp_dist_var, value="progresivo").pack(anchor='w', pady=2)

        tp_row = ttk.Frame(tp_frame)
        tp_row.pack(fill='x', pady=5)
        ttk.Label(tp_row, text=i18n.t("risk_tp_pesos")).pack(side='left')
        pesos_default = ",".join(str(p) for p in config.get("tp_pesos", [50, 25, 15, 10]))
        self.entry_tp_pesos = ttk.Entry(tp_row, width=20)
        self.entry_tp_pesos.insert(0, pesos_default)
        self.entry_tp_pesos.pack(side='left', padx=5)

        # --- Trailing Stop ---
        trail_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_trailing"), padding=10)
        trail_frame.pack(fill='x', padx=10, pady=5)

        self.trail_var = tk.BooleanVar(value=config.get("trailing_stop_habilitado", True))
        ttk.Checkbutton(trail_frame, text=i18n.t("risk_trailing"), variable=self.trail_var).pack(anchor='w', pady=2)

        trail_row1 = ttk.Frame(trail_frame)
        trail_row1.pack(fill='x', pady=2)
        ttk.Label(trail_row1, text=i18n.t("risk_trailing_activation")).pack(side='left')
        self.entry_trail_activation = ttk.Entry(trail_row1, width=6)
        self.entry_trail_activation.insert(0, str(config.get("trailing_activacion_porcentaje", 1.5)))
        self.entry_trail_activation.pack(side='left', padx=5)

        trail_row2 = ttk.Frame(trail_frame)
        trail_row2.pack(fill='x', pady=2)
        ttk.Label(trail_row2, text=i18n.t("risk_trailing_distance")).pack(side='left')
        self.entry_trail_distance = ttk.Entry(trail_row2, width=6)
        self.entry_trail_distance.insert(0, str(config.get("trailing_distancia_porcentaje", 0.8)))
        self.entry_trail_distance.pack(side='left', padx=5)

        # --- Máximo posiciones por exchange ---
        maxpos_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_max_positions"), padding=10)
        maxpos_frame.pack(fill='x', padx=10, pady=10)

        self.maxpos_widgets = {}
        maxpos_config = self.settings.get("max_positions_per_exchange", {})
        for i, (ex_id, info) in enumerate(EXCHANGES_DEFAULTS.items()):
            ttk.Label(maxpos_frame, text=f"{info['name']}:").grid(row=i, column=0, padx=5, pady=2, sticky='e')
            spin = ttk.Spinbox(maxpos_frame, from_=0, to=50, increment=1, width=5)
            val = maxpos_config.get(ex_id, 3)
            spin.set(val)
            spin.grid(row=i, column=1, padx=5, pady=2, sticky='w')
            self.maxpos_widgets[ex_id] = spin

        # --- % Capital por Exchange ---
        ex_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_capital_pct"), padding=10)
        ex_frame.pack(fill='x', padx=10, pady=10)

        self.ex_pct_widgets = {}
        pct_config = config.get("porcentaje_capital", {})

        for i, (ex_id, info) in enumerate(EXCHANGES_DEFAULTS.items()):
            ttk.Label(ex_frame, text=f"{info['name']}:").grid(row=i, column=0, padx=5, pady=2, sticky='e')
            spin = ttk.Spinbox(ex_frame, from_=0.1, to=100.0, increment=0.1, width=8)
            val = pct_config.get(ex_id, 5.0)
            spin.set(val)
            spin.grid(row=i, column=1, padx=5, pady=2, sticky='w')
            ttk.Label(ex_frame, text="%").grid(row=i, column=2, sticky='w')
            self.ex_pct_widgets[ex_id] = spin

        ttk.Button(scrollable, text=i18n.t("btn_save_all"), command=self.save_risk).pack(pady=20, padx=10, fill='x')

    def save_risk(self):
        try:
            config = load_risk_config()

            # Actualizar porcentajes por exchange
            new_pcts = {}
            for ex_id, spin in self.ex_pct_widgets.items():
                new_pcts[ex_id] = float(spin.get())

            # Actualizar máximos de posiciones
            new_maxpos = {}
            for ex_id, spin in self.maxpos_widgets.items():
                new_maxpos[ex_id] = int(spin.get())

            # Parsear pesos de TP
            pesos_str = self.entry_tp_pesos.get().strip()
            tp_pesos = [float(x) for x in pesos_str.split(",") if x.strip()]
            if not tp_pesos:
                tp_pesos = [50, 25, 15, 10]

            config.update({
                "apalancamiento": int(self.spin_lev.get()),
                "cantidad_minima_usdt": float(self.entry_min_usdt.get()),
                "modo_margen": self.margin_var.get(),
                "porcentaje_capital": new_pcts,
                "tp_count": int(self.spin_tp_count.get()),
                "auto_breakeven": self.be_var.get(),
                # Nuevas configuraciones
                "entrada_modalidad": self.entry_mode_var.get(),
                "desviacion_maxima_porcentaje": float(self.entry_max_dev.get()),
                "timeout_orden_limit_minutos": int(self.entry_timeout_limit.get()),
                "dca_habilitado": self.dca_var.get(),
                "dca_partes": int(self.spin_dca_parts.get()),
                "tp_distribucion": self.tp_dist_var.get(),
                "tp_pesos": tp_pesos,
                "trailing_stop_habilitado": self.trail_var.get(),
                "trailing_activacion_porcentaje": float(self.entry_trail_activation.get()),
                "trailing_distancia_porcentaje": float(self.entry_trail_distance.get()),
            })
            save_risk_config(config)

            # Guardar settings con máximos de posiciones
            self.settings["max_positions_per_exchange"] = new_maxpos
            save_settings(self.settings)

            messagebox.showinfo(i18n.t("save"), i18n.t("risk_save_success"))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

    # ==================== TAB: Canales ====================
    def setup_channels_tab(self):
        frame = self.tab_canales

        top = ttk.Frame(frame)
        top.pack(fill='x', pady=10, padx=10)
        ttk.Label(top, text=i18n.t("channels_id")).pack(side='left')
        self.entry_new_channel = ttk.Entry(top, width=20)
        self.entry_new_channel.pack(side='left', padx=5)
        ttk.Button(top, text=i18n.t("channels_add"), command=self.add_channel).pack(side='left')

        self.list_channels = tk.Listbox(frame, height=15)
        self.list_channels.pack(fill='both', expand=True, padx=10, pady=5)

        ttk.Button(frame, text=i18n.t("channels_remove"), command=self.remove_channel).pack(pady=10)

        self.refresh_channels_list()

    def refresh_channels_list(self):
        self.list_channels.delete(0, tk.END)
        for cid in load_channels():
            self.list_channels.insert(tk.END, str(cid))

    def add_channel(self):
        try:
            cid = int(self.entry_new_channel.get().strip())
            channels = load_channels()
            channels.add(cid)
            save_channels(channels)
            self.refresh_channels_list()
            self.entry_new_channel.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Error", i18n.t("channels_error_id"))

    def remove_channel(self):
        sel = self.list_channels.curselection()
        if not sel:
            return
        cid = int(self.list_channels.get(sel[0]))
        channels = load_channels()
        channels.discard(cid)
        save_channels(channels)
        self.refresh_channels_list()

    # ==================== TAB: Test ====================
    def setup_test_tab(self):
        frame = self.tab_test
        ttk.Label(frame, text=i18n.t("test_select")).pack(pady=10)
        self.combo_test_ex = ttk.Combobox(frame, values=list(EXCHANGES_DEFAULTS.keys()), state="readonly")
        self.combo_test_ex.pack(pady=5)

        ttk.Button(frame, text=i18n.t("test_button"), command=self.run_test_connection).pack(pady=10)

        self.text_test_result = tk.Text(frame, height=15, width=80)
        self.text_test_result.pack(pady=10, padx=10)

    def run_test_connection(self):
        ex_id = self.combo_test_ex.get()
        if not ex_id:
            return

        self.text_test_result.delete(1.0, tk.END)
        self.text_test_result.insert(tk.END, f"Testing {ex_id}...\n")

        creds = load_api_creds()["exchanges"].get(ex_id, {})

        async def _task():
            client = await exchange_service.create_client(ex_id, creds)
            if client:
                balance = await exchange_service.get_balance(ex_id)
                self.root.after(0, lambda: self.text_test_result.insert(tk.END,
                    f"{i18n.t('test_success')} {ex_id}.\n{i18n.t('test_balance')} {balance:.2f} USDT\n"))
            else:
                self.root.after(0, lambda: self.text_test_result.insert(tk.END,
                    f"{i18n.t('test_error')} {ex_id}. Check logs.\n"))

        threading.Thread(target=lambda: asyncio.run(_task()), daemon=True).start()

    # ==================== TAB: Posiciones ====================
    def setup_positions_tab(self):
        frame = self.tab_posiciones
        self.tree_pos = ttk.Treeview(frame, columns=("ex", "sym", "side", "price", "amount", "pnl", "status"), show='headings')
        col_texts = [
            i18n.t("positions_col_exchange"),
            i18n.t("positions_col_symbol"),
            i18n.t("positions_col_side"),
            i18n.t("positions_col_price"),
            i18n.t("positions_col_amount"),
            i18n.t("positions_col_pnl"),
            i18n.t("positions_col_status"),
        ]
        for col, text in zip(self.tree_pos["columns"], col_texts):
            self.tree_pos.heading(col, text=text)
            self.tree_pos.column(col, width=100, anchor='center')

        self.tree_pos.pack(fill='both', expand=True, padx=10, pady=10)
        ttk.Button(frame, text=i18n.t("positions_refresh"), command=self.update_positions_list).pack(pady=5)

    def update_positions_list(self):
        for item in self.tree_pos.get_children():
            self.tree_pos.delete(item)
        for p in pos_manager.get_all_positions():
            self.tree_pos.insert("", tk.END, values=(
                p.exchange_id, p.symbol, p.side, p.entry_price,
                p.amount, f"{p.pnl:.2f}" if p.pnl else "0.00", p.status))

    # ==================== TAB: Saldos ====================
    def setup_balances_tab(self):
        frame = self.tab_saldos
        self.tree_balances = ttk.Treeview(frame, columns=("ex", "balance"), show='headings')
        self.tree_balances.heading("ex", text=i18n.t("balances_col_exchange"))
        self.tree_balances.heading("balance", text=i18n.t("balances_col_balance"))
        self.tree_balances.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Button(frame, text=i18n.t("balances_refresh"), command=self.update_balances).pack(pady=5)

    def update_balances(self):
        for item in self.tree_balances.get_children():
            self.tree_balances.delete(item)

        async def _task():
            for ex_id in exchange_service.clients:
                bal = await exchange_service.get_balance(ex_id)
                self.root.after(0, lambda e=ex_id, b=bal: self.tree_balances.insert("", tk.END, values=(e, f"{b:.2f} USDT")))

        threading.Thread(target=lambda: asyncio.run(_task()), daemon=True).start()

    # ==================== TAB: Consola ====================
    def setup_console_tab(self):
        frame = self.tab_consola
        self.consola_text = scrolledtext.ScrolledText(frame, state=tk.DISABLED, bg="black", fg="lightgreen",
                                                       font=("Consolas", 10))
        self.consola_text.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=5)

        self.btn_toggle_bot = ttk.Button(btn_frame, text=i18n.t("console_bot_start"), command=lambda: self.toggle_bot())
        self.btn_toggle_bot.pack(side='left', padx=10)

        ttk.Button(btn_frame, text=i18n.t("console_clear"), command=self.clear_console).pack(side='right', padx=10)

    def clear_console(self):
        self.consola_text.config(state=tk.NORMAL)
        self.consola_text.delete(1.0, tk.END)
        self.consola_text.config(state=tk.DISABLED)

    def toggle_bot(self):
        pass

    def on_closing(self):
        if messagebox.askokcancel(i18n.t("cancel"), "¿Desea cerrar el bot?"):
            self.root.destroy()