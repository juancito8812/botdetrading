# Memoria del Proyecto: MiBotTrading

## Información General

- **Propósito:** Bot de trading automatizado que recibe señales vía Telegram y ejecuta órdenes en exchanges de criptomonedas (Bitget, BingX).
- **Stack:** Python 3.10+, Tkinter (GUI), CCXT (conexión exchanges), Telethon (Telegram), asyncio
- **Última sesión:** 11/06/2026 - Sesión inicial (configuración de memoria)
- **Versión de memoria:** 1

## Arquitectura

```
MiBotTrading/
├── main.py                    # Punto de entrada, TradingBotApp
├── config.json                # Configuración de riesgo
├── .env                       # Credenciales (API keys)
├── core/
│   ├── engine.py              # TradingEngine - ejecución de señales, SL/TP, DCA, trailing stop
│   ├── manager.py             # PositionManager - gestión y persistencia de posiciones
│   └── parser.py              # parse_trading_signal - parseo de mensajes Telegram
├── services/
│   ├── exchange_service.py    # ExchangeService - conexión CCXT con múltiples exchanges
│   └── market_data.py         # fetch_top20, fetch_market_indices (CoinGecko)
├── ui/
│   └── main_window.py         # TradingBotGUI - interfaz Tkinter (9 pestañas)
├── models/
│   └── data_classes.py        # Dataclasses: Position, Signal
├── utils/
│   ├── config.py              # Carga/guardado de config, credenciales, canales
│   ├── helpers.py             # Utilidades varias (atomic_write_json, patch_aiohttp_dns)
│   ├── logger.py              # Configuración de logging
│   ├── settings_manager.py    # Settings de UI + auto-inicio Windows
│   └── translations.py        # i18n español/inglés
├── tests/
│   ├── test_parser.py         # Tests del parseador de señales
│   └── test_manager.py        # Tests del gestor de posiciones
├── dist/                      # Archivos para distribución EXE
├── logs/                      # Logs de ejecución
└── telegram_session/          # Sesión de Telegram guardada
```

### Flujo de datos:
1. Telegram envía mensaje → `handler()` en main.py
2. `parse_trading_signal()` extrae símbolo, dirección, entradas, SL, targets
3. `TradingEngine.execute_signal()` orquesta la ejecución en cada exchange
4. Decide tipo de entrada (MARKET, LIMIT, DCA) basado en config y precio
5. Coloca orden + Stop Loss + Take Profits (distribución personalizada)
6. `PositionManager` guarda/recupera posiciones en `posiciones.json`
7. Watchdog cada 30s: monitorea órdenes LIMIT pendientes, trailing stop, breakeven, sincroniza estado

### Exchanges soportados:
- Habilitados: Bitget, BingX
- Configurados pero desactivados: Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin

## Decisiones Clave

- **[11/06/2026]** — Refactorización de código legacy monolítico a arquitectura modular con separación clara (core/, services/, ui/, utils/).
- **[11/06/2026]** — Implementación de entrada con modalidad auto/market/limit + DCA (órdenes escalonadas).
- **[11/06/2026]** — Trailing stop automático con activación por % de ganancia y distancia configurable.
- **[11/06/2026]** — Distribución personalizada de Take Profits (igual, progresivo con pesos configurables).
- **[11/06/2026]** — Persistencia de posiciones en %APPDATA%/MiBotTrading/ para entorno EXE.

## Estado Actual

- **Lo que se está trabajando:** Mantenimiento general y mejoras continuas
- **Exchanges activos en config.json:** bitget, bingx
- **Apalancamiento:** 5x
- **Modo margen:** Cross
- **Cantidad mínima:** 2.0 USDT
- **Entrada:** Auto (con validación de desviación máx 3%)
- **DCA:** Habilitado (3 partes)
- **Trailing stop:** Habilitado (activación 1.5%, distancia 0.8%)

## Cambios Recientes

- **[11/06/2026]** — Inicialización estructura modular completa y funcional.
- **[11/06/2026]** — Subido a GitHub: https://github.com/juancito8812/botdetrading.git

## Próximos Pasos / TODOs

- [ ] Determinar próximas mejoras/siguientes pasos con el usuario

## Notas / Problemas Conocidos

- Archivos temporales/legacy excluidos vía `.gitignore`: `_fix_probar.py`, `_fix_probar2.py`, `_fix_probar3.py`, `_new_method.py`, `_fx.py`, `bot_unificado v2.py`, `backup_modulos/`, `legacy_code/` — no se subieron al repositorio.
- Repositorio GitHub inicializado: https://github.com/juancito8812/botdetrading.git (rama master).
- Tests de parser y manager pasan correctamente.
- Credenciales (.env, config.json, canales.json) excluidas del repositorio por seguridad.
