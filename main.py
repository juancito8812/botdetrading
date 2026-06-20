import asyncio
import os
import threading
import time
from datetime import datetime
import tkinter as tk
from telethon import TelegramClient, events
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError
from telethon.sessions import StringSession
from typing import Optional, cast

from utils.config import (load_api_creds, load_risk_config,
                          load_channels, init_dirs, BASE_DIR)
from utils.logger import logger
from utils.helpers import patch_aiohttp_dns
from utils.crypto import encrypt as _crypto_encrypt, decrypt as _crypto_decrypt
from services.exchange_service import exchange_service
from core.engine import trading_engine, health_monitor
from core.parser import parse_trading_signal
from ui.main_window import TradingBotGUI
from utils.settings_manager import load_settings, enable_autostart


class AsyncWorker:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


_async_worker = AsyncWorker()


class TradingBotApp:
    def __init__(self):
        init_dirs()
        self._headless = False
        self.root = None
        self.gui = None
        try:
            self.root = tk.Tk()
            self.gui = TradingBotGUI(self.root, toggle_callback=self.toggle_bot)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        except Exception:
            self._headless = True
            logger.info("🔧 Modo headless: sin interfaz gráfica")

        self.bot_running = threading.Event()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.telegram_client: Optional[TelegramClient] = None
        # Protege contra reinicios rapidos: lock + event para sincronizar loops
        self._loop_lock = threading.Lock()
        self._loop_stopped = threading.Event()
        self._loop_stopped.set()  # Inicialmente detenido

        # Cache de config para evitar IO en cada mensaje
        self._cached_config = {}
        self._last_config_refresh = 0.0
        self._was_disconnected = False

        # Configurar parche DNS
        patch_aiohttp_dns()

    def toggle_bot(self):
        running = self.bot_running.is_set()
        logger.info(
            f"Bot toggle presionado. Estado actual bot_running: "
            f"{running}"
        )
        if not running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self):
        with self._loop_lock:
            if self.bot_running.is_set():
                return
            # Esperar a que el loop anterior termine completamente
            if not self._loop_stopped.wait(timeout=10):
                logger.warning("El loop anterior no termino en 10s, forzando inicio...")
            self._loop_stopped.clear()

            self.bot_running.set()
        if self.gui and not self._headless:
            self.gui.btn_toggle_bot.config(text="🛑 DETENER BOT")
        logger.info("Iniciando bot en segundo plano...")

        thread = threading.Thread(
            target=self._run_async_loop, daemon=True
        )
        thread.start()

    def stop_bot(self):
        with self._loop_lock:
            if not self.bot_running.is_set():
                return
            self.bot_running.clear()
        if self.gui and not self._headless:
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

    def _run_async_loop(self):
        with self._loop_lock:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.main_async())
        except asyncio.CancelledError:
            logger.debug("Async loop cancelled.")
        except Exception as e:
            logger.error(
                f"Error en el motor del bot: {e}", exc_info=True
            )
        finally:
            # Cerrar todas las tareas pendientes
            if self.loop and not self.loop.is_closed():
                try:
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

            self.bot_running.clear()
            self._loop_stopped.set()
            if not self._headless and self.gui:
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
        session_file = session_dir / "user_session.enc"

        session_data = None
        if session_file.exists():
            try:
                encrypted = session_file.read_text().strip()
                api_hash = tg.get("API_HASH", "")
                if encrypted and api_hash:
                    # Intentar con clave derivada primero
                    key = self._get_session_key(api_hash)
                    decrypted = _crypto_decrypt(key, encrypted)
                    if not decrypted:
                        # Fallback: clave legacy (API_HASH directo) - migración
                        decrypted = _crypto_decrypt(api_hash, encrypted)
                    if decrypted:
                        session_data = decrypted.strip() or None
            except Exception:
                logger.warning("No se pudo descifrar sesion existente, se pedira autenticacion")

        self.telegram_client = TelegramClient(
            StringSession(session_data), int(tg["API_ID"]), tg["API_HASH"]
        )

        # Registrar handler de todos los mensajes nuevos, filtrar por canal dentro
        logger.info(f"📡 Registrando handler — canales iniciales: {list(channels)[:3] if channels else '(vacio)'}...")
        @self.telegram_client.on(events.NewMessage)
        async def handler(event):
            if not self.bot_running.is_set():
                return
            # Filtrar: solo procesar mensajes de canales autorizados (siempre desde disco)
            current_channels = await asyncio.to_thread(load_channels)
            if event.chat_id not in current_channels:
                return
            text = event.raw_text
            chat_id = event.chat_id
            logger.info(f"📥 Mensaje recibido [chat:{chat_id}]: {text[:80]}...")

            now = time.time()
            if now - self._last_config_refresh > 30:
                self._cached_config = await asyncio.to_thread(load_risk_config)
                self._last_config_refresh = now
            config = self._cached_config

            signal = parse_trading_signal(text)
            if signal:
                active_exchanges = list(exchange_service.clients.keys())
                logger.info(
                    f"📊 Señal detectada: {signal.symbol} "
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

    def _get_session_key(self, api_hash: str) -> str:
        """Deriva una clave para cifrar la sesión de Telegram.
        Combina API_HASH + MachineGuid para evitar que API_HASH solo pueda descifrar.
        """
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            machine_id, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
        except Exception:
            import uuid
            machine_id = str(uuid.getnode())
        return f"{api_hash}::{machine_id}"

    def _save_telegram_session(self):
        """Guarda la sesion de StringSession a disco (cifrada con AES-256-GCM).
        Usa clave derivada (API_HASH + MachineGuid) en vez de API_HASH directo.
        """
        if not self.telegram_client:
            return
        tg = load_api_creds()["telegram"]
        api_hash = tg.get("API_HASH", "")
        if not api_hash:
            logger.warning("No se puede cifrar sesion: API_HASH no disponible")
            return
        try:
            session_dir = BASE_DIR / "telegram_session"
            session_dir.mkdir(parents=True, exist_ok=True)
            session_str = self.telegram_client.session.save()
            key = self._get_session_key(api_hash)
            encrypted = _crypto_encrypt(key, session_str)
            if encrypted:
                (session_dir / "user_session.enc").write_text(encrypted)
                logger.debug("Sesion Telegram guardada (cifrada con clave derivada).")
            else:
                logger.warning("Fallo al cifrar sesion Telegram")
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
                dialog = simpledialog.askstring(
                    "Telegram Auth",
                    "Introduce el código recibido:",
                    parent=self.root
                )
                q.put(dialog)

            def show_dialog():
                self.root.lift()
                self.root.focus_force()
                ask()

            self.root.after(0, show_dialog)
            logger.info("⏳ Esperando código de verificación... (revisa detrás de la ventana)")
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

        # Actualizar estado en UI (solo si hay GUI)
        if not self._headless:
            try:
                if not me_info:
                    me_info = await self.telegram_client.get_me()
                user_str = f"{getattr(me_info, 'first_name', '?')} (@{getattr(me_info, 'username', '?')})"
                phone_str = getattr(me_info, 'phone', '') or ''
                # Mostrar solo últimos 4 dígitos por seguridad
                masked_phone = phone_str[-4:] if len(phone_str) > 4 else "****"
                self.root.after(0, lambda u=user_str, p=masked_phone, cid=notification_chat_id:
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

        while self.bot_running.is_set():
            try:
                tc = cast(TelegramClient, self.telegram_client)

                # Conectar/reconectar el MISMO cliente (no crear uno nuevo)
                if not tc.is_connected():
                    logger.info("Conectando/reconectando Telegram...")
                    await tc.connect()
                    logger.info("Telegram conectado, iniciando sesión...")
                else:
                    logger.info("Telegram ya conectado.")

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
                if self._was_disconnected:
                    if trading_engine.notifier:
                        await trading_engine.notifier.send_message("🔗 Bot reconectado a Telegram")
                    self._was_disconnected = False
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
                    # Mensaje de inicio cuando el bot conecta
                    await notifier.send_message(
                        f"🤖 Bot iniciado\n"
                        f"Usuario: {user_first} (@{user_username})\n"
                        f"Canales: {len(channels)}\n"
                        f"Exchanges: {list(exchange_service.clients.keys()) or 'Conectando...'}"
                    )

                # Asegurar que el watchdog se esté ejecutando (solo uno a la vez)
                trading_engine.stop_watchdog()
                trading_engine._watchdog_task = asyncio.create_task(trading_engine.watchdog())

                # Forzar sync inmediato de posiciones al reconectar
                logger.info("🔄 Sincronizando posiciones inmediatamente...")
                await trading_engine._watchdog_tick()

                # Bloquear hasta que se pierda la conexion o se detenga el bot
                await tc.run_until_disconnected()

                if not self.bot_running.is_set():
                    break

                logger.warning(
                    "Conexion de Telegram perdida. "
                    "Reintentando en 10 segundos..."
                )
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except AuthKeyDuplicatedError as e:
                logger.error(f"❌ Error de sesión Telegram: {e}")
                logger.error("La sesión fue usada desde dos IPs diferentes. Elimina el archivo de sesión y re-autentica.")
                break
            except Exception as e:
                logger.error(f"Error en bucle de Telegram: {e}", exc_info=True)
                if trading_engine.notifier:
                    await trading_engine.notifier.send_message(
                        f"🔌 Bot desconectado de Telegram\nReintentando en 30 segundos..."
                    )
                self._was_disconnected = True
                if self.bot_running.is_set():
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

        # 1. Verificar credenciales de Telegram
        tg = creds["telegram"]
        api_id = tg.get("API_ID", "").strip()
        api_hash = tg.get("API_HASH", "").strip()
        phone = tg.get("PHONE_NUMBER", "").strip()
        if not api_id or not api_id.isdigit() or not phone or not api_hash:
            logger.error("Credenciales de Telegram incompletas o inválidas")
            self.stop_bot()
            return

        # 2. Lanzar inicialización de exchanges en background (no bloquea Telegram)
        logger.info("Inicializando exchanges activos en segundo plano...")
        async def _init_exchanges():
            for ex_id, ex_creds in creds["exchanges"].items():
                if ex_creds.get("enabled"):
                    try:
                        client = await asyncio.wait_for(
                            exchange_service.create_client(ex_id, ex_creds),
                            timeout=15
                        )
                        if client:
                            logger.info(f"✅ {ex_id}: Conectado correctamente")
                        else:
                            logger.warning(f"⚠️ {ex_id}: No se pudo conectar (revisa API keys)")
                    except asyncio.TimeoutError:
                        logger.warning(f"⚠️ {ex_id}: Timeout 15s, continuando sin él...")
                    except Exception as e:
                        logger.warning(f"⚠️ {ex_id}: Error conectando: {e}")
        asyncio.create_task(_init_exchanges())

        asyncio.create_task(self._alive_loop())

        # 3. Ejecutar el bucle de reconexión de Telegram
        logger.info("Iniciando bucle de reconexión de Telegram...")
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
            if not self._headless:
                self.gui.btn_toggle_bot.config(text="🛑 DETENER BOT")
                self.root.after(500, self.start_bot)
            else:
                # Headless: iniciar inmediatamente
                self.start_bot()

        if self._headless:
            # Headless: mantener vivo el hilo principal
            logger.info("🤖 Bot en modo headless — monitorea por Telegram")
            try:
                while True:
                    time.sleep(60)
                    if not self.bot_running.is_set():
                        # Si el bot se detuvo inesperadamente, reintentar
                        logger.warning("🔄 Bot detenido, reiniciando...")
                        self.start_bot()
            except KeyboardInterrupt:
                logger.info("🛑 Bot detenido por el usuario")
                self.stop_bot()
        else:
            self.root.mainloop()

    async def _alive_loop(self):
        first = True
        while self.bot_running.is_set():
            if not first:
                await asyncio.sleep(7200)
            else:
                first = False
                await asyncio.sleep(300)  # primer heartbeat a los 5 min
            notifier = trading_engine.notifier
            if notifier:
                now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
                from core.manager import pos_manager
                open_positions = pos_manager.get_open_positions()
                total_pnl = sum(p.pnl or 0.0 for p in open_positions)
                exchanges = list(exchange_service.clients.keys())
                msg = (
                    f"💓 Bot activo — {now_str}\n"
                    f"Exchanges: {', '.join(exchanges) if exchanges else 'Ninguno'}\n"
                    f"Posiciones abiertas: {len(open_positions)}\n"
                    f"PnL flotante: ${total_pnl:+.2f}"
                )
                await notifier.send_message(msg)


if __name__ == "__main__":
    app = TradingBotApp()
    app.run()
