# 🧠 Memoria del Proyecto — MiBotTrading

> ╔══════════════════════════════════════════════════════════════════╗
> ║  🟢 CHECKPOINT v2.1.9 — 19/06/2026                            ║
> ║  Estado: 🧪 PRODUCCIÓN — Auditoría seguridad completa        ║
> ║  Tests: 164 pasando (engine+parser+exchange_service+config)   ║
> ║  Cambios: .env cifrado, sesión derivada, cache GitHub, logs  ║
> ║  Exchanges activos: BingX + Bitget (ambos operativos)         ║
> ╚══════════════════════════════════════════════════════════════════╝

*Última actualización: 19/06/2026 (America/Caracas) — v2.1.9: Auditoría seguridad completa (7/7 hallazgos resueltos)*

---

## 📋 Resumen Ejecutivo

**MiBotTrading** es un bot de trading automatizado que escucha canales de Telegram en busca de señales de trading y ejecuta órdenes **LONG/SHORT** en exchanges de criptomonedas (actualmente **BingX + Bitget** activos).

### Stack Tecnológico
- **Lenguaje:** Python 3.10+
- **GUI:** Tkinter (interfaz de escritorio con 9 pestañas)
- **Exchanges:** CCXT (async) — **BingX + Bitget activos**, Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin disponibles
- **Telegram:** Telethon (cliente de usuario, no bot)
- **Async:** asyncio
- **Build:** PyInstaller + Inno Setup

### Estado Actual: 🧪 Prueba de 1 semana en curso
- [x] Conexión a Telegram y escucha de canales (3 canales activos)
- [x] Parseo de señales (símbolo, dirección, entradas, SL, targets)
- [x] Ejecución MARKET/LIMIT/DCA
- [x] Stop Loss + Take Profits personalizados
- [x] Trailing stop automático
- [x] Break-even automático al alcanzar TP1
- [x] Watchdog cada 30s (monitoreo y sincronización)
- [x] Persistencia de posiciones en disco
- [x] Interfaz gráfica completa
- [x] Tests unitarios (324 tests)
- [x] GitHub Actions (tests, lint, build)
- [x] Pre-commit hook Superpowers
- [x] Repositorio en GitHub
- [x] Notificaciones v2: SL hit, TP hit, alive heartbeat, signal received, LIMIT filled, DCA executed
- [x] Heartbeat cada 4h con estado del bot
- [x] Fix: DCA sin mínimo obligatorio
- [x] Fix: reporte diario solo tras 24h
- [x] Fix: event loop recovery elimina cliente roto antes de recrear
- [x] Fix: Logs de conexión verifican resultado real de create_client
- [x] Fix: CircuitBreaker.load() eliminado por Ponytail, código legacy removido

---

## 🏗️ Arquitectura del Proyecto

