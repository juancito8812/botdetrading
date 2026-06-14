import asyncio
import os
import threading
import tkinter as tk
from telethon import TelegramClient, events
from typing import Optional, cast

from utils.config import (load_api_creds, load_risk_config,
                          load_channels, BASE_DIR)
from utils.logger import logger
from utils.helpers import patch_aiohttp_dns
from services.exchange_service import exchange_service
from core.engine import trading_engine, health_monitor
from core.parser import parse_trading_signal
from ui.main_window import TradingBotGUI


class TradingBotApp:
    def __init__(self):
        self.root = tk.Tk()
        self.gui = TradingBotGUI(self.root)
        self.bot_running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.telegram_client: Optional[TelegramClient] = None

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
        logger.info("Solicitud de detención enviada.")

        # Detener watchdog (método sincrónico, no necesita create_task)
        if self.loop:
            self.loop.call_soon_threadsafe(trading_engine.stop_watchdog)

        # Limpiar conexiones de exchanges
        if self.loop:
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(exchange_service.close_all())
            )

        if self.loop and self.telegram_client:
            try:
                tc = cast(TelegramClient, self.telegram_client)
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(
                        tc.disconnect()  # type: ignore[arg-type]
                    )
                )
            except Exception as e:
                logger.error(f"Error al desconectar Telegram: {e}")

    def _run_async_loop(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.main_async())
        except Exception as e:
            logger.error(
                f"Error en el motor del bot: {e}", exc_info=True
            )
        finally:
            if self.loop:
                self.loop.close()
                self.loop = None
            self.bot_running = False
            # Actualizar UI desde otro hilo de forma segura
            self.root.after(
                0,
                lambda: self.gui.btn_toggle_bot.config(
                    text="🚀 INICIAR BOT"
                )
            )

    async def _create_telegram_client(self, creds, channels):
        """Crea el cliente de Telegram UNA SOLA VEZ y registra el handler."""
        tg = creds["telegram"]

        # Asegurar que la carpeta de sesión existe
        session_dir = BASE_DIR / "telegram_session"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = str(session_dir / "user_session")

        self.telegram_client = TelegramClient(
            session_path, int(tg["API_ID"]), tg["API_HASH"]
        )

        # Registrar handler de señales UNA SOLA VEZ (no se pierde al reconectar)
        # Filtra solo mensajes de los canales configurados
        @self.telegram_client.on(events.NewMessage(chats=list(channels)))
        async def handler(event):
            if not self.bot_running:
                return
            text = event.raw_text
            logger.info(f"📥 Mensaje recibido: {text[:50]}...")

            config = load_risk_config()
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
                    asyncio.create_task(
                        trading_engine.execute_signal(signal, config, ex_id)
                    )
            else:
                logger.info("Formato de señal no reconocido.")

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
            logger.info(f"Código recibido desde la GUI: {code}")
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

        notifier = TelegramNotifier(
            telegram_client=self.telegram_client,
            chat_id=notification_chat_id,
            enabled=True,
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

                # Bloquear hasta que se pierda la conexión
                await tc.run_until_disconnected()

                if self.bot_running:
                    logger.warning(
                        "⚠️ Conexión de Telegram perdida. "
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

        # Asegurar desconexión limpia al salir
        if self.telegram_client:
            try:
                tc = cast(TelegramClient, self.telegram_client)
                await tc.disconnect()
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
        if not tg["API_ID"] or not tg["PHONE_NUMBER"]:
            logger.error("Credenciales de Telegram incompletas.")
            self.stop_bot()
            return

        # 3. Ejecutar el bucle de reconexión de Telegram
        await self._telegram_reconnection_loop(creds, config, channels)

    def on_closing(self):
        self.stop_bot()
        self.root.destroy()

    def run(self):
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
            self.root.after(500, self.start_bot)
        self.root.mainloop()


if __name__ == "__main__":
    app = TradingBotApp()
    app.run()
