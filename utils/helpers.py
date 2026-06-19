import os
import json
import tempfile
from contextlib import contextmanager
import aiohttp
import aiohttp.resolver
import logging
import sys
from pathlib import Path

logger = logging.getLogger("TradingBot")

# --- DETERMINAR RAÍZ DEL PROYECTO ---
if getattr(sys, 'frozen', False):
    # Si es un ejecutable (.exe)
    BASE_DIR = Path(sys.executable).parent
    # Usar APPDATA para datos, excepto cuando corre como SYSTEM (sin sesión de usuario)
    system_user = os.environ.get('USERNAME', '').upper() == 'SYSTEM'
    if system_user:
        DATA_DIR = BASE_DIR
    else:
        DATA_DIR = Path(os.environ.get('APPDATA', Path.home())) / "MiBotTrading"
else:
    # Si se ejecuta como script (.py)
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR


# --- PARCHE DNS PARA WINDOWS ---
@contextmanager
def patched_dns_resolver():
    """Context manager que parchea aiohttp para usar ThreadedResolver en Windows."""
    _original_tcp_init = aiohttp.TCPConnector.__init__

    def _patched_tcp_init(self, *, resolver=None, **kwargs):
        if resolver is None:
            resolver = aiohttp.resolver.ThreadedResolver()
        _original_tcp_init(self, resolver=resolver, **kwargs)

    aiohttp.TCPConnector.__init__ = _patched_tcp_init
    try:
        yield
    finally:
        aiohttp.TCPConnector.__init__ = _original_tcp_init


def patch_aiohttp_dns():
    """Parchea aiohttp para usar ThreadedResolver en Windows (versión directa)."""
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
        logger.error(f"Error en escritura atómica a {filepath}: {e}")
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise
