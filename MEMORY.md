# 🧠 Memoria del Proyecto — MiBotTrading

*Última actualización: 15/06/2026 (America/Caracas)*

---

## 📋 Resumen Ejecutivo

**MiBotTrading** es un bot de trading automatizado que escucha canales de Telegram en busca de señales de trading y ejecuta órdenes **LONG/SHORT** en exchanges de criptomonedas (actualmente **Bitget** y **BingX** activos).

### Stack Tecnológico
- **Lenguaje:** Python 3.10+
- **GUI:** Tkinter (interfaz de escritorio con 9 pestañas)
- **Exchanges:** CCXT (async) — Bitget, BingX, Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin
- **Telegram:** Telethon (cliente de usuario, no bot)
- **Async:** asyncio
- **Build:** PyInstaller + Inno Setup

### Estado Actual: ✅ Funcional y operativo
- [x] Conexión a Telegram y escucha de canales
- [x] Parseo de señales (símbolo, dirección, entradas, SL, targets)
- [x] Ejecución MARKET/LIMIT/DCA
- [x] Stop Loss + Take Profits personalizados
- [x] Trailing stop automático
- [x] Break-even automático al alcanzar TP1
- [x] Watchdog cada 30s (monitoreo y sincronización)
- [x] Persistencia de posiciones en disco
- [x] Interfaz gráfica completa
- [x] Tests unitarios (365 tests, 92% cobertura)
- [x] GitHub Actions (tests, lint, build)
- [x] Pre-commit hook Superpowers (valida MEMORY.md + SESSION_HANDOFF.md)
- [x] Repositorio en GitHub

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
│   └── MEMORY.md                  # Memoria para skills de IA (Cline/Codebuff)
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
│   └── market_data.py          # Datos de CoinGecko (top 20 + índices)
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

### Exchanges Activos
| Exchange | Estado | % Capital |
|----------|--------|-----------|
| Bitget | ✅ Activo | 1.0% |
| BingX | ✅ Activo | 0.1% |

---

## 🧪 Tests

### test_parser.py (9 tests)
- [x] `test_parse_long_signal` — Señal LONG básica
- [x] `test_parse_short_signal` — Señal SHORT básica
- [x] `test_parse_with_entry_range` — Rango de entrada
- [x] `test_parse_invalid_no_symbol` — Sin símbolo → None
- [x] `test_parse_invalid_no_direction` — Sin dirección → None
- [x] `test_parse_with_multiple_formats` — Múltiples formatos
- [x] `test_parse_targets_ordered_long` — Targets ascendentes
- [x] `test_parse_targets_ordered_short` — Targets descendentes
- [x] `test_parse_duplicate_targets` — Eliminar duplicados

### test_manager.py (5 tests)
- [x] `test_add_position` — Agregar posición
- [x] `test_get_open_positions` — Obtener abiertas por exchange
- [x] `test_update_status` — Actualizar estado
- [x] `test_get_pending_positions` — Obtener pendientes
- [x] `test_persistence` — Persistencia en disco

**Ejecutar:** `python -m pytest tests/ -v`

### Estado actual (15/06/2026)
| Métrica | Valor |
|---------|-------|
| Tests totales | **365** |
| Cobertura | **92%** |
| Módulos al 100% | 11 |
| Archivos de test | 20 |
| Pre-commit hook | ✅ `.githooks/pre-commit` |
| .exe | ✅ `dist/MiBotTrading.exe` (sin consola) |

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

## 🐛 Problemas Conocidos

1. **Archivos legacy en raíz** — `_fix_probar.py`, `_fix_probar2.py`, `_fix_probar3.py`, `_new_method.py`, `_fx.py`, `bot_unificado v2.py`, `backup_modulos/`, `legacy_code/` — Excluidos del repo vía `.gitignore`. Se pueden eliminar del disco manualmente.

2. **Credenciales no subidas** — `.env`, `config.json`, `canales.json`, `posiciones.json` están en `.gitignore`. Cada desarrollador debe crear su propio `.env`.

3. **Primer inicio** — Al ejecutar por primera vez, Telegram pedirá autenticación (código SMS + 2FA si aplica). La sesión se guarda en `telegram_session/`.

4. **Dependencia de CoinGecko** — El dashboard usa la API gratuita de CoinGecko, tiene límite de 10-30 llamadas/minuto.

---

## 📌 Próximos Pasos (Sugerencias)

- [ ] **Subir cobertura a 100%** — Actualmente 92%, engine.py tiene ~55 líneas no cubiertas
- [ ] Notificaciones por Telegram cuando se abra/cierre una posición
- [ ] Soporte para más exchanges (Binance, Bybit, etc.)
- [ ] Backtesting con señales históricas
- [ ] Dashboard con P&L en tiempo real y gráficos
- [ ] Logs rotativos (actualmente crecen sin límite)

---

## 🦸 Superpowers Framework

> **⚠️ REGLA ABSOLUTA: Este proyecto USA SUPERPOWERS. Toda IA — sea Claude, ChatGPT, Codebuff, Cline, Copilot, o cualquier otro agente — DEBE seguir este flujo en CADA sesión, sin excepción.**

### Flujo obligatorio para TODA IA en TODA sesión:

| # | Paso | Descripción |
|---|------|-------------|
| 1 | 🦸 **Cargar Superpowers** | Al INICIAR cualquier sesión con cualquier IA — cargar skill `using-superpowers` |
| 2 | 📖 **Leer contexto** | `MEMORY.md` + `SESSION_HANDOFF.md` + `git log --oneline -5` |
| 3 | 🧠 **Brainstorming** | Antes de cualquier cambio creativo o implementación |
| 4 | 📄 **Writing Specs** | Documentar lo que se va a hacer en `docs/superpowers/specs/` |
| 5 | 📋 **Writing Plans** | Para tareas de 3+ pasos, plan detallado en `docs/superpowers/plans/` |
| 6 | ⚡ **Subagent Development** | Ejecutar con agentes especializados (file-picker, basher, code-searcher, etc.) |
| 7 | 👀 **Code Review** | Revisar cambios con code-reviewer antes de finalizar |
| 8 | ✅ **Verification** | Tests + cobertura + calidad antes de afirmar completitud |
| 9 | 📝 **Actualizar docs** | Este archivo + `SESSION_HANDOFF.md` + `README.md` si aplica |

> **🔴 Esto aplica a: Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini, y cualquier otro agente/IA que toque este proyecto. La metodología Superpowers es el contrato de calidad del proyecto. Ignorarla = cambios inconsistentes y pérdida de contexto.**

### Skills disponibles:
Los skills están en `.agents/skills/`. Los principales:
- `using-superpowers` — Skill base que activa toda la metodología
- `brainstorming` — Análisis y exploración de opciones
- `writing-plans` — Planificación estructurada
- `subagent-driven-development` — Desarrollo con agentes especializados
- `requesting-code-review` — Revisión de calidad
- `verification-before-completion` — Validación final

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