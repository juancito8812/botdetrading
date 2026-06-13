# 🪪 Session Handoff — MiBotTrading

> **Creado:** 13/06/2026
> **Propósito:** Documento de continuidad para que otra IA o sesión retome el proyecto exactamente donde lo dejamos.

---

## 📋 Resumen Rápido

**Proyecto:** Bot de trading automatizado que recibe señales vía Telegram y ejecuta órdenes LONG/SHORT en exchanges de criptomonedas (Bitget, BingX).

**Stack:** Python 3.14, Tkinter (GUI), CCXT async (exchanges), Telethon (Telegram), asyncio, pytest

**Último commit:** `9e23c53` — feat(resilience): add complete robustness system
**Tests:** 63/63 pasando ✅
**Repositorio:** https://github.com/juancito8812/botdetrading.git

---

## 🎯 Última Sesión: Sistema de Resiliencia (Completado)

### ¿Qué se hizo?
Se implementó un sistema completo de robustez siguiendo la metodología Superpowers:

| Paso | Archivo |
|------|---------|
| **Spec** | `docs/superpowers/specs/2026-06-13-resilience-system-design.md` |
| **Plan** | `docs/superpowers/plans/2026-06-13-resilience-system.md` |
| **Implementación** | `git log 9e23c53` |

### Módulos creados (7 nuevos en `utils/resilience/`)

| Módulo | Propósito |
|--------|-----------|
| `error_handler.py` | 7 clases de error personalizadas (ExchangeConnectionError, CircuitBreakerOpenError, MaxRetriesExceeded, etc.) |
| `retry_service.py` | Reintentos con backoff exponencial + jitter (máx 3 intentos, retry_on configurable) |
| `circuit_breaker.py` | Estados closed/open/half-open por exchange (5 fallos → OPEN 60s → HALF_OPEN) |
| `decorators.py` | `@retry`, `@circuit_breaker_dynamic`, `@timeout`, `@log_errors` |
| `health_monitor.py` | Health checks periódicos (cada 60s), estados healthy/degraded/down |
| `state_recovery.py` | Checkpoints con snapshots antes de operaciones críticas (máx 50) |
| `backup_manager.py` | Backups rotativos comprimidos gzip (24 máx, restauración automática) |

### Archivos modificados (3)

| Archivo | Cambio |
|---------|--------|
| `services/exchange_service.py` | Decoradores de resiliencia en get_balance, get_ticker, create_client, set_leverage, fetch_position, cancel_order |
| `core/engine.py` | HealthMonitor integrado en watchdog, método `_health_check_exchange`, `@log_errors` en execute_signal |
| `core/manager.py` | StateRecovery + BackupManager integrados en save/load, restauración automática de posición corrupta |

### Tests nuevos (8 archivos, 49 tests)

- `tests/test_error_handler.py` — Jerarquía de errores, mensajes, causas
- `tests/test_retry_service.py` — Reintentos, backoff, jitter, excepciones, callbacks
- `tests/test_circuit_breaker.py` — Estados, transiciones, persistencia
- `tests/test_decorators.py` — Decoradores async, circuit breaker dinámico
- `tests/test_health_monitor.py` — Health checks, estados, latencia
- `tests/test_state_recovery.py` — Checkpoints, rotación, persistencia
- `tests/test_backup_manager.py` — Backup, rotación, compresión, restauración

---

## 🏗️ Arquitectura Actual

```
Telegram → handler() → parse_trading_signal() → TradingEngine.execute_signal()
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
                                              └── Reintentar exchanges fallidos
```

### Exchanges
- **Activos:** Bitget, BingX
- **Configurados (inactivos):** Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin

---

## 🧪 Cómo verificar el estado

```bash
# Tests completos
python -m pytest tests/ -v

# Tests de un módulo específico
python -m pytest tests/test_retry_service.py -v
python -m pytest tests/test_circuit_breaker.py -v

# Estado de git
git status
git log --oneline -5

# Si existe posiciones.json
type "%APPDATA%\MiBotTrading\posiciones.json" 2>nul || echo "No hay posiciones"
```

---

## 📋 Próximos Pasos / TODOs

Priorizados por impacto:

1. **Activar más exchanges** — Binance, Bybit, OKX (ya configurados, solo falta habilitar en `.env` y probar)
2. **Notificaciones** — Sistema de alertas vía Telegram cuando: health check falle, circuit breaker se abra, posición se abra/cierre
3. **Tests para market_data.py** — El módulo de CoinGecko no tiene tests unitarios
4. **Dashboard UI** — Añadir indicadores de salud de exchanges (healthy/degraded/down) en la interfaz Tkinter
5. **Distribución EXE** — Generar ejecutable con PyInstaller para distribución

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

---

## 🦸 Superpowers Framework

Framework de metodología de desarrollo instalado (14 skills). Los skills están en `.agents/skills/` y se activan automáticamente.

**Flujo de trabajo:** brainstorming → writing-plans → subagent-driven-development (con revisión spec + code quality)

**Documentos de diseño y plan en:** `docs/superpowers/specs/` y `docs/superpowers/plans/`

---

## ⚠️ Notas Importantes

- **Credenciales excluidas de git:** `.env`, `config.json`, `canales.json` — están en `.gitignore`
- **Archivos legacy ignorados:** `_fix_probar*.py`, `_new_method.py`, `_fx.py`, `bot_unificado v2.py`, `backup_modulos/`, `legacy_code/`
- **Los decoradores de resiliencia requieren `pytest-asyncio`** para tests async (ya instalado)
- **Para empezar una nueva sesión:** Leer este archivo + `.agents/MEMORY.md` + `git log --oneline -3`