```
MiBotTrading/
│
├── main.py                     # Punto de entrada — TradingBotApp
├── config.json                 # Configuración de riesgo (NO subir a GitHub)
├── .env                        # Credenciales API (NO subir a GitHub)
├── canales.json                # IDs de canales Telegram (NO subir a GitHub)
├── posiciones.json             # Persistencia de posiciones (NO subir a GitHub)
├── MEMORY.md                   # ← ESTE ARCHIVO — Memoria del proyecto
├── README.md                   # Documentación general
├── requirements.txt            # Dependencias
├── .gitignore                      # Limpieza completa de temporales y artefactos
│
├── .githooks/
│   └── pre-commit                 # Hook Superpowers: valida docs al commitear código
│
├── .agents/
│   ├── MEMORY.md                  # Memoria para skills de IA
│   └── skills/                    # 14 skills de Superpowers + Ponytail
│       ├── brainstorming/
│       ├── writing-plans/
│       ├── test-driven-development/
│       ├── systematic-debugging/
│       ├── subagent-driven-development/
│       ├── executing-plans/
│       ├── dispatching-parallel-agents/
│       ├── requesting-code-review/
│       ├── receiving-code-review/
│       ├── verification-before-completion/
│       ├── finishing-a-development-branch/
│       ├── using-git-worktrees/
│       ├── using-superpowers/
│       ├── writing-skills/
│       └── ponytail/              # Ponytail lazy senior dev mode
│
├── .opencode/
│   └── plugins/
│       └── ponytail.mjs           # Plugin Ponytail para OpenCode
│
├── hooks/
│   ├── ponytail-config.js         # Config de niveles Ponytail
│   └── ponytail-instructions.js   # Builder de reglas por nivel
│
├── opencode.json                  # Superpowers (oficial) + Ponytail plugins
│
├── docs/
│   └── superpowers/               # Especificaciones y planes de diseño
│       ├── specs/                 #   - coverage-final.md
│       └── plans/                 #   - refactor-manager.md
│
├── .github/
│   └── workflows/
│       ├── tests.yml           # Tests automáticos (Python 3.10-3.12)
│       ├── lint.yml            # Flake8 + Mypy
│       └── build.yml           # Compilar EXE + Release
│
├── core/                       # ★ LÓGICA PRINCIPAL ★
│   ├── engine.py               # TradingEngine — orquestación de señales
│   ├── manager.py              # PositionManager — gestión de posiciones
│   └── parser.py               # parse_trading_signal — parseo de señales Telegram
│
├── services/                   # ★ SERVICIOS EXTERNOS ★
│   ├── exchange_service.py     # ExchangeService — conexión con exchanges vía CCXT
│   ├── market_data.py          # Datos de CoinGecko (top 20 + índices)
│    └── updater.py              # Auto-Updater real: GitHub API, download, apply .bat
│
├── ui/                         # ★ INTERFAZ DE USUARIO ★
│   └── main_window.py          # TradingBotGUI — Tkinter (9 pestañas)
│
├── models/                     # ★ MODELOS DE DATOS ★
│   └── data_classes.py         # Position, Signal (dataclasses)
│
├── utils/                      # ★ UTILIDADES ★
│   ├── config.py               # Carga/guardado de config, credenciales, canales
│   ├── helpers.py              # atomic_write_json, patch_aiohttp_dns
│   ├── logger.py               # Configuración de logging
│   ├── settings_manager.py     # Settings de UI + auto-inicio Windows
│   └── translations.py         # i18n — español/inglés
│
├── tests/                      # ★ TESTS ★
│   ├── test_parser.py          # Tests del parseador (9 tests)
│   └── test_manager.py         # Tests del gestor de posiciones (5 tests)
│
├── dist/                       # Archivos para distribución EXE
├── logs/                       # Logs de ejecución
├── telegram_session/           # Sesión de Telegram guardada
├── scripts/                    # Scripts auxiliares
│
├── build_distribucion.bat      # Script para build local
├── MiBotTrading.spec           # PyInstaller spec
└── Installer_Script.iss        # Inno Setup script
```

---

## 🔄 Flujo de Datos

```
Telegram Channel
      │
      ▼  (mensaje de señal)
TradingBotApp.main_async()
      │
      ▼  handler() en main.py
parse_trading_signal(text)
      │
      ├── Extrae: Símbolo, Dirección, Entry Min/Max, SL, Targets
      │
      ▼
TradingEngine.execute_signal(signal, config, exchange_id)
      │
      ├── 1. Validar duplicado (cooldown 60s)
      ├── 2. Obtener cliente + símbolo de mercado
      ├── 3. Obtener precio + balance
      ├── 4. Configurar apalancamiento y margen
      │
      ▼
_decide_entry_type()
      │
      ├── ¿Señal tiene rango de entrada?
      │   ├── NO → MARKET directo
      │   └── SÍ → Validar precio vs rango
      │       ├── ¿Desviación > máx? → RECHAZAR
      │       ├── ¿Precio en rango? → MARKET
      │       └── ¿Fuera de rango?
      │           ├── DCA habilitado → Órdenes LIMIT escalonadas
      │           └── DCA deshabilitado → LIMIT única en borde
      │
      ▼  (si MARKET)
Colocar orden + SL + TPs
      │
      ├── Stop Loss (orden TRIGGER_MARKET o limit)
      ├── Take Profits (distribución igual o progresiva)
      └── PositionManager.add_position()
      
      ▼  (cada 30s)
TradingEngine.watchdog()
      │
      ├── Revisar órdenes LIMIT pendientes (timeout 10 min)
      ├── Sincronizar posiciones abiertas con exchange
      ├── Actualizar trailing stop si aplica
      ├── Mover SL a break-even si TP1 alcanzado
      ├── Reintentar exchanges fallidos
      └── Limpiar caché de señales antiguas
```

---

