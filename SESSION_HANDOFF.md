# 🪪 Session Handoff — MiBotTrading

> **Creado:** 13/06/2026
> **Última actualización:** 14/06/2026 (v7 - Tooltips ❔ + Notificaciones seleccionables)
> **Propósito:** Documento de continuidad para que cualquier IA o agente retome el proyecto exactamente donde lo dejamos. **LEER ESTE ARCHIVO ES OBLIGATORIO AL INICIAR UNA NUEVA SESIÓN.**

---

## 🚨 REGLA #1: Usar Superpowers SIEMPRE

> **Cada vez que se inicie una nueva sesión o se cambie de agente de IA, se DEBE cargar el skill `using-superpowers` y seguir el flujo completo.**

### Flujo obligatorio:

1️⃣ **Cargar `using-superpowers`** — El PRIMER paso de cualquier sesión. Este skill activa la metodología completa.
2️⃣ **Leer `MEMORY.md` y `SESSION_HANDOFF.md`** — Contexto completo del proyecto y última sesión.
3️⃣ **Seguir el flujo Superpowers:**
    - `brainstorming` → antes de cualquier cambio creativo
    - `writing-plans` → para tareas de 3+ pasos
    - `subagent-driven-development` → ejecución con agentes especializados
    - `requesting-code-review` → revisión antes de finalizar
    - `verification-before-completion` → verificar tests antes de afirmar completitud
4️⃣ **Actualizar `MEMORY.md`** al finalizar cada sesión significativa.
5️⃣ **Actualizar `SESSION_HANDOFF.md`** con los commits y cambios de la sesión.

> ⚠️ **No seguir este flujo resultará en decisiones inconsistentes y pérdida de contexto entre sesiones.**

---

## 📋 Resumen Rápido

**Proyecto:** Bot de trading automatizado que recibe señales vía Telegram y ejecuta órdenes LONG/SHORT en exchanges de criptomonedas (Bitget, BingX).

**Stack:** Python 3.14, Tkinter (GUI), CCXT async (exchanges), Telethon (Telegram), asyncio, pytest, PyInstaller

**Última release:** `v1.1.0` — Chat ID UI, entity resolution, tests market_data
**Tests:** 348/348 pasando ✅ (87% cobertura)
**Coverage:** 75% → 87% (+86 tests)
**Últimas features:** ❔ Tooltips de ayuda + 🔔 Notificaciones seleccionables
**GitHub:** https://github.com/juancito8812/botdetrading.git
**Actions:** https://github.com/juancito8812/botdetrading/actions

**Commits recientes (origin/master):**
| Commit | Descripción |
|--------|-------------|
| `364e9de` | feat: tooltips ayuda (?) + notificaciones seleccionables |
| `b46ea2b` | test: mejorar cobertura de 75% a 87% (86 tests nuevos, 348 total) |
| `96aacfe` | ci: agregar cobertura con pytest-cov + Codecov badge en README |
| `39f8b1a` | test: 54 tests nuevos (data_classes, translations, helpers, config, logger) |
| `09ea0f1` | feat: 115 tests nuevos (engine, exchange, settings) + fixes estabilidad + docs v5 |

---

## 🎯 Últimas Sesiones (14/06/2026)

### 1. Health Dashboard Mejorado (commit `7893148`)

**Qué se hizo:** Cards de salud de exchanges mejoradas con LED indicator (🟢🟡🔴), circuit breaker state (🔒🔓⚠️), última vez OK con timestamp, y helper `_format_timestamp()`.

**Archivos:** `ui/main_window.py`, `utils/translations.py`

### 2. Break-even vs Trailing: Exclusión Mutua (commit `7893148`)

**Qué se hizo:** Lógica para que break-even y trailing stop sean mutuamente excluyentes. Gana el que se activa primero.
- `_check_trailing_stop()`: retorna si `pos.is_breakeven`
- Watchdog: no activa break-even si `pos.trailing_activated`

**Archivos:** `core/engine.py`

### 3. Pestaña Telegram Unificada (commit `62ab7aa`)

