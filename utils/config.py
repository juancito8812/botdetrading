import os
import json
import io
import logging
import shutil
from pathlib import Path
from dotenv import load_dotenv, set_key
from utils.helpers import atomic_write_json, BASE_DIR, DATA_DIR
from utils.crypto import encrypt as _crypto_encrypt, decrypt as _crypto_decrypt

logger = logging.getLogger("TradingBot")

# Archivos de configuración (se leen desde DATA_DIR)
ENV_FILE = BASE_DIR / ".env"
ENV_ENCRYPTED = BASE_DIR / ".env.encrypted"
ENV_SALT_FILE = BASE_DIR / ".env.salt"
CONFIG_FILE = DATA_DIR / "config.json"
CANALES_FILE = DATA_DIR / "canales.json"

# Archivos de datos (se escriben en DATA_DIR = %APPDATA%/MiBotTrading)
POSICIONES_FILE = DATA_DIR / "posiciones.json"
LOG_FILE = DATA_DIR / "log_bot.txt"
LOGS_DIR = DATA_DIR / "logs"


def init_dirs():
    """Crea los directorios necesarios para datos y logs."""
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

def _get_env_key() -> str:
    """
    Deriva una clave de cifrado para el .env.
    Usa MachineGuid de Windows (estable por instalación) + salt único.
    """
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        machine_id, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
    except Exception:
        import uuid
        machine_id = str(uuid.getnode())

    # Salt único por instalación (se crea en el primer guardado cifrado)
    if ENV_SALT_FILE.exists():
        salt = ENV_SALT_FILE.read_text(encoding="utf-8").strip()
    else:
        salt = os.urandom(16).hex()
        ENV_SALT_FILE.write_text(salt, encoding="utf-8")

    return f"{machine_id}::{salt}"


def _load_env_to_memory():
    """Carga .env cifrado o legacy a os.environ. Retorna True si hay credenciales."""
    if ENV_ENCRYPTED.exists():
        key = _get_env_key()
        encrypted = ENV_ENCRYPTED.read_text(encoding="utf-8")
        plaintext = _crypto_decrypt(key, encrypted)
        if plaintext:
            load_dotenv(stream=io.StringIO(plaintext))
            return True
        logger.warning("No se pudo descifrar .env.encrypted (¿cambio de hardware?)")
        return False
    elif ENV_FILE.exists():
        load_dotenv(ENV_FILE)
        return True
    return False


def _env_lines_from_creds(creds: dict) -> list:
    """Convierte el dict de credenciales a líneas de .env."""
    lines = []
    for ex, data in creds.get("exchanges", {}).items():
        api_key = data.get("api_key", "")
        secret = data.get("secret", "")
        enabled = data.get("enabled", False)
        if api_key or secret:
            lines.append(f"{ex.upper()}_API_KEY={api_key}")
            lines.append(f"{ex.upper()}_SECRET={secret}")
            if EXCHANGES_DEFAULTS.get(ex, {}).get("needs_passphrase"):
                pp = data.get("passphrase", "")
                if pp:
                    lines.append(f"{ex.upper()}_PASSPHRASE={pp}")
            lines.append(f"{ex.upper()}_ENABLED={'true' if enabled else 'false'}")

    tg = creds.get("telegram", {})
    tg_api_id = tg.get("API_ID", "")
    tg_hash = tg.get("API_HASH", "")
    tg_phone = tg.get("PHONE_NUMBER", "")
    if tg_api_id:
        lines.append(f"API_ID={tg_api_id}")
    if tg_hash:
        lines.append(f"API_HASH={tg_hash}")
    if tg_phone:
        lines.append(f"PHONE_NUMBER={tg_phone}")
    return lines


def _save_env_encrypted(creds: dict = None):
    """Cifra el .env actual a .env.encrypted y elimina el legacy.

    Args:
        creds: Dict de credenciales recién guardadas (evita leer de os.environ).
               Si es None, lee de os.environ (fallback).
    """
    if creds:
        lines = _env_lines_from_creds(creds)
    else:
        lines = []
        for ex in EXCHANGES_DEFAULTS:
            api_key = _clean(os.getenv(f"{ex.upper()}_API_KEY", ""))
            secret = _clean(os.getenv(f"{ex.upper()}_SECRET", ""))
            enabled = _clean(os.getenv(f"{ex.upper()}_ENABLED", "false"))
            if api_key or secret:
                lines.append(f"{ex.upper()}_API_KEY={api_key}")
                lines.append(f"{ex.upper()}_SECRET={secret}")
                if EXCHANGES_DEFAULTS[ex]["needs_passphrase"]:
                    pp = _clean(os.getenv(f"{ex.upper()}_PASSPHRASE", ""))
                    if pp:
                        lines.append(f"{ex.upper()}_PASSPHRASE={pp}")
                lines.append(f"{ex.upper()}_ENABLED={enabled}")

        tg_api_id = _clean(os.getenv("API_ID", ""))
        tg_hash = _clean(os.getenv("API_HASH", ""))
        tg_phone = _clean(os.getenv("PHONE_NUMBER", ""))
        if tg_api_id:
            lines.append(f"API_ID={tg_api_id}")
        if tg_hash:
            lines.append(f"API_HASH={tg_hash}")
        if tg_phone:
            lines.append(f"PHONE_NUMBER={tg_phone}")

    plaintext = "\n".join(lines)
    if not plaintext.strip():
        return
    key = _get_env_key()
    encrypted = _crypto_encrypt(key, plaintext)
    if encrypted:
        ENV_ENCRYPTED.write_text(encrypted, encoding="utf-8")
        # Eliminar legacy .env si existe
        if ENV_FILE.exists():
            ENV_FILE.unlink(missing_ok=True)
        logger.info("🔐 .env cifrado guardado")


def _clean(v):
    if v is None: return ""
    v = str(v).strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        return v[1:-1]
    return v


def load_api_creds():
    if not _load_env_to_memory():
        logger.warning("Archivo .env no encontrado en %s", ENV_FILE)

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
    if not isinstance(creds, dict) or "exchanges" not in creds:
        logger.error("Estructura de credenciales inválida")
        return
    # Primero guardar en .env legacy (para compatibilidad con dotenv)
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

    # Luego cifrar con los datos recién guardados
    _save_env_encrypted(creds)

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
    except Exception as e:
        logger.warning(f"⚠️ Error cargando config.json, usando defaults: {e}")
        try:
            shutil.copy(CONFIG_FILE, str(CONFIG_FILE) + ".corrupted")
        except Exception:
            pass
        return _get_default_risk_config()

def _get_default_risk_config():
    return {
        "apalancamiento": 10,
        "porcentaje_capital": {ex: 5.0 for ex in EXCHANGES_DEFAULTS},
        "cooldown_segundos": 30,
        "cantidad_minima_usdt": 1.0,
        "exchanges_activos": [],
        "limite_posiciones": 0,
        "modo_margen": "cross",
        "tp_count": 5,
        "auto_breakeven": True,
        "requerir_stop_loss": True,
        # Mejoras de entrada
        "entrada_modalidad": "auto",          # "market", "limit", "auto"
        "desviacion_maxima_porcentaje": 3.0,  # Rechazar si precio está >X% del rango
        "timeout_orden_limit_minutos": 30,    # Cancelar orden LIMIT si no se llena
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
        try:
            shutil.copy(CANALES_FILE, str(CANALES_FILE) + ".corrupted")
        except Exception:
            pass
        return set()

def save_channels(channels_set):
    atomic_write_json(CANALES_FILE, list(channels_set))
