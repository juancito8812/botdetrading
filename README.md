# 🤖 MiBotTrading

Bot de trading automatizado para criptomonedas con señales vía Telegram. Ejecuta órdenes **LONG/SHORT** en múltiples exchanges con gestión inteligente de riesgo.

## ✨ Características

- **📡 Señales vía Telegram**: Escucha canales de Telegram y parsea señales de trading automáticamente
- **⚡ Múltiples Exchanges**: Soporte para Bitget, BingX, Binance, Bybit, OKX, KuCoin, MEXC, Phemex, Blofin
- **🎯 Entradas Inteligentes**: Modalidad Auto/Market/Limit con validación de precio y desviación máxima
- **📊 DCA Automático**: Órdenes escalonadas para mejor precio de entrada
- **🛡️ Gestión de Riesgo**: Stop Loss, Take Profits personalizados (distribución igual/progresivo)
- **🔝 Trailing Stop**: Seguimiento automático del stop loss cuando el precio se mueve a favor
- **🔄 Break-even Automático**: Mueve el SL al precio de entrada cuando se alcanza el primer TP
- **🖥️ Interfaz Gráfica**: Dashboard con monitoreo en tiempo real, balances, posiciones y logs
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
Agrega los IDs de los canales de señales desde la interfaz o editando `canales.json`.

### 3. Configuración de Riesgo (`config.json`)
Ajusta apalancamiento, % de capital, modalidad de entrada, DCA, trailing stop, etc.

## 🖥️ Uso

```bash
python main.py
```

La interfaz gráfica se abrirá con las siguientes pestañas:
- **Dashboard**: Top 20 criptomonedas e índices de mercado (CoinGecko)
- **APIs**: Configuración de credenciales de exchanges y Telegram
- **Riesgo**: Apalancamiento, márgenes, DCA, trailing stop, distribución de TPs
- **Canales**: Gestión de canales de Telegram
- **Test**: Probar conexión con exchanges
- **Posiciones**: Ver posiciones abiertas/cerradas
- **Saldos**: Balances en USDT por exchange
- **Consola**: Logs en tiempo real y botón de iniciar/detener

## 🏗️ Arquitectura

```
MiBotTrading/
├── main.py                 # Punto de entrada
├── core/                   # Lógica principal
│   ├── engine.py           # Motor de trading
│   ├── manager.py          # Gestor de posiciones
│   └── parser.py           # Parseo de señales
├── services/               # Servicios externos
│   ├── exchange_service.py # Conexión con exchanges (CCXT)
│   └── market_data.py      # Datos de mercado (CoinGecko)
├── ui/                     # Interfaz de usuario
│   └── main_window.py      # GUI con Tkinter
├── models/                 # Modelos de datos
│   └── data_classes.py     # Signal, Position
├── utils/                  # Utilidades
│   ├── config.py           # Carga/guardado de config
│   ├── helpers.py          # Funciones auxiliares
│   ├── logger.py           # Logging
│   ├── settings_manager.py # Configuración de UI
│   └── translations.py     # i18n
└── tests/                  # Tests
    ├── test_parser.py
    └── test_manager.py
```

## 📦 Distribución

Para generar un ejecutable independiente:

```bash
pyinstaller MiBotTrading.spec
```

El instalador para Windows se genera con Inno Setup usando `Installer_Script.iss`.

## 🧪 Tests

```bash
python tests/test_parser.py
python tests/test_manager.py
```

## 📄 Licencia

Este proyecto es de uso privado.