**Qué se hizo:** Nueva pestaña **📱 Telegram** que unifica conexión, credenciales, canales e historial de notificaciones. Se eliminaron los controles de Telegram de la pestaña APIs y se fusionó la gestión de canales.

**Archivos:** `ui/main_window.py`, `utils/translations.py`, `services/notifier.py`, `main.py`

**Spec:** `docs/superpowers/specs/2026-06-14-telegram-tab-design.md`
**Plan:** `docs/superpowers/plans/2026-06-14-telegram-tab.md`

### 4. Eliminación de pestañas Canales y Saldos (commit `62ab7aa` - parte del mismo)

**Qué se hizo:** Se eliminaron las pestañas **📢 Canales** (redundante con Telegram) y **💰 Saldos**. Se actualizó `last_tab_index` y se limpiaron traducciones.

**Archivos:** `ui/main_window.py`, `utils/translations.py`

### 5. Conversión de Superpowers a carpeta normal (commit `b9e3f8e`)

**Qué se hizo:** El directorio `superpowers/` era un submódulo de git que causaba error en CI/CD. Se convirtió a carpeta normal trackeada en el repo (148 archivos).

### 6. Pestaña Reportes (commit `0878633`)

**Qué se hizo:** Nueva pestaña **📊 Reportes** con 3 secciones:
- **Resumen General**: Total trades, win rate, PnL total, mejor/peor trade, abiertas/cerradas
- **Performance por Exchange**: Trades, win %, PnL y balance por cada exchange
- **Últimos Trades**: Lista filtrable (Todas/Abiertas/Cerradas) con colores (verde=profit, rojo=loss)

**Archivos:** `ui/main_window.py`, `utils/translations.py`
**Spec:** `docs/superpowers/specs/2026-06-14-reports-tab-design.md`
**Plan:** `docs/superpowers/plans/2026-06-14-reports-tab.md`

### 7. Pestaña Posiciones mejorada (commits `1788f73`, `968bddd`)

**Qué se hizo:** Pestaña **📊 Posiciones** mejorada:
- Solo muestra posiciones **activas** con columnas completas (leverage, SL, TPs)
- **Doble clic**: en PnL → cerrar posición (orden MARKET opuesta real), en SL/TP → modificar
- **Popup modificar SL/TP**: ejecuta órdenes reales en el exchange (cancel SL anterior + crear nuevo)
- **Export CSV** en pestaña Reportes: `trades_YYYY-MM-DD_HH-MM-SS.csv`

**Archivos:** `ui/main_window.py`, `utils/translations.py`

### 8. Export/Import cifrado de configuración (commit `a9d7a05`)

**Qué se hizo:** Nueva funcionalidad en **⚙️ Ajustes**:
- `utils/config_backup.py` — cifrado AES vía `cryptography.fernet` + PBKDF2
- **Exportar**: recopila APIs, riesgo, canales y settings → cifra con contraseña → guarda como `.botconfig`
- **Importar**: selecciona `.botconfig` → pide contraseña → descifra → restaura todos los archivos
- **Indicador visual** de fecha del último backup en la UI
- **10 tests** unitarios para round-trip, contraseña incorrecta, archivo corrupto

**Archivos:** `utils/config_backup.py`, `tests/test_config_backup.py`, `ui/main_window.py`, `utils/translations.py`
**Spec:** `docs/superpowers/specs/2026-06-14-config-backup-design.md`

### 9. Bug Fixes críticos pre-operaciones reales (commits en master)

**Qué se hizo:** Revisión completa del código encontró 6 bugs que fueron arreglados:

| # | Bug | Fix | Archivo |
|---|-----|-----|---------|
| 🔴 | **HealthMonitor solo se ejecuta una vez** | Ahora se ejecuta cada 60s dentro del watchdog con time-check | `core/engine.py` |
| 🔴 | **PnL nunca calculado** | Se calcula desde `unrealizedPnl` del exchange o fórmula manual LONG/SHORT | `core/engine.py` |
| 🟡 | **Event loop no cerrado en error** | `loop.close()` ahora dentro de `try/finally` | `ui/main_window.py` |
| 🟡 | **Indentación extraña en export** | Código formateado correctamente | `ui/main_window.py` |
| 🟢 | **Language change sin backup** | `_on_language_change` llama `_update_backup_status()` | `ui/main_window.py` |
| 🟢 | **Re-imports redundantes** | Eliminados imports duplicados en `refresh_reports()` | `ui/main_window.py` |

