# Memoria del Proyecto: MiBotTrading

## Información General

- **Proposito:** Bot de trading automatizado que recibe senales via Telegram y ejecuta ordenes en exchanges de criptomonedas (Bitget, BingX).
- **Stack:** Python 3.10+, Tkinter (GUI), CCXT (conexion exchanges), Telethon (Telegram), asyncio
- **Ultimas features:** Dashboard auto-refresh 60s + Auto-start Windows por defecto + Bot auto-inicia al abrir
- **Ultima sesion:** 19/06/2026 - Fix produccion: 40109 Bitget plan orders + BingX setLeverage + Parser + Watchdog cancel SL/TP
- **Version de memoria:** 11

## Arquitectura

```
MiBotTrading/
+-- main.py                    # Punto de entrada, TradingBotApp
+-- config.json                # Configuracion de riesgo
+-- .env                       # Credenciales (API keys)
+-- core/
|   +-- engine.py              # TradingEngine - ejecucion de senales, SL/TP, DCA, trailing stop
|   +-- manager.py             # PositionManager - gestion y persistencia de posiciones
|   +-- parser.py              # parse_trading_signal - parseo de mensajes Telegram
+-- services/
|   +-- exchange_service.py    # ExchangeService - conexion CCXT con multiples exchanges
|   +-- market_data.py         # fetch_top20, fetch_market_indices (CoinGecko)
+-- ui/
|   +-- main_window.py         # TradingBotGUI - interfaz Tkinter (9 pestanas)
+-- models/
|   +-- data_classes.py        # Dataclasses: Position, Signal
+-- utils/
|   +-- config.py              # Carga/guardado de config, credenciales, canales
|   +-- helpers.py             # Utilidades varias (atomic_write_json, patch_aiohttp_dns)
|   +-- logger.py              # Configuracion de logging
|   +-- settings_manager.py    # Settings de UI + auto-inicio Windows
|   +-- translations.py        # i18n espanol/ingles
|   +-- config_backup.py       # Export/Import cifrado (cryptography.fernet + PBKDF2)
|   +-- resilience/            # Sistema de resiliencia (v2.0)
|       +-- error_handler.py   # Taxonomia de errores personalizados
|       +-- retry_service.py   # Reintentos con backoff exponencial + jitter
|       +-- circuit_breaker.py # Estados closed/open/half-open por exchange
|       +-- decorators.py      # @retry, @circuit_breaker, @timeout, @log_errors
|       +-- health_monitor.py  # Health checks periodicos + historial
|       +-- state_recovery.py  # Snapshots + restauracion de operaciones
|       +-- backup_manager.py  # Backup automatico rotativo con gzip
+-- tests/
|   +-- test_parser.py         # Tests del parseador de senales
|   +-- test_manager.py        # Tests del gestor de posiciones
|   +-- test_error_handler.py  # Tests de taxonomia de errores
|   +-- test_retry_service.py  # Tests de backoff y reintentos
|   +-- test_circuit_breaker.py# Tests de estados del circuit breaker
|   +-- test_decorators.py     # Tests de decoradores de resiliencia
|   +-- test_health_monitor.py # Tests de health checks
|   +-- test_state_recovery.py # Tests de checkpoints y restauracion
|   +-- test_backup_manager.py # Tests de backups rotativos
|   +-- test_notifier.py       # Tests del sistema de notificaciones Telegram
+-- dist/                      # Archivos para distribucion EXE
+-- logs/                      # Logs de ejecucion
+-- telegram_session/          # Sesion de Telegram guardada
```

### Flujo de datos:
1. Telegram envia mensaje -> `handler()` en main.py
2. `parse_trading_signal()` extrae simbolo, direccion, entradas, SL, targets
3. `TradingEngine.execute_signal()` orquesta la ejecucion en cada exchange
4. Decide tipo de entrada (MARKET, LIMIT, DCA) basado en config y precio
5. Coloca orden + Stop Loss + Take Profits (distribucion personalizada)
6. `PositionManager` guarda/recupera posiciones en `posiciones.json`
7. Watchdog cada 30s: monitorea ordenes LIMIT pendientes, trailing stop, breakeven, sincroniza estado

