"""Tests para utils/settings_manager.py — Gestor de ajustes (idioma, autostart)."""

import json
import subprocess
import sys
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from utils.settings_manager import (
    load_settings, save_settings,
    is_autostart_enabled, enable_autostart, disable_autostart,
    _get_exe_path, _get_task_name,
    SETTINGS_FILE, DEFAULT_SETTINGS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _get_exe_path
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.settings_manager.sys")
def test_get_exe_path_frozen(mock_sys):
    """Cuando sys.frozen es True, retorna sys.executable."""
    mock_sys.frozen = True
    mock_sys.executable = r"C:\MiBotTrading\dist\MiBotTrading.exe"
    result = _get_exe_path()
    assert result == r"C:\MiBotTrading\dist\MiBotTrading.exe"


@patch("utils.settings_manager.sys")
def test_get_exe_path_script(mock_sys):
    """Cuando sys.frozen es False, retorna main.py junto al ejecutable."""
    mock_sys.frozen = False
    mock_sys.executable = "C:/Python312/python.exe"
    result = _get_exe_path()
    assert "main.py" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _get_task_name
# ═══════════════════════════════════════════════════════════════════════════════

def test_get_task_name():
    """_get_task_name retorna el nombre esperado."""
    assert _get_task_name() == "MiBotTrading_AutoStart"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: load_settings
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.settings_manager.SETTINGS_FILE")
def test_load_settings_file_not_exists(mock_settings_file):
    """Si settings.json no existe, se crea con valores por defecto."""
    mock_settings_file.exists.return_value = False

    with patch("utils.settings_manager.save_settings") as mock_save:
        result = load_settings()

    assert result == DEFAULT_SETTINGS
    mock_save.assert_called_once_with(DEFAULT_SETTINGS)


@patch("utils.settings_manager.SETTINGS_FILE")
def test_load_settings_success(mock_settings_file):
    """Carga exitosa retorna los datos del archivo."""
    mock_settings_file.exists.return_value = True
    data = {"language": "en", "start_with_windows": True}
    mock_open_file = mock_open(read_data=json.dumps(data))

    with patch("builtins.open", mock_open_file):
        result = load_settings()

    assert result["language"] == "en"
    assert result["start_with_windows"] is True
    # Debe tener campos por defecto si faltan
    assert "max_positions_per_exchange" in result


@patch("utils.settings_manager.SETTINGS_FILE")
def test_load_settings_fills_missing_defaults(mock_settings_file):
    """Campos faltantes se rellenan con valores por defecto."""
    mock_settings_file.exists.return_value = True
    data = {"language": "fr"}  # Solo language, faltan los demás
    mock_open_file = mock_open(read_data=json.dumps(data))

    with patch("builtins.open", mock_open_file):
        result = load_settings()

    assert result["language"] == "fr"
    assert result["start_with_windows"] is True  # Default
    assert "max_positions_per_exchange" in result


@patch("utils.settings_manager.SETTINGS_FILE")
def test_load_settings_corrupted_json(mock_settings_file):
    """Archivo JSON corrupto retorna valores por defecto."""
    mock_settings_file.exists.return_value = True
    mock_open_file = mock_open(read_data="not valid json{{{")

    with patch("builtins.open", mock_open_file):
        result = load_settings()

    assert result == DEFAULT_SETTINGS


@patch("utils.settings_manager.SETTINGS_FILE")
def test_load_settings_read_error(mock_settings_file):
    """Error de lectura retorna valores por defecto."""
    mock_settings_file.exists.return_value = True
    mock_open_file = mock_open()
    mock_open_file.side_effect = PermissionError("Access denied")

    with patch("builtins.open", mock_open_file):
        result = load_settings()

    assert result == DEFAULT_SETTINGS


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: save_settings
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.settings_manager.atomic_write_json")
def test_save_settings_success(mock_atomic_write):
    """save_settings exitoso retorna True."""
    settings = {"language": "en", "start_with_windows": True}
    result = save_settings(settings)
    assert result is True
    mock_atomic_write.assert_called_once_with(SETTINGS_FILE, settings, indent=2)


@patch("utils.settings_manager.atomic_write_json")
def test_save_settings_error(mock_atomic_write):
    """save_settings con error retorna False."""
    mock_atomic_write.side_effect = OSError("Disk full")
    result = save_settings({"language": "en"})
    assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: is_autostart_enabled
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.settings_manager.subprocess.run")
def test_is_autostart_enabled_true(mock_run):
    """Tarea existe → True."""
    mock_run.return_value = MagicMock(returncode=0)
    assert is_autostart_enabled() is True
    mock_run.assert_called_once()


@patch("utils.settings_manager.subprocess.run")
def test_is_autostart_enabled_false(mock_run):
    """Tarea no existe → False."""
    mock_run.return_value = MagicMock(returncode=1)
    assert is_autostart_enabled() is False


@patch("utils.settings_manager.subprocess.run")
def test_is_autostart_enabled_error(mock_run):
    """Error ejecutando schtasks → False."""
    mock_run.side_effect = FileNotFoundError("schtasks not found")
    assert is_autostart_enabled() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: enable_autostart
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.settings_manager.is_autostart_enabled")
def test_enable_autostart_already_exists(mock_is_enabled):
    """Si ya existe, retorna False con mensaje."""
    mock_is_enabled.return_value = True
    success, msg = enable_autostart()
    assert success is False
    assert "ya existe" in msg.lower()


@patch("utils.settings_manager.is_autostart_enabled")
@patch("utils.settings_manager.subprocess.run")
def test_enable_autostart_success(mock_run, mock_is_enabled):
    """Creación exitosa retorna True."""
    mock_is_enabled.side_effect = [False, False]  # Primera llamada en is_autostart, segunda dentro
    mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS", stderr="")

    success, msg = enable_autostart()
    assert success is True
    assert "creada" in msg.lower()


@patch("utils.settings_manager.is_autostart_enabled")
@patch("utils.settings_manager.subprocess.run")
def test_enable_autostart_failure(mock_run, mock_is_enabled):
    """Error en schtasks retorna False con mensaje de error."""
    mock_is_enabled.return_value = False
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="Access denied"
    )

    success, msg = enable_autostart()
    assert success is False
    assert "error" in msg.lower() or "denied" in msg.lower()