**82 tests pasando** ✅

### 10. MiBotTrading.spec con hiddenimports (commit `5450cf7`)

**Qué se hizo:**
- El .exe compilado fallaba con `ModuleNotFoundError: No module named 'ui.main_window'`
- Agregados todos los módulos como `hiddenimports` en el spec (ui, core, services, utils, models, resilience)
- El archivo estaba ignorado por `*.spec` en `.gitignore` → se forzó `git add -f`

**Archivos:** `MiBotTrading.spec`

### 11. Bug fixes de producción — Commit `f7595e0` / Release `v1.0.1`

**Qué se hizo:** Sesión completa de estabilización tras probar el .exe en operaciones reales. Se encontraron y corrigieron 6 bugs:

| # | Bug | Fix | Archivo |
|---|-----|-----|---------|
| 🔴 | **Telegram entity no encontrada** — `chat_id` string no servía para Telethon | Convertir a `int` si es string numérico | `services/notifier.py` |
| 🟡 | **CoinGecko 429 constante** — Sin caché, rate limit en cada refresco | Caché con TTL 60s + manejo de 429/timeout | `services/market_data.py` |
| 🔴 | **Event loop is closed (CCXT)** — Client perdía referencia al loop | `_ensure_event_loop()` recrea client automáticamente | `services/exchange_service.py` |
| 🔴 | **Retry reintentaba RuntimeError** — Errores fatales se reintentaban | `_never_retry` con `RuntimeError` | `utils/resilience/retry_service.py` |
| 🔴 | **Event loop must not change (Telegram)** — Se recreaba cliente en cada reconexión | Refactor: cliente creado UNA vez, reconexiones con `connect()` + `start()` | `main.py` |
| 🟡 | **Notifier crash en Windows** — `disconnect()` rompía IOCP del event loop | Solo loguear warning, no tocar conexión | `services/notifier.py` |

**Tag:** `v1.0.1` — Release creada en GitHub con .exe compilado incluido.

### 12. Chat ID configurable desde la UI (14/06/2026)

**Qué se hizo:** Las notificaciones de Telegram solo podían configurarse editando `.env`. Se agregó un campo directo en la UI para que el usuario pueda cambiar el destino de las notificaciones sin editar archivos.

**Cambios:**
| Archivo | Cambio |
|---------|--------|
| `ui/main_window.py` | Nuevo campo Entry + botón "Guardar Chat ID" en pestaña 📱 Telegram. Método `_save_notification_chat_id()` que guarda en `settings.json` |
| `main.py` | `_init_notifier()` ahora lee `notification_chat_id` desde `settings.json` primero (prioridad máxima), luego `.env`, luego `get_me()` como fallback |
| `utils/translations.py` | Nuevas claves: `tg_notif_chat_id_label`, `tg_notif_chat_id_current`, `tg_notif_chat_id_save`, `tg_notif_chat_id_saved` en es/en |

**Orden de prioridad del `notification_chat_id`:**
1. ✅ `settings.json` (configurado desde la UI) — máxima prioridad
2. 🔄 `.env` (`NOTIFICATION_CHAT_ID`) — fallback
3. 🔄 ID del usuario autenticado (`get_me()`) — fallback final (Mensajes Guardados)

### 13. Fixes masivos de estabilidad + 115 tests nuevos (14/06/2026)

**Qué se hizo:** Auditoría profunda de todo el código encontró 8 bugs críticos/importantes que fueron corregidos, más 115 tests nuevos para 4 módulos que no tenían cobertura.

#### 🔴 Fixes críticos

