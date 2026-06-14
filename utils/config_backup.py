"""Export/Import cifrado de toda la configuración del bot."""

import json
import base64
import os
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils.config import (
    load_api_creds, save_api_creds,
    load_risk_config, save_risk_config,
    load_channels, save_channels,
)
from utils.settings_manager import load_settings, save_settings
from utils.logger import logger

BACKUP_VERSION = 1
SALT_SIZE = 16
PBKDF2_ITERATIONS = 100_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """Deriva una clave Fernet (32 bytes) desde una contraseña + salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _collect_all_data() -> dict:
    """Recopila toda la configuración actual del bot en un dict."""
    return {
        "apis": load_api_creds(),
        "risk": load_risk_config(),
        "channels": list(load_channels()),
        "settings": load_settings(),
    }


def _restore_all_data(data: dict) -> None:
    """Restaura toda la configuración desde un dict en los archivos correspondientes."""
    if "apis" in data:
        save_api_creds(data["apis"])
        logger.info("✅ APIs restauradas")
    if "risk" in data:
        save_risk_config(data["risk"])
        logger.info("✅ Riesgo restaurado")
    if "channels" in data:
        save_channels(set(data["channels"]))
        logger.info("✅ Canales restaurados")
    if "settings" in data:
        save_settings(data["settings"])
        logger.info("✅ Ajustes restaurados")


def export_config(password: str, filepath: str) -> bool:
    """Exporta toda la configuración a un archivo .botconfig cifrado.

    Args:
        password: Contraseña para cifrar el archivo.
        filepath: Ruta completa donde guardar el archivo (ej: /ruta/mi-backup.botconfig).

    Returns:
        True si se exportó correctamente, False en caso de error.
    """
    try:
        bundle = {
            "version": BACKUP_VERSION,
            "exported_at": datetime.now().isoformat(),
            "data": _collect_all_data(),
        }

        payload = json.dumps(bundle, indent=2, ensure_ascii=False).encode("utf-8")

        salt = os.urandom(SALT_SIZE)
        key = _derive_key(password, salt)
        fernet = Fernet(key)
        token = fernet.encrypt(payload)

        # Formato: salt (16 bytes) + token cifrado
        with open(filepath, "wb") as f:
            f.write(salt + token)

        logger.info(f"📤 Configuración exportada a {filepath}")
        return True

    except Exception as e:
        logger.error(f"Error exportando configuración: {e}", exc_info=True)
        return False


def import_config(password: str, filepath: str) -> Optional[dict]:
    """Importa configuración desde un archivo .botconfig cifrado.

    Args:
        password: Contraseña para descifrar el archivo.
        filepath: Ruta completa al archivo .botconfig.

    Returns:
        Dict con metadatos de la importación (version, exported_at, data_keys)
        si se importó correctamente. None en caso de error.
    """
    try:
        with open(filepath, "rb") as f:
            raw = f.read()

        if len(raw) < SALT_SIZE + 1:
            raise ValueError("Archivo corrupto: demasiado pequeño")

        salt = raw[:SALT_SIZE]
        token = raw[SALT_SIZE:]

        key = _derive_key(password, salt)
        fernet = Fernet(key)
        payload = fernet.decrypt(token)

        bundle = json.loads(payload.decode("utf-8"))

        # Validar versión
        version = bundle.get("version", 0)
        if version < 1 or version > BACKUP_VERSION:
            raise ValueError(f"Versión de backup no soportada: {version}")

        data = bundle.get("data", {})
        if not data:
            raise ValueError("El archivo de backup no contiene datos")

        # Restaurar
        _restore_all_data(data)

        logger.info(f"📥 Configuración importada desde {filepath}")
        return {
            "version": version,
            "exported_at": bundle.get("exported_at", ""),
            "data_keys": list(data.keys()),
        }

    except Exception as e:
        logger.error(f"Error importando configuración: {e}", exc_info=True)
        return None
