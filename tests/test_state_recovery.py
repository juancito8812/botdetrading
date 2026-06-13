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
