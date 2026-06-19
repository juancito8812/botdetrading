# 🔄 SESSION_HANDOFF.md — MiBotTrading

> ╔══════════════════════════════════════════════════════════════════╗
> ║  🟢 CHECKPOINT v2.0.2 — 18/06/2026                            ║
> ║  Estado: 🧪 PRUEBA DE 1 SEMANA INICIADA                       ║
> ║  Tests: 324/324 pasando                                       ║
> ║  .exe: v2.0.2 compilado + Release en GitHub                   ║
> ║  Exchanges activos: BingX + Bitget (ambos operativos)         ║
> ╚══════════════════════════════════════════════════════════════════╝

*Último commit: feat: seguridad + bug fixes + updater real + docs*
*Fecha del handoff: 18/06/2026*

---

## 🧠 Resumen de la Sesión (v2.0.2)

Sesión **final pre-prueba**: Bug fixes + Seguridad + Updater + Compilación + Verificación.

### 🔐 Seguridad (3 cambios)

| Archivo | Cambio |
|---------|--------|
| `utils/crypto.py` 🆕 | Módulo AES-256-GCM con PBKDF2 (600k iteraciones) |
| `utils/config_backup.py` | **Ahora cifra de verdad** con la password del usuario (antes ignoraba el parámetro). Detecta automáticamente backups v1 legacy vs v2. |
| `ui/main_window.py` | ❌ **Eliminado Fernet hardcodeado** con clave pública que rompía las conexiones (encriptaba keys al .env pero el backend no las descifraba) |

### 🐛 Bug fixes (7 bugs corregidos)

| # | Severidad | Bug | Archivo | Fix |
|---|-----------|-----|---------|-----|
| 1 | 🔴 | **SL notification falsa** — `_sync_positions()` notificaba SL aunque la posición se cerrara por TP | `core/engine.py` | Solo notifica SL si `pos.sl_order_id AND NOT pos.tp1_hit` |
| 2 | 🔴 | **Canales nuevos ignorados** — handler se registraba con copia estática de canales; nuevos canales no se escuchaban hasta reconectar | `main.py` | `events.NewMessage()` sin filtro + verificación `chat_id in canales_actuales` en vivo |
| 3 | 🔴 | **Posiciones duplicadas** — si fetch_order devolvía 'closed' en dos ciclos consecutivos, se creaban dos posiciones para la misma orden | `core/engine.py` | `pop()` del dict ANTES de procesar orden llenada, no después |
| 4 | 🟡 | **PnL% inflado** — tras TP parcial, el PnL% se calculaba sobre el monto remanente en vez del original | `services/notifier.py` | Usa `max(amount, entry_filled_amount)` en el cálculo |
| 5 | 🟡 | **Breakeven 30s tarde** — `_check_tp1_hit()` se ejecutaba DESPUÉS del bloque de breakeven, posponiendo el SL a break-even al siguiente ciclo | `core/engine.py` | Movido `_check_tp1_hit()` ANTES del bloque de breakeven y trailing después |
| 6 | 🟡 | **BingX leverage ignorado** — `set_leverage()` usaba `params['side']` en vez de `params['positionSide']` para BingX | `services/exchange_service.py` | Cambiado a `positionSide` (consistente con el resto del código) |
| 7 | 🟢 | **TP1 detectado por cualquier TP** — `_check_tp1_hit()` iteraba sobre TODOS los TPs, no solo el primero | `core/engine.py` | Solo revisa `tp_order_ids[0]` |

### 🚀 Updater real (services/updater.py)

| Función | Antes (stub) | Ahora |
|---------|-------------|-------|
| `check_latest_version()` | `return {tag_name: current, ...}` | Consulta **GitHub API** (`/releases/latest`) con urllib. Timeout 15s. |
| `download_update(url)` | `return None` | Descarga .exe en chunks 8KB con progreso. Timeout 120s. |
| `apply_update(path)` | `return False` | Crea script `_update.bat` que espera, reemplaza .exe y reinicia. Solo en modo frozen. |

### 🔧 Auto-arranque encender PC (sesión anterior, consolidado)

- `settings_manager.py`: Tarea con `/sc onstart` + `/ru SYSTEM` — arranca sin sesión de Windows
- `helpers.py`: `DATA_DIR` apunta a `BASE_DIR` cuando corre como SYSTEM
- `main.py`: Modo headless (sin ventana) cuando no hay escritorio
- `logger.py`: Log adicional junto al .exe para monitoreo de pruebas
- `main.py`: Heartbeat cada 2h (antes 4h)
- `main.py`: Sync inmediato de posiciones al reconectar Telegram

### ✅ Verificación pre-prueba

- **Parser:** Simuladas 4 señales (LONG/SHORT/BUY, multi-línea, 1 línea, rango, sin rango) — todas reconocidas correctamente
- **Bitget:** Reactivado con API keys nuevas
- **.exe v2.0.2:** Compilado, Release en GitHub actualizado
- **dist/:** Comprimido y copiado a la otra PC

### 🧪 Prueba de 1 Semana

- **Iniciada:** 18/06/2026
- **Ubicación:** Otra PC (sin sesión de Windows, headless)
- **Exchanges activos:** BingX + Bitget
- **Monitoreo:** Heartbeats cada 2h a Telegram
- **Logs:** log_bot.txt junto al .exe
- **Auto-arranque:** Al encender el PC arranca solo

---

## 🏗️ Arquitectura Actual

