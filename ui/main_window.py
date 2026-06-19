import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import asyncio
import threading
import logging
import os
from utils.config import (
    load_api_creds, save_api_creds, load_risk_config, save_risk_config,
    load_channels, save_channels, EXCHANGES_DEFAULTS
)
from utils.translations import i18n
from utils.settings_manager import (
    load_settings, save_settings,
    is_autostart_enabled, enable_autostart, disable_autostart
)
from utils import config_backup
from services.exchange_service import exchange_service
from services.market_data import fetch_top20, fetch_market_indices
from core.manager import pos_manager
from models.data_classes import PositionStatus
from core.engine import health_monitor, trading_engine
from services.updater import (get_current_version, check_latest_version,
                              is_newer_version, download_update, apply_update)
from utils.logger import logger
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path
import csv

COLOR_GREEN = "#00cc00"
COLOR_RED = "#ff4444"
COLOR_YELLOW = "#ccaa00"
COLOR_BRIGHT_GREEN = "#00ff00"


def safe_callback(fn):
    def wrapper(self, *args, **kwargs):
        try:
            if self.root.winfo_exists():
                return fn(self, *args, **kwargs)
        except tk.TclError:
            pass
    return wrapper


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
    def __init__(self, root, toggle_callback=None):
        self.root = root
        self.toggle_callback = toggle_callback
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
        self.tab_test = ttk.Frame(self.notebook)
        self.tab_posiciones = ttk.Frame(self.notebook)
        self.tab_consola = ttk.Frame(self.notebook)
        self.tab_telegram = ttk.Frame(self.notebook)
        self.tab_reportes = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_dashboard, text=i18n.t("tab_dashboard"))
        self.notebook.add(self.tab_telegram, text=i18n.t("tab_telegram"))
        self.notebook.add(self.tab_reportes, text=i18n.t("tab_reportes"))
        self.notebook.add(self.tab_apis, text=i18n.t("tab_apis"))
        self.notebook.add(self.tab_riesgo, text=i18n.t("tab_riesgo"))
        self.notebook.add(self.tab_test, text=i18n.t("tab_test"))
        self.notebook.add(self.tab_posiciones, text=i18n.t("tab_posiciones"))
        self.notebook.add(self.tab_consola, text=i18n.t("tab_consola"))
        self.notebook.add(self.tab_settings, text=i18n.t("tab_settings"))

        # Inicializar UI de pestañas
        self.setup_dashboard_tab()
        self.setup_telegram_tab()
        self.setup_reports_tab()
        self.setup_apis_tab()
        self.setup_risk_tab()
        self.setup_test_tab()
        self.setup_positions_tab()
        self.setup_console_tab()
        self.setup_settings_tab()

        # Cargar notificaciones recientes al inicio
        self.root.after(1000, self.refresh_telegram_notifications)

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

    def _show_help_popup(self, title: str, description: str):
        """Muestra un popup con ayuda descriptiva para un campo de configuración."""
        popup = tk.Toplevel(self.root)
        popup.title(f"❔ {title}")
        popup.geometry("450x250")
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)

        # Centrar sobre la ventana principal
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 225
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 125
        popup.geometry(f"+{x}+{y}")

        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text=f"❔ {title}", font=("", 12, "bold")).pack(anchor='w', pady=(0, 10))

        text_widget = tk.Text(frame, wrap='word', height=6, font=("", 10),
                              relief='flat', bg=popup.cget('bg'), bd=0,
                              padx=5, pady=5)
        text_widget.insert('1.0', description)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill='both', expand=True, pady=(0, 10))

        ttk.Button(frame, text=i18n.t("cancel"), command=popup.destroy).pack()

    def _make_help_btn(self, parent, help_key: str) -> ttk.Button:
        """Crea un botón ❔ que muestra ayuda para una clave de traducción help_."""
        title = help_key.replace("help_", "").replace("_", " ").title()
        desc = i18n.t(help_key)
        # Si la clave no tiene traducción, no devolver el key sino ignorar
        if desc == help_key:
            desc = f"No hay descripción disponible para '{help_key}'"
        btn = ttk.Button(parent, text="❔", width=2, command=lambda: self._show_help_popup(title, desc))
        return btn

    def _on_language_change(self):
        """Actualiza la UI cuando cambia el idioma."""
        self.root.title(i18n.t("app_title"))
        self.notebook.tab(self.tab_dashboard, text=i18n.t("tab_dashboard"))
        self.notebook.tab(self.tab_apis, text=i18n.t("tab_apis"))
        self.notebook.tab(self.tab_riesgo, text=i18n.t("tab_riesgo"))
        self.notebook.tab(self.tab_test, text=i18n.t("tab_test"))
        self.notebook.tab(self.tab_posiciones, text=i18n.t("tab_posiciones"))
        self.notebook.tab(self.tab_consola, text=i18n.t("tab_consola"))
        self.notebook.tab(self.tab_telegram, text=i18n.t("tab_telegram"))
        self.notebook.tab(self.tab_reportes, text=i18n.t("tab_reportes"))
        self.notebook.tab(self.tab_settings, text=i18n.t("tab_settings"))
        # Actualizar label de último backup al cambiar idioma
        self._update_backup_status()

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

        # --- Health Frame ---
        health_frame = ttk.LabelFrame(frame, text=i18n.t("dash_health"), padding=5)
        health_frame.pack(fill='x', padx=10, pady=2)

        # Contenedor interno con grid para los health cards
        self.health_container = ttk.Frame(health_frame)
        self.health_container.pack(fill='x', padx=5, pady=2)

        self.health_refresh_btn = ttk.Button(health_frame, text=i18n.t("dash_health_refresh"), command=self.refresh_health)
        self.health_refresh_btn.pack(anchor='e', padx=5, pady=2)

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
        self.dash_auto_btn = ttk.Button(btn_frame, text="⏹ Auto-Refresh (60s)", command=self.toggle_dash_auto_refresh)
        self.dash_auto_btn.pack(side='left', padx=5)

        self.dash_auto_active = True
        self.dash_auto_job = None

        # Cargar dashboard y health al inicio, luego auto-refresh cada 60s
        self.root.after(500, self.refresh_health)
        self.root.after(1000, self.refresh_dashboard)
        self.root.after(60000, self._dash_auto_tick)

    def refresh_dashboard(self):
        self.dash_status.config(text=i18n.t("dash_loading"))
        self.dash_btn.config(state='disabled')

        for item in self.dash_tree.get_children():
            self.dash_tree.delete(item)

        def _fetch():
            loop = None
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                coins, indices = loop.run_until_complete(self._fetch_dash_data())
                self.root.after(0, lambda: self._populate_dashboard(coins, indices))
            except Exception as e:
                self.root.after(0, lambda: self.dash_status.config(text=f"{i18n.t('dash_error')}: {str(e)[:60]}"))
            finally:
                if loop:
                    try:
                        if not loop.is_closed():
                            loop.close()
                    except Exception:
                        pass
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
            self.indices_labels["mcap_change"].config(foreground=COLOR_BRIGHT_GREEN)
        else:
            self.indices_labels["mcap_change"].config(foreground=COLOR_RED)

        # Poblar tree
        for i, coin in enumerate(coins):
            rank = i + 1
            symbol = coin.get("symbol", "?")
            name = coin.get("name", symbol)
            price = coin.get("price", 0)
            change = coin.get("change_24h") or 0
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

        self.dash_tree.tag_configure("up", foreground=COLOR_BRIGHT_GREEN)
        self.dash_tree.tag_configure("down", foreground=COLOR_RED)

    def _format_timestamp(self, timestamp: Optional[float]) -> str:
        """Formatea un timestamp UNIX a hora legible o 'Nunca'."""
        if not timestamp:
            return i18n.t("health_never")
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now(timezone.utc)
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        return dt.strftime("%d/%m %H:%M")

    def refresh_health(self):
        """Actualiza los indicadores de salud de exchanges desde health_monitor."""
        try:
            summary = health_monitor.get_summary()
            if not summary:
                # Si no hay datos, intentar usar exchanges activos
                for ex_id in list(exchange_service.clients.keys()):
                    health_monitor.add_exchange(ex_id)
                summary = health_monitor.get_summary()

            # Reconstruir labels si cambió la cantidad de exchanges
            for child in self.health_container.winfo_children():
                if child.winfo_exists():
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
                    fg_color = COLOR_GREEN
                elif status == "degraded":
                    led = "🟡"
                    status_text = i18n.t("dash_health_degraded")
                    fg_color = COLOR_YELLOW
                elif status == "down":
                    led = "🔴"
                    status_text = i18n.t("dash_health_down")
                    fg_color = COLOR_RED
                else:
                    led = "⚪"
                    status_text = i18n.t("dash_health_unknown")
                    fg_color = "gray"

                # Circuit breaker state
                if cb_state == "closed":
                    cb_icon = "🔒"
                    cb_text = i18n.t("health_cb_closed")
                    cb_color = COLOR_GREEN
                elif cb_state == "open":
                    cb_icon = "🔓"
                    cb_text = i18n.t("health_cb_open")
                    cb_color = COLOR_RED
                elif cb_state == "half_open":
                    cb_icon = "⚠️"
                    cb_text = i18n.t("health_cb_half_open")
                    cb_color = COLOR_YELLOW
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
                fail_color = COLOR_RED if failures > 0 else COLOR_GREEN
                ttk.Label(card, text=f"⚠ {fail_text}", foreground=fail_color, font=("", 8)).pack(anchor='w', padx=2)

                # Circuit breaker
                ttk.Label(card, text=f"{cb_icon} CB: {cb_text}", foreground=cb_color, font=("", 8)).pack(anchor='w', padx=2)

                # Última vez OK
                last_ok_text = self._format_timestamp(last_ok)
                ttk.Label(card, text=f"🕐 {i18n.t('health_last_ok')}: {last_ok_text}", font=("", 8)).pack(anchor='w', padx=2)

        except Exception as e:
            logger.warning(f"Error actualizando health en UI: {e}")

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
            self._dash_auto_refresh()

    def _dash_auto_tick(self):
        if not self.dash_auto_active:
            return
        self._dash_auto_refresh()

    def _dash_auto_refresh(self):
        if not self.dash_auto_active:
            return
        self.refresh_dashboard()
        self.refresh_health()
        self.root.after(60000, self._dash_auto_tick)

    # ==================== TAB: TELEGRAM ====================
    def setup_telegram_tab(self):
        canvas = tk.Canvas(self.tab_telegram)
        scrollbar = ttk.Scrollbar(self.tab_telegram, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        creds = load_api_creds()

        # ─── Conexión ─────────────────────
        conn_frame = ttk.LabelFrame(scrollable, text=i18n.t("tg_connection"), padding=10)
        conn_frame.pack(fill='x', padx=10, pady=5)

        self.tg_status_label = ttk.Label(conn_frame, text="⚪ Verificando...", font=("", 10, "bold"))
        self.tg_status_label.grid(row=0, column=0, columnspan=2, sticky='w', pady=2)

        self.tg_user_label = ttk.Label(conn_frame, text="")
        self.tg_user_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=2)

        self.tg_chatid_label = ttk.Label(conn_frame, text="")
        self.tg_chatid_label.grid(row=2, column=0, columnspan=2, sticky='w', pady=2)

        self.tg_notif_var = tk.BooleanVar(value=True)
        self.tg_notif_cb = ttk.Checkbutton(conn_frame, text=i18n.t("tg_notifications"), variable=self.tg_notif_var)
        self.tg_notif_cb.grid(row=3, column=0, sticky='w', pady=2)

        btn_row = ttk.Frame(conn_frame)
        btn_row.grid(row=4, column=0, columnspan=2, pady=5)
        ttk.Button(btn_row, text=i18n.t("tg_send_test"), command=self.send_test_notification).pack(side='left', padx=2)

        # ─── Credenciales ────────────────
        cred_frame = ttk.LabelFrame(scrollable, text="Credenciales", padding=10)
        cred_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(cred_frame, text="API_ID:").grid(row=0, column=0, sticky='e', pady=2)
        self.tg_entry_api_id = ttk.Entry(cred_frame, width=30, show="*")
        self.tg_entry_api_id.insert(0, creds["telegram"].get("API_ID", ""))
        self.tg_entry_api_id.grid(row=0, column=1, padx=5, pady=2, sticky='w')

        ttk.Label(cred_frame, text="API_HASH:").grid(row=1, column=0, sticky='e', pady=2)
        self.tg_entry_api_hash = ttk.Entry(cred_frame, width=50, show="*")
        self.tg_entry_api_hash.insert(0, creds["telegram"].get("API_HASH", ""))
        self.tg_entry_api_hash.grid(row=1, column=1, padx=5, pady=2, sticky='w')

        ttk.Label(cred_frame, text="Phone:").grid(row=2, column=0, sticky='e', pady=2)
        self.tg_entry_phone = ttk.Entry(cred_frame, width=30, show="*")
        self.tg_entry_phone.insert(0, creds["telegram"].get("PHONE_NUMBER", ""))
        self.tg_entry_phone.grid(row=2, column=1, padx=5, pady=2, sticky='w')

        ttk.Button(cred_frame, text=i18n.t("save"), command=self.save_telegram_creds).grid(row=3, column=0, columnspan=2, pady=5)

        # ─── Chat ID de Notificaciones ────
        chatid_frame = ttk.LabelFrame(scrollable, text=i18n.t("tg_notifications"), padding=10)
        chatid_frame.pack(fill='x', padx=10, pady=5)

        # Mostrar el chat_id actual si está disponible
        current_chat_id = self.settings.get("notification_chat_id", "")
        if current_chat_id:
            ttk.Label(
                chatid_frame,
                text=f"{i18n.t('tg_notif_chat_id_current')} {current_chat_id}",
                foreground="gray", font=("", 8)
            ).pack(anchor='w', pady=2)

        ttk.Label(chatid_frame, text=i18n.t("tg_notif_chat_id_label"), font=("", 9)).pack(anchor='w', pady=2)

        chatid_row = ttk.Frame(chatid_frame)
        chatid_row.pack(fill='x', pady=2)
        self.tg_entry_chat_id = ttk.Entry(chatid_row, width=30)
        self.tg_entry_chat_id.insert(0, current_chat_id)
        self.tg_entry_chat_id.pack(side='left', padx=5)
        ttk.Button(
            chatid_row,
            text=i18n.t("tg_notif_chat_id_save"),
            command=self._save_notification_chat_id
        ).pack(side='left', padx=5)

        ttk.Label(
            chatid_frame,
            text=i18n.t("tg_notif_chat_id_saved"),
            wraplength=600, foreground="gray", font=("", 8)
        ).pack(anchor='w', pady=2)

        # ─── Canales ─────────────────────
        ch_frame = ttk.LabelFrame(scrollable, text="Canales", padding=10)
        ch_frame.pack(fill='x', padx=10, pady=5)

        ch_row = ttk.Frame(ch_frame)
        ch_row.pack(fill='x', pady=2)
        ttk.Label(ch_row, text="ID:").pack(side='left')
        self.tg_entry_new_channel = ttk.Entry(ch_row, width=20)
        self.tg_entry_new_channel.pack(side='left', padx=5)
        ttk.Button(ch_row, text=i18n.t("channels_add"), command=self.add_telegram_channel).pack(side='left')

        self.tg_list_channels = tk.Listbox(ch_frame, height=6)
        self.tg_list_channels.pack(fill='x', pady=5)
        ttk.Button(ch_frame, text=i18n.t("channels_remove"), command=self.remove_telegram_channel).pack(pady=2)

        # ─── Notificaciones Seleccionables ──
        notif_sel_frame = ttk.LabelFrame(scrollable, text=i18n.t("notif_title"), padding=10)
        notif_sel_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(notif_sel_frame, text=i18n.t("notif_desc"), wraplength=700, foreground="gray", font=("", 8)).pack(anchor='w', pady=2)

        self._notif_vars = {}
        notif_types = [
            ("trade_open", i18n.t("notif_trade_open")),
            ("trade_closed", i18n.t("notif_trade_closed")),
            ("tp_hit", i18n.t("notif_tp_hit")),
            ("trailing_activated", i18n.t("notif_trailing_activated")),
            ("health_change", i18n.t("notif_health_change")),
            ("circuit_breaker", i18n.t("notif_circuit_breaker")),
            ("system_error", i18n.t("notif_system_error")),
            ("daily_report", i18n.t("notif_daily_report")),
        ]

        # Cargar preferencias guardadas
        saved_prefs = self.settings.get("notification_preferences", {})

        for key, label in notif_types:
            var = tk.BooleanVar(value=saved_prefs.get(key, True))
            cb = ttk.Checkbutton(notif_sel_frame, text=label, variable=var)
            cb.pack(anchor='w', padx=10, pady=1)
            self._notif_vars[key] = var

        ttk.Button(notif_sel_frame, text=i18n.t("save"), command=self._save_notification_prefs).pack(anchor='w', pady=5, padx=10)

        # ─── Últimas Notificaciones ──────
        notif_frame = ttk.LabelFrame(scrollable, text=i18n.t("tg_recent_notifications"), padding=10)
        notif_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.tg_notif_list = tk.Listbox(notif_frame, height=8)
        self.tg_notif_list.pack(fill='both', expand=True, padx=5, pady=5)

        ttk.Button(notif_frame, text=i18n.t("dash_refresh"), command=self.refresh_telegram_notifications).pack(pady=2)

        # Cargar canales
        self.refresh_telegram_channels()

    def save_telegram_creds(self):
        """Guarda credenciales de Telegram desde la UI."""
        creds = load_api_creds()
        creds["telegram"] = {
            "API_ID": self.tg_entry_api_id.get().strip(),
            "API_HASH": self.tg_entry_api_hash.get().strip(),
            "PHONE_NUMBER": self.tg_entry_phone.get().strip(),
        }
        save_api_creds(creds)
        messagebox.showinfo(i18n.t("save"), i18n.t("apis_save_success"))

    def add_telegram_channel(self):
        try:
            cid = int(self.tg_entry_new_channel.get().strip())
            channels = load_channels()
            channels.add(cid)
            save_channels(channels)
            self.refresh_telegram_channels()
            self.tg_entry_new_channel.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Error", i18n.t("channels_error_id"))

    def remove_telegram_channel(self):
        sel = self.tg_list_channels.curselection()
        if not sel:
            return
        cid = int(self.tg_list_channels.get(sel[0]))
        channels = load_channels()
        channels.discard(cid)
        save_channels(channels)
        self.refresh_telegram_channels()

    def _save_notification_prefs(self):
        """Guarda las preferencias de notificaciones en settings.json."""
        prefs = {}
        for key, var in self._notif_vars.items():
            prefs[key] = var.get()
        self.settings["notification_preferences"] = prefs
        save_settings(self.settings)

        # Actualizar en el notifier si está disponible
        if trading_engine.notifier:
            trading_engine.notifier.set_notification_prefs(prefs)

        messagebox.showinfo(i18n.t("save"), i18n.t("notif_saved"))

    def refresh_telegram_channels(self):
        self.tg_list_channels.delete(0, tk.END)
        for cid in load_channels():
            self.tg_list_channels.insert(tk.END, str(cid))

    def refresh_telegram_notifications(self):
        """Actualiza la lista de últimas notificaciones desde el notifier."""
        self.tg_notif_list.delete(0, tk.END)
        notifier = trading_engine.notifier
        if notifier and notifier.enabled:
            recent = notifier.get_recent()
            for entry in recent:
                self.tg_notif_list.insert(tk.END, entry)
        else:
            self.tg_notif_list.insert(tk.END, i18n.t("tg_no_notifications"))

    def _save_notification_chat_id(self):
        """Guarda el Chat ID de notificaciones desde la UI."""
        cid = self.tg_entry_chat_id.get().strip()
        if cid:
            self.settings["notification_chat_id"] = cid
            save_settings(self.settings)
            messagebox.showinfo(i18n.t("save"), i18n.t("tg_notif_chat_id_saved"))
        else:
            # Si está vacío, eliminar la clave
            self.settings.pop("notification_chat_id", None)
            save_settings(self.settings)
            messagebox.showinfo(i18n.t("save"), i18n.t("tg_notif_chat_id_saved"))

    def send_test_notification(self):
        """Envía una notificación de prueba y muestra el resultado."""
        notifier = trading_engine.notifier
        if notifier and notifier.enabled:
            def _do_test():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        notifier.send_message("🧪 Test desde MiBotTrading UI")
                    )
                    if result:
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Test", "✅ Notificación enviada correctamente."
                        ))
                    else:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Test", "❌ La notificación NO se pudo enviar.\nRevisa la consola para más detalles."
                        ))
                except Exception as e:
                    self.root.after(0, lambda e=e: messagebox.showerror(
                        "Test", f"❌ Error: {str(e)[:200]}"
                    ))
                finally:
                    loop.close()
            threading.Thread(target=_do_test, daemon=True).start()
        else:
            messagebox.showwarning("Test", "El notificador no está activo.\nInicia el bot primero.")

    def update_telegram_status(self, connected: bool, user: str = "", phone: str = "", chat_id: str = ""):
        """Actualiza el estado de conexión de Telegram en la UI."""
        if connected:
            self.tg_status_label.config(text=f"🟢 {i18n.t('tg_connected_as')}: {user}", foreground=COLOR_GREEN)
            if phone:
                self.tg_user_label.config(text=f"📱 {phone}")
            if chat_id:
                self.tg_chatid_label.config(text=f"🆔 {i18n.t('tg_chat_id')}: {chat_id}")
        else:
            self.tg_status_label.config(text="🔴 Desconectado", foreground=COLOR_RED)
            self.tg_user_label.config(text="")
            self.tg_chatid_label.config(text="")

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
        self._make_help_btn(lang_frame, "help_language").grid(row=0, column=2, padx=2)

        ttk.Label(lang_frame, text=i18n.t("settings_restart_hint"), foreground="gray").grid(row=1, column=0, columnspan=3, pady=5)

        # --- Auto-start ---
        autostart_frame = ttk.LabelFrame(frame, text=i18n.t("settings_autostart"), padding=10)
        autostart_frame.pack(fill='x', padx=10, pady=10)

        autostart_inner = ttk.Frame(autostart_frame)
        autostart_inner.pack(fill='x')
        self.autostart_var = tk.BooleanVar(value=self.settings.get("start_with_windows", False))
        ttk.Checkbutton(
            autostart_inner,
            text=i18n.t("settings_autostart_desc"),
            variable=self.autostart_var,
            command=self._on_autostart_toggle
        ).pack(side='left', pady=5)
        self._make_help_btn(autostart_inner, "help_autostart").pack(side='left', padx=2)

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

        self.btn_remove_task =        ttk.Button(btn_frame, text=i18n.t("settings_uninstall_task"), command=self._remove_autostart_task)
        self.btn_remove_task.pack(side='left', padx=5)

        self._update_autostart_status()

        # --- Config Backup ---
        backup_frame = ttk.LabelFrame(frame, text=i18n.t("backup_title"), padding=10)
        backup_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(backup_frame, text=i18n.t("backup_desc"), wraplength=700, foreground="gray").pack(anchor='w', pady=5)

        backup_btn_frame = ttk.Frame(backup_frame)
        backup_btn_frame.pack(fill='x', pady=5)
        ttk.Button(backup_btn_frame, text=i18n.t("backup_export"), command=self._export_config).pack(side='left', padx=5)
        ttk.Button(backup_btn_frame, text=i18n.t("backup_import"), command=self._import_config).pack(side='left', padx=5)

        # Backup status label
        self.backup_status_label = ttk.Label(backup_frame, text="", foreground="gray")
        self.backup_status_label.pack(anchor='w', padx=5, pady=5)
        self._update_backup_status()

        # --- Updates ---
        upd_frame = ttk.LabelFrame(frame, text=i18n.t("upd_title"), padding=10)
        upd_frame.pack(fill='x', padx=10, pady=10)

        # Current version
        version_row = ttk.Frame(upd_frame)
        version_row.pack(fill='x', pady=5)
        ttk.Label(version_row, text=i18n.t("upd_current_version"), font=("", 9, "bold")).pack(side='left')
        self.upd_version_label = ttk.Label(version_row, text="--", font=("", 9))
        self.upd_version_label.pack(side='left', padx=5)

        # Auto-check checkbox
        self.upd_auto_var = tk.BooleanVar(value=self.settings.get("auto_check_updates", True))
        def _on_upd_auto_toggle():
            self.settings["auto_check_updates"] = self.upd_auto_var.get()
            save_settings(self.settings)
        ttk.Checkbutton(
            upd_frame,
            text=i18n.t("upd_auto_check"),
            variable=self.upd_auto_var,
            command=_on_upd_auto_toggle
        ).pack(anchor='w', pady=2)

        # Buttons row
        upd_btn_row = ttk.Frame(upd_frame)
        upd_btn_row.pack(fill='x', pady=5)

        self.upd_check_btn = ttk.Button(
            upd_btn_row,
            text=i18n.t("upd_check"),
            command=self._check_for_updates
        )
        self.upd_check_btn.pack(side='left', padx=2)

        self.upd_download_btn = ttk.Button(
            upd_btn_row,
            text=i18n.t("upd_download"),
            command=self._download_update,
            state='disabled'
        )
        self.upd_download_btn.pack(side='left', padx=2)

        # Status / progress label
        self.upd_status_label = ttk.Label(upd_frame, text="", foreground="gray")
        self.upd_status_label.pack(anchor='w', padx=5, pady=5)

        # Release notes (scrollable text, hidden initially)
        self.upd_notes_text = tk.Text(upd_frame, height=5, wrap='word',
                                       font=("Consolas", 8),
                                       state=tk.DISABLED, foreground="gray")

        # Internal state for update flow
        self._upd_latest_info = None  # dict with tag_name, download_url, body

        # Cargar version inicial y hacer auto-check
        self._load_current_version()

    def _load_current_version(self):
        """Carga y muestra la versión actual desde VERSION file."""
        ver = get_current_version()
        self.upd_version_label.config(text=ver)

    def _check_for_updates(self):
        """Busca actualizaciones en segundo plano y actualiza la UI."""
        self.upd_check_btn.config(state='disabled', text=i18n.t("upd_checking"))
        self.upd_status_label.config(text=i18n.t("upd_checking"), foreground="gray")
        self.upd_download_btn.config(state='disabled')
        self.upd_notes_text.pack_forget()

        def _do_check():
            try:
                info = check_latest_version()
                if info is None:
                    self.root.after(0, lambda: (
                        self.upd_status_label.config(text=i18n.t("upd_error"), foreground=COLOR_RED),
                        self.upd_check_btn.config(state='normal', text=i18n.t("upd_check")),
                    ))
                    return

                current = get_current_version()
                latest = info["tag_name"]

                if is_newer_version(latest, current):
                    body = info.get("body", "")
                    self._upd_latest_info = info
                    self.root.after(0, lambda: (
                        self.upd_status_label.config(
                            text=f"{i18n.t('upd_available')} {latest}",
                            foreground=COLOR_GREEN
                        ),
                        self.upd_download_btn.config(state='normal'),
                        self.upd_check_btn.config(state='normal', text=i18n.t("upd_check")),
                        self._show_release_notes(body),
                    ))
                else:
                    self.root.after(0, lambda: (
                        self.upd_status_label.config(text=i18n.t("upd_uptodate"), foreground=COLOR_GREEN),
                        self.upd_check_btn.config(state='normal', text=i18n.t("upd_check")),
                    ))
            except Exception as e:
                self.root.after(0, lambda: (
                    self.upd_status_label.config(text=f"{i18n.t('upd_error')}: {str(e)[:60]}", foreground=COLOR_RED),
                    self.upd_check_btn.config(state='normal', text=i18n.t("upd_check")),
                ))

        threading.Thread(target=_do_check, daemon=True).start()

    def _show_release_notes(self, body: str):
        """Muestra las notas de la versión en el widget de texto."""
        if not body:
            return
        self.upd_notes_text.config(state=tk.NORMAL)
        self.upd_notes_text.delete(1.0, tk.END)
        self.upd_notes_text.insert(tk.END, f"{i18n.t('upd_release_notes')}\n{body}")
        self.upd_notes_text.config(state=tk.DISABLED)
        # Pack before the button row if visible
        if hasattr(self, 'upd_check_btn') and self.upd_check_btn.winfo_exists():
            self.upd_notes_text.pack(fill='x', padx=5, pady=5, before=self.upd_check_btn.master)
        else:
            self.upd_notes_text.pack(fill='x', padx=5, pady=5)

    def _download_update(self):
        """Descarga la actualización y la aplica."""
        if not self._upd_latest_info or not self._upd_latest_info.get("download_url"):
            return

        self.upd_download_btn.config(state='disabled', text=i18n.t("upd_downloading"))
        self.upd_status_label.config(text=i18n.t("upd_downloading"), foreground="gray")

        def _do_download():

            try:
                url = self._upd_latest_info["download_url"]
                dest = download_update(url)
                if dest:
                    self.root.after(0, lambda: (
                        self.upd_status_label.config(text=i18n.t("upd_downloaded"), foreground=COLOR_GREEN),
                    ))
                    # Apply update: lanza el .bat, luego cierra la app inmediatamente
                    success = apply_update(dest)
                    if success:
                        self.root.after(0, lambda: self.root.destroy())
                    else:
                        self.root.after(0, lambda: (
                            self.upd_status_label.config(
                                text="Error al aplicar la actualización",
                                foreground=COLOR_RED
                            ),
                            self.upd_download_btn.config(
                                state='normal', text=i18n.t("upd_download")
                            ),
                        ))
                else:
                    self.root.after(0, lambda: (
                        self.upd_status_label.config(
                            text="Error al descargar la actualización",
                            foreground="#ff4444"
                        ),
                        self.upd_download_btn.config(
                            state='normal', text=i18n.t("upd_download")
                        ),
                    ))
            except Exception as e:
                self.root.after(0, lambda: (
                    self.upd_status_label.config(
                        text=f"Error: {str(e)[:60]}", foreground="#ff4444"
                    ),
                    self.upd_download_btn.config(
                        state='normal', text=i18n.t("upd_download")
                    ),
                ))

        threading.Thread(target=_do_download, daemon=True).start()

    def _export_config(self):
        """Exporta toda la configuración a un archivo .botconfig cifrado."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".botconfig",
            filetypes=[(i18n.t("backup_file_desc"), "*.botconfig")],
            title=i18n.t("backup_export")
        )
        if not filepath:
            return

        # Popup para contraseña
        pw_popup = tk.Toplevel(self.root)
        pw_popup.title(i18n.t("backup_title"))
        pw_popup.geometry("350x200")
        pw_popup.transient(self.root)
        pw_popup.grab_set()

        ttk.Label(pw_popup, text=i18n.t("backup_password"), font=("", 10)).pack(pady=10)
        pw_var = tk.StringVar()
        ttk.Entry(pw_popup, textvariable=pw_var, show="*", width=30).pack(pady=5)

        ttk.Label(pw_popup, text=i18n.t("backup_confirm_password")).pack()
        pw_confirm_var = tk.StringVar()
        ttk.Entry(pw_popup, textvariable=pw_confirm_var, show="*", width=30).pack(pady=5)

        def _do_export():
            pw = pw_var.get()
            if len(pw) < 4:
                messagebox.showerror(i18n.t("backup_error"), i18n.t("backup_password_min"))
                return
            if pw != pw_confirm_var.get():
                messagebox.showerror(i18n.t("backup_error"), i18n.t("backup_passwords_mismatch"))
                return

            success = config_backup.export_config(pw, filepath)
            if success:
                # Guardar timestamp del backup en settings
                self.settings["last_backup_at"] = datetime.now(timezone.utc).isoformat()
                self.settings["last_backup_file"] = filepath
                save_settings(self.settings)
                self._update_backup_status()

                messagebox.showinfo(i18n.t("backup_title"), i18n.t("backup_success"))
                pw_popup.destroy()
            else:
                messagebox.showerror(i18n.t("backup_error"), i18n.t("backup_error"))

        ttk.Button(pw_popup, text=i18n.t("backup_export"), command=_do_export).pack(pady=10)
        ttk.Button(pw_popup, text=i18n.t("cancel"), command=pw_popup.destroy).pack()

    def _import_config(self):
        """Importa configuración desde un archivo .botconfig cifrado."""
        filepath = filedialog.askopenfilename(
            filetypes=[(i18n.t("backup_file_desc"), "*.botconfig")],
            title=i18n.t("backup_import")
        )
        if not filepath:
            return

        # Popup para contraseña
        pw_popup = tk.Toplevel(self.root)
        pw_popup.title(i18n.t("backup_title"))
        pw_popup.geometry("350x150")
        pw_popup.transient(self.root)
        pw_popup.grab_set()

        ttk.Label(pw_popup, text=i18n.t("backup_input_password"), font=("", 10)).pack(pady=10)
        pw_var = tk.StringVar()
        ttk.Entry(pw_popup, textvariable=pw_var, show="*", width=30).pack(pady=5)

        def _do_import():
            pw = pw_var.get()
            result = config_backup.import_config(pw, filepath)
            if result:
                messagebox.showinfo(
                    i18n.t("backup_title"),
                    i18n.t("backup_import_success")
                )
                pw_popup.destroy()
            else:
                messagebox.showerror(i18n.t("backup_error"), i18n.t("backup_wrong_password"))

        ttk.Button(pw_popup, text=i18n.t("backup_import"), command=_do_import).pack(pady=10)
        ttk.Button(pw_popup, text=i18n.t("cancel"), command=pw_popup.destroy).pack()

    def _update_backup_status(self):
        """Actualiza la etiqueta con la fecha del último respaldo."""
        last_at = self.settings.get("last_backup_at", "")
        last_file = self.settings.get("last_backup_file", "")
        if last_at:
            try:
                dt = datetime.fromisoformat(last_at)
                fecha = dt.strftime("%d/%m/%Y %H:%M")
                texto = f"🟢 {i18n.t('backup_last')}: {fecha}"
                if last_file:
                    nombre = os.path.basename(last_file)
                    texto += f"  |  {i18n.t('backup_file')}: {nombre}"
                self.backup_status_label.config(text=texto, foreground=COLOR_GREEN)
            except Exception:
                self.backup_status_label.config(text=f"⚪ {i18n.t('backup_last')}: {i18n.t('backup_never')}", foreground="gray")
        else:
            self.backup_status_label.config(text=f"⚪ {i18n.t('backup_last')}: {i18n.t('backup_never')}", foreground="gray")

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
            self._make_help_btn(frame, "help_api_enabled").grid(row=0, column=2, padx=2)
            widgets["enabled"] = enabled_var

            ttk.Label(frame, text=i18n.t("apis_api_key")).grid(row=1, column=0, sticky='e')
            key_entry = ttk.Entry(frame, width=50, show="*")
            key_entry.insert(0, creds["exchanges"].get(ex_id, {}).get("api_key", ""))
            key_entry.grid(row=1, column=1, padx=5, pady=2)
            self._make_help_btn(frame, "help_api_key").grid(row=1, column=2, padx=2)
            widgets["api_key"] = key_entry

            ttk.Label(frame, text=i18n.t("apis_secret")).grid(row=2, column=0, sticky='e')
            sec_entry = ttk.Entry(frame, width=50, show="*")
            sec_entry.insert(0, creds["exchanges"].get(ex_id, {}).get("secret", ""))
            sec_entry.grid(row=2, column=1, padx=5, pady=2)
            self._make_help_btn(frame, "help_api_secret").grid(row=2, column=2, padx=2)
            widgets["secret"] = sec_entry

            if info["needs_passphrase"]:
                ttk.Label(frame, text=i18n.t("apis_passphrase")).grid(row=3, column=0, sticky='e')
                pass_entry = ttk.Entry(frame, width=50, show="*")
                pass_entry.insert(0, creds["exchanges"].get(ex_id, {}).get("passphrase", ""))
                pass_entry.grid(row=3, column=1, padx=5, pady=2)
                self._make_help_btn(frame, "help_api_passphrase").grid(row=3, column=2, padx=2)
                widgets["passphrase"] = pass_entry

            self.exchange_widgets[ex_id] = widgets

    def save_apis(self):
        """Guarda las credenciales de los exchanges en texto plano en el .env."""
        new_creds = {"exchanges": {}, "telegram": {}}
        creds = load_api_creds()
        new_creds["telegram"] = creds.get("telegram", {})
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
        self._make_help_btn(gen_frame, "help_leverage").grid(row=row, column=2, padx=2)
        row += 1

        ttk.Label(gen_frame, text=i18n.t("risk_min_usdt")).grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.entry_min_usdt = ttk.Entry(gen_frame, width=12)
        self.entry_min_usdt.insert(0, str(config.get("cantidad_minima_usdt", 10.0)))
        self.entry_min_usdt.grid(row=row, column=1, sticky='w')
        self._make_help_btn(gen_frame, "help_min_usdt").grid(row=row, column=2, padx=2)
        row += 1

        ttk.Label(gen_frame, text=i18n.t("risk_margin")).grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.margin_var = tk.StringVar(value=config.get("modo_margen", "cross"))
        ttk.Radiobutton(gen_frame, text=i18n.t("risk_margin_cross"), variable=self.margin_var, value="cross").grid(row=row, column=1, sticky='w')
        ttk.Radiobutton(gen_frame, text=i18n.t("risk_margin_isolated"), variable=self.margin_var, value="isolated").grid(row=row, column=2, sticky='w')
        self._make_help_btn(gen_frame, "help_margin").grid(row=row, column=3, padx=2)
        row += 1

        ttk.Label(gen_frame, text=i18n.t("risk_tp_count")).grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.spin_tp_count = ttk.Spinbox(gen_frame, from_=1, to=10, width=10)
        self.spin_tp_count.set(config.get("tp_count", 5))
        self.spin_tp_count.grid(row=row, column=1, sticky='w')
        self._make_help_btn(gen_frame, "help_tp_count").grid(row=row, column=2, padx=2)
        row += 1

        self.be_var = tk.BooleanVar(value=config.get("auto_breakeven", True))
        be_frame = ttk.Frame(gen_frame)
        be_frame.grid(row=row, column=0, columnspan=3, pady=5, sticky='w')
        ttk.Checkbutton(be_frame, text=i18n.t("risk_breakeven"), variable=self.be_var).pack(side='left')
        self._make_help_btn(be_frame, "help_breakeven").pack(side='left', padx=2)
        row += 1

        self.require_sl_var = tk.BooleanVar(value=config.get("requerir_stop_loss", True))
        require_sl_frame = ttk.Frame(gen_frame)
        require_sl_frame.grid(row=row, column=0, columnspan=3, pady=5, sticky='w')
        ttk.Checkbutton(require_sl_frame, text=i18n.t("risk_require_sl"), variable=self.require_sl_var).pack(side='left')
        self._make_help_btn(require_sl_frame, "help_require_sl").pack(side='left', padx=2)
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
        self._make_help_btn(param_frame, "help_max_deviation").pack(side='left', padx=2)

        param_frame2 = ttk.Frame(entrada_frame)
        param_frame2.pack(fill='x', pady=5)
        ttk.Label(param_frame2, text=i18n.t("risk_timeout_limit")).pack(side='left')
        self.entry_timeout_limit = ttk.Entry(param_frame2, width=6)
        self.entry_timeout_limit.insert(0, str(config.get("timeout_orden_limit_minutos", 10)))
        self.entry_timeout_limit.pack(side='left', padx=5)
        self._make_help_btn(param_frame2, "help_timeout_limit").pack(side='left', padx=2)

        # --- DCA ---
        dca_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_dca"), padding=10)
        dca_frame.pack(fill='x', padx=10, pady=5)

        dca_inner = ttk.Frame(dca_frame)
        dca_inner.pack(fill='x')
        self.dca_var = tk.BooleanVar(value=config.get("dca_habilitado", True))
        ttk.Checkbutton(dca_inner, text=i18n.t("risk_dca"), variable=self.dca_var).pack(side='left', pady=2)
        self._make_help_btn(dca_inner, "help_dca").pack(side='left', padx=2)

        dca_row = ttk.Frame(dca_frame)
        dca_row.pack(fill='x', pady=2)
        ttk.Label(dca_row, text=i18n.t("risk_dca_parts")).pack(side='left')
        self.spin_dca_parts = ttk.Spinbox(dca_row, from_=2, to=10, width=5)
        self.spin_dca_parts.set(config.get("dca_partes", 3))
        self.spin_dca_parts.pack(side='left', padx=5)
        self._make_help_btn(dca_row, "help_dca_parts").pack(side='left', padx=2)

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
        self._make_help_btn(tp_row, "help_tp_pesos").pack(side='left', padx=2)

        # --- Trailing Stop ---
        trail_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_trailing"), padding=10)
        trail_frame.pack(fill='x', padx=10, pady=5)

        trail_inner = ttk.Frame(trail_frame)
        trail_inner.pack(fill='x')
        self.trail_var = tk.BooleanVar(value=config.get("trailing_stop_habilitado", True))
        ttk.Checkbutton(trail_inner, text=i18n.t("risk_trailing"), variable=self.trail_var).pack(side='left', pady=2)
        self._make_help_btn(trail_inner, "help_trailing").pack(side='left', padx=2)

        trail_row1 = ttk.Frame(trail_frame)
        trail_row1.pack(fill='x', pady=2)
        ttk.Label(trail_row1, text=i18n.t("risk_trailing_activation")).pack(side='left')
        self.entry_trail_activation = ttk.Entry(trail_row1, width=6)
        self.entry_trail_activation.insert(0, str(config.get("trailing_activacion_porcentaje", 1.5)))
        self.entry_trail_activation.pack(side='left', padx=5)
        self._make_help_btn(trail_row1, "help_trailing_activation").pack(side='left', padx=2)

        trail_row2 = ttk.Frame(trail_frame)
        trail_row2.pack(fill='x', pady=2)
        ttk.Label(trail_row2, text=i18n.t("risk_trailing_distance")).pack(side='left')
        self.entry_trail_distance = ttk.Entry(trail_row2, width=6)
        self.entry_trail_distance.insert(0, str(config.get("trailing_distancia_porcentaje", 0.8)))
        self.entry_trail_distance.pack(side='left', padx=5)
        self._make_help_btn(trail_row2, "help_trailing_distance").pack(side='left', padx=2)

        # --- Máximo posiciones por exchange ---
        maxpos_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_max_positions"), padding=10)
        maxpos_frame.pack(fill='x', padx=10, pady=10)

        maxpos_help_row = ttk.Frame(maxpos_frame)
        maxpos_help_row.grid(row=0, column=0, columnspan=3, sticky='e')
        self._make_help_btn(maxpos_help_row, "help_max_positions").pack(side='right', padx=2)

        self.maxpos_widgets = {}
        maxpos_config = self.settings.get("max_positions_per_exchange", {})
        for i, (ex_id, info) in enumerate(EXCHANGES_DEFAULTS.items()):
            ttk.Label(maxpos_frame, text=f"{info['name']}:").grid(row=i+1, column=0, padx=5, pady=2, sticky='e')
            spin = ttk.Spinbox(maxpos_frame, from_=0, to=50, increment=1, width=5)
            val = maxpos_config.get(ex_id, 3)
            spin.set(val)
            spin.grid(row=i+1, column=1, padx=5, pady=2, sticky='w')
            self.maxpos_widgets[ex_id] = spin

        # --- % Capital por Exchange ---
        ex_frame = ttk.LabelFrame(scrollable, text=i18n.t("risk_capital_pct"), padding=10)
        ex_frame.pack(fill='x', padx=10, pady=10)

        cap_help_row = ttk.Frame(ex_frame)
        cap_help_row.grid(row=0, column=0, columnspan=4, sticky='e')
        self._make_help_btn(cap_help_row, "help_capital_pct").pack(side='right', padx=2)

        self.ex_pct_widgets = {}
        pct_config = config.get("porcentaje_capital", {})

        for i, (ex_id, info) in enumerate(EXCHANGES_DEFAULTS.items()):
            ttk.Label(ex_frame, text=f"{info['name']}:").grid(row=i+1, column=0, padx=5, pady=2, sticky='e')
            spin = ttk.Spinbox(ex_frame, from_=0.1, to=100.0, increment=0.1, width=8)
            val = pct_config.get(ex_id, 5.0)
            spin.set(val)
            spin.grid(row=i+1, column=1, padx=5, pady=2, sticky='w')
            ttk.Label(ex_frame, text="%").grid(row=i+1, column=2, sticky='w')
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
                "requerir_stop_loss": self.require_sl_var.get(),
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

        # Top bar
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(top_frame, text=i18n.t("positions_title"), font=("", 12, "bold")).pack(side='left')
        ttk.Button(top_frame, text=i18n.t("positions_refresh"), command=self.update_positions_list).pack(side='right', padx=5)

        # Treeview with scrollbars
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ("ex", "sym", "side", "price", "amount", "leverage", "pnl", "sl", "tps", "actions")
        self.tree_pos = ttk.Treeview(tree_frame, columns=columns, show='headings', height=16)

        col_texts = [
            i18n.t("positions_col_exchange"),
            i18n.t("positions_col_symbol"),
            i18n.t("positions_col_side"),
            i18n.t("positions_col_price"),
            i18n.t("positions_col_amount"),
            i18n.t("positions_col_leverage"),
            i18n.t("positions_col_pnl"),
            i18n.t("positions_col_sl"),
            i18n.t("positions_col_tps"),
            i18n.t("positions_col_actions"),
        ]
        widths = {"ex": 80, "sym": 100, "side": 70, "price": 90, "amount": 80, "leverage": 70, "pnl": 90, "sl": 90, "tps": 120, "actions": 100}
        for col, text in zip(columns, col_texts):
            self.tree_pos.heading(col, text=text)
            self.tree_pos.column(col, width=widths.get(col, 80), anchor='center')

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_pos.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree_pos.xview)
        self.tree_pos.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree_pos.pack(side='top', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')

        # Double-click handler
        self.tree_pos.bind("<Double-1>", self._on_pos_double_click)

        # Initial load
        self.update_positions_list()

    def _on_pos_double_click(self, event):
        """Maneja doble clic en una posición."""
        item = self.tree_pos.focus()
        if not item:
            return
        col = self.tree_pos.identify_column(event.x)
        col_idx = int(col.replace("#", "")) - 1

        values = self.tree_pos.item(item, "values")
        if not values:
            return
        exchange_id = values[0].lower()

        # Use item index to find the correct position (handles duplicates)
        idx = self.tree_pos.index(item)
        open_positions = pos_manager.get_open_positions()
        if idx < len(open_positions):
            p = open_positions[idx]
            if col_idx >= 7:
                self._open_modify_popup(p)
            elif col_idx == 6:
                self._close_position(p)
            else:
                self._open_modify_popup(p)

    def update_positions_list(self):
        """Actualiza la tabla solo con posiciones activas."""
        for item in self.tree_pos.get_children():
            self.tree_pos.delete(item)

        open_positions = pos_manager.get_open_positions()
        if not open_positions:
            self.tree_pos.insert("", tk.END, values=(
                i18n.t("positions_empty"), "", "", "", "", "", "", "", "", ""))
            return

        for p in open_positions:
            side_emoji = "🚀" if p.side.lower() == "buy" else "🔻"
            side_text = "LONG" if p.side.lower() == "buy" else "SHORT"
            pnl_str = f"${p.pnl:+.2f}" if p.pnl else "$0.00"
            sl_str = f"${p.entry_price:.2f}" if p.is_breakeven else ("-" if not p.sl_order_id else "SL")
            tp_count = len(p.tp_order_ids) if p.tp_order_ids else 0
            tp_str = f"{tp_count} nivel(es)" if tp_count > 0 else "-"
            tags = ()
            if p.pnl and p.pnl > 0:
                tags = ("profit",)
            elif p.pnl and p.pnl < 0:
                tags = ("loss",)

            self.tree_pos.insert("", tk.END, values=(
                p.exchange_id.upper(), p.symbol, f"{side_emoji} {side_text}",
                f"${p.entry_price:,.2f}", p.amount, f"{p.leverage}x",
                pnl_str, sl_str, tp_str,
                f"{i18n.t('positions_modify')} | {i18n.t('positions_close')}"
            ), tags=tags)

        self.tree_pos.tag_configure("profit", foreground=COLOR_GREEN)
        self.tree_pos.tag_configure("loss", foreground=COLOR_RED)

    def _open_modify_popup(self, position):
        """Abre ventana para modificar SL/TP de una posición."""
        popup = tk.Toplevel(self.root)
        popup.title(f"{i18n.t('positions_modify_title')} — {position.symbol}")
        popup.geometry("400x300")
        popup.transient(self.root)
        popup.grab_set()

        # Header
        ttk.Label(popup, text=f"{position.exchange_id.upper()} — {position.symbol} ({position.side})",
                  font=("", 10, "bold")).pack(pady=10)

        # SL
        sl_frame = ttk.LabelFrame(popup, text=i18n.t("positions_sl_label"), padding=5)
        sl_frame.pack(fill='x', padx=10, pady=5)
        sl_var = tk.StringVar(value=str(position.entry_price))
        ttk.Entry(sl_frame, textvariable=sl_var, width=20).pack(pady=5)

        # TP
        tp_frame = ttk.LabelFrame(popup, text=i18n.t("positions_tp_current"), padding=5)
        tp_frame.pack(fill='x', padx=10, pady=5)

        tp_listbox = tk.Listbox(tp_frame, height=4)
        tp_listbox.pack(fill='x', pady=2)
        for i, tp_id in enumerate(position.tp_order_ids):
            tp_listbox.insert(tk.END, f"TP{i+1}: {tp_id}")

        new_tp_frame = ttk.Frame(tp_frame)
        new_tp_frame.pack(fill='x', pady=5)
        new_tp_var = tk.StringVar()
        ttk.Entry(new_tp_frame, textvariable=new_tp_var, width=15).pack(side='left', padx=2)
        ttk.Button(new_tp_frame, text=i18n.t("positions_tp_add"),
                   command=lambda: self._add_tp(position, new_tp_var, tp_listbox)).pack(side='left', padx=2)

        # Save button
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text=i18n.t("positions_save"),
                   command=lambda: self._save_sl_modify(position, sl_var, popup)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=i18n.t("cancel"), command=popup.destroy).pack(side='left', padx=5)

    def _save_sl_modify(self, position, sl_var, popup):
        """Guarda el nuevo SL ejecutando la orden en el exchange."""
        try:
            new_sl = float(sl_var.get())
        except ValueError:
            messagebox.showerror("Error", "SL debe ser un número válido.")
            return

        def _do_sl_update():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                client = exchange_service.clients.get(position.exchange_id)
                if not client:
                    self.root.after(0, lambda: messagebox.showerror(
                        i18n.t("positions_close_error"), "Cliente no disponible"))
                    loop.close()
                    return

                # 1. Cancelar SL anterior si existe
                if position.sl_order_id:
                    loop.run_until_complete(
                        exchange_service.cancel_order(
                            position.exchange_id, position.market_symbol, position.sl_order_id
                        )
                    )

                # 2. Crear nuevo SL según exchange
                sl_side = 'sell' if position.side.lower() == 'buy' else 'buy'
                sl_amount = float(client.amount_to_precision(position.market_symbol, position.amount))
                side_upper = 'LONG' if position.side.lower() == 'buy' else 'SHORT'

                if position.exchange_id == "bingx":
                    sl_order = loop.run_until_complete(client.create_order(
                        position.market_symbol, 'TRIGGER_MARKET', sl_side, sl_amount, None, {
                            'stopPrice': new_sl,
                            'positionSide': side_upper
                        }
                    ))
                elif position.exchange_id == "bitget":
                    sl_order = loop.run_until_complete(client.create_order(
                        position.market_symbol, 'limit', sl_side, sl_amount, new_sl, {
                            'stopPrice': new_sl,
                            'planType': 'normal_plan',
                            'reduceOnly': True
                        }
                    ))
                else:
                    sl_order = loop.run_until_complete(client.create_order(
                        position.market_symbol, 'market', sl_side, sl_amount, None, {
                            'stopPrice': new_sl,
                            'reduceOnly': True
                        }
                    ))

                # Actualizar referencia en la posición
                position.sl_order_id = sl_order.get('id', '')
                pos_manager.save()

                self.root.after(0, lambda: (
                    messagebox.showinfo(i18n.t("positions_sl_updated"),
                                        f"SL movido a ${new_sl:.2f}"),
                    popup.destroy(),
                    self.update_positions_list()
                ))
                logger.info(f"📝 SL actualizado para {position.symbol} → ${new_sl:.2f}")

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    i18n.t("positions_close_error"), str(e)))
                logger.error(f"Error actualizando SL {position.symbol}: {e}")
            finally:
                loop.close()

        threading.Thread(target=_do_sl_update, daemon=True).start()

    def _add_tp(self, position, tp_var, tp_listbox):
        """Agrega un nuevo TP ejecutando la orden en el exchange."""
        try:
            new_tp = float(tp_var.get())
        except ValueError:
            messagebox.showerror("Error", "TP debe ser un número válido.")
            return

        def _do_add_tp():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                client = exchange_service.clients.get(position.exchange_id)
                if not client:
                    self.root.after(0, lambda: messagebox.showerror(
                        i18n.t("positions_close_error"), "Cliente no disponible"))
                    loop.close()
                    return

                tp_side = 'sell' if position.side.lower() == 'buy' else 'buy'
                tp_amount = float(client.amount_to_precision(position.market_symbol, position.amount))
                side_upper = 'LONG' if position.side.lower() == 'buy' else 'SHORT'

                if position.exchange_id == "bingx":
                    tp_order = loop.run_until_complete(client.create_order(
                        position.market_symbol, 'TRIGGER_LIMIT', tp_side, tp_amount, new_tp, {
                            'stopPrice': new_tp,
                            'positionSide': side_upper
                        }
                    ))
                elif position.exchange_id == "bitget":
                    tp_order = loop.run_until_complete(client.create_order(
                        position.market_symbol, 'limit', tp_side, tp_amount, new_tp, {
                            'stopPrice': new_tp,
                            'planType': 'normal_plan',
                            'reduceOnly': True
                        }
                    ))
                else:
                    tp_order = loop.run_until_complete(client.create_order(
                        position.market_symbol, 'limit', tp_side, tp_amount, new_tp, {
                            'stopPrice': new_tp,
                            'reduceOnly': True
                        }
                    ))

                tp_id = tp_order.get('id', '')
                position.tp_order_ids.append(tp_id)
                pos_manager.save()

                self.root.after(0, lambda: (
                    tp_listbox.insert(tk.END, f"TP{len(position.tp_order_ids)}: ${new_tp:.2f}"),
                    tp_var.set(""),
                    messagebox.showinfo(i18n.t("positions_tp_added"),
                                        f"TP ${new_tp:.2f} creado en {position.exchange_id}")
                ))
                logger.info(f"🎯 Nuevo TP agregado para {position.symbol} → ${new_tp:.2f}")

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    i18n.t("positions_close_error"), str(e)))
                logger.error(f"Error agregando TP {position.symbol}: {e}")
            finally:
                loop.close()

        threading.Thread(target=_do_add_tp, daemon=True).start()

    def _close_position(self, position):
        """Cierra una posición en el exchange."""
        confirm = messagebox.askokcancel(
            i18n.t("positions_close_confirm"),
            i18n.t("positions_close_confirm_msg").format(
                symbol=position.symbol, exchange=position.exchange_id.upper())
        )
        if not confirm:
            return

        def _do_close():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                client = exchange_service.clients.get(position.exchange_id)
                if not client:
                    self.root.after(0, lambda: messagebox.showerror(
                        i18n.t("positions_close_error"), "Cliente no disponible"))
                    loop.close()
                    return

                side_map = {"Buy": "sell", "Sell": "buy"}
                close_side = side_map.get(position.side, "sell")
                amount = float(client.amount_to_precision(position.market_symbol, position.amount))

                params = {}
                side_upper = 'LONG' if position.side.lower() == 'buy' else 'SHORT'
                if position.exchange_id == "bingx":
                    params['positionSide'] = side_upper
                elif position.exchange_id == "bitget":
                    params['tdMode'] = 'cross'

                order = loop.run_until_complete(client.create_order(
                    position.market_symbol, 'market', close_side, amount, None, params
                ))

                if order.get('id'):
                    # Marcar como cerrada en pos_manager
                    position.status = PositionStatus.CLOSED
                    pos_manager.save()
                    self.root.after(0, lambda: (
                        messagebox.showinfo(i18n.t("positions_close_success"),
                                            f"{position.symbol}: ${position.pnl:+.2f}" if position.pnl else ""),
                        self.update_positions_list()
                    ))
                    logger.info(f"🔒 Posición cerrada manualmente: {position.symbol}")
                else:
                    self.root.after(0, lambda: messagebox.showerror(
                        i18n.t("positions_close_error"), "La orden no devolvió ID"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    i18n.t("positions_close_error"), str(e)))
                logger.error(f"Error cerrando posición {position.symbol}: {e}")
            finally:
                loop.close()

        threading.Thread(target=_do_close, daemon=True).start()

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
        if self.toggle_callback:
            self.toggle_callback()

    # ==================== TAB: REPORTES ====================
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
        ttk.Button(filter_row, text=i18n.t("dash_refresh"), command=self.refresh_reports).pack(side='right', padx=2)
        ttk.Button(filter_row, text=i18n.t("export_csv"), command=self._export_csv).pack(side='right', padx=2)

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

    def refresh_reports(self):
        """Actualiza todas las estadísticas de la pestaña Reportes."""
        all_positions = pos_manager.get_all_positions()
        closed = [p for p in all_positions if p.status == PositionStatus.CLOSED]
        open_pos = [p for p in all_positions if p.status == PositionStatus.OPEN]

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
            foreground=COLOR_GREEN if total_pnl >= 0 else COLOR_RED)
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
            try:
                for ex_id in list(ex_data.keys()):
                    if ex_id in exchange_service.clients:
                        try:
                            bal = loop.run_until_complete(exchange_service.get_balance(ex_id))
                            self.root.after(0, lambda e=ex_id, b=bal: self._update_ex_balance(e, b))
                        except Exception:
                            pass
            finally:
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

        # Sort by open_time descending
        filtered_sorted = sorted(filtered, key=lambda p: p.open_time or "", reverse=True)[:50]

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
                p.status.value.upper(), p.open_time), tags=tags)

        self.tree_reports_tr.tag_configure("profit", foreground=COLOR_GREEN)
        self.tree_reports_tr.tag_configure("loss", foreground=COLOR_RED)

    def _update_ex_balance(self, exchange_id: str, balance: float):
        """Actualiza la columna Balance en la tabla por exchange."""
        for item in self.tree_reports_ex.get_children():
            values = self.tree_reports_ex.item(item, "values")
            if values and values[0] == exchange_id.upper():
                self.tree_reports_ex.item(item, values=(
                    values[0], values[1], values[2], values[3], f"${balance:.2f}"))
                break

    def _export_csv(self):
        """Exporta todas las posiciones a un archivo CSV."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title=i18n.t("export_csv")
        )
        if not filepath:
            return

        try:
            all_positions = pos_manager.get_all_positions()

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Exchange", "Symbol", "Side", "Entry Price",
                    "Amount", "Leverage", "PnL", "Status", "Open Time"
                ])
                for p in all_positions:
                    writer.writerow([
                        p.exchange_id, p.symbol, p.side, p.entry_price,
                        p.amount, p.leverage,
                        f"{p.pnl:.2f}" if p.pnl else "0.00",
                        p.status.value, p.open_time
                    ])

            messagebox.showinfo(
                i18n.t("export_csv_success").format(file=filepath),
                f"{len(all_positions)} trades exportados"
            )
            logger.info(f"📥 CSV exportado: {filepath} ({len(all_positions)} trades)")
        except Exception as e:
            messagebox.showerror(i18n.t("export_csv_error"), str(e))
            logger.error(f"Error exportando CSV: {e}")