## ⚙️ Configuración Actual

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `apalancamiento` | 5x | Multiplicador de posición |
| `modo_margen` | cross | Cross o isolated |
| `cantidad_minima_usdt` | 2.0 | Mínimo por operación |
| `cooldown_segundos` | 60 | Tiempo entre señales duplicadas |
| `entrada_modalidad` | auto | auto / market / limit |
| `desviacion_maxima_porcentaje` | 3.0% | Máx desviación del rango de entrada |
| `timeout_orden_limit_minutos` | 10 | Cancelar LIMIT si no se llena |
| `dca_habilitado` | true | Órdenes escalonadas |
| `dca_partes` | 3 | Cantidad de órdenes DCA |
| `trailing_stop_habilitado` | true | Seguimiento automático del SL |
| `trailing_activacion_porcentaje` | 1.5% | % de ganancia para activar trailing |
| `trailing_distancia_porcentaje` | 0.8% | Distancia del trailing desde el máximo |
| `tp_distribucion` | progresivo | igual / progresivo |
| `tp_pesos` | 50,25,15,10 | % por cada TP |
| `auto_breakeven` | true | SL → entry price al alcanzar TP1 |

### Exchanges
| Exchange | Estado | Notas |
|----------|--------|-------|
| BingX | ✅ Activo | Conectado correctamente |
| Bitget | ✅ Activo | Reactivado con API keys nuevas (18/06/2026) |
| Binance | Deshabilitado | Sin credenciales |
| Bybit | Deshabilitado | Sin credenciales |
| OKX | Deshabilitado | Sin credenciales |

---

## 🔐 Seguridad

- `utils/crypto.py`: Cifrado AES-256-GCM con PBKDF2 (600k iteraciones)
- `utils/config_backup.py`: Backup cifrado real con contraseña del usuario
- `ui/main_window.py`: Eliminado Fernet hardcodeado que rompía las conexiones
- `.env` mantiene texto plano (estándar de la industria para apps locales)

## 🚀 Auto-Updater

`services/updater.py` implementado con:
- `check_latest_version()`: Consulta GitHub Releases API via urllib (cache 5 min)
- `download_update()`: Descarga .exe en chunks con progreso
- `apply_update()`: Renombra a .update (abre GitHub en navegador - evita Windows Defender)

## 🧪 Tests (324 tests)

### Cobertura de tests
| Archivo | Tests | Estado |
|---------|-------|--------|
| test_engine.py | ~80 | ✅ |
| test_notifier.py | ~50 | ✅ |
| test_parser.py | 9 | ✅ |
| test_manager.py | 5 | ✅ |
| test_exchange_service.py | ~20 | ✅ |
| test_market_data.py | ~20 | ✅ |
| test_config_backup.py | ~15 | ✅ |
| test_settings_manager.py | ~15 | ✅ |
| test_helpers.py | ~10 | ✅ |
| test_logger.py | ~10 | ✅ |
| test_translations.py | ~15 | ✅ |
| test_config.py | ~10 | ✅ |
| test_data_classes.py | ~10 | ✅ |
| test_circuit_breaker.py | ~20 | ✅ |
| test_retry_service.py | ~15 | ✅ |
| test_health_monitor.py | ~10 | ✅ |
| test_decorators.py | ~10 | ✅ |

**Ejecutar:** `python -m pytest tests/ -v`

---

## 🚀 GitHub Actions

| Workflow | Trigger | Descripción |
|----------|---------|-------------|
| **tests.yml** | push/PR a master | Tests en Python 3.10, 3.11, 3.12 |
| **lint.yml** | push/PR a master | Flake8 + Mypy |
| **build.yml** | tag v* o manual | Compila EXE + Release |

### Para crear un Release:
```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## 📝 Formato de Señales Soportadas

El parser (`core/parser.py`) reconoce estos formatos de mensajes Telegram:

```
LONG #BTCUSDT
ENTRY: 65000
SL: 64000
Target 1: 66000
Target 2: 67000

SHORT #ETHUSDT
ENTRY: 3500
SL: 3600
TP1: 3400
TP2: 3300

BUY SOLUSDT
ENTRADA: 100-110
STOPLOSS: 95
TARGETS: 120, 130
```

**Reglas de parseo:**
- Símbolo: cualquier `#BTCUSDT`, `BTC/USDT`, `BTC-USDT`, `SOLUSDT`
- Dirección: `LONG`/`BUY` → Buy, `SHORT`/`SELL` → Sell
- Entry: valor único o rango (`100-110`)
- Targets: por línea (`Target 1:`, `TP1:`) o lista (`TARGETS: 66000, 67000`)
- Targets LONG se ordenan ascendente, SHORT descendente
- Targets duplicados se eliminan

---

### 🐛 Bugs Corregidos — Sesión 19/06/2026

