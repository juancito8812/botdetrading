import logging
import os
from logging.handlers import RotatingFileHandler
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

def setup_logger():
    logger = logging.getLogger("TradingBot")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # File Handler
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        fh.namer = _compressed_namer
        fh.rotator = _compress_rotator
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
    return logger

logger = setup_logger()
