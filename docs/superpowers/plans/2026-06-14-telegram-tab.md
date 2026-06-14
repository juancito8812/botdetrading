# Pestaña Telegram — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nueva pestaña "📱 Telegram" con estado, credenciales, canales y notificaciones recientes.

**Architecture:** Modificar 4 archivos: `services/notifier.py` (historial), `utils/translations.py` (10 nuevas claves), `ui/main_window.py` (nueva pestaña + mover controles existentes), `main.py` (exponer estado a UI).

---

### Task 1: Agregar historial de notificaciones a notifier.py

**Files:**
- Modify: `services/notifier.py` — agregar `history` y `_add_to_history()`

- [ ] **Step 1: Agregar `history` al `__init__`**

```python
def __init__(self, telegram_client: Any, chat_id: str, enabled: bool = True):
    self.client = telegram_client
    self.chat_id = chat_id
    self.enabled = enabled
    self.history: List[str] = []  # NUEVO
```

- [ ] **Step 2: Agregar métodos `_add_to_history` y `get_recent`**

```python
def _add_to_history(self, text: str):
    """Agrega una entrada al historial (max 20)."""
    timestamp = datetime.now().strftime("%H:%M")
    self.history.append(f"[{timestamp}] {text}")
    if len(self.history) > 20:
        self.history = self.history[-20:]

def get_recent(self, count: int = 20) -> List[str]:
    """Retorna las últimas N notificaciones."""
    return self.history[-count:]
```

- [ ] **Step 3: Llamar `_add_to_history` en cada método de notificación**

Agregar `self._add_to_history(...)` al final de cada método (`notify_trade_open`, `notify_trade_closed`, `notify_tp_hit`, `notify_trailing_activated`, `notify_health_change`, `notify_circuit_breaker`, `notify_error`, `send_daily_report`).

Ejemplo para `notify_trade_open`:
```python
side_text = "LONG" if position.side.lower() == "buy" else "SHORT"
self._add_to_history(f"{side_emoji} {side_text} ABIERTA {position.symbol}")
```

- [ ] **Step 4: Verificar que no rompe tests**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: 9 passed

---

### Task 2: Agregar traducciones

**Files:**
- Modify: `utils/translations.py` — agregar ~10 nuevas claves

- [ ] **Step 1: Agregar claves en español**

En la sección `# Health` o crear nueva sección `# Telegram`:
```python
"tab_telegram": "📱 Telegram",
"tg_connection": "Conexión",
"tg_connected_as": "Conectado como",
"tg_chat_id": "Chat ID",
"tg_notifications": "Notificaciones",
"tg_disconnect": "Desconectar",
"tg_send_test": "Enviar Test",
"tg_recent_notifications": "Últimas Notificaciones",
"tg_no_notifications": "Sin notificaciones",
```

- [ ] **Step 2: Agregar claves en inglés**

```python
"tab_telegram": "📱 Telegram",
"tg_connection": "Connection",
"tg_connected_as": "Connected as",
"tg_chat_id": "Chat ID",
"tg_notifications": "Notifications",
"tg_disconnect": "Disconnect",
"tg_send_test": "Send Test",
"tg_recent_notifications": "Recent Notifications",
"tg_no_notifications": "No notifications",
```

- [ ] **Step 3: Verificar**

Run: `python -c "from utils.translations import i18n; print(i18n.t('tab_telegram'))"`
Expected: `📱 Telegram`

---

### Task 3: Nueva pestaña Telegram en main_window.py

**Files:**
- Modify: `ui/main_window.py` — nueva pestaña + eliminar controles duplicados

- [ ] **Step 1: Agregar la pestaña en `__init__`**

Después de `self.tab_settings`, agregar:
```python
self.tab_telegram = ttk.Frame(self.notebook)
```

Luego en la sección de crear pestañas, agregar después de settings:
```python
self.notebook.add(self.tab_telegram, text=i18n.t("tab_telegram"))
```

Y en la lista de `setup_*`:
```python
self.setup_telegram_tab()
```

- [ ] **Step 2: Eliminar controles de Telegram de `setup_apis_tab()`**

Quitar de `setup_apis_tab()` todo el bloque de Telegram (labels + entries para API_ID, API_HASH, PHONE). Dejar solo los exchanges.

- [ ] **Step 3: Crear `setup_telegram_tab()` con las 4 secciones**