```
MiBotTrading/
├── main.py                     # Punto de entrada — TradingBotApp + headless
├── core/                       # ★ LÓGICA PRINCIPAL
│   ├── engine.py               # TradingEngine — orquestación de señales + watchdog
│   ├── manager.py              # PositionManager — gestión de posiciones
│   └── parser.py               # parse_trading_signal — parseo de señales Telegram
├── services/                   # ★ SERVICIOS EXTERNOS
│   ├── exchange_service.py     # ExchangeService — conexión con exchanges vía CCXT async
│   ├── market_data.py          # Datos de CoinGecko (top 20 + índices)
│   ├── notifier.py             # TelegramNotifier — 12 métodos + helper _notify()
│   └── updater.py              # Auto-Updater real: GitHub API, download, apply .bat
├── ui/                         # ★ INTERFAZ DE USUARIO
│   └── main_window.py          # TradingBotGUI — Tkinter (9 pestañas) sin Fernet
├── models/                     # ★ MODELOS DE DATOS
│   └── data_classes.py         # Position, Signal (dataclasses)
├── utils/                      # ★ UTILIDADES
│   ├── config.py               # Carga/guardado de config, credenciales, canales
│   ├── helpers.py              # atomic_write_json, patch_aiohttp_dns, DATA_DIR para SYSTEM
│   ├── logger.py               # Logging + log junto al .exe
│   ├── settings_manager.py     # Settings + auto-inicio Windows (onstart SYSTEM)
│   ├── crypto.py               # AES-256-GCM + PBKDF2 (encrypt/decrypt)
│   ├── config_backup.py        # Export/Import cifrado real con contraseña
│   ├── translations.py         # i18n — español/inglés (120+ claves)
│   └── resilience/             # Circuit breaker, retry, health monitor, decorators
├── tests/                      # ★ TESTS (324 tests)
│   ├── test_engine.py          # TradingEngine — SL, TP, DCA, trailing, breakeven
│   ├── test_notifier.py        # TelegramNotifier
│   ├── test_exchange_service.py# ExchangeService
│   ├── test_market_data.py     # CoinGecko
│   └── ... (18 archivos de test)
├── scripts/
│   └── test_bingx_connection.py# Diagnóstico de conexión BingX
├── dist/                       # .exe compilado + .env para ejecutable
├── logs/                       # Logs de ejecución
├── telegram_session/           # Sesión de Telegram guardada
├── .agents/skills/             # 14 skills Superpowers + Ponytail
├── .github/workflows/          # tests.yml, lint.yml, build.yml
├── hooks/                      # ponytail plugins
└── docs/superpowers/           # specs/ y plans/ de diseño
```

---

## ⚙️ Configuración Activa

| Parámetro | Valor |
|-----------|-------|
| Exchanges activos | BingX + Bitget (ambos operativos) |
| Apalancamiento | 5x, Cross |
| Mínimo | 2.0 USDT |
| Entrada | Auto (desviación máx 3%) |
| DCA | 3 partes, habilitado |
| Trailing stop | Activación 1.5%, distancia 0.8% |
| TP distribución | Progresivo (50,25,15,10) |
| Break-even | Automático al alcanzar TP1 |
| Cooldown | 60s entre señales duplicadas |
| Heartbeat | 2h (primer a los 5 min) |
| Auto-start Windows | Onstart (sin sesión) ✅ |
| Telegram canales | 3 canales activos |

---

## 🧪 Tests

```bash
python -m pytest tests/ -v        # 324 tests, todos pasando
```

---

## 🐛 Deuda Técnica / Bugs Conocidos

1. **Archivos legacy en raíz** — `_fix_probar.py`, `legacy_code/`, etc. excluidos vía `.gitignore` pero existen en disco
2. **CoinGecko API gratuita** — Límite 10-30 llamadas/minuto
3. **Faltan tests** para `utils/crypto.py` y `services/updater.py`

---

## 📋 Próximos Pasos Sugeridos

- [ ] **Tras la prueba de 1 semana:** revisar logs, resultados, ajustar config
- [ ] Tests para `utils/crypto.py` y `services/updater.py`
- [ ] Activar más exchanges (Binance, Bybit, OKX)
- [ ] Gráficos en pestaña Reportes (matplotlib)

---

## 🦸 Metodología Superpowers — Recordatorio

**⚠️ REGLA ABSOLUTA:** Toda IA que toque este proyecto DEBE seguir el flujo:

```
0. 🦊 PONYTAIL — Siempre activo (default: full)
1. 🦸 Cargar Superpowers
2. 📖 Leer contexto → MEMORY.md + SESSION_HANDOFF.md + git log --oneline -5
3. 🧠 Brainstorming (antes de cualquier cambio creativo)
4. 📄 Writing Specs → docs/superpowers/specs/
5. 📋 Writing Plans → docs/superpowers/plans/ (tareas 3+ pasos)
6. ⚡ Subagent Development
7. 👀 Code Review
8. ✅ Verification (tests + cobertura)
9. 📝 Actualizar docs → MEMORY.md + SESSION_HANDOFF.md + README si aplica
```

---

## 📎 Enlaces

- **Repositorio:** https://github.com/juancito8812/botdetrading
- **Acciones:** https://github.com/juancito8812/botdetrading/actions
- **Releases:** https://github.com/juancito8812/botdetrading/releases
- **Skills:** `.agents/skills/` (14 skills + Ponytail)

---

*Handoff generado el 18/06/2026 — v2.0.2: seguridad + bug fixes + updater real*
