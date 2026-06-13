import pytest
from unittest.mock import AsyncMock
from services.notifier import TelegramNotifier
from models.data_classes import Position


@pytest.fixture
def mock_telegram():
    return AsyncMock()


@pytest.fixture
def notifier(mock_telegram):
    return TelegramNotifier(
        telegram_client=mock_telegram,
        chat_id="test_chat",
        enabled=True,
    )


@pytest.mark.asyncio
async def test_send_message(notifier, mock_telegram):
    """Enviar un mensaje básico."""
    result = await notifier.send_message("Hello from bot!")
    assert result is True
    mock_telegram.send_message.assert_called_once_with("test_chat", "Hello from bot!")


@pytest.mark.asyncio
async def test_disabled_notifier(mock_telegram):
    """Notificador deshabilitado no envía mensajes."""
    n = TelegramNotifier(telegram_client=mock_telegram, chat_id="test", enabled=False)
    result = await n.send_message("test")
    assert result is False
    mock_telegram.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_notify_trade_open(notifier, mock_telegram):
    """Notificación de apertura de posición."""
    pos = Position(
        exchange_id="bitget",
        symbol="BTC/USDT",
        market_symbol="BTC/USDT:USDT",
        side="Buy",
        entry_price=67432.50,
        amount=0.025,
        leverage=5,
        sl_order_id="sl123",
        tp_order_ids=["tp1", "tp2"],
    )
    await notifier.notify_trade_open(pos)
    args = mock_telegram.send_message.call_args[0]
    assert "🚀" in args[1] or "LONG" in args[1]
    assert "BTC/USDT" in args[1]
    assert "67,432" in args[1].replace(",", "") or "67432" in args[1]
    assert "5x" in args[1]


@pytest.mark.asyncio
async def test_notify_trade_closed(notifier, mock_telegram):
    """Notificación de cierre de posición."""
    pos = Position(
        exchange_id="bingx",
        symbol="ETH/USDT",
        market_symbol="ETH/USDT",
        side="Buy",
        entry_price=3450.0,
        amount=0.1,
        leverage=5,
        pnl=85.20,
    )
    await notifier.notify_trade_closed(pos)
    args = mock_telegram.send_message.call_args[0]
    assert "ETH/USDT" in args[1]
    assert "85.20" in args[1] or "85,20" in args[1]


@pytest.mark.asyncio
async def test_notify_health_change(notifier, mock_telegram):
    """Notificación de cambio de salud."""
    await notifier.notify_health_change("bitget", "degraded", 3, 1234.0)
    args = mock_telegram.send_message.call_args[0]
    assert "bitget" in args[1]
    assert "DEGRADED" in args[1] or "degraded" in args[1]


@pytest.mark.asyncio
async def test_notify_circuit_breaker(notifier, mock_telegram):
    """Notificación de circuit breaker."""
    await notifier.notify_circuit_breaker("bingx", "open", 60.0)
    args = mock_telegram.send_message.call_args[0]
    assert "bingx" in args[1]
    assert "OPEN" in args[1] or "open" in args[1]


@pytest.mark.asyncio
async def test_send_daily_report(notifier, mock_telegram):
    """Reporte diario con posiciones y balances."""
    positions = [
        Position(
            exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
            side="Buy", entry_price=67000, amount=0.1, leverage=5, pnl=45.20,
        ),
        Position(
            exchange_id="bingx", symbol="ETH/USDT", market_symbol="ETH/USDT",
            side="Sell", entry_price=3400, amount=0.5, leverage=5, pnl=-12.0,
        ),
    ]
    balances = {"bitget": 678.90, "bingx": 555.66}
    await notifier.send_daily_report(positions, balances)
    args = mock_telegram.send_message.call_args[0]
    assert "Reporte" in args[1]
    assert "BTC/USDT" in args[1]
    assert "678.90" in args[1] or "678,90" in args[1]


@pytest.mark.asyncio
async def test_notify_trailing_activated(notifier, mock_telegram):
    """Notificación de trailing stop activado."""
    pos = Position(
        exchange_id="bitget",
        symbol="BTC/USDT",
        market_symbol="BTC/USDT:USDT",
        side="Buy",
        entry_price=67000.0,
        amount=0.025,
        leverage=5,
    )
    await notifier.notify_trailing_activated(pos)
    args = mock_telegram.send_message.call_args[0]
    assert "BTC/USDT" in args[1]
    assert "Trailing" in args[1]


@pytest.mark.asyncio
async def test_send_message_error(notifier, mock_telegram):
    """Error al enviar mensaje no lanza excepción."""
    mock_telegram.send_message.side_effect = Exception("Network error")
    result = await notifier.send_message("test")
    assert result is False