| # | Bug | Fix | Archivo |
|---|-----|-----|---------|
| **C1** | **Watchdogs duplicados** en cada reconexión — tras 3 reconexiones, 3 watchdogs en paralelo | `stop_watchdog()` cancela la tarea anterior antes de crear una nueva | `main.py`, `core/engine.py` |
| **C2** | **`asyncio.TimeoutError` no se reintentaba** en Python 3.10 | Agregado explícitamente a `retry_on` tuple | `utils/resilience/retry_service.py` |
| **C3** | **Órdenes LIMIT pendientes se perdían** al reiniciar el bot | Persistencia en `pending_limits.json` con `_load_pending_limits()` / `_save_pending_limits()` | `core/engine.py` |
| **C4** | **stop_bot() no cancelaba el watchdog** — seguía procesando posiciones con bot detenido | Llama `trading_engine.stop_watchdog()` al detener | `main.py` |

#### 🟡 Fixes importantes

| # | Bug | Fix | Archivo |
|---|-----|-----|---------|
| **I1** | **circuit_breaker_state** nunca se sincronizaba en health monitor | Nuevo `sync_circuit_breaker_states()` + llamado desde watchdog | `health_monitor.py`, `engine.py` |
| **I2** | **Sin rate limiting** en notificaciones — posibles bans de Telegram | Mínimo 2s entre mensajes via `asyncio.sleep()` | `services/notifier.py` |
| **I3** | **Entity cache no se invalidaba** si cambiaba chat_id | `_cached_chat_id` trackea el chat_id usado | `services/notifier.py` |
| **I4** | **Health check** usaba símbolos hardcodeados | Primero prueba mercados reales del exchange, luego fallback | `core/engine.py` |

#### 🆕 Tests nuevos (115)

| Archivo | Tests | Cobertura |
|---------|-------|-----------|
| `tests/test_engine.py` | 31 | TradingEngine: watchdogs, DCA, trailing, SL, health, persistencia LIMIT |
| `tests/test_exchange_service.py` | 44 | ExchangeService: CCXT clients, balance, leverage, market symbols, posiciones |
| `tests/test_settings_manager.py` | 21 | Settings: load/save, autostart Windows, edge cases |
| `tests/test_market_data.py` | 19 | CoinGecko: caché, 429, timeout, errores, valores nulos |

#### 🐛 Fixes adicionales
- `import asyncio` faltante en `notifier.py` (causaba crash en rate limiting)
- `import os` muerto eliminado de `engine.py`
- Event loop leaks en `refresh_dashboard()` corregidos

**Total tests:** 197/197 pasando ✅

**.exe compilado:** `dist/MiBotTrading.exe` — con todos los fixes + tooltips ❔ + notificaciones seleccionables + 348 tests + 87% cobertura

### 14. Tooltips de ayuda (❔) + Notificaciones seleccionables (14/06/2026)

**Qué se hizo:** Dos features de UX:

#### ❔ Tooltips de ayuda en configuración
- Cada campo de configuración en **⚖️ Riesgo** (15 campos), **⚙️ Ajustes** (2 campos) y **🔐 APIs** (4 por exchange) tiene un botón ❔
- Al hacer clic, se abre un popup (Toplevel) con la descripción detallada de ese parámetro
- Helper `_show_help_popup()` reutilizable con título + descripción centrada en la ventana principal
- 18 nuevas claves `help_*` en `translations.py` (ES/EN) con descripciones técnicas completas

#### 🔔 Notificaciones seleccionables
- Nueva sección con **8 checkboxes** en la pestaña 📱 Telegram
  - ✅ Posición Abierta, ✅ Posición Cerrada, ✅ TP Alcanzado, ✅ Trailing Activado
  - ✅ Error del Sistema, ✅ Health Change, ✅ Circuit Breaker, ✅ Reporte Diario
- Cada método `notify_*` en `TelegramNotifier` verifica si el tipo está habilitado antes de enviar
- Preferencias persistentes en `settings.json` como `notification_prefs`
- Se aplican en tiempo real al guardar (sin reiniciar el bot)
- 9 nuevas claves `notif_*` en `translations.py` (ES/EN)