@patch("utils.settings_manager.is_autostart_enabled")
@patch("utils.settings_manager.subprocess.run")
def test_enable_autostart_exception(mock_run, mock_is_enabled):
    """Excepción en subprocess retorna False."""
    mock_is_enabled.return_value = False
    mock_run.side_effect = PermissionError("Access denied")

    success, msg = enable_autostart()
    assert success is False
    assert "error" in msg.lower() or "denied" in msg.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: disable_autostart
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.settings_manager.is_autostart_enabled")
def test_disable_autostart_not_exists(mock_is_enabled):
    """Si no hay tarea, retorna False con mensaje."""
    mock_is_enabled.return_value = False
    success, msg = disable_autostart()
    assert success is False
    assert "no hay" in msg.lower()


@patch("utils.settings_manager.is_autostart_enabled")
@patch("utils.settings_manager.subprocess.run")
def test_disable_autostart_success(mock_run, mock_is_enabled):
    """Eliminación exitosa retorna True."""
    mock_is_enabled.side_effect = [True, True]
    mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS", stderr="")

    success, msg = disable_autostart()
    assert success is True
    assert "eliminada" in msg.lower()


@patch("utils.settings_manager.is_autostart_enabled")
@patch("utils.settings_manager.subprocess.run")
def test_disable_autostart_failure(mock_run, mock_is_enabled):
    """Error en schtasks retorna False."""
    mock_is_enabled.return_value = True
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="Task not found"
    )

    success, msg = disable_autostart()
    assert success is False
    assert "error" in msg.lower()


@patch("utils.settings_manager.is_autostart_enabled")
@patch("utils.settings_manager.subprocess.run")
def test_disable_autostart_exception(mock_run, mock_is_enabled):
    """Excepción en subprocess retorna False."""
    mock_is_enabled.return_value = True
    mock_run.side_effect = TimeoutError("Timed out")

    success, msg = disable_autostart()
    assert success is False
    assert "error" in msg.lower() or "timeout" in msg.lower() or "time" in msg.lower()
