# Memoria del Proyecto: MiBotTrading

## Información General

- **Propósito:** Bot de trading automatizado que recibe señales vía Telegram y ejecuta órdenes en exchanges de criptomonedas (Bitget, BingX).
- **Stack:** Python 3.10+, Tkinter (GUI), CCXT (conexión exchanges), Telethon (Telegram), asyncio
- **Última sesión:** 14/06/2026 - Chat ID configurable desde la UI para notificaciones Telegram
- **Versión de memoria:** 7

## Arquitectura

```
MiBotTrading/
├── main.py                    # Punto de entrada, TradingBotApp
├── config.json                # Configuración de riesgo
├── .env                       # Credenciales (API keys)
├── core/
│   ├── engine.py              # TradingEngine - ejecución de señales, SL/TP, DCA, trailing stop
│   ├── manager.py             # PositionManager - gestión y persistencia de posiciones
│   └── parser.py              # parse_trading_signal - parseo de mensajes Telegram
├── services/
│   ├── exchange_service.py    # ExchangeService - conexión CCXT con múltiples exchanges
│   └── market_data.py         # fetch_top20, fetch_market_indices (CoinGecko)
├── ui/
│   └── main_window.py         # TradingBotGUI - interfaz Tkinter (9 pestañas)
├── models/
│   └── data_classes.py        # Dataclasses: Position, Signal
├── utils/
│   ├── config.py              # Carga/guardado de config, credenciales, canales
│   ├── helpers.py             # Utilidades varias (atomic_write_json, patch_aiohttp_dns)
│   ├── logger.py              # Configuración de logging
│   ├── settings_manager.py    # Settings de UI + auto-inicio Windows
│   ├── translations.py        # i18n español/inglés
│   ├── config_backup.py       # Export/Import cifrado (cryptography.fernet + PBKDF2)
│   └── resilience/            # Sistema de resiliencia (v2.0)
│       ├── error_handler.py   # Taxonomía de errores personalizados
│       ├── retry_service.py   # Reintentos con backoff exponencial + jitter
│       ├── circuit_breaker.py # Estados closed/open/half-open por exchange
│       ├── decorators.py      # @retry, @circuit_breaker, @timeout, @log_errors
│       ├── health_monitor.py  # Health checks periódicos + historial
│       ├── state_recovery.py  # Snapshots + restauración de operaciones
│       └── backup_manager.py  # Backup automático rotativo con gzip
├── tests/
│   ├── test_parser.py         # Tests del parseador de señales
│   ├── test_manager.py        # Tests del gestor de posiciones
│   ├── test_error_handler.py  # Tests de taxonomía de errores
│   ├── test_retry_service.py  # Tests de backoff y reintentos
│   ├── test_circuit_breaker.py# Tests de estados del circuit breaker
│   ├── test_decorators.py     # Tests de decoradores de resiliencia
│   ├── test_health_monitor.py # Tests de health checks
│   ├── test_state_recovery.py # Tests de checkpoints y restauración
│   ├── test_backup_manager.py # Tests de backups rotativos
│   └── test_notifier.py       # Tests del sistema de notificaciones Telegram
├── dist/                      # Archivos para distribución EXE
├── logs/                      # Logs de ejecución
└── telegram_session/          # Sesión de Telegram guardada
```

### Flujo de datos:
1. Telegram envía mensaje → `handler()` en main.py
2. `parse_trading_signal()` extrae símbolo, dirección, entradas, SL, targets
3. `TradingEngine.execute_signal()` orquesta la ejecución en cada exchange
4. Decide tipo de entrada (MARKET, LIMIT, DCA) basado en config y precio
5. Coloca orden + Stop Loss + Take Profits (distribución personalizada)
6. `PositionManager` guarda/recupera posiciones en `posiciones.json`
7. Watchdog cada 30s: monitorea órdenes LIMIT pendientes, trailing stop, breakeven, sincroniza estado

