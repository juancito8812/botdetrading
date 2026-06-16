# Session Handoff -- MiBotTrading

> **Creado:** 13/06/2026
> **Ultima actualizacion:** 14/06/2026 (v8 - Dashboard auto-refresh + Auto-start Windows + Fix pack/grid)
> **Proposito:** Documento de continuidad para que cualquier IA o agente retome el proyecto exactamente donde lo dejamos. **LEER ESTE ARCHIVO ES OBLIGATORIO AL INICIAR UNA NUEVA SESION.**

---

## REGLA #1: Usar Superpowers SIEMPRE — con TODA IA, en TODA sesion

> **⚠️ REGLA ABSOLUTA: Este proyecto USA SUPERPOWERS. Toda IA — sea Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini, o cualquier otro agente — DEBE seguir este flujo en CADA sesion, sin excepcion.**

> **Cada vez que se inicie una NUEVA sesion o se CAMBIE de agente/modelo de IA, se DEBE cargar el skill `using-superpowers` y seguir el flujo completo. No importa si la IA anterior era Claude y ahora es ChatGPT — el flujo es el MISMO.**

### Flujo obligatorio para TODA IA en TODA sesion:

```
1. 🦸 CARGAR Superpowers      → Al INICIAR cualquier sesion con cualquier IA
                                 (skill: using-superpowers)
2. 📖 LEER contexto           → MEMORY.md + SESSION_HANDOFF.md + git log --oneline -5
3. 🧠 BRAINSTORMING           → Antes de cualquier cambio creativo o implementacion
4. 📄 WRITING SPECS           → Documentar en docs/superpowers/specs/
5. 📋 WRITING PLANS           → Para tareas de 3+ pasos en docs/superpowers/plans/
6. ⚡ SUBAGENT DEVELOPMENT    → Ejecutar con agentes especializados
7. 👀 CODE REVIEW             → Revisar cambios antes de finalizar
8. ✅ VERIFICATION            → Tests + cobertura + calidad
9. 📝 ACTUALIZAR docs         → MEMORY.md + SESSION_HANDOFF.md + README si aplica
```

> **🔴 Esto aplica a: Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini, y cualquier otro agente/IA que toque este proyecto. La metodologia Superpowers es el contrato de calidad del proyecto. Ignorarla = cambios inconsistentes y perdida de contexto entre sesiones.**

> **💡 Si eres una IA leyendo esto: DETENTE. Carga el skill `using-superpowers` AHORA antes de continuar. No asumas que otra IA ya lo hizo por ti.**

---

## Resumen Rapido

**Proyecto:** Bot de trading automatizado que recibe senales via Telegram y ejecuta ordenes LONG/SHORT en exchanges de criptomonedas (Bitget, BingX).

**Stack:** Python 3.14, Tkinter (GUI), CCXT async (exchanges), Telethon (Telegram), asyncio, pytest, PyInstaller

**Ultima release:** `v1.1.0` -- Chat ID UI, entity resolution, tests market_data
**Tests:** 348/348 pasando (87% cobertura)
**Coverage:** 75% -> 87% (+86 tests)
**Ultimas features:** Dashboard auto-refresh 60s + Auto-start Windows por defecto + Bot auto-inicia al abrir
**GitHub:** https://github.com/juancito8812/botdetrading.git
**Actions:** https://github.com/juancito8812/botdetrading/actions

**Commits recientes (origin/master):**
| Commit | Descripcion |
|--------|-------------|
| (pendiente) | docs: update MEMORY, SESSION_HANDOFF, README with latest UX features |
| (pendiente) | fix: pack/grid conflict + dashboard auto-refresh + auto-start Windows |
| `364e9de` | feat: tooltips ayuda (?) + notificaciones seleccionables |
| `b46ea2b` | test: mejorar cobertura de 75% a 87% (86 tests nuevos, 348 total) |
| `96aacfe` | ci: agregar cobertura con pytest-cov + Codecov badge en README |

