import json
import logging
from typing import List, Optional
from models.data_classes import Position
from utils.config import POSICIONES_FILE
from utils.helpers import atomic_write_json

logger = logging.getLogger("TradingBot")

class PositionManager:
    def __init__(self):
        self.positions: List[Position] = []
        self.load()

    def load(self):
        if not POSICIONES_FILE.exists():
            self.positions = []
            return
        try:
            with open(POSICIONES_FILE, "r") as f:
                data = json.load(f)
                self.positions = [Position(**p) for p in data if isinstance(p, dict)]
        except Exception as e:
            logger.error(f"Error cargando posiciones: {e}")
            self.positions = []

    def save(self):
        try:
            data = [p.__dict__ for p in self.positions]
            atomic_write_json(POSICIONES_FILE, data, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error guardando posiciones: {e}")

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
        for p in self.positions:
            if p.exchange_id == exchange_id and p.market_symbol == market_symbol and p.status in ["open", "pending"]:
                p.status = status
                self.save()
                return True
        return False

# Instancia global
pos_manager = PositionManager()
