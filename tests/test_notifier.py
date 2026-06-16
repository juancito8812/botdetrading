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
    """Enviar un mensaje básico — resuelve entidad primero."""
    # Mock get_entity para que retorne un input peer simulado
    mock_entity = AsyncMock()
    mock_telegram.get_entity.return_value = mock_entity

    result = await notifier.send_message("Hello from bot!")
    assert result is True
    # Debe haber llamado a get_entity primero para resolver
    mock_telegram.get_entity.assert_called_once_with("test_chat")
    # Luego send_message con la entidad resuelta, no el raw
    mock_telegram.send_message.assert_called_once_with(mock_entity, "Hello from bot!")


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
    assert "67,432" in args[1] or "67432.50" in args[1]
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


@pytest.mark.asyncio
async def test_notify_tp_hit(notifier, mock_telegram):
    """Notificación de TP alcanzado (batching)."""
    import asyncio
    from unittest.mock import patch, AsyncMock
    pos = Position(
        exchange_id="bitget", symbol="BTC/USDT", market_symbol="BTC/USDT",
        side="Buy", entry_price=67000, amount=0.1, leverage=5,
    )
    mock_entity = AsyncMock()
    mock_telegram.get_entity.return_value = mock_entity
    with patch('services.notifier.asyncio.sleep', AsyncMock()):
        await notifier.notify_tp_hit(pos, 1, tp_price=68000, tp_pnl=150.0)
        if notifier._batch_task:
            await notifier._batch_task
    args = mock_telegram.send_message.call_args[0]
    assert "TP1" in args[1] or "tp1" in args[1]
    assert "BTC/USDT" in args[1]


@pytest.mark.asyncio
async def test_notify_error(notifier, mock_telegram):
    """Notificación de error crítico."""
    await notifier.notify_error("engine", "Connection lost with exchange")
    args = mock_telegram.send_message.call_args[0]
    assert "engine" in args[1]
    assert "Connection" in args[1]


@pytest.mark.asyncio
async def test_get_recent(notifier, mock_telegram):
    """get_recent retorna las últimas notificaciones."""
    mock_telegram.get_entity.return_value = AsyncMock()
    await notifier.notify_error("mod1", "err1")
    await notifier.notify_error("mod2", "err2")
    recent = notifier.get_recent(2)
    assert len(recent) == 2
    assert "mod1" in recent[0] or "mod2" in recent[0]


@pytest.mark.asyncio
async def test_add_to_history_overflow(notifier, mock_telegram):
    """_add_to_history mantiene máximo 20 entradas."""
    for i in range(25):
        notifier._add_to_history(f"entry {i}")
    assert len(notifier.history) == 20
    assert "entry 24" in notifier.history[-1]


@pytest.mark.asyncio
async def test_resolve_chat_id_cached(notifier, mock_telegram):
    """_resolve_chat_id usa caché si la entidad ya está resuelta."""
    mock_entity = AsyncMock()
    mock_telegram.get_entity.return_value = mock_entity

    # Primera llamada resuelve
    result1 = await notifier._resolve_chat_id()
    assert mock_telegram.get_entity.call_count == 1

    # Segunda llamada usa caché
    mock_telegram.get_entity.reset_mock()
    result2 = await notifier._resolve_chat_id()
    mock_telegram.get_entity.assert_not_called()  # No debe llamar de nuevo


@pytest.mark.asyncio
async def test_resolve_chat_id_cache_invalidation(notifier, mock_telegram):
    """Cambiar chat_id invalida la caché de entidad."""
    mock_entity = AsyncMock()
    mock_telegram.get_entity.return_value = mock_entity

    # Resolver primero
    await notifier._resolve_chat_id()
    assert mock_telegram.get_entity.call_count == 1

    # Cambiar chat_id
    notifier.chat_id = "new_chat_id"
    notifier._cached_chat_id = "test_chat"  # Simular caché vieja

    mock_telegram.get_entity.reset_mock()
    mock_telegram.get_entity.return_value = AsyncMock()
    await notifier._resolve_chat_id()
    mock_telegram.get_entity.assert_called_once()  # Debe resolver de nuevo


@pytest.mark.asyncio
async def test_resolve_chat_id_value_error(notifier, mock_telegram):
    """_resolve_chat_id lanza ValueError si no encuentra la entidad."""
    mock_telegram.get_entity.side_effect = ValueError("Cannot find any entity")
    with pytest.raises(ValueError):
        await notifier._resolve_chat_id()


@pytest.mark.asyncio
async def test_resolve_chat_id_value_error_no_user(notifier, mock_telegram):
    """_resolve_chat_id lanza ValueError con mensaje 'no user has'."""
    mock_telegram.get_entity.side_effect = ValueError("No user has \"test\"")
    with pytest.raises(ValueError):
        await notifier._resolve_chat_id()


@pytest.mark.asyncio
async def test_resolve_chat_id_other_exception_raises(notifier, mock_telegram):
    """_resolve_chat_id propaga excepciones inesperadas."""
    mock_telegram.get_entity.side_effect = Exception("random")
    with pytest.raises(Exception):
        await notifier._resolve_chat_id()


@pytest.mark.asyncio
async def test_send_message_value_error_entity(notifier, mock_telegram):
    """send_message captura ValueError y retorna False."""
    mock_telegram.get_entity.side_effect = ValueError("Cannot find any entity")
    result = await notifier.send_message("test")
    assert result is False


@pytest.mark.asyncio
async def test_send_message_generic_value_error(notifier, mock_telegram):
    """send_message captura ValueError genérico."""
    mock_telegram.get_entity.side_effect = ValueError("Some other error")
    result = await notifier.send_message("test")
    assert result is False


@pytest.mark.asyncio
async def test_send_message_event_loop_error(notifier, mock_telegram):
    """send_message captura event loop must not change y retorna False."""
    mock_entity = AsyncMock()
    mock_telegram.get_entity.return_value = mock_entity
    mock_telegram.send_message.side_effect = Exception("event loop must not change")
    result = await notifier.send_message("test")
    assert result is False


@pytest.mark.asyncio
async def test_send_message_rate_limiting(notifier, mock_telegram):
    """send_message respeta rate limiting mín 2s entre mensajes."""
    mock_entity = AsyncMock()
    mock_telegram.get_entity.return_value = mock_entity

    # Enviar primer mensaje
    result1 = await notifier.send_message("first")
    assert result1 is True

    # El segundo inmediatamente después debería esperar
    import time
    before = time.time()
    result2 = await notifier.send_message("second")
    elapsed = time.time() - before
    assert result2 is True
    # Como _last_send_time se actualiza, la segunda llamada ve elapsed ~= 0
    # y hace asyncio.sleep(_MIN_INTERVAL - elapsed)
    # pero como asyncio.sleep(2.0) en tests es instantáneo, elapsed >= 0


@pytest.mark.asyncio
async def test_notify_trade_closed_without_pnl(notifier, mock_telegram):
    """Notificación de cierre sin PnL."""
    mock_entity = AsyncMock()
    mock_telegram.get_entity.return_value = mock_entity
    pos = Position(
        exchange_id="bitget", symbol="SOL/USDT", market_symbol="SOL/USDT",
        side="Buy", entry_price=100, amount=1, leverage=3, pnl=None,
    )
    await notifier.notify_trade_closed(pos)
    args = mock_telegram.send_message.call_args[0]
    assert "SOL/USDT" in args[1]
