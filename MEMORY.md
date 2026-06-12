# 🧠 Memoria del Proyecto — MiBotTrading

*Última actualización: 11/06/2026 11:04 PM (America/Caracas)*

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
- [x] Tests unitarios (parser + manager)
- [x] GitHub Actions (tests, lint, build)
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
├── .gitignore
│
├── .agents/
│   └── MEMORY.md               # Memoria para skills de IA (Cline/Codebuff)
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

**Ejecutar:** `python tests/test_parser.py && python tests/test_manager.py`

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

- [ ] Notificaciones por Telegram cuando se abra/cierre una posición
- [ ] Soporte para más exchanges (Binance, Bybit, etc.)
- [ ] Backtesting con señales históricas
- [ ] Dashboard con P&L en tiempo real y gráficos
- [ ] Órdenes OCO (One Cancels Other)
- [ ] Alertas de precio y trailing stop por Telegram
- [ ] Logs rotativos (actualmente crecen sin límite)
- [ ] Modo simulación/paper trading

---

## 🔗 Enlaces

- **Repositorio:** https://github.com/juancito8812/botdetrading
- **Acciones:** https://github.com/juancito8812/botdetrading/actions
- **Releases:** https://github.com/juancito8812/botdetrading/releases

---

*Este archivo debe mantenerse actualizado con cada sesión de trabajo significativa.*