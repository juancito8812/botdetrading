import json
import logging
from typing import List, Optional
from models.data_classes import Position, PositionStatus
from utils.config import POSICIONES_FILE
from utils.helpers import atomic_write_json

logger = logging.getLogger("TradingBot")

class PositionManager:
    def __init__(self):
        self.positions: List[Position] = []
        self.load()

    def _write_positions(self):
        def _serialize(obj):
            if isinstance(obj, PositionStatus):
                return obj.value
            return str(obj)
        data = [p.__dict__ for p in self.positions]
        atomic_write_json(POSICIONES_FILE, data, indent=2, default=_serialize)

    def _load_positions_from_data(self, data):
        result = []
        for p in data:
            if not isinstance(p, dict):
                continue
            status = p.get("status", "")
            if isinstance(status, str) and status.startswith("PositionStatus."):
                p["status"] = status.replace("PositionStatus.", "").lower()
            result.append(Position(**p))
        return result

    def load(self):
        if not POSICIONES_FILE.exists():
            self.positions = []
            return
        try:
            with open(POSICIONES_FILE, "r") as f:
                data = json.load(f)
                self.positions = self._load_positions_from_data(data)
        except Exception:
            self.positions = []
            logger.warning("No se pudieron cargar posiciones desde disco")

    def save(self):
        try:
            self._write_positions()
        except Exception as e:
            logger.error(f"Error guardando posiciones: {e}")

    def add_position(self, position: Position):
        self.positions.append(position)
        try:
            self.save()
        except Exception as e:
            self.positions.pop()
            logger.error("Error saving position: %s", e)
            raise

    def get_open_positions(self, exchange_id: Optional[str] = None) -> List[Position]:
        if exchange_id:
            return [p for p in self.positions if p.status == PositionStatus.OPEN and p.exchange_id == exchange_id]
        return [p for p in self.positions if p.status == PositionStatus.OPEN]

    def get_all_positions(self) -> List[Position]:
        return self.positions

    def get_pending_positions(self) -> List[Position]:
        return [p for p in self.positions if p.status == PositionStatus.PENDING]

    def update_status(self, exchange_id: str, market_symbol: str, status: str):
        updated = False
        for p in self.positions:
            if p.exchange_id == exchange_id and p.market_symbol == market_symbol and p.status in [PositionStatus.OPEN, PositionStatus.PENDING]:
                p.status = PositionStatus(status)
                updated = True
        if updated:
            self.save()
            return True
        return False

# Instancia global
pos_manager = PositionManager()
