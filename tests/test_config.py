"""Tests para utils/config.py — Config, API creds, risk config, canales."""

import json
import os
import pytest
from unittest.mock import mock_open, patch, MagicMock
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: EXCHANGES_DEFAULTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_exchanges_defaults_has_required():
    """EXCHANGES_DEFAULTS tiene los exchanges esperados."""
    from utils.config import EXCHANGES_DEFAULTS

    required = ["binance", "bybit", "bitget", "bingx", "okx"]
    for ex in required:
        assert ex in EXCHANGES_DEFAULTS, f"Falta exchange '{ex}'"
        assert "name" in EXCHANGES_DEFAULTS[ex]
        assert "needs_passphrase" in EXCHANGES_DEFAULTS[ex]
        assert "default_type" in EXCHANGES_DEFAULTS[ex]


def test_exchanges_defaults_passphrase():
    """Exchanges que requieren passphrase están correctos."""
    from utils.config import EXCHANGES_DEFAULTS

    assert EXCHANGES_DEFAULTS["bitget"]["needs_passphrase"] is True
    assert EXCHANGES_DEFAULTS["okx"]["needs_passphrase"] is True
    assert EXCHANGES_DEFAULTS["bingx"]["needs_passphrase"] is False
    assert EXCHANGES_DEFAULTS["binance"]["needs_passphrase"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _get_default_risk_config
# ═══════════════════════════════════════════════════════════════════════════════

def test_default_risk_config_has_keys():
    """_get_default_risk_config retorna todas las claves esperadas."""
    from utils.config import _get_default_risk_config

    config = _get_default_risk_config()
    required = ["apalancamiento", "porcentaje_capital", "cooldown_segundos",
                "cantidad_minima_usdt", "entrada_modalidad", "dca_habilitado",
                "trailing_stop_habilitado", "tp_distribucion", "tp_pesos"]
    for key in required:
        assert key in config, f"Falta clave '{key}' en default risk config"


def test_default_risk_config_values():
    """Valores por defecto del risk config son correctos."""
    from utils.config import _get_default_risk_config

    config = _get_default_risk_config()
    assert config["apalancamiento"] == 10
    assert config["cooldown_segundos"] == 30
    assert config["cantidad_minima_usdt"] == 1.0
    assert config["dca_habilitado"] is True
    assert config["tp_distribucion"] == "progresivo"
    assert config["tp_pesos"] == [50, 25, 15, 10]


def test_default_risk_capital_per_exchange():
    """porcentaje_capital tiene todos los exchanges."""
    from utils.config import _get_default_risk_config, EXCHANGES_DEFAULTS

    config = _get_default_risk_config()
    assert len(config["porcentaje_capital"]) == len(EXCHANGES_DEFAULTS)
    for ex in EXCHANGES_DEFAULTS:
        assert ex in config["porcentaje_capital"]
        assert config["porcentaje_capital"][ex] == 5.0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: load_risk_config
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.config.CONFIG_FILE")
def test_load_risk_config_not_exists(mock_cfg_file):
    """Si config.json no existe, retorna valores por defecto."""
    mock_cfg_file.exists.return_value = False
    from utils.config import load_risk_config, _get_default_risk_config

    result = load_risk_config()
    assert result == _get_default_risk_config()


@patch("utils.config.CONFIG_FILE")
def test_load_risk_config_success(mock_cfg_file):
    """Carga exitosa retorna los datos del archivo."""
    mock_cfg_file.exists.return_value = True
    data = {"apalancamiento": 15, "cooldown_segundos": 60}
    mock_open_file = mock_open(read_data=json.dumps(data))

    with patch("builtins.open", mock_open_file):
        from utils.config import load_risk_config
        result = load_risk_config()

    assert result["apalancamiento"] == 15
    assert result["cooldown_segundos"] == 60
    # Debe rellenar campos faltantes con defaults
    assert "trailing_stop_habilitado" in result


@patch("utils.config.CONFIG_FILE")
def test_load_risk_config_corrupted(mock_cfg_file):
    """JSON corrupto retorna valores por defecto."""
    mock_cfg_file.exists.return_value = True
    mock_open_file = mock_open(read_data="not valid json{{{")

    with patch("builtins.open", mock_open_file):
        from utils.config import load_risk_config, _get_default_risk_config
        result = load_risk_config()

    assert result == _get_default_risk_config()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: save_risk_config
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.config.atomic_write_json")
def test_save_risk_config(mock_atomic):
    """save_risk_config llama atomic_write_json."""
    from utils.config import save_risk_config, CONFIG_FILE

    config = {"apalancamiento": 15}
    save_risk_config(config)
    mock_atomic.assert_called_once_with(CONFIG_FILE, config, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: load_channels / save_channels
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.config.CANALES_FILE")
def test_load_channels_not_exists(mock_canales):
    """Si canales.json no existe, retorna set vacío."""
    mock_canales.exists.return_value = False
    from utils.config import load_channels

    result = load_channels()
    assert result == set()


@patch("utils.config.CANALES_FILE")
def test_load_channels_success(mock_canales):
    """Carga exitosa retorna set de IDs."""
    mock_canales.exists.return_value = True
    mock_open_file = mock_open(read_data=json.dumps([-100123, -100456]))

    with patch("builtins.open", mock_open_file):
        from utils.config import load_channels
        result = load_channels()

    assert result == {-100123, -100456}


@patch("utils.config.CANALES_FILE")
def test_load_channels_corrupted(mock_canales):
    """JSON corrupto retorna set vacío."""
    mock_canales.exists.return_value = True
    mock_open_file = mock_open(read_data="not valid")

    with patch("builtins.open", mock_open_file):
        from utils.config import load_channels
        result = load_channels()

    assert result == set()


@patch("utils.config.atomic_write_json")
def test_save_channels(mock_atomic):
    """save_channels llama atomic_write_json con lista de IDs."""
    from utils.config import save_channels, CANALES_FILE

    channels = {-100123, -100456}
    save_channels(channels)
    mock_atomic.assert_called_once()
    args, _ = mock_atomic.call_args
    assert args[0] == CANALES_FILE
    # La lista puede venir en cualquier orden (set -> list conversion)
    assert sorted(args[1]) == sorted(list(channels))


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: load_api_creds / save_api_creds
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.config.load_dotenv")
@patch.dict(os.environ, {
    "BITGET_API_KEY": "test_key",
    "BITGET_SECRET": "test_secret",
    "BITGET_PASSPHRASE": "test_pass",
    "BITGET_ENABLED": "true",
    "API_ID": "12345",
    "API_HASH": "abc123",
    "PHONE_NUMBER": "+584241234567",
}, clear=True)
def test_load_api_creds(mock_dotenv):
    """load_api_creds retorna credenciales correctamente."""
    from utils.config import load_api_creds

    creds = load_api_creds()
    assert "bitget" in creds["exchanges"]
    assert creds["exchanges"]["bitget"]["api_key"] == "test_key"
    assert creds["exchanges"]["bitget"]["enabled"] is True
    assert creds["telegram"]["API_ID"] == "12345"


@patch("utils.config.load_dotenv")
@patch.dict(os.environ, {"BINGX_API_KEY": "'quoted_key'", "BINGX_ENABLED": "true",
                          "API_ID": "", "API_HASH": "", "PHONE_NUMBER": ""}, clear=True)
def test_load_api_creds_cleans_quotes(mock_dotenv):
    """load_api_creds limpia comillas simples de los valores."""
    from utils.config import load_api_creds

    creds = load_api_creds()
    assert creds["exchanges"]["bingx"]["api_key"] == "quoted_key"


@patch("utils.config.load_dotenv")
@patch.dict(os.environ, {}, clear=True)
def test_load_api_creds_empty(mock_dotenv):
    """load_api_creds con vars vacías retorna valores vacíos."""
    from utils.config import load_api_creds

    creds = load_api_creds()
    for ex, data in creds["exchanges"].items():
        assert data["api_key"] == ""
        assert data["secret"] == ""
        assert data["enabled"] is False


@patch("utils.config.set_key")
def test_save_api_creds(mock_set_key):
    """save_api_creds llama set_key para cada campo."""
    from utils.config import save_api_creds

    creds = {
        "exchanges": {
            "bitget": {"api_key": "k1", "secret": "s1", "passphrase": "p1", "enabled": True},
        },
        "telegram": {"API_ID": "123", "API_HASH": "abc", "PHONE_NUMBER": "+000"},
    }
    save_api_creds(creds)

    # Verificar que se llamó set_key para los campos requeridos
    calls = [call[0][1] for call in mock_set_key.call_args_list]
    assert "BITGET_API_KEY" in calls
    assert "BITGET_SECRET" in calls
    assert "BITGET_PASSPHRASE" in calls
    assert "BITGET_ENABLED" in calls
    assert "API_ID" in calls