---

## Ultimas Sesiones (14/06/2026)

### 1-14. (Sesiones anteriores documentadas en versiones previas)

### 15. Tooltips de ayuda + Notificaciones seleccionables (commit `364e9de`)

Ver sesion #14 en version v7 del documento.

### 16. Dashboard auto-refresh + Auto-start Windows + Fix pack/grid

**Que se hizo:** Mejoras de UX y auto-inicio:

#### Dashboard auto-carga + auto-refresh 60s
- Dashboard ahora carga datos (top 20 + indices + health) automaticamente al abrir el bot (1s delay)
- Auto-refresh cada 60s activo por defecto -- no necesita el boton
- Boton de toggle existe como opcion para detener si el usuario quiere
- Intervalo cambiado de 30s a 60s en `_dash_auto_tick()`

#### Auto-start con Windows por defecto
- `start_with_windows` ahora es `True` por defecto en `DEFAULT_SETTINGS`
- `run()` en `main.py` auto-configura la tarea del Programador de Tareas en cada arranque
- El boton en la UI se actualiza inmediatamente a "DETENER BOT" sin flash visual

#### Bot auto-inicia al abrir
- Si hay credenciales configuradas, el bot se conecta automaticamente sin necesitar clic en INICIAR
- El boton muestra "DETENER BOT" desde el primer momento

#### Fix pack/grid conflict
- **Error:** `_tkinter.TclError: cannot use geometry manager grid inside ... which already has slaves managed by pack`
- **Causa:** Los botones de ayuda en `maxpos_frame` y `ex_frame` usaban `pack()` mientras el resto usaba `grid()`
- **Fix:** Cambiados `pack()` a `grid()` en `maxpos_help_row` y `cap_help_row`

#### Fix enable_autostart tuple check
- **Error:** `enable_autostart()` retorna `Tuple[bool, str]`, no `bool`. `if not enable_autostart()` siempre era falsy
- **Fix:** `success, _ = enable_autostart(); if not success:`

**Archivos modificados:**
| Archivo | Cambio |
|---------|--------|
| `ui/main_window.py` | Dashboard auto-carga + auto-refresh 60s + fix pack/grid en risk tab |
| `utils/settings_manager.py` | `start_with_windows` default True |
| `main.py` | Auto-configurar Windows Task, boton inmediato, fix tuple enable_autostart |
| `tests/test_settings_manager.py` | Test actualizado para default True |

**Tests:** 348/348 pasando
**.exe compilado:** `dist/MiBotTrading.exe`

---

## Arquitectura Actual

```
Telegram (senales) -> handler() -> parse_trading_signal() -> TradingEngine.execute_signal()
                                                                 |
                                                    @log_errors -> decide_entry_type()
                                                                 |
                                                    @timeout -> @retry -> @circuit_breaker -> CCXT
                                                                 |
                                                      PositionManager.save()
                                                                 |
                                                      StateRecovery (checkpoint)
                                                      BackupManager (backup gzip)
                                                                 |
                                                      Watchdog (cada 30s)
                                                        +-- HealthMonitor (cada 60s)
                                                        +-- Trailing stop (excluyente con break-even)
                                                        +-- Break-even (excluyente con trailing)
                                                        +-- Reintentar exchanges fallidos
                                                        +-- notify_trade_closed()
                                                        +-- notify_tp_hit()
                                                        +-- send_daily_report() (c/24h)

Telegram (notificaciones) -> TelegramNotifier <- engine.notifier
                                                    ^
                              health_monitor.on_status_change callback

GUI (Tkinter -- 9 pestanas):
+-- Dashboard     -> CoinGecko top20 + health cards (auto-refresh cada 60s)
+-- Telegram      -> Estado, credenciales, canales, notificaciones seleccionables
+-- Reportes      -> Resumen, performance, historial + export CSV
+-- APIs          -> API keys de exchanges con tooltips
+-- Riesgo        -> Configuracion de trading con tooltips
+-- Test          -> Probar conexion con exchanges
+-- Posiciones    -> Posiciones activas con PnL, SL/TP, cerrar
+-- Consola       -> Logs en tiempo real (bot auto-inicia)
+-- Ajustes       -> Idioma + auto-inicio Windows (default ON) + backup/restore
```

