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

BACKUP_VERSION = 1

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
    Exporta la configuración a un archivo JSON.
    Nota: el parámetro password se mantiene por compatibilidad con la UI
    pero la exportación actual es en texto plano.
    """
    try:
        data = _collect_all_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"📤 Configuración exportada a {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error exportando configuración: {e}")
        return False

def import_config(password: str, filepath: str) -> bool:
    """
    Importa la configuración desde un archivo JSON.
    Nota: el parámetro password se mantiene por compatibilidad con la UI
    pero la importación actual no requiere cifrado.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
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
