import json
import logging
import os
from typing import List, Optional
from models.data_classes import Position
from utils.config import POSICIONES_FILE, DATA_DIR
from utils.helpers import atomic_write_json
from utils.resilience.state_recovery import StateRecovery
from utils.resilience.backup_manager import BackupManager

logger = logging.getLogger("TradingBot")

# Instancias globales de resiliencia
RECOVERY_DIR = DATA_DIR / "recovery"
state_recovery = StateRecovery(max_checkpoints=50)
backup_manager = BackupManager(
    backup_dir=str(RECOVERY_DIR / "backups"),
    max_backups=24,
    interval_minutes=15,
)
os.makedirs(RECOVERY_DIR, exist_ok=True)

class PositionManager:
    def __init__(self):
        self.positions: List[Position] = []
        self._backup_counter = 0
        self.load()
        self._check_pending_recovery()

    def _check_pending_recovery(self):
        """Verifica checkpoints pendientes al iniciar."""
        recovery_file = RECOVERY_DIR / "checkpoints.json"
        if recovery_file.exists():
            state_recovery.load(str(recovery_file))
            pending = state_recovery.get_pending()
            if pending:
                logger.warning(
                    f"⚠️ {len(pending)} operaciones pendientes encontradas "
                    f"al cargar"
                )

    def _create_save_checkpoint(self):
        """Crea checkpoint antes de guardar. Retorna el checkpoint."""
        return state_recovery.create_checkpoint(
            operation="save_positions",
            data={"count": len(self.positions)},
        )

    def _write_positions(self):
        """Escribe posiciones a disco con escritura atómica."""
        data = [p.__dict__ for p in self.positions]
        atomic_write_json(POSICIONES_FILE, data, indent=2, default=str)

    def _finalize_save(self, cp):
        """Completa checkpoint, persiste recovery y hace backup si toca."""
        state_recovery.complete_checkpoint(cp.id)
        state_recovery.persist(str(RECOVERY_DIR / "checkpoints.json"))

        self._backup_counter += 1
        if self._backup_counter >= 15:
            self._backup_counter = 0
            backup_manager.create_backup(str(POSICIONES_FILE), "posiciones")

    def _load_positions_from_data(self, data):
        """Convierte datos JSON a lista de Position."""
        return [Position(**p) for p in data if isinstance(p, dict)]

    def load(self):
        """Carga posiciones, con restauración desde backup si es necesario."""
        if not POSICIONES_FILE.exists():
            self.positions = []
            return
        try:
            with open(POSICIONES_FILE, "r") as f:
                data = json.load(f)
                self.positions = self._load_positions_from_data(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error cargando posiciones: {e}. Intentando restaurar backup...")
            restored = backup_manager.restore_latest(str(POSICIONES_FILE), "posiciones")
            if restored:
                try:
                    with open(POSICIONES_FILE, "r") as f:
                        data = json.load(f)
                        self.positions = self._load_positions_from_data(data)
                except Exception:
                    self.positions = []
            else:
                self.positions = []
                logger.error("No se pudo restaurar el archivo de posiciones")

    def save(self):
        """Guarda posiciones con checkpoint y backup automático."""
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                cp = self._create_save_checkpoint()
                self._write_positions()
                self._finalize_save(cp)
                break
            except Exception as e:
                logger.error(
                    f"Error guardando posiciones (intento {attempt + 1}/{max_attempts}): {e}"
                )
                if attempt == max_attempts - 1:
                    logger.error(f"❌ No se pudo guardar posiciones tras {max_attempts} intentos")

    def add_position(self, position: Position):
        self.positions.append(position)
        self.save()

    def get_open_positions(self, exchange_id: Optional[str] = None) -> List[Position]:
        if exchange_id:
            return [p for p in self.positions if p.status == "open" and p.exchange_id == exchange_id]
        return [p for p in self.positions if p.status == "open"]

    def get_all_positions(self) -> List[Position]:
        return self.positions

    def get_pending_positions(self) -> List[Position]:
        return [p for p in self.positions if p.status == "pending"]

    def update_status(self, exchange_id: str, market_symbol: str, status: str):
        updated = False
        for p in self.positions:
            if p.exchange_id == exchange_id and p.market_symbol == market_symbol and p.status in ["open", "pending"]:
                p.status = status
                updated = True
        if updated:
            self.save()
            return True
        return False

# Instancia global
pos_manager = PositionManager()
