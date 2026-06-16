import re
import logging
from typing import Optional
from models.data_classes import Signal

logger = logging.getLogger("TradingBot")

def parse_trading_signal(text: str) -> Optional[Signal]:
    """
    Parsea un mensaje de Telegram para extraer una señal de trading.
    Retorna un objeto Signal o None si no se reconoce el formato.
    """
    upper = text.upper()
    
    # 1. Extraer Símbolo (ej: BTC/USDT, #ETHUSDT, SOL-USDT)
    symbol = None
    m_sym = re.search(r'[\$#]?([A-Z0-9]+)[/|\-]?USDT', upper)
    if m_sym:
        symbol = m_sym.group(1)
    
    if not symbol:
        return None
        
    # 2. Dirección (LONG/BUY o SHORT/SELL)
    direction = None
    if re.search(r'\b(LONG|BUY)\b', upper):
        direction = "Buy"
    elif re.search(r'\b(SHORT|SELL)\b', upper):
        direction = "Sell"
        
    if not direction:
        return None
        
    # 3. Entradas (Entry)
    entry_min = entry_max = None
    m_entry = re.search(r'(?:ENTRY|ENTRADA)[S]?\s*[:\-]?\s*([\d\.]+)(?:\s*[-a]\s*([\d\.]+))?', upper)
    if m_entry:
        try:
            val1 = float(m_entry.group(1))
            val2 = float(m_entry.group(2)) if m_entry.group(2) else val1
        except ValueError:
            return None
        entry_min = min(val1, val2)
        entry_max = max(val1, val2)
        
    # 4. Stop Loss (SL)
    sl = None
    m_sl = re.search(r'(?:STOP\s*LOSS|SL|STOPLOSS)\s*[:\-]?\s*([\d\.]+)', upper)
    if m_sl:
        try:
            sl = float(m_sl.group(1))
        except ValueError:
            return None
    
    # 5. Take Profits (TP/Targets)
    targets = []
    # Opción A: Lista en una sola línea (ej: "Targets: 66000, 67000" o "Take Profit: 66000")
    m_targets_line = re.search(r'(?:TARGETS\s*|TAKE\s*PROFIT)\s*[:\-]?\s*([\d\.\s\,\-]+)', upper)
    if m_targets_line:
        try:
            targets = [float(x) for x in re.findall(r'[\d\.]+', m_targets_line.group(1))]
        except ValueError:
            return None
    else:
        # Opción B: Múltiples líneas individuales (TP1: xxx, Target 1: yyy...)
        tp_matches = re.finditer(r'(?:TP\s*\d+\s*|TARGET\s+\d+\s*)[:\-]\s*([\d\.]+)', upper)
        try:
            targets = [float(m.group(1)) for m in tp_matches]
        except ValueError:
            return None
    
    if targets:
        # Ordenar targets según dirección
        targets = sorted(list(set(targets)), reverse=(direction == "Sell"))
        
    return Signal(
        simbolo=symbol,
        direccion=direction,
        entry_min=entry_min,
        entry_max=entry_max,
        stop_loss=sl,
        targets=targets,
        raw_text=text
    )
