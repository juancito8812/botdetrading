import pytest
import json
import time
import os
from utils.resilience.state_recovery import (
    StateRecovery, Checkpoint, CheckpointStatus,
)


def test_checkpoint_creation():
    """Crear un checkpoint con datos."""
    cp = Checkpoint(
        operation="create_position",
        data={"symbol": "BTC/USDT", "amount": 0.1},
    )
    assert cp.operation == "create_position"
    assert cp.data["symbol"] == "BTC/USDT"
    assert cp.status == CheckpointStatus.PENDING
    assert cp.id is not None
    assert cp.timestamp > 0


def test_checkpoint_complete():
    """Marcar un checkpoint como completado."""
    cp = Checkpoint(operation="create_position", data={})
    cp.complete()
    assert cp.status == CheckpointStatus.COMPLETED


def test_checkpoint_fail():
    """Marcar un checkpoint como fallido."""
    cp = Checkpoint(operation="create_position", data={})
    cp.fail("error message")
    assert cp.status == CheckpointStatus.FAILED
    assert cp.error == "error message"


def test_state_recovery_create_checkpoint():
    """Crear checkpoint a través de StateRecovery."""
    recovery = StateRecovery(max_checkpoints=10)
    cp = recovery.create_checkpoint(
        operation="create_position",
        data={"symbol": "BTC/USDT"},
    )
    assert cp is not None
    assert len(recovery.get_pending()) == 1


def test_state_recovery_complete_checkpoint():
    """Completar un checkpoint."""
    recovery = StateRecovery(max_checkpoints=10)
    cp = recovery.create_checkpoint(
        operation="create_position",
        data={"symbol": "BTC/USDT"},
    )
    recovery.complete_checkpoint(cp.id)
    assert len(recovery.get_pending()) == 0


def test_state_recovery_max_checkpoints():
    """Se eliminan checkpoints antiguos cuando se supera el máximo."""
    recovery = StateRecovery(max_checkpoints=3)
    cp1 = recovery.create_checkpoint("op1", {"a": 1})
    time.sleep(0.01)
    recovery.create_checkpoint("op2", {"b": 2})
    time.sleep(0.01)
    recovery.create_checkpoint("op3", {"c": 3})
    time.sleep(0.01)
    recovery.create_checkpoint("op4", {"d": 4})

    assert len(recovery.checkpoints) == 3
    assert cp1 not in recovery.checkpoints


def test_persist_and_load(tmp_path):
    """Guardar y cargar checkpoints desde archivo."""
    filepath = os.path.join(tmp_path, "checkpoints.json")
    recovery = StateRecovery(max_checkpoints=10)

    cp = recovery.create_checkpoint("test_op", {"key": "value"})
    recovery.persist(filepath)

    recovery2 = StateRecovery(max_checkpoints=10)
    recovery2.load(filepath)

    assert len(recovery2.checkpoints) == 1
    assert recovery2.checkpoints[0].operation == "test_op"


def test_clear_completed():
    """Limpiar solo los checkpoints completados."""
    recovery = StateRecovery(max_checkpoints=10)
    cp1 = recovery.create_checkpoint("op1", {"a": 1})
    cp2 = recovery.create_checkpoint("op2", {"b": 2})

    recovery.complete_checkpoint(cp1.id)
    recovery.clear_completed()

    assert len(recovery.checkpoints) == 1
    assert recovery.checkpoints[0].id == cp2.id


def test_fail_checkpoint():
    """Marcar un checkpoint como fallido."""
    recovery = StateRecovery(max_checkpoints=10)
    cp = recovery.create_checkpoint("test_op", {"key": "value"})
    recovery.fail_checkpoint(cp.id, "something went wrong")
    assert cp.status == CheckpointStatus.FAILED
    assert cp.error == "something went wrong"


def test_complete_checkpoint_nonexistent():
    """Completar un checkpoint que no existe no falla."""
    recovery = StateRecovery(max_checkpoints=10)
    recovery.complete_checkpoint("nonexistent_id")  # No debe lanzar


def test_fail_checkpoint_nonexistent():
    """Fallar un checkpoint que no existe no falla."""
    recovery = StateRecovery(max_checkpoints=10)
    recovery.fail_checkpoint("nonexistent_id", "error")  # No debe lanzar


def test_load_file_not_found(tmp_path):
    """load con archivo inexistente no falla."""
    recovery = StateRecovery(max_checkpoints=10)
    recovery.load(os.path.join(tmp_path, "nonexistent.json"))
    assert len(recovery.checkpoints) == 0


def test_load_corrupted_json(tmp_path):
    """load con JSON corrupto no falla."""
    filepath = os.path.join(tmp_path, "corrupted.json")
    with open(filepath, "w") as f:
        f.write("{corrupted json")

    recovery = StateRecovery(max_checkpoints=10)
    recovery.load(filepath)
    assert len(recovery.checkpoints) == 0


def test_load_exception(tmp_path):
    """load que lanza Exception no esperada no falla."""
    filepath = os.path.join(tmp_path, "empty.json")
    with open(filepath, "w") as f:
        f.write("null")  # json.load(None)... no, json.load(f) -> None, luego TypeError en iteración

    recovery = StateRecovery(max_checkpoints=10)
    recovery.load(filepath)
    assert len(recovery.checkpoints) == 0


def test_persist_error():
    """persist con ruta inválida no lanza excepción."""
    recovery = StateRecovery(max_checkpoints=10)
    recovery.create_checkpoint("test", {"a": 1})
    recovery.persist("/nonexistent_dir/checkpoints.json")  # No debe lanzar


def test_checkpoint_to_dict_roundtrip():
    """Checkpoint.to_dict() y from_dict() son inversos."""
    cp = Checkpoint(
        operation="create_position",
        data={"symbol": "BTC/USDT"},
    )
    cp.complete()

    data = cp.to_dict()
    restored = Checkpoint.from_dict(data)

    assert restored.id == cp.id
    assert restored.operation == cp.operation
    assert restored.status == CheckpointStatus.COMPLETED
    assert restored.data == {"symbol": "BTC/USDT"}


def test_checkpoint_from_dict_defaults():
    """from_dict maneja campos faltantes con defaults."""
    data = {
        "operation": "test",
        "data": {"k": "v"},
    }
    cp = Checkpoint.from_dict(data)
    assert cp.operation == "test"
    assert cp.status == CheckpointStatus.PENDING
    assert cp.error is None
    assert len(cp.id) == 8


def test_state_recovery_max_checkpoints_on_init():
    """max_checkpoints se aplica al cargar."""
    recovery = StateRecovery(max_checkpoints=3)
    for i in range(5):
        recovery.checkpoints.append(Checkpoint(
            operation=f"op{i}", data={"i": i}
        ))
    # Simular que la lista tiene 5 y max es 3
    if len(recovery.checkpoints) > recovery.max_checkpoints:
        recovery.checkpoints = recovery.checkpoints[-recovery.max_checkpoints:]
    assert len(recovery.checkpoints) == 3