**Archivos modificados (5):**
| Archivo | Cambio |
|---------|--------|
| `utils/translations.py` | +27 claves ES/EN (18 help + 9 notif) |
| `services/notifier.py` | `DEFAULT_NOTIFICATION_PREFS`, checks en 8 métodos `is_notification_enabled()` |
| `ui/main_window.py` | `_show_help_popup()`, `_make_help_btn()`, ❔ en 3 tabs, checkboxes notif, `_save_notification_prefs()` |
| `main.py` | `notification_prefs` pasado al `TelegramNotifier` desde settings |
| `docs/superpowers/specs/` | `2026-06-14-help-tooltips-and-notification-prefs-design.md` |

**Spec:** `docs/superpowers/specs/2026-06-14-help-tooltips-and-notification-prefs-design.md`
**Tests:** 348/348 pasando ✅ (sin cambios en count)
**Commit:** `364e9de`

---

## 🏗️ Arquitectura Actual

```
Telegram (señales) → handler() → parse_trading_signal() → TradingEngine.execute_signal()
                                                                 │
                                                    @log_errors → decide_entry_type()
                                                                 │
                                                    @timeout → @retry → @circuit_breaker → CCXT
                                                                 │
                                                      PositionManager.save()
                                                                 │
                                                      StateRecovery (checkpoint)
                                                      BackupManager (backup gzip)
                                                                 │
                                                      Watchdog (cada 30s)
                                                        ├── HealthMonitor (cada 60s)
                                                        ├── Trailing stop (excluyente con break-even)
                                                        ├── Break-even (excluyente con trailing)
                                                        ├── Reintentar exchanges fallidos
                                                        ├── notify_trade_closed()
                                                        ├── notify_tp_hit()
                                                        └── send_daily_report() (c/24h)

Telegram (notificaciones) → TelegramNotifier ← engine.notifier
                                                    ↑
                              health_monitor.on_status_change callback

GUI (Tkinter — 9 pestañas):
├── 📈 Dashboard      → CoinGecko top20 + health cards
├── 📱 Telegram       → Estado, credenciales, canales, notificaciones
├── 📊 Reportes       → Resumen, performance, historial + export CSV
├── 🔐 APIs           → API keys de exchanges
├── ⚖️ Riesgo         → Configuración de trading
├── 🔌 Test           → Probar conexión con exchanges
├── 📊 Posiciones     → Posiciones activas con PnL, SL/TP, cerrar
├── 📟 Consola        → Logs en tiempo real
└── ⚙️ Ajustes        → Idioma + auto-inicio Windows + backup/restore
```

### Exchanges
- **Activos:** Bitget, BingX
- **Configurados (inactivos):** Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin

---

## 🤖 GitHub Actions — Workflows

Se activan automáticamente en push/PR a master:

| Workflow | Trigger | Stack | Qué hace |
|----------|---------|-------|----------|
| **Tests** (`tests.yml`) | Push/PR a master/main/develop | Ubuntu, Python 3.10/3.11/3.12 | `pip install -r requirements.txt + pytest pytest-asyncio` → `pytest tests/ -v` |
| **Lint** (`lint.yml`) | Push/PR a master/main/develop | Ubuntu, Python 3.11 | flake8 + mypy (continue-on-error) |
| **Build** (`build.yml`) | Tags `v*` o `workflow_dispatch` | Windows-latest | PyInstaller → `.exe` → Release |

**Nota:** Para correr el build manual: ir a Actions → Build Executable → Run workflow.
**Nota:** Para evitar errores del submódulo `superpowers/`, el checkout está configurado con `submodules: false`.

---

## 🧪 Cómo verificar el estado

```bash
# Tests completos (348 tests · 87% cobertura)
python -m pytest tests/ -v

# Cobertura local
python -m pytest tests/ --cov=core --cov=models --cov=services --cov=utils --cov-report=term

# Tests de un módulo específico
python -m pytest tests/test_notifier.py -v
python -m pytest tests/test_engine.py -v

# Estado de git
git status
git log --oneline -5

# Ver workflows en GitHub
# https://github.com/juancito8812/botdetrading/actions
```

