"""Gestor de ajustes de la aplicación (idioma, inicio con Windows, etc.)."""
import json
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Tuple
from utils.helpers import BASE_DIR, DATA_DIR, atomic_write_json

logger = logging.getLogger("TradingBot")

# settings.json se guarda en DATA_DIR (junto con datos del bot)
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "language": "es",
    "start_with_windows": True,
    "auto_check_updates": True,
    "max_positions_per_exchange": {
        "binance": 3,
        "bybit": 3,
        "bitget": 3,
        "bingx": 3,
        "okx": 3,
        "kucoin": 3,
        "mexc": 3,
        "phemex": 3,
        "blofin": 3,
    }
}

def _get_exe_path() -> str:
    """Retorna la ruta al ejecutable, o al script Python."""
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable))
    return str(Path(sys.executable).parent / "main.py")

def _get_task_name() -> str:
    """Nombre de la tarea en el Programador de Tareas."""
    return "MiBotTrading_AutoStart"

def load_settings() -> dict:
    """Carga los ajustes desde el archivo settings.json."""
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        # Asegurar campos por defecto
        for k, v in DEFAULT_SETTINGS.items():
            if k not in data:
                data[k] = v
        return data
    except Exception as e:
        logger.error(f"Error cargando settings: {e}")
        return dict(DEFAULT_SETTINGS)

def save_settings(settings: dict):
    """Guarda los ajustes."""
    try:
        atomic_write_json(SETTINGS_FILE, settings, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error guardando settings: {e}")
        return False

# --- Funciones para inicio con Windows (Programador de Tareas) ---

def is_autostart_enabled() -> bool:
    """Verifica si la tarea de inicio automático existe."""
    try:
        result = subprocess.run(
            ['schtasks', '/query', '/tn', _get_task_name(), '/fo', 'LIST'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

def enable_autostart() -> Tuple[bool, str]:
    """
    Crea una tarea en el Programador de Tareas para iniciar el bot al encender.
    Retorna (éxito, mensaje).
    """
    if is_autostart_enabled():
        return False, "La tarea de inicio ya existe."
    
    exe_path = _get_exe_path()
    task_name = _get_task_name()
    working_dir = str(BASE_DIR)
    
    # Crear tarea que se ejecuta al iniciar el sistema (SYSTEM), antes del login
    cmd = [
        'schtasks', '/create', '/tn', task_name,
        '/tr', f'"{exe_path}"',
        '/sc', 'onstart',
        '/ru', 'SYSTEM',
        '/rl', 'HIGHEST',
        '/f',
        '/it'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            logger.info("Tarea de inicio automático creada correctamente.")
            return True, "Tarea de inicio automático creada correctamente."
        else:
            error_msg = result.stderr or result.stdout or "Error desconocido"
            logger.error(f"Error creando tarea: {error_msg}")
            return False, f"Error al crear tarea: {error_msg}"
    except Exception as e:
        logger.error(f"Error en enable_autostart: {e}")
        return False, f"Error: {e}"

def disable_autostart() -> Tuple[bool, str]:
    """
    Elimina la tarea del Programador de Tareas.
    Retorna (éxito, mensaje).
    """
    if not is_autostart_enabled():
        return False, "No hay tarea de inicio automático."
    
    task_name = _get_task_name()
    cmd = ['schtasks', '/delete', '/tn', task_name, '/f']
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            logger.info("Tarea de inicio automático eliminada.")
            return True, "Tarea de inicio automático eliminada."
        else:
            error_msg = result.stderr or result.stdout or "Error desconocido"
            return False, f"Error al eliminar tarea: {error_msg}"
    except Exception as e:
        logger.error(f"Error en disable_autostart: {e}")
        return False, f"Error: {e}"