```python
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

    # ─── Sección: CONEXIÓN ──────────────────
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

    # ─── Sección: CREDENCIALES ──────────────
    cred_frame = ttk.LabelFrame(scrollable, text="Credenciales", padding=10)
    cred_frame.pack(fill='x', padx=10, pady=5)

    ttk.Label(cred_frame, text="API_ID:").grid(row=0, column=0, sticky='e', pady=2)
    self.tg_entry_api_id = ttk.Entry(cred_frame, width=30)
    self.tg_entry_api_id.insert(0, creds["telegram"].get("API_ID", ""))
    self.tg_entry_api_id.grid(row=0, column=1, padx=5, pady=2, sticky='w')

    ttk.Label(cred_frame, text="API_HASH:").grid(row=1, column=0, sticky='e', pady=2)
    self.tg_entry_api_hash = ttk.Entry(cred_frame, width=50)
    self.tg_entry_api_hash.insert(0, creds["telegram"].get("API_HASH", ""))
    self.tg_entry_api_hash.grid(row=1, column=1, padx=5, pady=2, sticky='w')

    ttk.Label(cred_frame, text="Phone:").grid(row=2, column=0, sticky='e', pady=2)
    self.tg_entry_phone = ttk.Entry(cred_frame, width=30)
    self.tg_entry_phone.insert(0, creds["telegram"].get("PHONE_NUMBER", ""))
    self.tg_entry_phone.grid(row=2, column=1, padx=5, pady=2, sticky='w')

    ttk.Button(cred_frame, text=i18n.t("save"), command=self.save_telegram_creds).grid(row=3, column=0, columnspan=2, pady=5)

    # ─── Sección: CANALES ──────────────────
    ch_frame = ttk.LabelFrame(scrollable, text="Canales", padding=10)
    ch_frame.pack(fill='x', padx=10, pady=5)

    ttk.Label(ch_frame, text="ID:").grid(row=0, column=0, sticky='e')
    self.tg_entry_new_channel = ttk.Entry(ch_frame, width=20)
    self.tg_entry_new_channel.grid(row=0, column=1, padx=5, pady=2, sticky='w')
    ttk.Button(ch_frame, text=i18n.t("channels_add"), command=self.add_telegram_channel).grid(row=0, column=2)

    self.tg_list_channels = tk.Listbox(ch_frame, height=6)
    self.tg_list_channels.grid(row=1, column=0, columnspan=3, sticky='ew', pady=5, padx=5)
    ttk.Button(ch_frame, text=i18n.t("channels_remove"), command=self.remove_telegram_channel).grid(row=2, column=0, columnspan=3, pady=2)

    # ─── Sección: NOTIFICACIONES ────────────
    notif_frame = ttk.LabelFrame(scrollable, text=i18n.t("tg_recent_notifications"), padding=10)
    notif_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.tg_notif_list = tk.Listbox(notif_frame, height=8)
    self.tg_notif_list.pack(fill='both', expand=True, padx=5, pady=5)

    ttk.Button(notif_frame, text=i18n.t("dash_refresh"), command=self.refresh_telegram_notifications).pack(pady=2)
```

- [ ] **Step 4: Agregar métodos helper** para credenciales, canales y notificaciones

```python
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

def refresh_telegram_channels(self):
    self.tg_list_channels.delete(0, tk.END)
    for cid in load_channels():
        self.tg_list_channels.insert(tk.END, str(cid))

def refresh_telegram_notifications(self):
    """Actualiza la lista de últimas notificaciones desde el notifier."""
    self.tg_notif_list.delete(0, tk.END)
    # Acceder al notifier desde el engine (si está disponible)
    notifier = trading_engine.notifier
    if notifier and notifier.enabled:
        recent = notifier.get_recent()
        for entry in recent:
            self.tg_notif_list.insert(tk.END, entry)
    else:
        self.tg_notif_list.insert(tk.END, i18n.t("tg_no_notifications"))

def send_test_notification(self):
    """Envía una notificación de prueba."""
    notifier = trading_engine.notifier
    if notifier and notifier.enabled:
        threading.Thread(
            target=lambda: asyncio.run(notifier.send_message("🧪 Test desde MiBotTrading UI")),
            daemon=True
        ).start()
        messagebox.showinfo("Test", "Notificación de prueba enviada.")
    else:
        messagebox.showwarning("Test", "El notificador no está activo.")
```

- [ ] **Step 5: Llamar `refresh_telegram_notifications` al inicializar**

En `__init__`, después de `setup_telegram_tab()`, agregar:
```python
self.root.after(1000, self.refresh_telegram_notifications)
```

- [ ] **Step 6: Actualizar `_on_language_change`**

Agregar en `_on_language_change()`:
```python
self.notebook.tab(self.tab_telegram, text=i18n.t("tab_telegram"))
```

---

### Task 4: Exponer estado de Telegram desde main.py

**Files:**
- Modify: `main.py` — pasar referencias a la GUI

- [ ] **Step 1: Agregar referencias de estado en `_telegram_reconnection_loop`**

Después de inicializar el notifier y conectar Telegram, pasar referencias a la GUI:

```python
# En _telegram_reconnection_loop, después de conectar Telegram:
if self.telegram_client:
    me = await self.telegram_client.get_me()
    user_str = f"{getattr(me, 'first_name', '?')} (@{getattr(me, 'username', '?')})"
    phone_str = getattr(me, 'phone', '?')
    # Actualizar UI desde otro hilo
    self.root.after(0, lambda u=user_str, p=phone_str: self.gui.update_telegram_status(
        connected=True, user=u, phone=p
    ))

# Al desconectar:
self.root.after(0, lambda: self.gui.update_telegram_status(
    connected=False, user="", phone=""
))
```

- [ ] **Step 2: Agregar método `update_telegram_status` en main_window.py**

```python
def update_telegram_status(self, connected: bool, user: str = "", phone: str = ""):
    if connected:
        self.tg_status_label.config(text=f"🟢 {i18n.t('tg_connected_as')}: {user}")
        self.tg_user_label.config(text=f"📱 {phone}")
    else:
        self.tg_status_label.config(text="🔴 Desconectado", foreground="#ff4444")
        self.tg_user_label.config(text="")
```

- [ ] **Step 3: Pasar el notifier a la UI para notificaciones**

En `_telegram_reconnection_loop`, después de crear el notifier, actualizar la GUI:
```python
if notifier:
    self.root.after(0, lambda n=notifier: setattr(self.gui, '_notifier_ref', n))
```

---

### Task 5: Verificar y compilar

- [ ] **Step 1: Verificar imports**

Run: `python -c "from ui.main_window import TradingBotGUI; print('OK')"`
Expected: `OK`

- [ ] **Step 2: Ejecutar tests**

Run: `python -m pytest tests/ -v`
Expected: 72+ tests passing

- [ ] **Step 3: Compilar .exe local**

Run: `python -m PyInstaller MiBotTrading.spec`
Expected: Build complete
