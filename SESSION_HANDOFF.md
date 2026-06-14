# 🪪 Session Handoff — MiBotTrading

> **Creado:** 13/06/2026
> **Última actualización:** 14/06/2026
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

**Último commit:** `0878633` — feat: agregar pestaña Reportes con resumen, performance por exchange e historial de trades
**Tests:** 72/72 pasando ✅
**GitHub:** https://github.com/juancito8812/botdetrading.git
**Actions:** https://github.com/juancito8812/botdetrading/actions

**Commits recientes en origin/master:**
| Commit | Descripción |
|--------|-------------|
| `0878633` | feat: agregar pestaña Reportes con resumen, performance por exchange e historial de trades |
| `62ab7aa` | feat: nueva pestaña Telegram unificada con historial de notificaciones |
| `b9e3f8e` | fix: convertir superpowers de submodule a carpeta normal para CI/CD |
| `7893148` | feat: health dashboard mejorado + break-even/trailing mutual exclusion |
| `9789457` | SESSION_HANDOFF.md para continuidad de sesiones |
| `9e23c53` | Sistema de resiliencia (retry, circuit breaker, health monitor, state recovery, backups) |
| `e063655` | Sistema de notificaciones Telegram (10 métodos, 9 tests) |

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
├── 📊 Reportes       → Resumen, performance, historial
├── 🔐 APIs           → API keys de exchanges
├── ⚖️ Riesgo         → Configuración de trading
├── 🔌 Test           → Probar conexión con exchanges
├── 📊 Posiciones     → Posiciones abiertas/cerradas
├── 📟 Consola        → Logs en tiempo real
└── ⚙️ Ajustes        → Idioma + auto-inicio Windows
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

---

## 🧪 Cómo verificar el estado

```bash
# Tests completos (72 tests)
python -m pytest tests/ -v

# Tests de un módulo específico
python -m pytest tests/test_notifier.py -v
python -m pytest tests/test_retry_service.py -v

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
7. **Tests para market_data.py** — El módulo de CoinGecko no tiene tests unitarios
8. **Gráficos en pestaña Reportes** — Agregar matplotlib para visualizar PnL histórico
9. **Exportar reportes a CSV** — Botón para descargar datos de trades
10. **Configurar NOTIFICATION_CHAT_ID** — Variable de entorno para el chat ID de Telegram donde recibir notificaciones

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
