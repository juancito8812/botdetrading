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
    assert signal.symbol == "BTC", f"Esperaba BTC, obtuvo {signal.symbol}"
    assert signal.direccion == "Buy", f"Esperaba Buy, obtuvo {signal.direccion}"
    assert signal.stop_loss == 64000.0
    assert 66000.0 in signal.targets


def test_parse_short_signal():
    """Test básico de señal SHORT."""
    signal = _assert_signal("SHORT #ETHUSDT\nENTRY: 3500\nSL: 3600\nTP1: 3400\nTP2: 3300")
    assert signal.symbol == "ETH"
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
        assert signal.symbol is not None
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


def test_parse_scalp_long():
    """Señal SCALP con LONG explicito."""
    signal = _assert_signal("Scalp Long $PARTI (Leverage 5x) F\nEntry: 0.06095 - 0.05730\nTP: 0.06520 - 0.07090 - 0.07544 - 0.08069 - 0.08738\nSL: 0.05450")
    assert signal.symbol == "PARTI"
    assert signal.direccion == "Buy"
    assert signal.entry_min == 0.05730
    assert signal.entry_max == 0.06095
    assert signal.stop_loss == 0.05450
    assert len(signal.targets) == 5


def test_parse_scalp_default_buy():
    """Señal SCALP sin direccion explicita → default Buy."""
    signal = _assert_signal("SCALP $SOL\nEntry: 100\nSL: 95\nTP: 120, 130")
    assert signal.symbol == "SOL"
    assert signal.direccion == "Buy"
    assert len(signal.targets) == 2


def test_parse_scalp_short():
    """Señal SCALP con SHORT explicito → Sell."""
    signal = _assert_signal("Scalp Short $DOGE\nEntry: 0.5\nSL: 0.55\nTP: 0.45, 0.40")
    assert signal.symbol == "DOGE"
    assert signal.direccion == "Sell"


def test_parse_symbol_without_usdt():
    """Simbolo $XXX sin USDT."""
    signal = _assert_signal("LONG $BTC\nENTRY: 100\nSL: 90\nTARGETS: 110")
    assert signal.symbol == "BTC"


def test_parse_tp_without_number():
    """TP: sin numero individual (TP: val1, val2...)."""
    signal = _assert_signal("LONG ETH/USDT\nENTRY: 3500\nSL: 3400\nTP: 3600, 3700, 3800")
    assert len(signal.targets) == 3


def test_reject_loss_message():
    """Mensaje con 'Loss' debe ser rechazado."""
    text = "📍SIGNAL ID: #2161📍\nCOIN: $AVAX/USDT (2-5X)\nDirection: LONG\n➖➖➖➖➖➖➖\n\nSTOP LOSS: 6.150\n\n🚫17.8% Loss (2x)🚫\n\nVolatility across global markets took this one out."
    signal = parse_trading_signal(text)
    assert signal is None, "Mensaje de pérdida NO debe parsearse como señal"


def test_reject_took_out_message():
    """Mensaje con 'took this one out' debe ser rechazado."""
    text = "$BTC took this one out. On to the next."
    signal = parse_trading_signal(text)
    assert signal is None


def test_accept_valid_signal_with_signal_id():
    """Señal real con SIGNAL ID NO debe ser rechazada (es apertura)."""
    text = "📍SIGNAL ID: #2162📍\nCOIN: $ZEC/USDT (2-5x)\nDirection: LONG\n➖➖➖➖➖➖➖\nENTRY: 436.00 - 440.00\n\nTARGETS: 460.00 - 480.00 - 505.00\n\nSTOP LOSS: 400.00"
    signal = parse_trading_signal(text)
    assert signal is not None, "Señal real NO debe ser rechazada"
    assert signal.symbol == "ZEC"
    assert signal.direccion == "Buy"


def test_parse_limit_long_format():
    """Formato 'Limit Long $SIMBOLO (Leverage X) Entry: ... TP: ...'."""
    text = "Limit Long $BASED (Leverage 4x) ↗️\n\nEntry: 0.07725 - 0.08411\nTP: 0.09261 - 0.10187"
    signal = parse_trading_signal(text)
    assert signal is not None, "Limit Long debe parsearse"
    assert signal.symbol == "BASED"
    assert signal.direccion == "Buy"
    assert signal.entry_min == 0.07725
    assert signal.entry_max == 0.08411
    assert len(signal.targets) == 2
    assert signal.targets[0] == 0.09261
    assert signal.targets[1] == 0.10187
    assert signal.stop_loss is None  # No tiene SL


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
    test_parse_scalp_long()
    test_parse_scalp_default_buy()
    test_parse_scalp_short()
    test_parse_symbol_without_usdt()
    test_parse_tp_without_number()
print("✅ Todos los tests del parser pasaron correctamente.")