### Notificaciones (Telegram):
```
Trading:
  execute_signal() -> notify_trade_open(position)
  watchdog/posicion cerrada -> notify_trade_closed(position)
  watchdog/TP1 hit -> notify_tp_hit(position, 1)
  _check_trailing_stop(LONG+SHORT) -> notify_trailing_activated(position)
  _process_filled_limit_order(DCA) -> notify_dca_executed(exchange, symbol, price)

Sistema:
  health_monitor.on_status_change -> notify_health_change(exchange, status, failures, latency)

Reportes:
  watchdog/cada 24h -> send_daily_report(positions, balances)
```

### Capa de Resiliencia (v2.0):
Cada llamada a exchange pasa por:
```
@timeout -> @retry (backoff exp.) -> @circuit_breaker -> @log_errors -> CCXT
                              |
                        HealthMonitor <- cada 60s verifica conexiones
                              |
                        StateRecovery <- antes de cada mutacion critica
                              |
                        BackupManager <- cada ~15 saves
```

### Exchanges soportados:
- Habilitados: Bitget, BingX
- Configurados pero desactivados: Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin

## Decisiones Clave

- **[11/06/2026]** -- Refactorizacion de codigo legacy monolitico a arquitectura modular con separacion clara (core/, services/, ui/, utils/).
- **[11/06/2026]** -- Implementacion de entrada con modalidad auto/market/limit + DCA (ordenes escalonadas).
- **[11/06/2026]** -- Trailing stop automatico con activacion por % de ganancia y distancia configurable.
- **[11/06/2026]** -- Distribucion personalizada de Take Profits (igual, progresivo con pesos configurables).
- **[11/06/2026]** -- Persistencia de posiciones en %APPDATA%/MiBotTrading/ para entorno EXE.
- **[13/06/2026]** -- Sistema de resiliencia completo (Enfoque A: Decoradores) usando metodologia Superpowers:
  - Reintentos con backoff exponencial + jitter (max 3 intentos)
  - Circuit breaker por exchange (5 fallos -> OPEN 60s -> HALF_OPEN)
  - Timeouts configurables (15s ticker, 30s balance, 60s orders)
  - HealthMonitor integrado en watchdog (checks cada 60s)
  - StateRecovery con checkpoints antes de operaciones criticas (max 50)
  - BackupManager con rotacion automatica (24 backups comprimidos)

## Estado Actual

- **Lo que se esta trabajando:** Estabilizacion produccion (fix 40109, BingX, parser, watchdog)
- **Exchanges activos en config.json:** bitget, bingx
- **Apalancamiento:** 5x
- **Modo margen:** Cross
- **Cantidad minima:** 2.0 USDT
- **Entrada:** Auto (con validacion de desviacion max 3%)
- **DCA:** Habilitado (3 partes)
- **Trailing stop:** Habilitado (activacion 1.5%, distancia 0.8%)
- **Resiliencia:** Completada
- **Notificaciones:** Completadas
- **Notificaciones seleccionables:** Completadas (8 checkboxes en UI)
- **Tooltips de ayuda:** Completados (18 campos en Riesgo, Ajustes, APIs)
- **Dashboard auto-refresh:** Completado (auto-carga + ciclo 60s)
- **Auto-start Windows:** Completado (default ON + tarea automatica al iniciar)
- **Bot auto-inicia:** Completado (al abrir la app ya escucha senales)
- **Backup cifrado:** Completado (82 tests, todos pasando)

## Cambios Recientes

