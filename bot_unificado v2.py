#!/usr/bin/env python3
"""
Bot Unificado v2 - Launcher

Los modulos han sido separados en:
  - config.py: configuracion, constantes, helpers
  - exchange.py: clientes CCXT, ExchangeAdapter
  - positions.py: Position, PositionManager
  - signals.py: parseo de senales de Telegram
  - gui.py: interfaz grafica Tkinter
  - main.py: punto de entrada y orquestacion
"""

import sys
import os

# Asegurar que el directorio raiz esta en el path
_bot_dir = os.path.dirname(os.path.abspath(__file__))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

# Iniciar la aplicacion
from main import run_bot
run_bot()
