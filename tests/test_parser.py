"""Tests para el parseador de señales de trading."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser import parse_trading_signal
from models.data_classes import Signal


def _assert_signal(text: str) -> Signal:
    """Helper para parsear y verificar que la señal no es None."""
    signal = parse_trading_signal(text)
    assert signal is not None, f"No se pudo parsear: {text[:50]}..."
    return signal

def test_parse_long_signal():
    """Test básico de señal LONG."""
    signal = _assert_signal("LONG #BTCUSDT\nENTRY: 65000\nSL: 64000\nTarget 1: 66000")
    assert signal is not None, "Debería parsear una señal válida"
    assert signal.simbolo == "BTC", f"Esperaba BTC, obtuvo {signal.simbolo}"
    assert signal.direccion == "Buy", f"Esperaba Buy, obtuvo {signal.direccion}"
    assert signal.stop_loss == 64000.0
    assert 66000.0 in signal.targets


def test_parse_short_signal():
    """Test básico de señal SHORT."""
    signal = _assert_signal("SHORT #ETHUSDT\nENTRY: 3500\nSL: 3600\nTP1: 3400\nTP2: 3300")
    assert signal.simbolo == "ETH"
    assert signal.direccion == "Sell"
    assert signal.stop_loss == 3600.0
    assert len(signal.targets) == 2


def test_parse_with_entry_range():
    """Test con rango de entrada."""
    signal = _assert_signal("LONG #SOLUSDT\nENTRY: 100-110\nSL: 95\nTarget 1: 120\nTarget 2: 130")
    assert signal.entry_min == 100.0
    assert signal.entry_max == 110.0


def test_parse_invalid_no_symbol():
    """Test con texto que no contiene símbolo."""
    text = "LONG\nENTRY: 100\nSL: 90"
    signal = parse_trading_signal(text)
    assert signal is None, "No debería parsear sin símbolo"


def test_parse_invalid_no_direction():
    """Test con texto que no contiene dirección."""
    text = "#BTCUSDT\nENTRY: 100"
    signal = parse_trading_signal(text)
    assert signal is None, "No debería parsear sin dirección"


def test_parse_with_multiple_formats():
    """Test con diferentes formatos de señal."""
    texts = [
        "LONG BTC/USDT\nENTRY: 50000\nSL: 49000\nTarget 1: 51000",
        "BUY #ETHUSDT\nENTRADA: 3000\nSTOPLOSS: 2900\nTARGETS: 3100, 3200",
        "SHORT SOLUSDT\nENTRY: 150\nSL: 155\nTP1: 145\nTP2: 140",
        "SELL BNB-USDT\nENTRADA: 600\nSTOP LOSS: 610\nTAKE PROFIT 1: 590\nTAKE PROFIT 2: 580",
    ]
    for text in texts:
        signal = _assert_signal(text)
        assert signal.simbolo is not None
        assert signal.direccion is not None


def test_parse_targets_ordered_long():
    """Verificar que los targets se ordenan correctamente para LONG (ascendente)."""
    signal = _assert_signal("LONG #BTCUSDT\nENTRY: 65000\nSL: 64000\nTarget 1: 66000\nTarget 2: 67000")
    assert signal.targets[0] <= signal.targets[-1], "Targets LONG deben estar en orden ascendente"


def test_parse_targets_ordered_short():
    """Verificar que los targets se ordenan correctamente para SHORT (descendente)."""
    signal = _assert_signal("SHORT #BTCUSDT\nENTRY: 65000\nSL: 66000\nTarget 1: 64000\nTarget 2: 63000")
    assert signal.targets[0] >= signal.targets[-1], "Targets SHORT deben estar en orden descendente"


def test_parse_duplicate_targets():
    """Verificar que se eliminan targets duplicados."""
    signal = _assert_signal("LONG #BTCUSDT\nENTRY: 100\nSL: 90\nTarget 1: 110\nTarget 2: 110")
    assert len(signal.targets) == 1, f"Esperaba 1 target único, obtuvo {len(signal.targets)}"


if __name__ == "__main__":
    test_parse_long_signal()
    test_parse_short_signal()
    test_parse_with_entry_range()
    test_parse_invalid_no_symbol()
    test_parse_invalid_no_direction()
    test_parse_with_multiple_formats()
    test_parse_targets_ordered_long()
    test_parse_targets_ordered_short()
    test_parse_duplicate_targets()
    print("✅ Todos los tests del parser pasaron correctamente.")