---

## 📋 Próximos Pasos / TODOs

Priorizados por impacto:

1. **Activar más exchanges** — Binance, Bybit, OKX (ya configurados, solo falta habilitar en `.env` y probar)
2. ✅ ~~Sistema de notificaciones Telegram~~ (completado)
3. ✅ ~~Dashboard UI con health cards~~ (completado)
4. ✅ ~~Break-even vs trailing exclusión mutua~~ (completado)
5. ✅ ~~Pestaña Telegram unificada~~ (completado)
6. ✅ ~~Pestaña Reportes / Estadísticas~~ (completado)
7. ✅ ~~Pestaña Posiciones mejorada (solo activas, SL/TP real, export CSV)~~ (completado)
8. ✅ ~~Backup/restore cifrado de configuración~~ (completado)
9. ✅ ~~Bug fixes críticos (HealthMonitor periódico, PnL real, event loop)~~ (completado)
10. ✅ ~~MiBotTrading.spec con hiddenimports~~ (completado)
11. ✅ ~~Bug fixes de producción (notifier, CoinGecko, event loop CCXT, reconexión Telegram)~~ (completado)
12. ✅ ~~Tests para market_data.py (19 tests)~~ (completado)
13. ✅ ~~Tests para engine.py (31 tests)~~ (completado)
14. ✅ ~~Tests para exchange_service.py (44 tests)~~ (completado)
15. ✅ ~~Tests para settings_manager.py (21 tests)~~ (completado)
16. ✅ ~~Fixes estabilidad: watchdogs duplicados, persistencia LIMIT, rate limiting, entity cache, health sync~~ (completado)
17. ✅ ~~Cobertura 75% → 87% (86 tests nuevos en 8 archivos)~~ (completado)
18. **Gráficos en pestaña Reportes** — Agregar matplotlib para visualizar PnL histórico
19. **Tests de integración** con exchanges simulados (mock CCXT)
20. **Cubrir watchdog loop de engine.py** — subir de 69% a 85%

---

## ⚙️ Configuración Actual

| Parámetro | Valor |
|-----------|-------|
| Apalancamiento | 5x |
| Modo margen | Cross |
| Cantidad mínima | 2.0 USDT |
| Entrada | Auto (desviación máx 3%) |
| DCA | 3 partes |
| Trailing stop | Activación 1.5%, distancia 0.8% |
| Timeout orden LIMIT | 10 min |
| Notificaciones | Activadas si hay `NOTIFICATION_CHAT_ID` en `.env` (fallback: ID del usuario) |
| Check interval health | 60s |
| Retry intentos | 3 (backoff exp. 1s→2s→4s) |
| Circuit breaker | 5 fallos → OPEN 60s → HALF_OPEN |
| Backup rotación | 24 backups comprimidos (gzip) |

---

## 🦸 Superpowers Framework

Framework de metodología de desarrollo instalado (14 skills). Los skills están en `.agents/skills/` y se activan automáticamente.

**Flujo de trabajo:** brainstorming → writing-plans → subagent-driven-development (con revisión spec + code quality)

**Documentos de diseño y plan en:** `docs/superpowers/specs/` y `docs/superpowers/plans/`

---

## ⚠️ Notas Importantes

- **Credenciales excluidas de git:** `.env`, `config.json`, `canales.json` — están en `.gitignore`
- **Archivos legacy eliminados del repo:** `bot_unificado v2.py`, `README_BACKUP.md`, `build_distribucion.bat` (commit `eb595e5`)
- **Archivos legacy ignorados (`.gitignore`):** `_fix_probar*.py`, `_new_method.py`, `_fx.py`, `backup_modulos/`, `legacy_code/`
- **Los tests async requieren `pytest-asyncio`** (ya está en `requirements.txt`)
- **Para activar notificaciones:** Crear variable `NOTIFICATION_CHAT_ID` en `.env`. Si no existe, se usa el ID del usuario autenticado de Telegram por defecto.
- **Para empezar una nueva sesión:** Leer este archivo + `.agents/MEMORY.md` + `git log --oneline -3`