- **[11/06/2026]** -- Inicializacion estructura modular completa y funcional.
- **[11/06/2026]** -- Subido a GitHub: https://github.com/juancito8812/botdetrading.git
- **[13/06/2026]** -- Implementacion del sistema de resiliencia completo via Superpowers
- **[13/06/2026]** -- Implementacion del sistema de notificaciones Telegram
- **[14/06/2026]** -- Pestana Reportes, Posiciones, Export/Import cifrado, Bug fixes
- **[14/06/2026]** -- Chat ID configurable desde la UI
- **[14/06/2026]** -- Fixes estabilidad + 115 tests nuevos
- **[14/06/2026]** -- Cobertura 75% -> 87% (86 tests nuevos)
- **[14/06/2026]** -- Tooltips ayuda + Notificaciones seleccionables
- **[14/06/2026]** -- Dashboard auto-refresh + Auto-start Windows + Fix pack/grid:
  - **ui/main_window.py**: Dashboard ahora auto-carga al iniciar (1s) y auto-refresh cada 60s (sin boton). Fix pack/grid en maxpos_frame y ex_frame
  - **utils/settings_manager.py**: start_with_windows = True por defecto
  - **main.py**: Auto-configura tarea de Windows al arrancar, boton se actualiza inmediatamente (sin flash), fix desempaquetado tuple enable_autostart()
  - **tests/test_settings_manager.py**: Test actualizado para nuevo default True

- **[19/06/2026] -- Fix produccion v2.1.2 (3 bugs + parser):**
  - **Bug 40109 Bitget**: `fetch_plan_order()` + `cancel_order()` con `planType: 'normal_plan'` para Bitget. Arregla 5 callers
  - **BingX setLeverage**: `positionSide` -> `side` en params (elimina warning)
  - **Watchdog cancel SL/TP**: Cancela SL y TPs al detectar posicion cerrada
  - **Parser REJECT_PATTERNS**: Rechaza mensajes con Loss, took out, Volatility
  - **Parser TPs antes que SL**: TPs primero, SL despues (Bitget sin reduceOnly)
  - **Test Limit Long**: Formato "Limit Long $SIMBOLO" ya soportado
  - **Tests**: 146 tests (engine 85 + parser 18 + exchange_service 43)

## Proximos Pasos / TODOs

- [ ] Activar mas exchanges (Binance, Bybit, OKX) con el nuevo sistema robusto
- [x] Sistema de notificaciones Telegram
- [x] Tests para market_data.py, engine.py, exchange_service.py, settings_manager.py
- [x] Pestana Reportes, Posiciones, Backup cifrado
- [x] Bug fixes criticos y de produccion
- [x] Chat ID configurable desde la UI
- [x] Fixes estabilidad + cobertura 75% -> 87%
- [x] Tooltips de ayuda + Notificaciones seleccionables
- [x] Dashboard auto-refresh + Auto-start Windows + Bot auto-inicia
- [x] Fix produccion v2.1.2: 40109, BingX, parser, watchdog
- [ ] Desplegar v2.1.2 a produccion
- [ ] Graficos en pestana Reportes (matplotlib para PnL historico)
- [ ] Tests de integracion con exchanges simulados
- [ ] Cubrir watchdog loop de engine.py (de 69% a 85%)

## Notas / Problemas Conocidos

- Archivos temporales/legacy excluidos via `.gitignore`
- Repositorio GitHub: https://github.com/juancito8812/botdetrading.git (rama master)
- Tests: 348+ tests en total, todos pasando (146 de engine+parser+exchange_service)
- Auto-start con Windows: habilitado por defecto, crea tarea Programador de Tareas al primer arranque
- Bot auto-inicia si hay credenciales configuradas (no necesita clic en INICIAR)
- Dashboard carga datos automaticamente al abrir y refresca cada 60s
- Bug 40109 Bitget: fetch_plan_order + cancel_order con planType arreglan consulta/cancelacion de plan orders
- BingX setLeverage: cambiado de positionSide a side param

---

## Superpowers Framework

**Repositorio:** https://github.com/obra/superpowers
**Skills instalados:** 14 skills en `.agents/skills/`

**Metodologia:** Especificacion -> Planificacion -> Subagentes -> TDD

**Instalado:** 13/06/2026
