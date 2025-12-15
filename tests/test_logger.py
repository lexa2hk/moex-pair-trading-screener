"""Tests for logger module."""

import logging
from pathlib import Path

import pytest
import structlog

from src.utils.logger import get_logger, setup_logger


class TestLogger:
    """Test logger setup."""

    def test_setup_logger_default(self, tmp_path):
        """Test logger setup with default parameters."""
        log_file = str(tmp_path / "test.log")
        logger = setup_logger(log_level="INFO", log_file=log_file)

        assert logger is not None
        assert hasattr(logger, "info")
        assert Path(log_file).parent.exists()

    def test_setup_logger_debug(self, tmp_path):
        """Test logger setup with DEBUG level."""
        log_file = str(tmp_path / "debug.log")
        logger = setup_logger(log_level="DEBUG", log_file=log_file)

        assert logger is not None
        logger.debug("Test debug message")
        logger.info("Test info message")

    def test_setup_logger_no_file(self):
        """Test logger setup without file."""
        logger = setup_logger(log_level="INFO", log_file=None)

        assert logger is not None
        logger.info("Test message without file")

    def test_get_logger(self):
        """Test getting logger instance."""
        logger = get_logger("test_module")
        assert logger is not None
        assert hasattr(logger, "info")

    def test_logger_output(self, tmp_path, caplog):
        """Test that logger actually logs messages."""
        log_file = str(tmp_path / "output.log")
        logger = setup_logger(log_level="INFO", log_file=log_file)

        logger.info("Test info message", key="value")
        logger.warning("Test warning message")
        logger.error("Test error message")

        # Verify log file was created
        assert Path(log_file).exists()

        # Verify messages are logged
        with open(log_file) as f:
            log_content = f.read()
            assert "Test info message" in log_content or "info" in log_content.lower()