### Notificaciones (Telegram):
```
Trading:
  execute_signal() → notify_trade_open(position)
  watchdog/posición cerrada → notify_trade_closed(position)
  watchdog/TP1 hit → notify_tp_hit(position, 1)
  _check_trailing_stop(LONG+SHORT) → notify_trailing_activated(position)
  _process_filled_limit_order(DCA) → notify_dca_executed(exchange, symbol, price)

Sistema:
  health_monitor.on_status_change → notify_health_change(exchange, status, failures, latency)

Reportes:
  watchdog/cada 24h → send_daily_report(positions, balances)
```

### Capa de Resiliencia (v2.0):
Cada llamada a exchange pasa por:
```
@timeout → @retry (backoff exp.) → @circuit_breaker → @log_errors → CCXT
                              │
                        HealthMonitor ← cada 60s verifica conexiones
                              │
                        StateRecovery ← antes de cada mutación crítica
                              │
                        BackupManager ← cada ~15 saves
```

### Exchanges soportados:
- Habilitados: Bitget, BingX
- Configurados pero desactivados: Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin

## Decisiones Clave

- **[11/06/2026]** — Refactorización de código legacy monolítico a arquitectura modular con separación clara (core/, services/, ui/, utils/).
- **[11/06/2026]** — Implementación de entrada con modalidad auto/market/limit + DCA (órdenes escalonadas).
- **[11/06/2026]** — Trailing stop automático con activación por % de ganancia y distancia configurable.
- **[11/06/2026]** — Distribución personalizada de Take Profits (igual, progresivo con pesos configurables).
- **[11/06/2026]** — Persistencia de posiciones en %APPDATA%/MiBotTrading/ para entorno EXE.
- **[13/06/2026]** — Sistema de resiliencia completo (Enfoque A: Decoradores) usando metodología Superpowers:
  - Reintentos con backoff exponencial + jitter (máx 3 intentos)
  - Circuit breaker por exchange (5 fallos → OPEN 60s → HALF_OPEN)
  - Timeouts configurables (15s ticker, 30s balance, 60s orders)
  - HealthMonitor integrado en watchdog (checks cada 60s)
  - StateRecovery con checkpoints antes de operaciones críticas (máx 50)
  - BackupManager con rotación automática (24 backups comprimidos)

## Estado Actual

- **Lo que se está trabajando:** Export/Import cifrado de configuración completado.
- **Exchanges activos en config.json:** bitget, bingx
- **Apalancamiento:** 5x
- **Modo margen:** Cross
- **Cantidad mínima:** 2.0 USDT
- **Entrada:** Auto (con validación de desviación máx 3%)
- **DCA:** Habilitado (3 partes)
- **Trailing stop:** Habilitado (activación 1.5%, distancia 0.8%)
- **Resiliencia:** Completada
- **Notificaciones:** Completadas
- **Backup cifrado:** Completado (82 tests, todos pasando)

## Cambios Recientes

- **[11/06/2026]** — Inicialización estructura modular completa y funcional.
- **[11/06/2026]** — Subido a GitHub: https://github.com/juancito8812/botdetrading.git
- **[13/06/2026]** — Implementación del sistema de resiliencia completo vía Superpowers:
  - Brainstorming: diseño y aprobación del sistema
  - writing-plans: plan detallado con 11 tareas TDD
  - subagent-driven-development: ejecución con revisión en 2 etapas
  - Módulos: error_handler, retry_service, circuit_breaker, decorators, health_monitor, state_recovery, backup_manager
  - Integración: decoradores en ExchangeService, HealthMonitor en Watchdog, StateRecovery+Backup en PositionManager
  - 49 tests nuevos (63 total), todos pasando
  - Commit: `9e23c53`
