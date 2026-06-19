import json
from datetime import datetime
from typing import Optional

from utils.config import (
    load_api_creds, save_api_creds,
    load_risk_config, save_risk_config,
    load_channels, save_channels,
)
from utils.settings_manager import load_settings, save_settings
from utils.logger import logger
from utils.crypto import encrypt as _crypto_encrypt, decrypt as _crypto_decrypt

BACKUP_VERSION = 2  # v2: cifrado real con AES-256-GCM


def _collect_all_data():
    return {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now().isoformat(),
        "api_creds": load_api_creds(),
        "risk_config": load_risk_config(),
        "channels": list(load_channels()),
        "settings": load_settings(),
    }


def export_config(password: str, filepath: str) -> bool:
    """
    Exporta la configuración a un archivo JSON cifrado con AES-256-GCM.

    La password del usuario se usa para derivar la clave vía PBKDF2.
    """
    if not password:
        logger.error("Se requiere una contraseña para exportar")
        return False
    try:
        data = _collect_all_data()
        plaintext = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        encrypted = _crypto_encrypt(password, plaintext)
        if not encrypted:
            raise RuntimeError("Fallo al cifrar")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(encrypted)
        logger.info(f"📤 Configuración exportada (cifrada) a {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error exportando configuración: {e}")
        return Falsedef import_config(password: str, filepath: str) -> bool:
    """
    Importa la configuración desde un archivo cifrado con AES-256-GCM (v2).
    """
    try:
        if not password:
            raise ValueError("Este backup requiere contraseña")
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        # Solo v2: descifrado AES requerido
        plaintext = _crypto_decrypt(password, raw)
        if not plaintext:
            raise ValueError("Contraseña incorrecta o archivo corrupto")
        data = json.loads(plaintext)
        version = data.get("version", 0)
        if version != BACKUP_VERSION:
            raise ValueError(f"Versión de backup no soportada: {version}")

        if not data.get("api_creds"):
            raise ValueError("El archivo de backup no contiene datos")
        save_api_creds(data["api_creds"])
        save_risk_config(data["risk_config"])
        save_channels(set(data.get("channels", [])))
        save_settings(data["settings"])
        logger.info("📥 Configuración importada correctamente")
        return True
    except Exception as e:
        logger.error(f"Error importando configuración: {e}")
        return False
