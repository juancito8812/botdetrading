"""Sistema de traducciones Español/Inglés para la UI."""

TRANSLATIONS = {
    "es": {
        # General
        "app_title": "🤖 MiBotTrading - Bot de Trading Multi-Exchange",
        "save": "💾 GUARDAR",
        "cancel": "Cancelar",
        
        # Tabs
        "tab_apis": "🔐 APIs",
        "tab_riesgo": "⚖️ Riesgo",

        "tab_test": "🔌 Test",
        "tab_posiciones": "📊 Posiciones",

        "tab_consola": "📟 Consola",
        "tab_dashboard": "📈 Dashboard",
        "tab_settings": "⚙️ Ajustes",
        "tab_reportes": "📊 Reportes",
        
        # Dashboard
        "dash_title": "📊 Top 20 Criptomonedas - CoinGecko",
        "dash_col_rank": "#",
        "dash_col_symbol": "Símbolo",
        "dash_col_name": "Nombre",
        "dash_col_price": "Precio",
        "dash_col_change": "Cambio 24h",
        "dash_col_volume": "Volumen 24h",
        "dash_col_market_cap": "Cap. Mercado",
        "dash_indices": "📈 Índices del Mercado",
        "dash_total_mcap": "Cap. Total Mercado:",
        "dash_volume_24h": "Volumen 24h:",
        "dash_btc_dominance": "Dominancia BTC:",
        "dash_eth_dominance": "Dominancia ETH:",
        "dash_mcap_change": "Cambio Cap. 24h:",
        "dash_btc_price": "BTC:",
        "dash_eth_price": "ETH:",
        "dash_refresh": "🔄 Actualizar",
        "dash_refreshing": "Actualizando...",
        "dash_error": "Error al obtener datos",
        "dash_loading": "Cargando datos del mercado...",
        "dash_source": "Fuente: CoinGecko",
        # Health
        "dash_health": "🩺 Salud de Exchanges",
        "dash_health_healthy": "🟢 Saludable",
        "dash_health_degraded": "🟡 Degradado",
        "dash_health_down": "🔴 Caído",
        "dash_health_unknown": "⚪ Sin datos",
        "dash_health_latency": "ms",
        "dash_health_failures": "fallos",
        "dash_health_cb": "CB:",
        "dash_health_refresh": "🔄 Refresh Health",
        "health_cb_closed": "Cerrado",
        "health_cb_open": "Abierto",
        "health_cb_half_open": "Medio abierto",
        "health_last_ok": "Última vez OK",
        "health_never": "Nunca",
        "health_failures": "fallos",
        "health_latency": "Latencia",
        
        # APIs
        "apis_title": "Configuración de APIs",
        "apis_enabled": "Habilitado",
        "apis_api_key": "API Key:",
        "apis_secret": "Secret:",
        "apis_passphrase": "Passphrase:",
        "apis_telegram": "Configuración de Telegram",
        "apis_save_success": "Credenciales actualizadas correctamente.",
        
        # Riesgo
        "risk_title": "Configuración General de Riesgo",
        "risk_leverage": "Apalancamiento (X):",
        "risk_min_usdt": "Mínimo USDT por Orden:",
        "risk_margin": "Modo de Margen:",
        "risk_margin_cross": "Cruzado",
        "risk_margin_isolated": "Aislado",
        "risk_tp_count": "Cantidad de TPs a ejecutar:",
        "risk_breakeven": "Mover SL a Break-even al tocar TP1",
        "risk_max_positions": "Máximo de posiciones abiertas por exchange:",
        "risk_capital_pct": "% Capital a usar por Exchange (sobre balance disponible)",
        "risk_entry_mode": "Modo de entrada:",
        "risk_entry_auto": "Automático (MERCADO si está en rango, LIMIT si no)",
        "risk_entry_market": "Siempre MERCADO",
        "risk_entry_limit": "Siempre LIMIT (esperar el precio)",
        "risk_max_deviation": "Desviación máxima del rango (%):",
        "risk_timeout_limit": "Timeout orden LIMIT (minutos):",
        "risk_dca": "DCA (entradas escalonadas)",
        "risk_dca_parts": "Partes DCA:",
        "risk_tp_distribution": "Distribución de TPs:",
        "risk_tp_equal": "Igual (misma cantidad en cada TP)",
        "risk_tp_progressive": "Progresivo (más peso en TP1)",
        "risk_tp_pesos": "Pesos personalizados (ej: 50,25,15,10):",
        "risk_trailing": "Trailing Stop",
        "risk_trailing_activation": "Activación trailing (% ganancia):",
        "risk_trailing_distance": "Distancia trailing (%):",
        "risk_breakeven": "Mover SL a Break-even al tocar TP1",
        "risk_save_success": "Configuración de riesgo actualizada correctamente.",
        
        # Settings
        "settings_title": "Ajustes de la Aplicación",
        "settings_language": "Idioma / Language:",
        "settings_autostart": "Iniciar con Windows",
        "settings_autostart_desc": "Ejecuta el bot automáticamente al iniciar el sistema (incluso sin inicio de sesión)",
        "settings_autostart_info": "Se creará una tarea en el Programador de Tareas de Windows para iniciar el bot al encender el equipo.",
        "settings_restart_hint": "Reinicia la aplicación para aplicar el cambio de idioma.",
        "settings_save_success": "Ajustes guardados correctamente.",
        "settings_autostart_enabled": "Inicio automático activado",
        "settings_autostart_disabled": "Inicio automático desactivado",
        "settings_install_task": "Crear tarea de inicio automático",
        "settings_uninstall_task": "Eliminar tarea de inicio automático",
        "settings_task_created": "Tarea de inicio automático creada correctamente.",
        "settings_task_removed": "Tarea de inicio automático eliminada.",
        "settings_task_error": "Error al configurar inicio automático:",
        "settings_task_exists": "La tarea de inicio ya existe.",
        
        # Canales
        "channels_id": "ID de Canal:",
        "channels_add": "➕ Añadir",
        "channels_remove": "❌ Eliminar Seleccionado",
        "channels_error_id": "ID de canal debe ser un número.",
        
        # Test
        "test_title": "Probar Conexión con Exchanges",
        "test_select": "Seleccione Exchange para Probar Conexión:",
        "test_button": "⚡ PROBAR CONEXIÓN",
        "test_success": "✅ ÉXITO: Conectado a",
        "test_error": "❌ ERROR: No se pudo conectar a",
        "test_balance": "Balance Futuros:",
        
        # Posiciones
        "positions_title": "Posiciones Abiertas",
        "positions_col_exchange": "Exchange",
        "positions_col_symbol": "Símbolo",
        "positions_col_side": "Lado",
        "positions_col_price": "Precio Entrada",
        "positions_col_amount": "Cantidad",
        "positions_col_status": "Estado",
        "positions_col_pnl": "PnL",
        "positions_refresh": "🔄 Actualizar Lista",
        "positions_empty": "No hay posiciones",
        

        
        # Consola
        "console_clear": "🗑️ Limpiar Consola",
        "console_bot_start": "🚀 INICIAR BOT",
        "console_bot_stop": "🛑 DETENER BOT",
        
        # Telegram
        "tab_telegram": "📱 Telegram",
        "tg_connection": "Conexión",
        "tg_connected_as": "Conectado como",
        "tg_chat_id": "Chat ID",
        "tg_notifications": "Notificaciones",
        "tg_disconnect": "Desconectar",
        "tg_send_test": "Enviar Test",
        "tg_recent_notifications": "Últimas Notificaciones",
        "tg_no_notifications": "Sin notificaciones",
        
        # Botones comunes
        "btn_save_all": "💾 GUARDAR TODA LA CONFIGURACIÓN",
        
        # Reportes
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
    },
    "en": {
        # General
        "app_title": "🤖 MiBotTrading - Multi-Exchange Trading Bot",
        "save": "💾 SAVE",
        "cancel": "Cancel",
        
        # Tabs
        "tab_apis": "🔐 APIs",
        "tab_riesgo": "⚖️ Risk",

        "tab_test": "🔌 Test",
        "tab_posiciones": "📊 Positions",

        "tab_consola": "📟 Console",
        "tab_dashboard": "📈 Dashboard",
        "tab_settings": "⚙️ Settings",
        "tab_reportes": "📊 Reports",
        
        # Dashboard
        "dash_title": "📊 Top 20 Cryptocurrencies - CoinGecko",
        "dash_col_rank": "#",
        "dash_col_symbol": "Symbol",
        "dash_col_name": "Name",
        "dash_col_price": "Price",
        "dash_col_change": "24h Change",
        "dash_col_volume": "24h Volume",
        "dash_col_market_cap": "Market Cap",
        "dash_indices": "📈 Market Indices",
        "dash_total_mcap": "Total Market Cap:",
        "dash_volume_24h": "24h Volume:",
        "dash_btc_dominance": "BTC Dominance:",
        "dash_eth_dominance": "ETH Dominance:",
        "dash_mcap_change": "Market Cap 24h Change:",
        "dash_btc_price": "BTC:",
        "dash_eth_price": "ETH:",
        "dash_refresh": "🔄 Refresh",
        "dash_refreshing": "Refreshing...",
        "dash_error": "Error fetching data",
        "dash_loading": "Loading market data...",
        "dash_source": "Source: CoinGecko",
        # Health
        "dash_health": "🩺 Exchange Health",
        "dash_health_healthy": "🟢 Healthy",
        "dash_health_degraded": "🟡 Degraded",
        "dash_health_down": "🔴 Down",
        "dash_health_unknown": "⚪ No data",
        "dash_health_latency": "ms",
        "dash_health_failures": "failures",
        "dash_health_cb": "CB:",
        "dash_health_refresh": "🔄 Refresh Health",
        "health_cb_closed": "Closed",
        "health_cb_open": "Open",
        "health_cb_half_open": "Half-open",
        "health_last_ok": "Last OK",
        "health_never": "Never",
        "health_failures": "failures",
        "health_latency": "Latency",
        
        # APIs
        "apis_title": "API Configuration",
        "apis_enabled": "Enabled",
        "apis_api_key": "API Key:",
        "apis_secret": "Secret:",
        "apis_passphrase": "Passphrase:",
        "apis_telegram": "Telegram Configuration",
        "apis_save_success": "Credentials updated successfully.",
        
        # Riesgo
        "risk_title": "General Risk Configuration",
        "risk_leverage": "Leverage (X):",
        "risk_min_usdt": "Minimum USDT per Order:",
        "risk_margin": "Margin Mode:",
        "risk_margin_cross": "Cross",
        "risk_margin_isolated": "Isolated",
        "risk_tp_count": "Number of TPs to execute:",
        "risk_breakeven": "Move SL to Break-even on TP1 hit",
        "risk_max_positions": "Maximum open positions per exchange:",
        "risk_capital_pct": "% Capital per Exchange (over available balance)",
        "risk_entry_mode": "Entry mode:",
        "risk_entry_auto": "Auto (MARKET if in range, LIMIT if not)",
        "risk_entry_market": "Always MARKET",
        "risk_entry_limit": "Always LIMIT (wait for price)",
        "risk_max_deviation": "Max range deviation (%):",
        "risk_timeout_limit": "LIMIT order timeout (minutes):",
        "risk_dca": "DCA (scaled entries)",
        "risk_dca_parts": "DCA parts:",
        "risk_tp_distribution": "TP distribution:",
        "risk_tp_equal": "Equal (same amount each TP)",
        "risk_tp_progressive": "Progressive (more weight on TP1)",
        "risk_tp_pesos": "Custom weights (e.g. 50,25,15,10):",
        "risk_trailing": "Trailing Stop",
        "risk_trailing_activation": "Trailing activation (% gain):",
        "risk_trailing_distance": "Trailing distance (%):",
        "risk_save_success": "Risk configuration updated successfully.",
        
        # Settings
        "settings_title": "Application Settings",
        "settings_language": "Idioma / Language:",
        "settings_autostart": "Start with Windows",
        "settings_autostart_desc": "Run the bot automatically on system startup (even without login)",
        "settings_autostart_info": "A task will be created in Windows Task Scheduler to start the bot on boot.",
        "settings_restart_hint": "Restart the application to apply the language change.",
        "settings_save_success": "Settings saved successfully.",
        "settings_autostart_enabled": "Auto-start enabled",
        "settings_autostart_disabled": "Auto-start disabled",
        "settings_install_task": "Create auto-start task",
        "settings_uninstall_task": "Remove auto-start task",
        "settings_task_created": "Auto-start task created successfully.",
        "settings_task_removed": "Auto-start task removed.",
        "settings_task_error": "Error configuring auto-start:",
        "settings_task_exists": "Auto-start task already exists.",
        
        # Canales
        "channels_id": "Channel ID:",
        "channels_add": "➕ Add",
        "channels_remove": "❌ Remove Selected",
        "channels_error_id": "Channel ID must be a number.",
        
        # Test
        "test_title": "Test Exchange Connection",
        "test_select": "Select Exchange to Test:",
        "test_button": "⚡ TEST CONNECTION",
        "test_success": "✅ SUCCESS: Connected to",
        "test_error": "❌ ERROR: Could not connect to",
        "test_balance": "Balance:",
        
        # Posiciones
        "positions_title": "Open Positions",
        "positions_col_exchange": "Exchange",
        "positions_col_symbol": "Symbol",
        "positions_col_side": "Side",
        "positions_col_price": "Entry Price",
        "positions_col_amount": "Amount",
        "positions_col_status": "Status",
        "positions_col_pnl": "PnL",
        "positions_refresh": "🔄 Refresh List",
        "positions_empty": "No positions",
        

        
        # Consola
        "console_clear": "🗑️ Clear Console",
        "console_bot_start": "🚀 START BOT",
        "console_bot_stop": "🛑 STOP BOT",
        
        # Telegram
        "tab_telegram": "📱 Telegram",
        "tg_connection": "Connection",
        "tg_connected_as": "Connected as",
        "tg_chat_id": "Chat ID",
        "tg_notifications": "Notifications",
        "tg_disconnect": "Disconnect",
        "tg_send_test": "Send Test",
        "tg_recent_notifications": "Recent Notifications",
        "tg_no_notifications": "No notifications",
        
        # Botones comunes
        "btn_save_all": "💾 SAVE ALL CONFIGURATION",
        
        # Reportes
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
    }
}

class I18n:
    """Gestor de internacionalización."""
    
    def __init__(self, lang: str = "es"):
        self.lang = lang
        self.current_lang = lang
        self.listeners = []
    
    def set_language(self, lang: str):
        """Cambia el idioma."""
        if lang in TRANSLATIONS and lang != self.current_lang:
            self.current_lang = lang
            self._notify()
    
    def t(self, key: str) -> str:
        """Retorna la traducción para la clave dada en el idioma actual."""
        result = TRANSLATIONS.get(self.current_lang, {}).get(key)
        if result is not None:
            return result
        result = TRANSLATIONS.get("es", {}).get(key)
        if result is not None:
            return result
        return key
    
    def add_listener(self, callback):
        """Añade un callback que se ejecuta al cambiar idioma."""
        self.listeners.append(callback)
    
    def _notify(self):
        """Notifica a todos los listeners del cambio de idioma."""
        for callback in self.listeners:
            callback()

# Instancia global
i18n = I18n("es")