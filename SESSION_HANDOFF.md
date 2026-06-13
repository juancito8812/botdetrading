# 🪪 Session Handoff — MiBotTrading

> **Creado:** 13/06/2026
> **Última actualización:** 13/06/2026
> **Propósito:** Documento de continuidad para que otra IA o sesión retome el proyecto exactamente donde lo dejamos.

---

## 📋 Resumen Rápido

**Proyecto:** Bot de trading automatizado que recibe señales vía Telegram y ejecuta órdenes LONG/SHORT en exchanges de criptomonedas (Bitget, BingX).

**Stack:** Python 3.14, Tkinter (GUI), CCXT async (exchanges), Telethon (Telegram), asyncio, pytest

**Último commit:** `eb595e5` — chore: remove legacy files (bot_unificado v2.py, README_BACKUP.md, build_distribucion.bat)
**Tests:** 72/72 pasando ✅
**GitHub:** https://github.com/juancito8812/botdetrading.git
**Actions:** https://github.com/juancito8812/botdetrading/actions

**Commits en origin/master:**
| Commit | Descripción |
|--------|-------------|
| `9789457` | SESSION_HANDOFF.md para continuidad de sesiones |
| `9e23c53` | Sistema de resiliencia (retry, circuit breaker, health monitor, state recovery, backups) |
| `e063655` | Sistema de notificaciones Telegram (10 métodos, 9 tests) |
| `f731307` | CI: tests.yml con pytest para todos los tests + pytest-asyncio en requirements |
| `eb595e5` | Limpieza de archivos legacy (bot_unificado v2.py, README_BACKUP.md, build_distribucion.bat) |

---

## 🎯 Última Sesión: Limpieza de Archivos Legacy (Completado)

### ¿Qué se eliminó?

Se eliminaron 3 archivos legacy que ya no son necesarios:

| Archivo | Motivo |
|---------|--------|
| `bot_unificado v2.py` | Versión monolítica antigua — el bot ahora es modular (`core/`, `services/`, etc.) |
| `README_BACKUP.md` | Backup obsoleto del README original |
| `build_distribucion.bat` | Script de build manual — ahora se usa GitHub Actions |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `.agents/MEMORY.md` | Referencias a legacy eliminadas |
| `SESSION_HANDOFF.md` | Referencias a legacy eliminadas |

---

## 🎯 Sesión Anterior: Sistema de Notificaciones Telegram (Completado)

### ¿Qué se hizo?
Se implementó un sistema completo de notificaciones vía Telegram siguiendo la metodología Superpowers:

| Paso | Archivo |
|------|---------|
| **Spec** | `docs/superpowers/specs/2026-06-13-telegram-notifications-design.md` |
| **Plan** | `docs/superpowers/plans/2026-06-13-telegram-notifications.md` |
| **Implementación** | `git log e063655` |

### Nuevo: `services/notifier.py` — TelegramNotifier

```python
class TelegramNotifier:
    async def send_message(text)                    # Mensaje raw
    async def notify_trade_open(position)            # 🚀 Apertura LONG/SHORT
    async def notify_trade_closed(position)           # ✅/❌ Cierre con PnL
    async def notify_tp_hit(position, tp_number)      # 🎯 TP alcanzado
    async def notify_trailing_activated(position)     # 🔝 Trailing stop activado
    async def notify_dca_executed(exchange, sym, price) # 📊 Orden DCA ejecutada
    async def notify_health_change(ex, status, fails, lat) # ⚠️ Health change
    async def notify_circuit_breaker(ex, state, retry) # 🔴 Circuit breaker
    async def notify_error(module, error)              # ❌ Error crítico
    async def send_daily_report(positions, balances)   # 📊 Reporte diario
```

### Archivos modificados (3)

| Archivo | Cambio |
|---------|--------|
| `core/engine.py` | `notify_trade_open` en execute_signal, `notify_trade_closed`/`notify_tp_hit` en watchdog, `notify_trailing_activated` en LONG+SHORT, `notify_dca_executed` en DCA fill, reporte diario cada 24h |
| `utils/resilience/health_monitor.py` | Callback `on_status_change` para alertas de salud |
| `main.py` | Inicialización de TelegramNotifier después de conectar Telegram + callback de salud |

### Tests nuevos (1 archivo, 9 tests)

- `tests/test_notifier.py` — send_message, disabled, trade_open/closed, health_change, circuit_breaker, trailing_activated, daily_report, error handling

### Estado del proyecto
- **72 tests, todos pasando** ✅
- **Sin archivos legacy en el repo** — solo código activo y documentación
- **GitHub Actions:** tests.yml ejecuta pytest completo, lint.yml con flake8+mypy, build.yml para releases

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
                                                        ├── Trailing stop
                                                        ├── Break-even
                                                        ├── Reintentar exchanges fallidos
                                                        ├── notify_trade_closed()
                                                        ├── notify_tp_hit()
                                                        └── send_daily_report() (c/24h)

Telegram (notificaciones) → TelegramNotifier ← engine.notifier
                                                    ↑
                              health_monitor.on_status_change callback
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
3. **Tests para market_data.py** — El módulo de CoinGecko no tiene tests unitarios
4. **Dashboard UI** — Añadir indicadores de salud de exchanges (healthy/degraded/down) + últimas notificaciones en Tkinter
5. **Reporte semanal** — PnL por exchange, tasa de aciertos, distribución de trades
6. **Configurar NOTIFICATION_CHAT_ID** — Variable de entorno para el chat ID de Telegram donde recibir notificaciones

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
