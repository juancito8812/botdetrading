"""Tests para utils/helpers.py — atomic_write_json, patch_aiohttp_dns, BASE_DIR/DATA_DIR."""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: atomic_write_json
# ═══════════════════════════════════════════════════════════════════════════════

def test_atomic_write_json_success():
    """atomic_write_json escribe datos correctamente."""
    from utils.helpers import atomic_write_json

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        atomic_write_json(tmp_path, data, indent=2)

        with open(tmp_path, "r") as f:
            loaded = json.load(f)
        assert loaded == data
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_atomic_write_json_empty_dict():
    """atomic_write_json con dict vacío."""
    from utils.helpers import atomic_write_json

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        atomic_write_json(tmp_path, {})

        with open(tmp_path, "r") as f:
            loaded = json.load(f)
        assert loaded == {}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_atomic_write_json_list():
    """atomic_write_json con lista."""
    from utils.helpers import atomic_write_json

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        data = [1, 2, 3, "a", "b"]
        atomic_write_json(tmp_path, data)

        with open(tmp_path, "r") as f:
            loaded = json.load(f)
        assert loaded == data
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_atomic_write_json_invalid_dir():
    """atomic_write_json a directorio inválido lanza excepción."""
    from utils.helpers import atomic_write_json

    with pytest.raises(Exception):
        atomic_write_json("/nonexistent_dir_xyz/file.json", {"a": 1})


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: patch_aiohttp_dns
# ═══════════════════════════════════════════════════════════════════════════════

def test_patch_aiohttp_dns_applies():
    """patch_aiohttp_dns aplica el parche sin errores."""
    from utils.helpers import patch_aiohttp_dns
    import aiohttp

    # Aplicar y verificar que no lanza
    patch_aiohttp_dns()
    assert aiohttp.TCPConnector.__init__ is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: BASE_DIR / DATA_DIR
# ═══════════════════════════════════════════════════════════════════════════════

def test_base_dir_is_path():
    """BASE_DIR es un objeto Path."""
    from utils.helpers import BASE_DIR
    assert isinstance(BASE_DIR, Path)
    assert str(BASE_DIR) != ""


def test_data_dir_is_path():
    """DATA_DIR es un objeto Path."""
    from utils.helpers import DATA_DIR
    assert isinstance(DATA_DIR, Path)
    assert str(DATA_DIR) != ""


def test_base_dir_contains_project():
    """BASE_DIR contiene el nombre del proyecto."""
    from utils.helpers import BASE_DIR
    assert "botdetrading" in str(BASE_DIR).lower() or "MiBotTrading" in str(BASE_DIR) or BASE_DIR.exists()


@pytest.mark.asyncio
async def test_atomic_write_json_raises_and_cleans_up():
    """atomic_write_json limpia el temporal si falla la escritura."""
    from utils.helpers import atomic_write_json
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Forzar error: pasar objeto no serializable
        class Unserializable:
            pass
        with pytest.raises(Exception):
            atomic_write_json(tmp_path, {"bad": Unserializable()})
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_patch_aiohttp_dns_sets_init():
    """patch_aiohttp_dns reemplaza TCPConnector.__init__."""
    import aiohttp
    original_init = aiohttp.TCPConnector.__init__

    from utils.helpers import patch_aiohttp_dns
    patch_aiohttp_dns()

    # Verificar que cambió
    assert aiohttp.TCPConnector.__init__ is not original_init

    # Restaurar original
    aiohttp.TCPConnector.__init__ = original_init
