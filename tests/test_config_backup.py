"""Tests para utils/config_backup.py — Export/Import cifrado de configuración."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

# ─── Tests: export_config ────────────────────────────────────────────────────


@pytest.fixture
def mock_all_config():
    """Mockea todas las funciones de carga de configuración."""
    with patch.multiple(
        "utils.config_backup",
        load_api_creds=MagicMock(return_value={"exchanges": {"bitget": {"enabled": True}}}),
        save_api_creds=MagicMock(),
        load_risk_config=MagicMock(return_value={"apalancamiento": 10}),
        save_risk_config=MagicMock(),
        load_channels=MagicMock(return_value={-100123456}),
        save_channels=MagicMock(),
    ):
        with patch.multiple(
            "utils.settings_manager",
            load_settings=MagicMock(return_value={"language": "es"}),
            save_settings=MagicMock(),
        ):
            yield


def test_export_config_success(tmp_path, mock_all_config):
    """export_config crea un archivo .botconfig cifrado."""
    from utils.config_backup import export_config

    backup_path = os.path.join(tmp_path, "backup.botconfig")
    result = export_config("mypassword", backup_path)
    assert result is True
    assert os.path.exists(backup_path)
    assert os.path.getsize(backup_path) > 16  # salt + token


def test_export_config_error(tmp_path):
    """export_config retorna False si hay error (ej: dir inválido)."""
    from utils.config_backup import export_config

    result = export_config("password", "/nonexistent_dir/backup.botconfig")
    assert result is False


# ─── Tests: import_config ────────────────────────────────────────────────────


@pytest.fixture
def valid_backup(tmp_path, mock_all_config):
    """Crea un backup válido para usar en tests de import."""
    from utils.config_backup import export_config

    backup_path = os.path.join(tmp_path, "backup.botconfig")
    export_config("mypassword", backup_path)
    return backup_path


def test_import_config_success(tmp_path, mock_all_config):
    """import_config descifra y restaura configuración correctamente."""
    from utils.config_backup import export_config, import_config

    backup_path = os.path.join(tmp_path, "backup.botconfig")
    export_config("mypassword", backup_path)

    result = import_config("mypassword", backup_path)
    assert result is not None
    assert "version" in result
    assert "data_keys" in result
    assert "apis" in result["data_keys"]


def test_import_config_wrong_password(valid_backup):
    """import_config con contraseña incorrecta retorna None."""
    from utils.config_backup import import_config

    result = import_config("wrongpassword", valid_backup)
    assert result is None


def test_import_config_corrupted_too_small(tmp_path):
    """import_config con archivo demasiado pequeño retorna None."""
    from utils.config_backup import import_config

    corrupt_path = os.path.join(tmp_path, "corrupt.botconfig")
    with open(corrupt_path, "wb") as f:
        f.write(b"too small")  # < 16 bytes

    result = import_config("password", corrupt_path)
    assert result is None


def test_import_config_corrupted_data(tmp_path):
    """import_config con datos cifrados corruptos retorna None."""
    from utils.config_backup import import_config

    corrupt_path = os.path.join(tmp_path, "corrupt.botconfig")
    # Escribir salt válido + token inválido
    import os as _os
    salt = _os.urandom(16)
    with open(corrupt_path, "wb") as f:
        f.write(salt + b"invalid_token_data_that_wont_decrypt")

    result = import_config("password", corrupt_path)
    assert result is None


def test_import_config_wrong_version(tmp_path, mock_all_config):
    """import_config con versión no soportada retorna None."""
    from utils.config_backup import _collect_all_data, _derive_key, BACKUP_VERSION, SALT_SIZE
    import json
    import base64
    from cryptography.fernet import Fernet

    # Crear bundle con versión inválida
    bundle = {
        "version": 999,  # No soportada
        "exported_at": datetime.now().isoformat(),
        "data": _collect_all_data(),
    }
    payload = json.dumps(bundle, indent=2).encode("utf-8")

    salt = os.urandom(SALT_SIZE)
    key = _derive_key("password", salt)
    fernet = Fernet(key)
    token = fernet.encrypt(payload)

    backup_path = os.path.join(tmp_path, "bad_version.botconfig")
    with open(backup_path, "wb") as f:
        f.write(salt + token)

    from utils.config_backup import import_config
    result = import_config("password", backup_path)
    assert result is None


def test_import_config_empty_data(tmp_path):
    """import_config con datos vacíos retorna None."""
    from utils.config_backup import _derive_key, SALT_SIZE
    import json
    import base64
    from cryptography.fernet import Fernet

    # Bundle sin data
    bundle = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "data": {},  # Vacío
    }
    payload = json.dumps(bundle, indent=2).encode("utf-8")

    salt = os.urandom(SALT_SIZE)
    key = _derive_key("password", salt)
    fernet = Fernet(key)
    token = fernet.encrypt(payload)

    backup_path = os.path.join(tmp_path, "empty_data.botconfig")
    with open(backup_path, "wb") as f:
        f.write(salt + token)

    from utils.config_backup import import_config
    result = import_config("password", backup_path)
    assert result is None
