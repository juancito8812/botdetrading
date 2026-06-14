"""Tests para utils/config_backup.py — cifrado/descifrado, export/import."""

import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils.config_backup as cb


# ─── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_DATA = {
    "apis": {
        "exchanges": {"bitget": {"api_key": "test123", "secret": "secret123", "passphrase": "", "enabled": True}},
        "telegram": {"API_ID": "12345", "API_HASH": "abc", "PHONE_NUMBER": "+111"}
    },
    "risk": {"apalancamiento": 10, "cooldown_segundos": 30},
    "channels": [123456789, 987654321],
    "settings": {"language": "es", "start_with_windows": False},
}


def _mock_collect_all_data() -> dict:
    """Versión mockeada de _collect_all_data que retorna datos fijos."""
    return dict(SAMPLE_DATA)


restore_called_with = []


def _mock_restore_all_data(data: dict) -> None:
    """Versión mockeada de _restore_all_data que registra lo recibido."""
    global restore_called_with
    restore_called_with.append(data)


# ─── Tests: _derive_key ─────────────────────────────────────────────────────

def test_derive_key_deterministic():
    """Misma contraseña + mismo salt produce la misma clave."""
    salt = b"0123456789abcdef"
    key1 = cb._derive_key("mypassword", salt)
    key2 = cb._derive_key("mypassword", salt)
    assert key1 == key2
    assert len(key1) == 44  # Fernet key is 32 bytes base64 → 44 chars


def test_derive_key_different_password():
    """Contraseñas diferentes producen claves diferentes."""
    salt = b"0123456789abcdef"
    key1 = cb._derive_key("password1", salt)
    key2 = cb._derive_key("password2", salt)
    assert key1 != key2


def test_derive_key_different_salt():
    """Salts diferentes producen claves diferentes."""
    key1 = cb._derive_key("mypassword", b"0123456789abcdef")
    key2 = cb._derive_key("mypassword", b"fedcba9876543210")
    assert key1 != key2


# ─── Tests: export + import (round-trip) ─────────────────────────────────────

@patch("utils.config_backup._collect_all_data", side_effect=_mock_collect_all_data)
@patch("utils.config_backup._restore_all_data", side_effect=_mock_restore_all_data)
def test_export_import_roundtrip(mock_restore, mock_collect):
    """Exportar con contraseña e importar con la misma contraseña debe restaurar los datos."""
    global restore_called_with
    restore_called_with = []

    password = "mi-contraseña-segura-123"

    with tempfile.NamedTemporaryFile(suffix=".botconfig", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Export
        result = cb.export_config(password, tmp_path)
        assert result is True, "export_config debe retornar True"

        # Verificar que el archivo existe y tiene contenido
        assert os.path.getsize(tmp_path) > 0

        # Verificar que tiene salt (16 bytes) + al menos un token
        with open(tmp_path, "rb") as f:
            raw = f.read()
        assert len(raw) > cb.SALT_SIZE  # salt + token
        salt = raw[:cb.SALT_SIZE]
        assert len(salt) == cb.SALT_SIZE

        # Import con la misma contraseña
        result_import = cb.import_config(password, tmp_path)
        assert result_import is not None
        assert result_import["version"] == cb.BACKUP_VERSION
        assert "exported_at" in result_import
        assert sorted(result_import["data_keys"]) == sorted(SAMPLE_DATA.keys())

        # Verificar que se llamó a _restore_all_data con los datos correctos
        assert len(restore_called_with) == 1
        restored = restore_called_with[0]
        assert restored["apis"] == SAMPLE_DATA["apis"]
        assert restored["risk"] == SAMPLE_DATA["risk"]
        assert restored["channels"] == SAMPLE_DATA["channels"]
        assert restored["settings"] == SAMPLE_DATA["settings"]

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@patch("utils.config_backup._collect_all_data", side_effect=_mock_collect_all_data)
@patch("utils.config_backup._restore_all_data", side_effect=_mock_restore_all_data)
def test_import_wrong_password(mock_restore, mock_collect):
    """Importar con contraseña incorrecta debe retornar None."""
    global restore_called_with
    restore_called_with = []

    with tempfile.NamedTemporaryFile(suffix=".botconfig", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Export con una contraseña
        assert cb.export_config("correcta", tmp_path) is True

        # Import con contraseña incorrecta
        result = cb.import_config("incorrecta", tmp_path)
        assert result is None, "Debe retornar None con contraseña incorrecta"

        # _restore_all_data no debe haber sido llamada
        assert len(restore_called_with) == 0

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@patch("utils.config_backup._collect_all_data", side_effect=_mock_collect_all_data)
@patch("utils.config_backup._restore_all_data", side_effect=_mock_restore_all_data)
def test_import_corrupted_file(mock_restore, mock_collect):
    """Importar un archivo corrupto debe retornar None."""
    global restore_called_with
    restore_called_with = []

    with tempfile.NamedTemporaryFile(suffix=".botconfig", delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(b"this is not a valid encrypted file at all")
        tmp.close()

    try:
        result = cb.import_config("cualquier", tmp_path)
        assert result is None, "Debe retornar None con archivo corrupto"
        assert len(restore_called_with) == 0
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@patch("utils.config_backup._collect_all_data", side_effect=_mock_collect_all_data)
@patch("utils.config_backup._restore_all_data", side_effect=_mock_restore_all_data)
def test_import_too_short(mock_restore, mock_collect):
    """Importar un archivo muy pequeño debe retornar None."""
    global restore_called_with
    restore_called_with = []

    with tempfile.NamedTemporaryFile(suffix=".botconfig", delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(b"short")
        tmp.close()

    try:
        result = cb.import_config("cualquier", tmp_path)
        assert result is None, "Debe retornar None con archivo demasiado pequeño"
        assert len(restore_called_with) == 0
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@patch("utils.config_backup._collect_all_data", side_effect=_mock_collect_all_data)
@patch("utils.config_backup._restore_all_data", side_effect=_mock_restore_all_data)
def test_export_error_returns_false(mock_restore, mock_collect):
    """Si ocurre un error durante export, debe retornar False."""
    # Pasar una ruta inválida (None) debería causar error
    result = cb.export_config("password", None)
    assert result is False, "Debe retornar False en caso de error"


@patch("utils.config_backup._collect_all_data", side_effect=_mock_collect_all_data)
@patch("utils.config_backup._restore_all_data", side_effect=_mock_restore_all_data)
def test_import_nonexistent_file(mock_restore, mock_collect):
    """Importar un archivo que no existe debe retornar None."""
    result = cb.import_config("password", "/ruta/que/no/existe.botconfig")
    assert result is None


# ─── Tests: export + multiple imports con distintos passwords ────────────────

@patch("utils.config_backup._collect_all_data", side_effect=_mock_collect_all_data)
@patch("utils.config_backup._restore_all_data", side_effect=_mock_restore_all_data)
def test_multiple_exports_independent(mock_restore, mock_collect):
    """Exportar dos veces con distintas contraseñas produce archivos diferentes."""
    global restore_called_with

    with tempfile.NamedTemporaryFile(suffix=".botconfig", delete=False) as tmp1:
        path1 = tmp1.name
    with tempfile.NamedTemporaryFile(suffix=".botconfig", delete=False) as tmp2:
        path2 = tmp2.name

    try:
        assert cb.export_config("pass1", path1) is True
        assert cb.export_config("pass2", path2) is True

        # Los archivos deben tener contenido distinto (diferente salt + cifrado)
        with open(path1, "rb") as f1, open(path2, "rb") as f2:
            data1 = f1.read()
            data2 = f2.read()

        assert data1 != data2, "Archivos con distinta contraseña deben ser diferentes"

        # Cada uno debe poder importarse con su respectiva contraseña
        restore_called_with = []
        r1 = cb.import_config("pass1", path1)
        assert r1 is not None

        restore_called_with = []
        r2 = cb.import_config("pass2", path2)
        assert r2 is not None

    finally:
        for p in [path1, path2]:
            try:
                os.unlink(p)
            except OSError:
                pass


if __name__ == "__main__":
    test_derive_key_deterministic()
    test_derive_key_different_password()
    test_derive_key_different_salt()
    test_export_import_roundtrip()
    test_import_wrong_password()
    test_import_corrupted_file()
    test_import_too_short()
    test_export_error_returns_false()
    test_import_nonexistent_file()
    test_multiple_exports_independent()
    print("✅ Todos los tests de config_backup pasaron correctamente.")