- **[13/06/2026]** — Implementación del sistema de notificaciones Telegram vía Superpowers:
  - Brainstorming: diseño y aprobación del sistema (Enfoque A: TelegramNotifier simple)
  - writing-plans: plan detallado con 5 tareas
  - subagent-driven-development: ejecución con revisión
  - Nuevo: services/notifier.py (10 métodos de notificación: trading, sistema, reportes)
  - Integración: engine.py (trade open/close, TP1, trailing stop, DCA fill), main.py (inicialización), health_monitor.py (callback on_status_change)
  - 9 tests nuevos (72 total), todos pasando
  - Commits: `e063655`
- **[14/06/2026]** — Pestaña Reportes con resumen, performance por exchange e historial de trades:
  - 3 secciones: Resumen General, Performance por Exchange, Últimos Trades con filtro
  - Commits: varias sesiones
- **[14/06/2026]** — Pestaña Posiciones mejorada (solo activas, columnas completas, colores PnL):
  - Doble clic → cerrar posición / modificar SL/TP
  - Conexión real con exchange para SL/TP y cierre
  - Export CSV en pestaña Reportes
- **[14/06/2026]** — Export/Import cifrado de configuración:
  - Nuevo: utils/config_backup.py (cryptography.fernet + PBKDF2)
  - Tests: 10 tests nuevos para round-trip, contraseña incorrecta, archivo corrupto
  - UI: Sección en Ajustes + indicador de último backup
  - Dependencia: cryptography (ya instalada)
  - Commit: `a9d7a05`
- **[14/06/2026]** — Bug fixes críticos pre-operaciones reales:
  - 🔴 HealthMonitor ahora se ejecuta cada 60s dentro del watchdog (antes solo una vez al inicio)
  - 🔴 PnL calculado desde `unrealizedPnl` del exchange o fórmula manual LONG/SHORT
  - 🟡 Event loop cerrado correctamente con `try/finally` en `_fetch_balances()`
  - 🟢 `_on_language_change` ahora actualiza el label de último backup
  - 🟢 Re-imports redundantes eliminados de `refresh_reports()`
  - Commits: incluidos en bug fixes
- **[14/06/2026]** — Compilación .exe con hiddenimports:
  - Agregado `MiBotTrading.spec` al repositorio (estaba ignorado por `*.spec` en `.gitignore`)
  - hiddenimports para todos los módulos del proyecto (ui, core, services, utils, models)
  - Commit: `5450cf7`
- **[14/06/2026]** — Bug fixes de producción:
  - 🔴 **notifier.py**: `chat_id` convertido a `int` para Telethon (antes string, no encontraba entidad)
  - 🟡 **market_data.py**: Caché de 60s para CoinGecko + manejo de 429 y timeouts
  - 🔴 **exchange_service.py**: `_ensure_event_loop()` detecta loop cerrado y recrea client automáticamente
  - 🔴 **retry_service.py**: `_never_retry` con `RuntimeError` — errores fatales no se reintentan
  - 🔴 **main.py**: Refactor completo de reconexión Telegram — cliente se crea UNA vez, reconexiones reusan el mismo
  - 🟡 **notifier.py**: Eliminado `disconnect()` del notifier (causaba crash del event loop en Windows)
- **[14/06/2026]** — Chat ID configurable desde la UI:
  - 🟢 **ui/main_window.py**: Nuevo campo Entry + botón Guardar en pestaña 📱 Telegram para `notification_chat_id`
  - 🟢 **main.py**: `_init_notifier()` ahora lee `notification_chat_id` desde `settings.json` primero (prioridad máxima), luego `.env`, luego `get_me()` como fallback
  - 🟢 **utils/translations.py**: Nuevas claves i18n para el campo de Chat ID
