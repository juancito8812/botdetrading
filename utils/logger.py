import logging
import os
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
    except Exception:
        pass

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

def setup_logger():
    logger = logging.getLogger("TradingBot")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = TimedRotatingFileHandler(
            LOG_FILE, when='midnight', interval=1,
            backupCount=30, encoding='utf-8'
        )
        fh.namer = _compressed_namer
        fh.rotator = _compress_rotator
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        _cleanup_old_logs(LOG_FILE, max_age_days=30)

        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger

logger = setup_logger()