#### v2.1.2 (3 bugs post-producción)

**Bug 1 🔴 — 40109: TP1 de Bitget nunca detectado**
| Item | Detalle |
|------|---------|
| **Síntoma** | Cada ~32s: `⚠️ Error fetching TP1 order for BAT: bitget {"code":"40109","msg":"The data of the order cannot be found"}` durante 2.5h |
| **Causa** | `_check_tp1_hit()` usaba `client.fetch_order()` que no funciona para plan orders de Bitget (necesitan `planType: 'normal_plan'`) |
| **Fix** | Nuevo método `fetch_plan_order()` en `exchange_service.py` que pasa `params={'planType': 'normal_plan'}` para Bitget. También `cancel_order()` ahora pasa el mismo param. Un solo cambio arregla 5 callers |

**Bug 2 🟡 — BingX setLeverage warning**
| Item | Detalle |
|------|---------|
| **Síntoma** | En cada trade: `⚠️ bingx: No se pudo configurar apalancamiento/margen: bingx setLeverage() requires a side argument` |
| **Causa** | `set_leverage()` pasaba `params['positionSide']` pero BingX requiere `params['side']` |
| **Fix** | Cambiado `positionSide` → `side` en `exchange_service.py:set_leverage()` |

**Bug 3 🟡 — Parser no filtraba mensajes de pérdida**
| Item | Detalle |
|------|---------|
| **Síntoma** | Mensaje de SL hit se ejecutó como orden de compra (AVAX comprado a 6.041 con SL en 6.15) |
| **Causa** | Parser detectaba `$AVAX/USDT` + `LONG` + `STOP LOSS` sin validar que era mensaje de cierre |
| **Fix** | Filtro `REJECT_PATTERNS` en `parser.py`: rechaza `% Loss`, `took this one out`, `Volatility across` |

**Mejora 🟢 — TPs antes que SL + Watchdog cancel SL/TP**
| Item | Detalle |
|------|---------|
| **Problema** | SL se colocaba primero (reduceOnly 100%) → TPs bloqueados por límite reduceOnly |
| **Fix** | TPs primero, SL después (Bitget sin reduceOnly). Watchdog cancela SL+TPs al cerrar posición |

#### v2.1.3 — Build fix + auto-update funcional

| Problema | Causa | Fix |
|----------|-------|-----|
| 🔴 **v2.1.2 .exe no abre** — `ImportError: cannot import name 'config_backup' from 'utils'` | Faltaban `__init__.py` en packages | Creados `__init__.py` vacíos en 5 directorios |
| 🟢 **Auto-update no funcionaba** | Repo era privado | Repo hecho público |

#### v2.1.4 — PyInstaller fix final (.exe funcional)

| Problema | Causa | Fix |
|----------|-------|-----|
| 🔴 **v2.1.3 .exe mismo error** — `cannot import name 'config_backup' from 'utils' (__init__.py)` | `__init__.py` vacíos — PyInstaller frozen importer no resuelve submodules sin import explícito | `utils/__init__.py`: `from . import config_backup` |
| 🔴 **SyntaxError en config_backup.py** | `return Falsedef import_config(...)` pegado sin newline | Newline añadido |

#### v2.1.7 — Auto-update sin Windows Defender

| Problema | Solución |
|----------|---------|
| 🔴 Windows Defender bloqueaba .bat y .ps1 | Abre GitHub Releases en navegador. Usuario descarga manualmente desde el navegador (confiable para Defender) |

#### v2.1.8/v2.1.9 — Auditoría de seguridad completa

| ID | Hallazgo | Fix |
|----|----------|-----|
| H-1 🔴 | `.env` en texto plano | Cifrado AES-256-GCM con MachineGuid + salt. Migración automática desde legacy |
| M-1 🟡 | Sesión Telegram cifrada con API_HASH directo | Clave derivada (API_HASH + MachineGuid). Fallback para sesiones legacy |
| M-2 🟡 | GitHub API sin cache (60 req/hora) | Cache de 5 min en check_latest_version() |
| M-3 🟡 | Número de teléfono visible en UI | Enmascarado a últimos 4 dígitos |
| L-1 🟢 | .exe descargado sin validación | _verify_exe(): tamaño >1MB + cabecera PE "MZ" |
| L-2 🟢 | API keys visibles en logs | SensitiveDataFilter: enmascara API_KEY, SECRET, PASSPHRASE en logs |

---

## 🐛 Deuda Técnica Pendiente

