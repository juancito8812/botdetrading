"""Tests para utils/logger.py — setup_logger y configuración de logging."""

import io
import logging
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: setup_logger
# ═══════════════════════════════════════════════════════════════════════════════

@patch("utils.logger.LOG_FILE")
def test_setup_logger_creates_logger(mock_log_file):
    """setup_logger crea y retorna un logger."""
    from utils.logger import setup_logger

    logger = setup_logger()
    assert logger is not None
    assert logger.name == "TradingBot"
    assert logger.level == logging.INFO


@patch("utils.logger.LOG_FILE")
def test_setup_logger_has_handlers(mock_log_file):
    """setup_logger agrega handlers correctly."""
    from utils.logger import setup_logger

    logger = setup_logger()
    assert len(logger.handlers) > 0


@patch("utils.logger.LOG_FILE")
def test_setup_logger_does_not_duplicate(mock_log_file):
    """setup_logger no duplica handlers si ya existen."""
    from utils.logger import setup_logger

    logger = setup_logger()
    handler_count = len(logger.handlers)

    # Segunda llamada no debe agregar más handlers
    logger2 = setup_logger()
    assert len(logger2.handlers) == handler_count


def test_logger_output():
    """El logger escribe mensajes correctamente."""
    logger = logging.getLogger("TradingBot")

    # Capturar output del StreamHandler
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)

    try:
        test_msg = "Test log message"
        logger.info(test_msg)
        output = stream.getvalue()
        assert "INFO" in output
        assert test_msg in output
    finally:
        logger.removeHandler(handler)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Log levels
# ═══════════════════════════════════════════════════════════════════════════════

def test_logger_levels():
    """El logger maneja todos los niveles de log."""
    logger = logging.getLogger("TradingBot")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)

    try:
        logger.info("info msg")
        logger.warning("warn msg")
        logger.error("error msg")

        output = stream.getvalue()
        assert "INFO" in output
        assert "WARNING" in output
        assert "ERROR" in output
        assert "info msg" in output
        assert "warn msg" in output
        assert "error msg" in output
    finally:
        logger.removeHandler(handler)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _compressed_namer y _compress_rotator
# ═══════════════════════════════════════════════════════════════════════════════

def test_compressed_namer():
    """_compressed_namer agrega .gz al nombre."""
    from utils.logger import _compressed_namer

    result = _compressed_namer("log.txt.1")
    assert result == "log.txt.1.gz"


def test_compress_rotator_creates_gz():
    """_compress_rotator comprime el archivo y elimina el original."""
    from utils.logger import _compress_rotator

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"test log content")
        source = f.name

    dest = source + ".gz"
    try:
        _compress_rotator(source, dest)
        assert os.path.exists(dest), "El archivo .gz no se creó"
        assert not os.path.exists(source), "El original no se eliminó"
    finally:
        try:
            os.unlink(dest)
        except OSError:
            pass


def test_compress_rotator_missing_source():
    """_compress_rotator no lanza si el archivo no existe."""
    from utils.logger import _compress_rotator

    # No debe lanzar excepción
    _compress_rotator("/nonexistent_file_xyz.log", "/nonexistent_dest.gz")
