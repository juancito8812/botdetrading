"""Sistema de snapshots y recuperación de estado para operaciones críticas."""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

from utils.helpers import atomic_write_json

logger = logging.getLogger("TradingBot")


class CheckpointStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Checkpoint:
    """Snapshot del estado antes de una operación crítica."""
    operation: str
    data: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    status: CheckpointStatus = CheckpointStatus.PENDING
    error: Optional[str] = None

    def complete(self):
        """Marca el checkpoint como completado."""
        self.status = CheckpointStatus.COMPLETED

    def fail(self, error: str):
        """Marca el checkpoint como fallido."""
        self.status = CheckpointStatus.FAILED
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a dict."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "operation": self.operation,
            "data": self.data,
            "status": self.status.value,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Deserializa desde dict."""
        cp = cls(
            operation=data["operation"],
            data=data.get("data", {}),
        )
        cp.id = data.get("id", cp.id)
        cp.timestamp = data.get("timestamp", cp.timestamp)
        cp.status = CheckpointStatus(data.get("status", "pending"))
        cp.error = data.get("error")
        return cp


class StateRecovery:
    """
    Gestiona checkpoints de estado para operaciones críticas.

    Antes de cada mutación (crear posición, modificar SL/TP), se crea
    un checkpoint. Si el sistema se cae durante la operación, al reiniciar
    se pueden restaurar los checkpoints pendientes.
    """

    def __init__(self, max_checkpoints: int = 50):
        self.max_checkpoints = max_checkpoints
        self.checkpoints: List[Checkpoint] = []

    def create_checkpoint(
        self, operation: str, data: Dict[str, Any]
    ) -> Checkpoint:
        """Crea un nuevo checkpoint y lo añade a la lista."""
        cp = Checkpoint(operation=operation, data=data)
        self.checkpoints.append(cp)

        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints = self.checkpoints[-self.max_checkpoints:]

        logger.debug(f"📌 Checkpoint creado: {cp.id} - {operation}")
        return cp

    def complete_checkpoint(self, checkpoint_id: str):
        """Marca un checkpoint como completado."""
        for cp in self.checkpoints:
            if cp.id == checkpoint_id:
                cp.complete()
                logger.debug(f"✅ Checkpoint completado: {checkpoint_id}")
                return

    def fail_checkpoint(self, checkpoint_id: str, error: str):
        """Marca un checkpoint como fallido."""
        for cp in self.checkpoints:
            if cp.id == checkpoint_id:
                cp.fail(error)
                logger.warning(f"❌ Checkpoint fallido: {checkpoint_id}: {error}")
                return

    def get_pending(self) -> List[Checkpoint]:
        """Retorna todos los checkpoints pendientes."""
        return [cp for cp in self.checkpoints if cp.status == CheckpointStatus.PENDING]

    def clear_completed(self):
        """Elimina los checkpoints completados."""
        self.checkpoints = [
            cp for cp in self.checkpoints
            if cp.status != CheckpointStatus.COMPLETED
        ]

    def persist(self, filepath: str):
        """Guarda los checkpoints a un archivo JSON."""
        try:
            data = [cp.to_dict() for cp in self.checkpoints]
            atomic_write_json(filepath, data, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error persistiendo checkpoints: {e}")

    def load(self, filepath: str):
        """Carga los checkpoints desde un archivo JSON."""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            self.checkpoints = [Checkpoint.from_dict(cp) for cp in data]

            if len(self.checkpoints) > self.max_checkpoints:
                self.checkpoints = self.checkpoints[-self.max_checkpoints:]

            pending = self.get_pending()
            if pending:
                logger.warning(
                    f"⚠️ {len(pending)} checkpoints pendientes encontrados "
                    f"al cargar"
                )
        except (FileNotFoundError, json.JSONDecodeError):
            self.checkpoints = []
        except Exception as e:
            logger.error(f"Error cargando checkpoints: {e}")
            self.checkpoints = []