- **[14/06/2026]** — Fixes masivos de estabilidad + tests:
  - 🔴 Watchdogs duplicados eliminados en reconexión | `main.py`, `core/engine.py`
  - 🔴 `asyncio.TimeoutError` ahora se reintenta en Python 3.10 | `utils/resilience/retry_service.py`
  - 🔴 Órdenes LIMIT pendientes persistidas en disco | `core/engine.py`
  - 🟡 Rate limiting en notificaciones (2s) | `services/notifier.py`
  - 🟡 Entity cache invalidation al cambiar chat_id | `services/notifier.py`
  - 🟡 Circuit breaker states sincronizados en health | `health_monitor.py`, `engine.py`
  - 🟡 Health check usa mercados reales del exchange | `core/engine.py`
  - 🟢 Event loop leaks en dashboard fix | `ui/main_window.py`
  - 🆕 **31 tests** para `core/engine.py` — TradingEngine (watchdog, DCA, trailing, SL)
  - 🆕 **44 tests** para `services/exchange_service.py` — ExchangeService (CCXT clients)
  - 🆕 **21 tests** para `utils/settings_manager.py` — Settings (idioma, autostart)
  - 🆕 **19 tests** para `services/market_data.py` — CoinGecko caché, 429, timeout

## Próximos Pasos / TODOs

- [ ] Activar más exchanges (Binance, Bybit, OKX) con el nuevo sistema robusto
- [x] Sistema de notificaciones Telegram para alertas de trading, health y reportes diarios
- [x] Tests para market_data.py (19 tests)
- [x] Tests para engine.py (31 tests)
- [x] Tests para exchange_service.py (44 tests)
- [x] Tests para settings_manager.py (21 tests)
- [x] Pestaña Reportes con estadísticas de trading
- [x] Mejora de pestaña Posiciones (solo activas, SL/TP real, export CSV)
- [x] Backup/restore cifrado de configuración
- [x] Bug fixes críticos (HealthMonitor periódico, PnL real, event loop)
- [x] Bug fixes de producción (notifier, CoinGecko, event loop CCXT, reconexión Telegram)
- [x] Chat ID configurable desde la UI
- [x] Fixes estabilidad: watchdogs duplicados, persistencia LIMIT, rate limiting, etc.
- [ ] Gráficos en pestaña Reportes (matplotlib para PnL histórico)
- [ ] Tests de integración con exchanges simulados

## Notas / Problemas Conocidos

- Archivos temporales/legacy excluidos vía `.gitignore`: `_fix_probar.py`, `_fix_probar2.py`, `_fix_probar3.py`, `_new_method.py`, `_fx.py`, `backup_modulos/`, `legacy_code/` — no se subieron al repositorio.
- Archivos legacy eliminados del repositorio: `bot_unificado v2.py`, `README_BACKUP.md`, `build_distribucion.bat`.
- Repositorio GitHub inicializado: https://github.com/juancito8812/botdetrading.git (rama master).
- Tests: 197 tests en total, todos pasando.
- Credenciales (.env, config.json, canales.json) excluidas del repositorio por seguridad.
- Todo el desarrollo sigue la metodología Superpowers (brainstorming → writing-plans → subagent-driven-development).
- Archivos de diseño y plan guardados en `docs/superpowers/specs/` y `docs/superpowers/plans/`.
- Para activar las notificaciones: configurar `NOTIFICATION_CHAT_ID` en `.env`, o desde la UI en la pestaña 📱 Telegram > Chat ID para Notificaciones, o se usará el ID del usuario autenticado por defecto.
- Orden de prioridad del `notification_chat_id`: 1) `settings.json` (UI) → 2) `.env` → 3) `get_me()` del usuario autenticado.

---

## 🦸 Superpowers Framework

**Repositorio:** https://github.com/obra/superpowers
**Clonado en:**  (dentro del proyecto)
**Skills instalados en:**  (14 skills copiados)

### Skills disponibles:
- brainstorming, dispatching-parallel-agents, executing-plans
- finishing-a-development-branch, receiving-code-review, requesting-code-review
- subagent-driven-development, systematic-debugging, test-driven-development
- using-git-worktrees, using-superpowers, verification-before-completion
- writing-plans, writing-skills

**Metodología:** Especificación → Planificación → Subagentes → TDD

**Instalado:** 13/06/2026
