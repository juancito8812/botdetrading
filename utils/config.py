import os
import json
import logging
from dotenv import load_dotenv, set_key
from utils.helpers import atomic_write_json, BASE_DIR, DATA_DIR

# Archivos de configuración (se leen desde BASE_DIR, junto al .exe)
ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = BASE_DIR / "config.json"
CANALES_FILE = BASE_DIR / "canales.json"

# Archivos de datos (se escriben en DATA_DIR = %APPDATA%/MiBotTrading)
POSICIONES_FILE = DATA_DIR / "posiciones.json"
LOG_FILE = DATA_DIR / "log_bot.txt"
LOGS_DIR = DATA_DIR / "logs"

# Asegurar que los directorios de datos existen
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

EXCHANGES_DEFAULTS = {
    "binance": {"name": "Binance", "needs_passphrase": False, "default_type": "future"},
    "bybit": {"name": "Bybit", "needs_passphrase": False, "default_type": "linear"},
    "bitget": {"name": "Bitget", "needs_passphrase": True, "default_type": "swap"},
    "bingx": {"name": "BingX", "needs_passphrase": False, "default_type": "swap"},
    "okx": {"name": "OKX", "needs_passphrase": True, "default_type": "swap"},
    "kucoin": {"name": "KuCoin", "needs_passphrase": True, "default_type": "future"},
    "mexc": {"name": "MEXC", "needs_passphrase": False, "default_type": "swap"},
    "phemex": {"name": "Phemex", "needs_passphrase": False, "default_type": "swap"},
    "blofin": {"name": "Blofin", "needs_passphrase": False, "default_type": "swap"},
}

def load_api_creds():
    load_dotenv(ENV_FILE)
    def _clean(v):
        if v is None: return ""
        v = str(v).strip()
        if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
            return v[1:-1]
        return v

    creds = {"exchanges": {}, "telegram": {}}
    for ex in EXCHANGES_DEFAULTS:
        creds["exchanges"][ex] = {
            "api_key": _clean(os.getenv(f"{ex.upper()}_API_KEY", "")),
            "secret": _clean(os.getenv(f"{ex.upper()}_SECRET", "")),
            "passphrase": _clean(os.getenv(f"{ex.upper()}_PASSPHRASE", "")) if EXCHANGES_DEFAULTS[ex]["needs_passphrase"] else "",
            "enabled": _clean(os.getenv(f"{ex.upper()}_ENABLED", "false")).lower() == "true"
        }
    
    creds["telegram"] = {
        "API_ID": _clean(os.getenv("API_ID", "")),
        "API_HASH": _clean(os.getenv("API_HASH", "")),
        "PHONE_NUMBER": _clean(os.getenv("PHONE_NUMBER", ""))
    }
    return creds

def save_api_creds(creds):
    for ex, data in creds["exchanges"].items():
        set_key(str(ENV_FILE), f"{ex.upper()}_API_KEY", data["api_key"])
        set_key(str(ENV_FILE), f"{ex.upper()}_SECRET", data["secret"])
        if EXCHANGES_DEFAULTS[ex]["needs_passphrase"]:
            set_key(str(ENV_FILE), f"{ex.upper()}_PASSPHRASE", data["passphrase"])
        set_key(str(ENV_FILE), f"{ex.upper()}_ENABLED", "true" if data["enabled"] else "false")
    
    tg = creds["telegram"]
    set_key(str(ENV_FILE), "API_ID", tg["API_ID"])
    set_key(str(ENV_FILE), "API_HASH", tg["API_HASH"])
    set_key(str(ENV_FILE), "PHONE_NUMBER", tg["PHONE_NUMBER"])

def load_risk_config():
    if not CONFIG_FILE.exists():
        return _get_default_risk_config()
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            # Asegurar campos mínimos
            defaults = _get_default_risk_config()
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return _get_default_risk_config()

def _get_default_risk_config():
    return {
        "apalancamiento": 10,
        "porcentaje_capital": {ex: 5.0 for ex in EXCHANGES_DEFAULTS},
        "cooldown_segundos": 30,
        "cantidad_minima_usdt": 10.0,
        "exchanges_activos": [],
        "limite_posiciones": 0,
        "modo_margen": "cross",
        "tp_count": 5,
        "auto_breakeven": True,
        "requerir_stop_loss": True,
        # Mejoras de entrada
        "entrada_modalidad": "auto",          # "market", "limit", "auto"
        "desviacion_maxima_porcentaje": 3.0,  # Rechazar si precio está >X% del rango
        "timeout_orden_limit_minutos": 10,    # Cancelar orden LIMIT si no se llena
        "dca_habilitado": True,               # Múltiples entradas escalonadas
        "dca_partes": 3,                      # En cuántas partes dividir
        # Trailing stop
        "trailing_stop_habilitado": True,
        "trailing_activacion_porcentaje": 1.5,  # % ganancia para activar trailing
        "trailing_distancia_porcentaje": 0.8,   # % de retroceso desde el máximo
        # TPs personalizados
        "tp_distribucion": "progresivo",     # "igual", "progresivo", "personalizado"
        "tp_pesos": [50, 25, 15, 10],        # % por TP (progresivo)
    }

def save_risk_config(config):
    atomic_write_json(CONFIG_FILE, config, indent=2)

def load_channels():
    if not CANALES_FILE.exists(): return set()
    try:
        with open(CANALES_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_channels(channels_set):
    atomic_write_json(CANALES_FILE, list(channels_set))
