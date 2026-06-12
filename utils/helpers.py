import os
import json
import tempfile
import aiohttp
import aiohttp.resolver
import logging
import sys
from pathlib import Path

# --- DETERMINAR RAÍZ DEL PROYECTO ---
if getattr(sys, 'frozen', False):
    # Si es un ejecutable (.exe) - usar APPDATA para datos escribibles
    BASE_DIR = Path(sys.executable).parent
    DATA_DIR = Path(os.environ.get('APPDATA', Path.home())) / "MiBotTrading"
else:
    # Si se ejecuta como script (.py)
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR

# --- PARCHE DNS PARA WINDOWS ---
# ... (rest of helper code) ...
def patch_aiohttp_dns():
    """
    Parche para forzar el uso de ThreadedResolver en aiohttp,
    evitando errores de DNS en entornos Windows.
    """
    _original_tcp_init = aiohttp.TCPConnector.__init__

    def _patched_tcp_init(self, *, resolver=None, **kwargs):
        if resolver is None:
            resolver = aiohttp.resolver.ThreadedResolver()
        _original_tcp_init(self, resolver=resolver, **kwargs)

    aiohttp.TCPConnector.__init__ = _patched_tcp_init

# --- ESCRITURA ATÓMICA ---
def atomic_write_json(filepath, data, **kwargs):
    """Escribe un JSON de forma atómica para evitar corrupción de archivos."""
    dir_path = os.path.dirname(filepath)
    fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='.tmp_', dir=dir_path)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, **kwargs)
        os.replace(tmp_path, filepath)
    except Exception as e:
        logging.error(f"Error en escritura atómica a {filepath}: {e}")
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise
