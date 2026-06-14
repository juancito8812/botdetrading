# 🤖 MiBotTrading

<div align="center">

![Tests](https://github.com/juancito8812/botdetrading/actions/workflows/tests.yml/badge.svg?branch=master)
![Lint](https://github.com/juancito8812/botdetrading/actions/workflows/lint.yml/badge.svg?branch=master)
![Build](https://github.com/juancito8812/botdetrading/actions/workflows/build.yml/badge.svg)
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
- **📱 Telegram Unificado**: Conexión, credenciales, canales e historial de notificaciones en una pestaña
- **🛡️ Sistema de Resiliencia**: Circuit breaker, health monitor, retry con backoff, state recovery y backups automáticos
- **🔔 Notificaciones**: Alertas por Telegram de apertura/cierre de trades, TP alcanzados, trailing, salud y errores
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
- **📈 Dashboard**: Top 20 criptomonedas, índices de mercado y salud de exchanges
- **📱 Telegram**: Estado de conexión, credenciales, canales e historial de notificaciones
- **📊 Reportes**: Resumen general (win rate, PnL), performance por exchange e historial de trades
- **🔐 APIs**: Configuración de API keys de exchanges
- **⚖️ Riesgo**: Apalancamiento, márgenes, DCA, trailing stop, distribución de TPs
- **🔌 Test**: Probar conexión con exchanges
- **📊 Posiciones**: Ver posiciones abiertas con PnL
- **📟 Consola**: Logs en tiempo real y botón de iniciar/detener
- **⚙️ Ajustes**: Idioma e inicio automático con Windows

## 🦸 Metodología de Desarrollo: Superpowers

Este proyecto utiliza el framework **Superpowers** para mantener consistencia entre sesiones de IA y agentes.

### Flujo obligatorio para cualquier IA o agente:

1. **`using-superpowers`** — Al iniciar cada sesión, cargar este skill primero
2. **`brainstorming`** — Antes de cualquier cambio creativo o implementación
3. **`writing-plans`** — Para tareas de 3+ pasos, escribir plan detallado
4. **`subagent-driven-development`** — Ejecutar tareas con agentes especializados
5. **`requesting-code-review`** — Revisar cambios antes de finalizar
6. **`verification-before-completion`** — Verificar tests y calidad antes de afirmar completitud

> **⚠️ Importante:** Todo agente de IA que retome este proyecto DEBE cargar el skill `using-superpowers` al inicio de cada sesión y seguir el flujo completo.

### Skills disponibles:
`.agents/skills/` contiene: brainstorming, writing-plans, subagent-driven-development, test-driven-development, systematic-debugging, requesting-code-review, verification-before-completion, entre otros.

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
├── tests/                      # ★ TESTS (72 tests)
│   ├── test_parser.py
│   ├── test_manager.py
│   ├── test_notifier.py
│   └── ... (resiliencia, decoradores, etc.)
├── docs/superpowers/           # ★ DOCUMENTACIÓN DE DISEÑO
│   ├── specs/                  # Especificaciones de features
│   └── plans/                  # Planes de implementación
└── .agents/                    # ★ SKILLS DE IA
    ├── MEMORY.md               # Memoria persistente del proyecto
    └── skills/                 # Skills Superpowers
```

## 📦 Distribución

Para generar un ejecutable independiente:

```bash
pyinstaller MiBotTrading.spec
```

El instalador para Windows se genera con Inno Setup usando `Installer_Script.iss`.

## 🧪 Tests

```bash
# Todos los tests (72)
python -m pytest tests/ -v

# Tests específicos
python -m pytest tests/test_parser.py -v
python -m pytest tests/test_notifier.py -v
```

## 🤖 GitHub Actions

| Workflow | Trigger | Descripción |
|----------|---------|-------------|
| **tests.yml** | push/PR a master | Tests en Python 3.10, 3.11, 3.12 |
| **lint.yml** | push/PR a master | Flake8 + Mypy |
| **build.yml** | tag v* o manual | Compila .exe con PyInstaller |

## 📄 Licencia

Este proyecto es de uso privado.