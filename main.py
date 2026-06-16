import asyncio
import os
import threading
import time
import tkinter as tk
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from typing import Optional, cast

from utils.config import (load_api_creds, load_risk_config,
                          load_channels, BASE_DIR)
from utils.logger import logger
from utils.helpers import patch_aiohttp_dns
from services.exchange_service import exchange_service
from core.engine import trading_engine, health_monitor
from core.parser import parse_trading_signal
from ui.main_window import TradingBotGUI
from utils.settings_manager import load_settings, enable_autostart
from services.updater import get_current_version, check_latest_version, is_newer_version


class TradingBotApp:
    def __init__(self):
        self.root = tk.Tk()
        self.gui = TradingBotGUI(self.root)
        self.bot_running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.telegram_client: Optional[TelegramClient] = None
        # Protege contra reinicios rapidos: lock + event para sincronizar loops
        self._loop_lock = threading.Lock()
        self._loop_stopped = threading.Event()
        self._loop_stopped.set()  # Inicialmente detenido

        # Cache de config para evitar IO en cada mensaje
        self._cached_config = {}
        self._last_config_refresh = 0.0

        # Configurar parche DNS
        patch_aiohttp_dns()

        # Sobrescribir el comando del botón en la GUI
        self.gui.toggle_bot = self.toggle_bot
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def toggle_bot(self):
        logger.info(
            f"Bot toggle presionado. Estado actual bot_running: "
            f"{self.bot_running}"
        )
        if not self.bot_running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self):
        if self.bot_running:
            return
        # Esperar a que el loop anterior termine completamente
        if not self._loop_stopped.wait(timeout=10):
            logger.warning("El loop anterior no termino en 10s, forzando inicio...")
        self._loop_stopped.clear()

        self.bot_running = True
        self.gui.btn_toggle_bot.config(text="🛑 DETENER BOT")
        logger.info("Iniciando bot en segundo plano...")

        # Iniciamos el hilo pero sin bloquear la UI
        thread = threading.Thread(
            target=self._run_async_loop, daemon=True
        )
        thread.start()

    def stop_bot(self):
        if not self.bot_running:
            return
        self.bot_running = False
        self.gui.btn_toggle_bot.config(text="🚀 INICIAR BOT")
        logger.info("Solicitud de detencion enviada.")

        # Detener watchdog (metodo sincronico)
        loop = self.loop
        if loop and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(trading_engine.stop_watchdog)
            except RuntimeError:
                logger.debug("Loop ya cerrado al detener watchdog")

        # Forzar salida del run_until_disconnected() para que el loop termine
        if self.telegram_client and self.loop and not self.loop.is_closed():
            try:
                tc = cast(TelegramClient, self.telegram_client)
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(tc.disconnect())
                )
            except Exception as e:
                logger.warning(f"Error al desconectar Telegram: {e}")

        # El loop de reconexion detectara bot_running=False, saldra de
        # run_until_disconnected(), hara cleanup natural y start_bot()
        # espera con _loop_stopped.wait() a que termine completamente.

    def _run_async_loop(self):
        with self._loop_lock:
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(self.main_async())
            except Exception as e:
                logger.error(
                    f"Error en el motor del bot: {e}", exc_info=True
                )
            finally:
                # Cerrar todas las tareas pendientes
                if self.loop and not self.loop.is_closed():
                    try:
                        # Cancelar todas las tareas pendientes
                        pending = asyncio.all_tasks(self.loop)
                        for task in pending:
                            task.cancel()
                        if pending:
                            self.loop.run_until_complete(
                                asyncio.gather(*pending, return_exceptions=True)
                            )
                    except Exception:
                        pass
                    finally:
                        self.loop.close()
                        self.loop = None

                self.bot_running = False
                self._loop_stopped.set()
                # Actualizar UI desde otro hilo de forma segura
                self.root.after(
                    0,
                    lambda: self.gui.btn_toggle_bot.config(
                        text="🚀 INICIAR BOT"
                    )
                )

    async def _create_telegram_client(self, creds, channels):
        """Crea el cliente de Telegram UNA SOLA VEZ y registra el handler.
        Usa StringSession para evitar file locking de SQLite.
        """
        tg = creds["telegram"]

        if self.telegram_client:
            try:
                old = cast(TelegramClient, self.telegram_client)
                if old.is_connected():
                    await old.disconnect()
                await old.disconnected
                logger.info("Cliente Telegram anterior desconectado.")
            except Exception as e:
                logger.warning(f"Error al desconectar cliente anterior: {e}")
            finally:
                self.telegram_client = None

        session_dir = BASE_DIR / "telegram_session"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "user_session.string"

        session_data = None
        if session_file.exists():
            session_data = session_file.read_text().strip() or None

        self.telegram_client = TelegramClient(
            StringSession(session_data), int(tg["API_ID"]), tg["API_HASH"]
        )

        # Registrar handler de senales UNA SOLA VEZ (no se pierde al reconectar)
        # Filtra solo mensajes de los canales configurados
        @self.telegram_client.on(events.NewMessage(chats=list(channels)))
        async def handler(event):
            if not self.bot_running:
                return
            text = event.raw_text
            logger.info(f"📥 Mensaje recibido: {text[:50]}...")

            now = time.time()
            if now - self._last_config_refresh > 30:
                self._cached_config = load_risk_config()
                self._last_config_refresh = now
            config = self._cached_config
            signal = parse_trading_signal(text)
            if signal:
                active_exchanges = list(exchange_service.clients.keys())
                logger.info(
                    f"📊 Señal detectada: {signal.simbolo} "
                    f"{signal.direccion}. "
                    f"Procesando en {len(active_exchanges)} exchanges: "
                    f"{active_exchanges}"
                )
                for ex_id in active_exchanges:
                    task = asyncio.create_task(
                        trading_engine.execute_signal(signal, config, ex_id)
                    )
                    trading_engine.active_tasks.add(task)
                    task.add_done_callback(trading_engine.active_tasks.discard)
            else:
                logger.info("Formato de señal no reconocido.")

    def _save_telegram_session(self):
        """Guarda la sesion de StringSession a disco."""
        if not self.telegram_client:
            return
        try:
            session_dir = BASE_DIR / "telegram_session"
            session_dir.mkdir(parents=True, exist_ok=True)
            session_str = self.telegram_client.session.save()
            (session_dir / "user_session.string").write_text(session_str)
            logger.debug("Sesion Telegram guardada.")
        except Exception as e:
            logger.warning(f"No se pudo guardar sesion Telegram: {e}")

    def _get_auth_callbacks(self):
        """Retorna las funciones de autenticación vía GUI."""
        def get_code_gui():
            logger.info("Solicitando código de verificación al usuario...")
            from tkinter import simpledialog
            import queue

            q = queue.Queue()

            def ask():
                code = simpledialog.askstring(
                    "Telegram Auth",
                    "Introduce el código recibido:",
                    parent=self.root
                )
                q.put(code)

            self.root.after(0, ask)
            code = q.get()
            logger.info("Código de verificación recibido desde la GUI")
            return code

        def get_password_gui():
            logger.info("Solicitando contraseña 2FA al usuario...")
            from tkinter import simpledialog
            import queue

            q = queue.Queue()

            def ask():
                pwd = simpledialog.askstring(
                    "Telegram 2FA",
                    "TU CUENTA TIENE VERIFICACIÓN EN DOS PASOS.\n\n"
                    "Introduce tu contraseña de Telegram:",
                    parent=self.root,
                    show='*'
                )
                q.put(pwd)

            self.root.after(0, ask)
            pwd = q.get()
            if pwd:
                logger.info("Contraseña 2FA recibida desde la GUI.")
            else:
                logger.warning("No se introdujo contraseña 2FA.")
            return pwd

        return get_code_gui, get_password_gui

    async def _init_notifier(self):
        """Inicializa o actualiza el notificador después de conectar Telegram.
        Prioridad del chat_id: 1) settings.json (UI) 2) .env 3) ID del usuario autenticado
        """
        from services.notifier import TelegramNotifier
        from utils.settings_manager import load_settings

        if not self.telegram_client or not self.telegram_client.is_connected():
            return None

        # 1. Intentar desde settings.json (configurado en UI)
        settings = load_settings()
        notification_chat_id = settings.get("notification_chat_id", "").strip()
        me_info = None

        # 2. Fallback a .env
        if not notification_chat_id:
            notification_chat_id = os.getenv("NOTIFICATION_CHAT_ID", "").strip()

        # 3. Fallback al ID del usuario autenticado
        if not notification_chat_id:
            try:
                me_info = await self.telegram_client.get_me()
                notification_chat_id = str(me_info.id)
            except Exception:
                pass

        if not notification_chat_id:
            return None

        from services.notifier import DEFAULT_NOTIFICATION_PREFS

        notifier = TelegramNotifier(
            telegram_client=self.telegram_client,
            chat_id=notification_chat_id,
            enabled=True,
            notification_prefs=settings.get("notification_preferences", dict(DEFAULT_NOTIFICATION_PREFS)),
        )
        logger.info(f"🔔 Notificador inicializado (chat_id: {notification_chat_id})")

        # Actualizar estado en UI
        try:
            if not me_info:
                me_info = await self.telegram_client.get_me()
            user_str = f"{getattr(me_info, 'first_name', '?')} (@{getattr(me_info, 'username', '?')})"
            phone_str = getattr(me_info, 'phone', '') or ''
            self.root.after(0, lambda u=user_str, p=phone_str, cid=notification_chat_id:
                self.gui.update_telegram_status(True, u, p, cid))
        except Exception:
            pass

        return notifier

    async def _telegram_reconnection_loop(self, creds, config, channels):
        """
        Bucle que mantiene la conexión de Telegram.
        El cliente se crea UNA SOLA VEZ, las reconexiones reusan el mismo cliente
        para evitar el error 'event loop must not change after connection'.
        """
        # Crear cliente y registrar handler UNA SOLA VEZ
        await self._create_telegram_client(creds, channels)
        get_code, get_password = self._get_auth_callbacks()
        tg = creds["telegram"]

        while self.bot_running:
            try:
                tc = cast(TelegramClient, self.telegram_client)

                # Conectar/reconectar el MISMO cliente (no crear uno nuevo)
                if not tc.is_connected():
                    logger.info("Conectando/reconectando Telegram...")
                    await tc.connect()

                # Autenticar (usa sesión guardada si existe)
                await tc.start(
                    phone=tg["PHONE_NUMBER"],
                    code_callback=get_code,
                    password=get_password,
                )

                if not await tc.is_user_authorized():
                    logger.error("❌ No se pudo autenticar Telegram.")
                    await asyncio.sleep(30)
                    continue

                logger.info("✅ Bot conectado a Telegram con éxito.")
                self._save_telegram_session()
                me = await tc.get_me()
                user_first = getattr(me, 'first_name', '?')
                user_username = getattr(me, 'username', '?')
                logger.info(f"Sesión iniciada como: {user_first} (@{user_username})")

                logger.info(f"📡 Escuchando en {len(channels)} canales...")

                # Actualizar notificador en cada reconexión
                notifier = await self._init_notifier()
                trading_engine.notifier = notifier

                if notifier:
                    async def health_callback(exchange, status, failures, latency):
                        await notifier.notify_health_change(
                            exchange, status, failures, latency
                        )
                    health_monitor.on_status_change = health_callback

                # Asegurar que el watchdog se esté ejecutando (solo uno a la vez)
                trading_engine.stop_watchdog()
                trading_engine._watchdog_task = asyncio.create_task(trading_engine.watchdog())

                # Bloquear hasta que se pierda la conexion o se detenga el bot
                await tc.run_until_disconnected()

                if not self.bot_running:
                    break

                logger.warning(
                    "Conexion de Telegram perdida. "
                    "Reintentando en 10 segundos..."
                )
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en bucle de Telegram: {e}", exc_info=True)
                if self.bot_running:
                    logger.warning("🔄 Reintentando conexión en 30 segundos...")
                    await asyncio.sleep(30)

        # Asegurar desconexion limpia al salir
        if self.telegram_client:
            try:
                tc = cast(TelegramClient, self.telegram_client)
                await tc.disconnect()
            except Exception:
                pass

        # Cerrar conexiones de exchanges
        try:
            await exchange_service.close_all()
        except Exception:
            pass

    async def main_async(self):
        creds = load_api_creds()
        config = load_risk_config()
        channels = load_channels()

        # 1. Inicializar Exchanges
        logger.info("Inicializando exchanges activos...")
        for ex_id, ex_creds in creds["exchanges"].items():
            if ex_creds.get("enabled"):
                await exchange_service.create_client(ex_id, ex_creds)

        # 2. Verificar credenciales de Telegram
        tg = creds["telegram"]
        api_id = tg.get("API_ID", "").strip()
        api_hash = tg.get("API_HASH", "").strip()
        phone = tg.get("PHONE_NUMBER", "").strip()
        if not api_id or not api_id.isdigit() or not phone or not api_hash:
            logger.error("Credenciales de Telegram incompletas o inválidas (API_ID numérico, API_HASH, PHONE_NUMBER requeridos)")
            self.stop_bot()
            return

        # 3. Ejecutar el bucle de reconexión de Telegram
        await self._telegram_reconnection_loop(creds, config, channels)

    def on_closing(self):
        self.stop_bot()
        self.root.destroy()

    def run(self):
        # Auto-iniciar con Windows si está habilitado en settings
        settings = load_settings()
        if settings.get("start_with_windows", True):
            success, _ = enable_autostart()
            if not success:
                logger.debug("Auto-start con Windows ya estaba configurado.")

        # Iniciar bot automáticamente si hay credenciales configuradas
        creds = load_api_creds()
        tg_ok = bool(
            creds["telegram"].get("API_ID")
            and creds["telegram"].get("PHONE_NUMBER")
        )
        exchanges_ok = any(
            ex.get("enabled") and ex.get("api_key") and ex.get("secret")
            for ex in creds["exchanges"].values()
        )
        if tg_ok and exchanges_ok:
            logger.info(
                "Credenciales detectadas. Iniciando bot automáticamente..."
            )
            # Actualizar botón inmediatamente para evitar flash visual
            self.gui.btn_toggle_bot.config(text="🛑 DETENER BOT")
            self.root.after(500, self.start_bot)

        # Auto-check de actualizaciones al iniciar
        self.root.after(3000, self._auto_check_updates)

        self.root.mainloop()

    def _auto_check_updates(self):
        """Verifica actualizaciones al iniciar si está habilitado en settings."""
        settings = load_settings()
        if not settings.get("auto_check_updates", True):
            return

        def _do_check():
            try:
                info = check_latest_version()
                if not info:
                    return
                current = get_current_version()
                latest = info["tag_name"]
                if is_newer_version(latest, current):
                    logger.info(
                        f"📥 Nueva versión disponible: {latest} "
                        f"(actual: {current})"
                    )
                    # Actualizar la UI si la pestaña de ajustes ya se cargó
                    download_url = info.get("download_url", "")
                    body = info.get("body", "")
                    if download_url:
                        self.root.after(0, lambda: self.gui.upd_status_label.config(
                            text=f"📥 {latest} disponible. Ve a Ajustes > Actualizaciones",
                            foreground="#ffaa00"
                        ))
                        # Configurar el botón de descarga
                        self.root.after(0, lambda: (
                            setattr(self.gui, '_upd_latest_info', info),
                            self.gui.upd_download_btn.config(state='normal'),
                        ))
                else:
                    logger.debug(f"Bot actualizado: {current}")
            except Exception as e:
                logger.debug(f"Auto-check de actualizaciones: {e}")

        # Ejecutar en un hilo separado para no bloquear la UI
        import threading
        thread = threading.Thread(target=_do_check, daemon=True)
        thread.start()


if __name__ == "__main__":
    app = TradingBotApp()
    app.run()