### Exchanges
- **Activos:** Bitget, BingX
- **Configurados (inactivos):** Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin

---

## GitHub Actions -- Workflows

| Workflow | Trigger | Stack | Que hace |
|----------|---------|-------|----------|
| **Tests** (`tests.yml`) | Push/PR a master | Ubuntu, Python 3.10/3.11/3.12 | pip install + pytest tests/ -v |
| **Lint** (`lint.yml`) | Push/PR a master | Ubuntu, Python 3.11 | flake8 + mypy |
| **Build** (`build.yml`) | Tags v* o manual | Windows-latest | PyInstaller -> .exe -> Release |

**Nota:** Checkout configurado con `submodules: false` para evitar errores del submodulo superpowers/.

---

## Como verificar el estado

```bash
# Tests completos (348 tests - 87% cobertura)
python -m pytest tests/ -v

# Cobertura local
python -m pytest tests/ --cov=core --cov=models --cov=services --cov=utils --cov-report=term

# Estado de git
git status
git log --oneline -5

# Ver workflows en GitHub
# https://github.com/juancito8812/botdetrading/actions
```

---

## Proximos Pasos / TODOs

Priorizados por impacto:

1. **Activar mas exchanges** -- Binance, Bybit, OKX (ya configurados, solo falta habilitar en `.env` y probar)
2. **Graficos en pestana Reportes** -- Agregar matplotlib para visualizar PnL historico
3. **Tests de integracion** con exchanges simulados (mock CCXT)
4. **Cubrir watchdog loop de engine.py** -- subir de 69% a 85%

---

## Configuracion Actual

| Parametro | Valor |
|-----------|-------|
| Apalancamiento | 5x |
| Modo margen | Cross |
| Cantidad minima | 2.0 USDT |
| Entrada | Auto (desviacion max 3%) |
| DCA | 3 partes |
| Trailing stop | Activacion 1.5%, distancia 0.8% |
| Timeout orden LIMIT | 10 min |
| Auto-start Windows | Activado por defecto |
| Dashboard auto-refresh | 60s (activado por defecto) |
| Notificaciones | Seleccionables desde UI (8 tipos) |
| Check interval health | 60s |
| Retry intentos | 3 (backoff exp. 1s->2s->4s) |
| Circuit breaker | 5 fallos -> OPEN 60s -> HALF_OPEN |
| Backup rotacion | 24 backups comprimidos (gzip) |

---

## Superpowers Framework

Framework de metodologia de desarrollo instalado (14 skills). Los skills estan en `.agents/skills/` y se activan automaticamente.

**Flujo de trabajo:** brainstorming -> writing-plans -> subagent-driven-development (con revision spec + code quality)

**Documentos de diseno y plan en:** `docs/superpowers/specs/` y `docs/superpowers/plans/`

---

## Notas Importantes

- **Credenciales excluidas de git:** `.env`, `config.json`, `canales.json` -- estan en `.gitignore`
- **Auto-start Windows:** Se crea tarea en el Programador de Tareas al primer arranque (idempotente)
- **Bot auto-inicia:** Si hay credenciales, el bot arranca solo al abrir la app (500ms delay)
- **Dashboard auto-refresh:** Carga datos a los 1s de abrir, luego refresca cada 60s
- **Para activar notificaciones:** Configurar desde UI en pestana Telegram -> Chat ID / checkboxes
- **Para empezar una nueva sesion:** Leer este archivo + `.agents/MEMORY.md` + `git log --oneline -3`
