"""Tests para models/data_classes.py — Position y Signal dataclasses."""

import time
import pytest
from models.data_classes import Position, Signal


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Signal
# ═══════════════════════════════════════════════════════════════════════════════

def test_signal_minimal():
    """Signal con campos mínimos."""
    s = Signal(simbolo="BTC", direccion="Buy")
    assert s.simbolo == "BTC"
    assert s.direccion == "Buy"
    assert s.entry_min is None
    assert s.entry_max is None
    assert s.stop_loss is None
    assert s.targets == []
    assert s.raw_text == ""


def test_signal_full():
    """Signal con todos los campos."""
    s = Signal(
        simbolo="ETH",
        direccion="Sell",
        entry_min=3200.0,
        entry_max=3300.0,
        stop_loss=3400.0,
        targets=[3100.0, 3000.0],
        raw_text="SHORT ETH 3200-3300 SL 3400 TP1 3100 TP2 3000",
    )
    assert s.simbolo == "ETH"
    assert s.direccion == "Sell"
    assert s.entry_min == 3200.0
    assert s.entry_max == 3300.0
    assert s.stop_loss == 3400.0
    assert s.targets == [3100.0, 3000.0]
    assert "SHORT" in s.raw_text


def test_signal_side_values():
    """Signal acepta Buy o Sell como dirección."""
    s1 = Signal(simbolo="BTC", direccion="Buy")
    s2 = Signal(simbolo="BTC", direccion="Sell")
    assert s1.direccion == "Buy"
    assert s2.direccion == "Sell"
    assert s1.direccion != s2.direccion


def test_signal_targets_immutable_copy():
    """Cada Signal tiene su propia lista de targets."""
    s1 = Signal(simbolo="BTC", direccion="Buy", targets=[70000, 71000])
    s2 = Signal(simbolo="BTC", direccion="Buy", targets=[70000])
    assert len(s1.targets) == 2
    assert len(s2.targets) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Position
# ═══════════════════════════════════════════════════════════════════════════════

def test_position_minimal():
    """Position con campos obligatorios mínimos."""
    p = Position(
        exchange_id="bitget",
        symbol="BTC/USDT",
        market_symbol="BTC/USDT:USDT",
        side="Buy",
        entry_price=67000.0,
        amount=0.01,
        leverage=5,
    )
    assert p.exchange_id == "bitget"
    assert p.symbol == "BTC/USDT"
    assert p.market_symbol == "BTC/USDT:USDT"
    assert p.side == "Buy"
    assert p.entry_price == 67000.0
    assert p.amount == 0.01
    assert p.leverage == 5
    assert p.status == "open"
    assert p.pnl == 0.0
    assert p.tp1_hit is False
    assert p.is_breakeven is False
    assert p.trailing_activated is False
    assert p.highest_price == 0.0
    assert p.lowest_price == 0.0
    assert p.entry_order_ids == []
    assert p.open_time is not None


def test_position_side():
    """Position acepta Buy y Sell como side."""
    p1 = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                  side="Buy", entry_price=67000, amount=0.01, leverage=5)
    p2 = Position(exchange_id="bingx", symbol="ETH/USDT", market_symbol="ETH/USDT",
                  side="Sell", entry_price=3400, amount=0.1, leverage=10)
    assert p1.side == "Buy"
    assert p2.side == "Sell"


def test_position_status_values():
    """Position acepta todos los estados posibles."""
    p = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                 side="Buy", entry_price=67000, amount=0.01, leverage=5, status="pending")
    assert p.status == "pending"

    p.status = "closed"
    assert p.status == "closed"

    p.status = "failed"
    assert p.status == "failed"


def test_position_pnl_values():
    """PnL positivo y negativo se almacenan correctamente."""
    p = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                 side="Buy", entry_price=67000, amount=0.01, leverage=5, pnl=85.50)
    assert p.pnl == 85.50

    p.pnl = -12.30
    assert p.pnl == -12.30


def test_position_breakeven():
    """Flags de breakeven y trailing son independientes."""
    p = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                 side="Buy", entry_price=67000, amount=0.01, leverage=5,
                 is_breakeven=True, trailing_activated=False)
    assert p.is_breakeven is True
    assert p.trailing_activated is False


def test_position_trailing_activated():
    """trailing_activated se activa correctamente."""
    p = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                 side="Buy", entry_price=67000, amount=0.01, leverage=5,
                 trailing_activated=True, highest_price=68000.0)
    assert p.trailing_activated is True
    assert p.highest_price == 68000.0


def test_position_entry_filled_amount():
    """entry_filled_amount se usa para órdenes parcialmente llenadas."""
    p = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                 side="Buy", entry_price=67000, amount=0.01, leverage=5,
                 entry_filled_amount=0.005)
    assert p.entry_filled_amount == 0.005


def test_position_entry_order_ids():
    """entry_order_ids almacena IDs de órdenes de entrada."""
    p = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                 side="Buy", entry_price=67000, amount=0.01, leverage=5,
                 entry_order_ids=["order_1", "order_2"])
    assert len(p.entry_order_ids) == 2
    assert "order_1" in p.entry_order_ids


def test_position_open_time_generated():
    """open_time se genera automáticamente si no se especifica."""
    before = time.strftime("%Y-%m-%d %H:%M:%S")
    p = Position(exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT:USDT",
                 side="Buy", entry_price=67000, amount=0.01, leverage=5)
    after = time.strftime("%Y-%m-%d %H:%M:%S")
    assert before <= p.open_time <= after
