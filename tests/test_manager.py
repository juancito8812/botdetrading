"""Tests para el gestor de posiciones."""
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Monkey-patch POSICIONES_FILE antes de importar el manager
from utils.config import POSICIONES_FILE

_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w')
_temp_file.write('[]')
_temp_file.close()
_temp_path = _temp_file.name

import utils.config
utils.config.POSICIONES_FILE = type(POSICIONES_FILE)(_temp_path)

from core.manager import pos_manager, PositionManager
from models.data_classes import Position


def setup_module():
    """Reiniciar posiciones antes de cada test."""
    pos_manager.positions = []
    pos_manager.save()


def test_add_position():
    """Test agregar posición."""
    pos = Position(
        exchange_id="bitget",
        symbol="BTC",
        market_symbol="BTC/USDT",
        side="Buy",
        entry_price=65000.0,
        amount=0.01,
        leverage=5
    )
    pos_manager.add_position(pos)
    assert len(pos_manager.get_all_positions()) == 1
    assert pos_manager.get_all_positions()[0].symbol == "BTC"


def test_get_open_positions():
    """Test obtener posiciones abiertas."""
    pos_manager.positions = []
    pos_manager.save()
    
    pos1 = Position(exchange_id="bitget", symbol="BTC", market_symbol="BTC/USDT", side="Buy", entry_price=65000, amount=0.01, leverage=5, status="open")
    pos2 = Position(exchange_id="bingx", symbol="ETH", market_symbol="ETH/USDT", side="Sell", entry_price=3500, amount=0.1, leverage=10, status="open")
    pos3 = Position(exchange_id="bitget", symbol="SOL", market_symbol="SOL/USDT", side="Buy", entry_price=100, amount=1, leverage=3, status="closed")
    
    for p in [pos1, pos2, pos3]:
        pos_manager.add_position(p)
    
    open_all = pos_manager.get_open_positions()
    assert len(open_all) == 2, f"Esperaba 2 abiertas, obtuvo {len(open_all)}"
    
    open_bitget = pos_manager.get_open_positions("bitget")
    assert len(open_bitget) == 1
    assert open_bitget[0].symbol == "BTC"


def test_update_status():
    """Test actualizar estado de posición."""
    result = pos_manager.update_status("bitget", "BTC/USDT", "closed")
    assert result == True
    
    btc_pos = [p for p in pos_manager.positions if p.symbol == "BTC"]
    assert btc_pos[0].status == "closed"


def test_get_pending_positions():
    """Test obtener posiciones pendientes."""
    pos_manager.positions = []
    pos_manager.save()
    
    pos = Position(exchange_id="bitget", symbol="BTC", market_symbol="BTC/USDT", side="Buy", entry_price=65000, amount=0.01, leverage=5, status="pending")
    pos_manager.add_position(pos)
    
    pending = pos_manager.get_pending_positions()
    assert len(pending) == 1


def test_persistence():
    """Test que las posiciones persisten en disco."""
    pos_manager.positions = []
    pos_manager.save()
    
    pos = Position(exchange_id="bingx", symbol="ADA", market_symbol="ADA/USDT", side="Buy", entry_price=0.5, amount=10, leverage=5)
    pos_manager.add_position(pos)
    
    # Crear nuevo manager y verificar que carga los datos
    new_manager = PositionManager()
    assert len(new_manager.get_all_positions()) > 0
    assert new_manager.get_all_positions()[0].symbol == "ADA"

    # Limpiar
    new_manager.positions = []
    new_manager.save()


def cleanup():
    """Limpiar archivo temporal."""
    try:
        os.unlink(_temp_path)
    except:
        pass


if __name__ == "__main__":
    setup_module()
    test_add_position()
    test_get_open_positions()
    test_update_status()
    test_get_pending_positions()
    test_persistence()
    cleanup()
    print("✅ Todos los tests del manager pasaron correctamente.")