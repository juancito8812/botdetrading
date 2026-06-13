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
