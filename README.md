# 🤖 MiBotTrading

<div align="center">

![Tests](https://github.com/juancito8812/botdetrading/actions/workflows/tests.yml/badge.svg?branch=master)
![Lint](https://github.com/juancito8812/botdetrading/actions/workflows/lint.yml/badge.svg?branch=master)
![Build](https://github.com/juancito8812/botdetrading/actions/workflows/build.yml/badge.svg)
[![Coverage](https://codecov.io/gh/juancito8812/botdetrading/branch/master/graph/badge.svg)](https://codecov.io/gh/juancito8812/botdetrading)
![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12-blue)
![License](https://img.shields.io/badge/Licencia-Privado-red)
![Last Commit](https://img.shields.io/github/last-commit/juancito8812/botdetrading)

</div>

Bot de trading automatizado para criptomonedas con señales vía Telegram. Ejecuta órdenes **LONG/SHORT** en múltiples exchanges con gestión inteligente de riesgo.

## ✨ Características

- **📡 Señales vía Telegram**: Escucha canales de Telegram y parsea señales de trading automáticamente
- **⚡ Múltiples Exchanges**: Soporte para Bitget, BingX, Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin
- **🎯 Entradas Inteligentes**: Modalidad Auto/Market/Limit con validación de precio y desviación máxima
- **📊 DCA Automático**: Órdenes escalonadas para mejor precio de entrada
- **🛡️ Gestión de Riesgo**: Stop Loss, Take Profits personalizados (distribución igual/progresivo)
- **🔝 Trailing Stop**: Seguimiento automático del stop loss cuando el precio se mueve a favor
- **🔄 Break-even Automático**: Mueve el SL al precio de entrada cuando se alcanza el primer TP
- **🖥️ Dashboard**: Top 20 criptomonedas, índices de mercado y salud de exchanges en tiempo real
- **📊 Reportes**: Resumen de trading, performance por exchange e historial de trades
- **📱 Telegram Unificado**: Conexión, credenciales, canales, historial de notificaciones y **Chat ID configurable desde la UI** en una pestaña
- **📊 PnL en Tiempo Real**: Cálculo de ganancia/pérdida desde el exchange en cada ciclo del watchdog
- **💾 Backup Cifrado**: Export/Import de toda la configuración en archivo .botconfig protegido con contraseña (AES)
- **🛡️ Sistema de Resiliencia**: Circuit breaker, health monitor (cada 60s), retry con backoff, state recovery y backups automáticos
- **🔔 Notificaciones seleccionables**: Elige qué alertas quieres recibir (apertura/cierre, TP, trailing, errores, etc.) desde la UI
- **❔ Tooltips de ayuda**: Cada campo de configuración (Riesgo, Ajustes, APIs) tiene un botón ❔ con descripción detallada
- **⚡ Inicio automático**: El bot arranca con Windows y se conecta automáticamente al abrir la app — sin necesidad del botón INICIAR
- **🌐 Multi-idioma**: Español e Inglés

## 🚀 Instalación

```bash
# Clonar repositorio
git clone https://github.com/juancito8812/botdetrading.git
cd MiBotTrading

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

## ⚙️ Configuración

### 1. Credenciales (`.env`)
Copia el archivo `.env.example` a `.env` y completa:

```env
# Telegram
API_ID=tu_api_id
API_HASH=tu_api_hash
PHONE_NUMBER=+584241234567

# Exchanges (ejemplo con Bitget y BingX)
BITGET_API_KEY=...
BITGET_SECRET=...
BITGET_PASSPHRASE=...
BITGET_ENABLED=true

BINGX_API_KEY=...
BINGX_SECRET=...
BINGX_ENABLED=true
```

### 2. Canales de Telegram
Agrega los IDs de los canales de señales desde la pestaña **📱 Telegram** o editando `canales.json`.

### 3. Configuración de Riesgo (`config.json`)
Ajusta apalancamiento, % de capital, modalidad de entrada, DCA, trailing stop, etc.

## 🖥️ Uso

```bash
python main.py
```

La interfaz gráfica se abrirá con las siguientes pestañas:
- **📈 Dashboard**: Top 20 criptomonedas, índices de mercado y salud de exchanges — auto-carga al iniciar + auto-refresh cada 60s
- **📱 Telegram**: Estado de conexión, credenciales, canales, historial de notificaciones, **Chat ID** y **checkbox de notificaciones seleccionables** (elige qué alertas recibir)
- **📊 Reportes**: Resumen general (win rate, PnL), performance por exchange e historial de trades + export CSV
- **🔐 APIs**: Configuración de API keys de exchanges — todos con ❔ tooltip de ayuda
- **⚖️ Riesgo**: Apalancamiento, márgenes, DCA, trailing stop, distribución de TPs — todos con ❔ tooltip de ayuda
- **🔌 Test**: Probar conexión con exchanges
- **📊 Posiciones**: Posiciones activas con PnL, modificar SL/TP, cerrar posición, export CSV
- **📟 Consola**: Logs en tiempo real y botón de iniciar/detener
- **⚙️ Ajustes**: Idioma, auto-inicio Windows y backup/restore de configuración

## 🦸 Metodología de Desarrollo: Superpowers

> **⚠️ REGLA ABSOLUTA: Este proyecto USA SUPERPOWERS. Toda IA — sea Claude, ChatGPT, Codebuff, Cline, Copilot, o cualquier otro agente — DEBE seguir este flujo en CADA sesión, sin excepción.**

Este proyecto utiliza el framework **Superpowers** para mantener consistencia absoluta entre sesiones de IA, independientemente del modelo o herramienta que se esté usando.

### Flujo obligatorio para TODA IA en TODA sesión:

```
1. 🦸 Cargar Superpowers    → Al INICIAR cualquier sesión con cualquier IA
2. 📖 Leer contexto          → MEMORY.md + SESSION_HANDOFF.md + git log
3. 🧠 Brainstorming          → Antes de cualquier cambio creativo o implementación
4. 📄 Writing Specs          → Documentar lo que se va a hacer
5. 📋 Writing Plans          → Para tareas de 3+ pasos, plan detallado
6. ⚡ Subagent Development   → Ejecutar con agentes especializados
7. 👀 Code Review            → Revisar cambios antes de finalizar
8. ✅ Verification           → Tests + cobertura + calidad antes de completar
9. 📝 Actualizar docs        → MEMORY.md + SESSION_HANDOFF.md + README si aplica
```

> **🔴 Esto aplica a: Claude, ChatGPT, Codebuff, Cline, Copilot, Gemini, y cualquier otro agente/IA que toque este proyecto. Si es una IA trabajando en este código, DEBE seguir Superpowers.**

### Skills disponibles:
`.agents/skills/` contiene: `using-superpowers`, `brainstorming`, `writing-plans`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `requesting-code-review`, `verification-before-completion`, entre otros.

## 🏗️ Arquitectura

```
MiBotTrading/
├── main.py                     # Punto de entrada — TradingBotApp
├── core/                       # ★ LÓGICA PRINCIPAL
│   ├── engine.py               # TradingEngine — orquestación de señales + watchdog
│   ├── manager.py              # PositionManager — gestión de posiciones con resiliencia
│   └── parser.py               # parse_trading_signal — parseo de señales Telegram
├── services/                   # ★ SERVICIOS EXTERNOS
│   ├── exchange_service.py     # ExchangeService — conexión con exchanges vía CCXT async
│   ├── market_data.py          # Datos de CoinGecko (top 20 + índices)
│   └── notifier.py             # TelegramNotifier — 10 métodos de notificación
├── ui/                         # ★ INTERFAZ DE USUARIO
│   └── main_window.py          # TradingBotGUI — Tkinter (9 pestañas)
├── models/                     # ★ MODELOS DE DATOS
│   └── data_classes.py         # Position, Signal (dataclasses)
├── utils/                      # ★ UTILIDADES
│   ├── config.py               # Carga/guardado de config, credenciales, canales
│   ├── helpers.py              # atomic_write_json, patch_aiohttp_dns
│   ├── logger.py               # Configuración de logging
│   ├── settings_manager.py     # Settings de UI + auto-inicio Windows
│   ├── translations.py         # i18n — español/inglés (120+ claves)
│   └── resilience/             # ★ SISTEMA DE RESILIENCIA
│       ├── circuit_breaker.py  # Circuit breaker por exchange
│       ├── retry_service.py    # Retry con backoff exponencial
│       ├── health_monitor.py   # Monitoreo de salud de exchanges
│       ├── state_recovery.py   # Checkpoints para recuperación de estado
│       ├── backup_manager.py   # Backups comprimidos automáticos
│       ├── error_handler.py    # Manejo centralizado de errores
│       └── decorators.py       # Decoradores @retry, @circuit_breaker, @log_errors
├── utils/
│   ├── config_backup.py        # Export/Import cifrado con AES (cryptography.fernet)
├── MiBotTrading.spec           # Spec de PyInstaller para compilar .exe
├── tests/                      # ★ TESTS (348 tests · 87% cobertura)
│   ├── test_parser.py          # Parseo de señales
│   ├── test_config_backup.py   # Cifrado/descifrado, round-trip, errores (100%)
│   ├── test_manager.py         # PositionManager — persistencia, estados
│   ├── test_notifier.py        # TelegramNotifier (99%)
│   ├── test_engine.py          # TradingEngine — SL, TP, DCA, trailing, breakeven, limits
│   ├── test_exchange_service.py# ExchangeService — CCXT clients (97%)
│   ├── test_settings_manager.py# Settings — idioma, autostart Windows (100%)
│   ├── test_market_data.py     # CoinGecko caché, 429, timeout (94%)
│   ├── test_health_monitor.py  # HealthMonitor — sync CB, persist, start/stop (91%)
│   ├── test_helpers.py         # atomic_write_json, patch_aiohttp_dns (95%)
│   ├── test_state_recovery.py  # Checkpoints, load, persist (99%)
│   ├── test_backup_manager.py  # Backups rotativos gzip (95%)
│   └── ... (resiliencia, decoradores, data_classes, translations, logger, config)
├── docs/superpowers/           # ★ DOCUMENTACIÓN DE DISEÑO
│   ├── specs/                  # Especificaciones de features (tooltips, notif prefs, etc.)
│   └── plans/                  # Planes de implementación
└── .agents/                    # ★ SKILLS DE IA
    ├── MEMORY.md               # Memoria persistente del proyecto
    └── skills/                 # Skills Superpowers
```

## 💾 Backup de Configuración

Desde la pestaña **⚙️ Ajustes** puedes exportar/importar toda la configuración:

- **📤 Exportar**: Cifra API keys, riesgo, canales y ajustes en un archivo `.botconfig` protegido con contraseña
- **📥 Importar**: Restaura toda la configuración desde un `.botconfig` existente
- **🛡️ Cifrado AES** vía `cryptography.fernet` con derivación PBKDF2 (SHA256, 100k iteraciones)

```bash
# Dependencia adicional (ya incluida en requirements.txt)
pip install cryptography
```

## 📦 Distribución

Para generar un ejecutable independiente:

```bash
pyinstaller MiBotTrading.spec
```

El instalador para Windows se genera con Inno Setup usando `Installer_Script.iss`.

## 🧪 Tests

```bash
# Todos los tests (348)
python -m pytest tests/ -v

# Cobertura local
python -m pytest tests/ --cov=core --cov=models --cov=services --cov=utils --cov-report=term

# Tests específicos
python -m pytest tests/test_parser.py -v
python -m pytest tests/test_notifier.py -v
python -m pytest tests/test_engine.py -v
python -m pytest tests/test_exchange_service.py -v
```

### 📊 Cobertura actual (87%)

| Módulo | Cobertura |
|--------|-----------|
| `models/data_classes.py` | 100% |
| `utils/config_backup.py` | 100% |
| `utils/config.py` | 100% |
| `utils/logger.py` | 100% |
| `utils/settings_manager.py` | 100% |
| `core/parser.py` | 100% |
| `utils/resilience/error_handler.py` | 100% |
| `services/notifier.py` | 99% |
| `utils/resilience/state_recovery.py` | 99% |
| `services/exchange_service.py` | 97% |
| `utils/helpers.py` | 95% |
| `services/market_data.py` | 94% |
| `utils/resilience/health_monitor.py` | 91% |
| `utils/resilience/circuit_breaker.py` | 90% |
| **TOTAL** | **87%** |

## 🤖 GitHub Actions

| Workflow | Trigger | Descripción |
|----------|---------|-------------|
| **tests.yml** | push/PR a master | Tests en Python 3.10, 3.11, 3.12 + cobertura con Codecov |
| **lint.yml** | push/PR a master | Flake8 + Mypy |
| **build.yml** | tag v* o manual | Compila .exe con PyInstaller |

### 📊 Cobertura de código

El workflow **tests.yml** genera automáticamente un reporte de cobertura con `pytest-cov` y lo sube a [Codecov](https://codecov.io).

**Para activar el badge de cobertura:**
1. Ve a [codecov.io](https://codecov.io) e inicia sesión con tu cuenta de GitHub
2. Agrega el repositorio `juancito8812/botdetrading`
3. Copia el token de Codecov y agrégalo como `CODECOV_TOKEN` en los secrets del repositorio (Settings → Secrets and variables → Actions)
4. El badge se actualizará automáticamente en el próximo push a master

## 🔧 Bug Fixes (14/06/2026 — Sesión de estabilización pre-operaciones reales)

### Bugs críticos pre-operaciones (sesión anterior)

| # | Bug | Fix | Archivo |
|---|-----|-----|---------|
| 🔴 | **HealthMonitor solo se ejecutaba una vez** | Se ejecuta cada 60s dentro del watchdog con time-check | `core/engine.py` |
| 🔴 | **PnL nunca calculado** | Se calcula desde `unrealizedPnl` del exchange o fórmula manual | `core/engine.py` |
| 🟡 | **Event loop no cerrado en error** | `loop.close()` dentro de `try/finally` | `ui/main_window.py` |
| 🟡 | **Indentación extraña** | Formateado | `ui/main_window.py` |
| 🟢 | **Language change sin backup** | `_update_backup_status()` en change handler | `ui/main_window.py` |
| 🟢 | **Re-imports redundantes** | Eliminados | `ui/main_window.py` |

### Bugs corregidos en esta sesión (14/06/2026)

| # | Bug | Fix | Archivo |
|---|-----|-----|---------|
| 🔴 | **Telegram entity '1399591912' no encontrada** — `send_message()` fallaba con string en vez de int | `chat_id` se convierte a `int` si es string numérico | `services/notifier.py` |
| 🟡 | **CoinGecko 429 constante** — Cada refresco llamaba sin caché | Caché con TTL de 60s + manejo de 429 y timeout | `services/market_data.py` |
| 🔴 | **Event loop is closed (CCXT)** — Clientes de exchange perdían referencia al loop | `_ensure_event_loop()` recrea client automáticamente | `services/exchange_service.py` |
| 🔴 | **Retry reintentaba RuntimeError** — Errores fatales se reintentaban en vano | `_never_retry` con `RuntimeError` y `CancelledError` | `utils/resilience/retry_service.py` |
| 🔴 | **Event loop must not change (Telegram)** — Telethon detectaba cambio de loop al reconectar | Cliente Telegram se crea UNA vez, reconexiones usan `connect()` + `start()` en el mismo cliente | `main.py` (refactor completo) |
| 🟡 | **Notifier crash en Windows** — `disconnect()` rompía IOCP de Windows | Solo loguea warning sin manipular conexión | `services/notifier.py` |
| 🟢 | **Nuevo: Chat ID configurable desde UI** — Antes solo se podía cambiar en `.env` | Campo Entry + botón Guardar en pestaña 📱 Telegram, guarda en `settings.json` | `ui/main_window.py`, `main.py`, `utils/translations.py` |

## 📄 Licencia

Este proyecto es de uso privado.