1. **Archivos legacy en raíz** — excluidos vía `.gitignore` pero existen en disco
2. **CoinGecko API gratuita** — Límite 10-30 llamadas/minuto
3. **Tests para updater.py y crypto.py** — faltan tests unitarios

---

## 📌 Próximos Pasos Sugeridos

- [x] Analizar log de producción (24h)
- [x] Fix 40109 Bitget plan orders
- [x] Fix BingX setLeverage
- [x] Fix parser: filtrar mensajes de pérdida
- [x] Mejora: TPs antes que SL + Watchdog cancel SL/TP
- [x] Fix build: __init__.py faltantes
- [x] Repo público + auto-update funcional
- [x] Auditoría seguridad completa (7/7 hallazgos)
- [x] Build .exe funcional + auto-update OK
- [x] Fix 40109 Bitget + BingX setLeverage + Parser REJECT_PATTERNS
- [ ] Activar más exchanges (Binance, Bybit, OKX)
- [ ] Tests para updater.py y crypto.py
- [ ] Gráficos en pestaña Reportes (matplotlib para PnL histórico)

---

## 🦸 Superpowers Framework

> **⚠️ REGLA ABSOLUTA: Este proyecto USA SUPERPOWERS. Toda IA — sea Claude, ChatGPT, Codebuff, Cline, Copilot, o cualquier otro agente — DEBE seguir este flujo en CADA sesión, sin excepción.**

### Flujo obligatorio para TODA IA en TODA sesión:

```
0. 🦊 PONYTAIL                → ✅ SIEMPRE ACTIVO (default: full). Capa transversal.
                                 ¿stdlib? ¿nativo? ¿dep existente? ¿una linea?
                                 Minimo codigo que funciona. YAGNI.
1. 🦸 CARGAR Superpowers      → Al INICIAR cualquier sesion con cualquier IA
                                 (skill: using-superpowers). Instalado via plugin
                                 oficial `obra/superpowers` en opencode.json
2. 📖 LEER contexto           → MEMORY.md + SESSION_HANDOFF.md + git log --oneline -5
3. 🧠 BRAINSTORMING           → Antes de cualquier cambio creativo o implementacion
4. 📄 WRITING SPECS           → Documentar en docs/superpowers/specs/
5. 📋 WRITING PLANS           → Para tareas de 3+ pasos en docs/superpowers/plans/
6. ⚡ SUBAGENT DEVELOPMENT    → Ejecutar con agentes especializados
7. 👀 CODE REVIEW             → Revisar cambios antes de finalizar (usar /ponytail-review)
8. ✅ VERIFICATION            → Tests + cobertura + calidad
9. 📝 ACTUALIZAR docs         → MEMORY.md + SESSION_HANDOFF.md + README si aplica
```

> **🔴 Esto aplica a: Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini, y cualquier otro agente/IA que toque este proyecto. La metodología Superpowers es el contrato de calidad del proyecto. Ignorarla = cambios inconsistentes y pérdida de contexto.**

### Skills disponibles (14 skills en `.agents/skills/`):

| Skill | Propósito |
|-------|-----------|
| `using-superpowers` | Skill base que activa toda la metodología |
| `brainstorming` | Análisis, preguntas y diseño colaborativo |
| `writing-plans` | Planificación estructurada con TDD |
| `test-driven-development` | Ciclo RED-GREEN-REFACTOR |
| `systematic-debugging` | Debugging de 4 fases con root cause |
| `subagent-driven-development` | Desarrollo con agentes + 2-stage review |
| `executing-plans` | Ejecución por lotes con checkpoints |
| `dispatching-parallel-agents` | Múltiples subagentes en paralelo |
| `requesting-code-review` | Pre-review checklist |
| `receiving-code-review` | Responder a feedback |
| `verification-before-completion` | Validación final antes de afirmar éxito |
| `using-git-worktrees` | Ramas de desarrollo aisladas |
| `finishing-a-development-branch` | Merge/PR workflow |
| `writing-skills` | Crear nuevos skills |

### Archivos de diseño:
- `docs/superpowers/specs/` — Especificaciones detalladas de features
- `docs/superpowers/plans/` — Planes de implementación

---

## 🔗 Enlaces

- **Repositorio:** https://github.com/juancito8812/botdetrading
- **Acciones:** https://github.com/juancito8812/botdetrading/actions
- **Releases:** https://github.com/juancito8812/botdetrading/releases

---

*Este archivo debe mantenerse actualizado con cada sesión de trabajo significativa.*