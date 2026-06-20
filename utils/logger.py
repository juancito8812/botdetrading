import logging
import os
import re
import sys
import time
from logging.handlers import TimedRotatingFileHandler
import gzip
import shutil
from utils.config import LOG_FILE


def _compressed_namer(name):
    return name + ".gz"


def _compress_rotator(source, dest):
    try:
        with open(source, 'rb') as f_in:
            with gzip.open(dest, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)
    except Exception as e:
        log = logging.getLogger("TradingBot")
        log.warning("Error comprimiendo log %s: %s", source, e)


def _cleanup_old_logs(log_file, max_age_days=30):
    log = logging.getLogger("TradingBot")
    try:
        log_dir = os.path.dirname(log_file)
        base_name = os.path.basename(log_file)
        now = time.time()
        cutoff = now - (max_age_days * 86400)
        for fname in os.listdir(log_dir):
            if fname.startswith(base_name):
                fpath = os.path.join(log_dir, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    try:
                        os.remove(fpath)
                    except OSError as e:
                        log.warning(f"No se pudo eliminar log antiguo {fname}: {e}")
    except Exception as e:
        log.warning(f"Error limpiando logs antiguos: {e}")

class SensitiveDataFilter(logging.Filter):
    """Filtro que oculta API keys y secrets en los logs."""
    # Patrones de datos sensibles a enmascarar
    _SENSITIVE_PATTERNS = [
        (re.compile(r'(API_KEY|SECRET|PASSPHRASE)=[A-Za-z0-9_\-+/=]+', re.I),
         lambda m: f"{m.group(1)}=***"),
        (re.compile(r'(apiKey|secret|passphrase)["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-+/=]+["\']', re.I),
         lambda m: f"{m.group(1)}='***'"),
    ]

    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern, replacer in self._SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacer, record.msg)
        return True


def setup_logger():
    logger = logging.getLogger("TradingBot")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Agregar filtro de datos sensibles
        sensitive_filter = SensitiveDataFilter()
        logger.addFilter(sensitive_filter)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # Handler principal en DATA_DIR con rotación diaria
        fh = TimedRotatingFileHandler(
            LOG_FILE, when='midnight', interval=1,
            backupCount=30, encoding='utf-8'
        )
        fh.namer = _compressed_namer
        fh.rotator = _compress_rotator
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        _cleanup_old_logs(LOG_FILE, max_age_days=30)

        # Handler adicional junto al .exe (solo cuando es ejecutable)
        if getattr(sys, 'frozen', False):
            from utils.helpers import BASE_DIR
            exe_log = BASE_DIR / "log_bot.txt"
            try:
                exe_handler = logging.FileHandler(exe_log, encoding='utf-8')
                exe_handler.setFormatter(formatter)
                logger.addHandler(exe_handler)
                logger.info(f"📝 Log también en: {exe_log}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo crear log en {exe_log}: {e}")

        # Consola
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger


logger = setup_logger()
