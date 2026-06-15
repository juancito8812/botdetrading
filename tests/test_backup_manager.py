import pytest
import json
import os
import time
import gzip
from utils.resilience.backup_manager import BackupManager


def test_backup_creation(tmp_path):
    """Crear un backup de un archivo."""
    source = os.path.join(tmp_path, "test.json")
    with open(source, "w") as f:
        json.dump({"key": "value"}, f)

    backup_dir = os.path.join(tmp_path, "backups")
    manager = BackupManager(backup_dir=backup_dir, max_backups=5)

    result = manager.create_backup(source, "test")
    assert result is not None
    assert os.path.exists(result)

    with gzip.open(result, "rt") as f:
        data = json.load(f)
    assert data["key"] == "value"


def test_backup_naming(tmp_path):
    """El nombre del backup incluye fecha y hora."""
    source = os.path.join(tmp_path, "posiciones.json")
    with open(source, "w") as f:
        json.dump([], f)

    manager = BackupManager(
        backup_dir=os.path.join(tmp_path, "backups"), max_backups=5
    )
    result = manager.create_backup(source, "posiciones")
    filename = os.path.basename(result)
    assert filename.startswith("posiciones_")
    assert filename.endswith(".json.gz")


def test_backup_rotation(tmp_path):
    """Se eliminan los backups más antiguos cuando se excede el máximo."""
    backup_dir = os.path.join(tmp_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    source = os.path.join(tmp_path, "data.json")
    with open(source, "w") as f:
        json.dump({"data": 1}, f)

    manager = BackupManager(backup_dir=backup_dir, max_backups=3)

    for i in range(5):
        with open(source, "w") as f:
            json.dump({"data": i}, f)
        manager.create_backup(source, "data")
        time.sleep(0.01)

    remaining = [f for f in os.listdir(backup_dir) if f.endswith(".json.gz")]
    assert len(remaining) == 3


def test_restore_from_backup(tmp_path):
    """Restaurar desde el backup más reciente."""
    source = os.path.join(tmp_path, "data.json")
    with open(source, "w") as f:
        json.dump({"version": 1}, f)

    manager = BackupManager(
        backup_dir=os.path.join(tmp_path, "backups"), max_backups=5
    )
    manager.create_backup(source, "data")

    with open(source, "w") as f:
        f.write("corrupted data{")

    result = manager.restore_latest(source, "data")
    assert result is True

    with open(source, "r") as f:
        data = json.load(f)
    assert data["version"] == 1


def test_no_backup_to_restore(tmp_path):
    """Si no hay backups, restore_latest devuelve False."""
    source = os.path.join(tmp_path, "data.json")
    manager = BackupManager(
        backup_dir=os.path.join(tmp_path, "backups"), max_backups=5
    )
    result = manager.restore_latest(source, "data")
    assert result is False


def test_backup_source_not_exists(tmp_path):
    """create_backup con source que no existe retorna None."""
    backup_dir = os.path.join(tmp_path, "backups")
    manager = BackupManager(backup_dir=backup_dir, max_backups=5)
    result = manager.create_backup("/nonexistent/path.json", "test")
    assert result is None


def test_restore_failure(tmp_path):
    """restore_latest falla si el archivo backup está corrupto."""
    backup_dir = os.path.join(tmp_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    source = os.path.join(tmp_path, "data.json")
    with open(source, "w") as f:
        json.dump({"version": 1}, f)

    manager = BackupManager(backup_dir=backup_dir, max_backups=5)
    manager.create_backup(source, "data")

    # Corromper el backup
    backups = [f for f in os.listdir(backup_dir) if f.endswith(".json.gz")]
    assert len(backups) == 1
    backup_path = os.path.join(backup_dir, backups[0])
    with open(backup_path, "wb") as f:
        f.write(b"corrupted data")

    result = manager.restore_latest(source, "data")
    assert result is False


def test_list_backups_mixed_files(tmp_path):
    """_list_backups solo incluye .json.gz que coinciden con el patrón."""
    backup_dir = os.path.join(tmp_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # Crear archivos mezclados
    for fname in ["data_20240101.json.gz", "data_20240102.json.gz", "other_20240101.json.gz", "data_old.json"]:
        with open(os.path.join(backup_dir, fname), "w") as f:
            f.write("dummy")

    manager = BackupManager(backup_dir=backup_dir, max_backups=5)
    backups = manager._list_backups("data")

    assert len(backups) == 2  # Solo 2 .json.gz con prefijo 'data_'
    assert all(b.endswith(".json.gz") for b in backups)


def test_rotate_removes_old(tmp_path):
    """_rotate elimina backups antiguos cuando excede max_backups."""
    backup_dir = os.path.join(tmp_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # Crear 5 backups con diferentes mtimes
    for i in range(5):
        fname = f"data_2024010{i+1}.json.gz"
        fpath = os.path.join(backup_dir, fname)
        with open(fpath, "w") as f:
            f.write(f"backup {i}")
        time.sleep(0.01)

    manager = BackupManager(backup_dir=backup_dir, max_backups=3)
    manager._rotate("data")

    remaining = [f for f in os.listdir(backup_dir) if f.endswith(".json.gz")]
    assert len(remaining) == 3
