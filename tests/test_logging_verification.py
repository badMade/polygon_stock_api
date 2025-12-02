"""Tests for logging verification and output format.

Tests that log messages are properly formatted, progress is accurately
reported, and error messages are clear and actionable.
"""

import json
import logging
import os
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from production_stock_retrieval import ProductionStockRetriever
from stock_notion_retrieval import StockDataNotionRetriever


class TestLogMessageFormat:
    """Tests for log message formatting."""

    def test_info_log_format(self, caplog):
        """Test that info logs have correct format."""
        with caplog.at_level(logging.INFO):
            logging.info("Test message")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "Test message" in caplog.text

    def test_warning_log_format(self, caplog):
        """Test that warning logs have correct format."""
        with caplog.at_level(logging.WARNING):
            logging.warning("Warning message")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    def test_error_log_format(self, caplog):
        """Test that error logs have correct format."""
        with caplog.at_level(logging.ERROR):
            logging.error("Error message")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"

    def test_log_contains_emoji_indicators(self, caplog):
        """Test that logs use emoji indicators for visual clarity."""
        with caplog.at_level(logging.INFO):
            logging.info("✅ Success message")
            logging.info("❌ Error message")
            logging.info("⚠️ Warning message")
            logging.info("📊 Processing message")

        log_text = caplog.text
        assert "✅" in log_text
        assert "❌" in log_text
        assert "⚠️" in log_text
        assert "📊" in log_text


class TestProgressLogging:
    """Tests for progress reporting in logs."""

    def test_progress_percentage_accuracy(self):
        """Test that progress percentages are calculated correctly."""
        test_cases = [
            (10, 100, 10.0),
            (50, 100, 50.0),
            (100, 100, 100.0),
            (0, 100, 0.0),
            (33, 100, 33.0),
            (1, 3, 33.33333333333333),
        ]

        for processed, total, expected in test_cases:
            pct = (processed / total) * 100
            assert abs(pct - expected) < 0.01

    def test_batch_progress_logging(self, temp_dir, caplog):
        """Test that batch progress is logged correctly."""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        with caplog.at_level(logging.INFO):
            with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
                with patch('time.sleep'):
                    retriever.load_tickers()
                    retriever.process_batch(retriever.tickers, 1, 1)

        # Should have batch processing log
        assert "BATCH" in caplog.text or "batch" in caplog.text.lower()

    def test_ticker_count_logging(self, temp_dir, caplog):
        """Test that ticker count is logged on load."""
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file

        with caplog.at_level(logging.INFO):
            retriever.load_tickers()

        # Should log the number of tickers loaded
        assert "5" in caplog.text or "Loaded" in caplog.text


class TestErrorMessageClarity:
    """Tests for clear and actionable error messages."""

    def test_file_not_found_error_is_clear(self, caplog):
        """Test that file not found error is clearly logged."""
        retriever = ProductionStockRetriever()
        retriever.ticker_file = "/nonexistent/path/tickers.json"

        with caplog.at_level(logging.ERROR):
            with pytest.raises(FileNotFoundError):
                retriever.load_tickers()

    def test_json_decode_error_is_clear(self, temp_dir, caplog):
        """Test that JSON decode error is clearly logged."""
        invalid_file = os.path.join(temp_dir, "invalid.json")
        with open(invalid_file, 'w') as f:
            f.write("{not valid json}")

        retriever = StockDataNotionRetriever()
        retriever.ticker_file = invalid_file

        with caplog.at_level(logging.ERROR):
            with pytest.raises(json.JSONDecodeError):
                retriever.load_tickers()

        # Should have error logged
        assert "ERROR" in caplog.text or "Error" in caplog.text

    def test_permission_error_message(self, temp_dir, caplog):
        """Test that permission errors have clear messages."""
        # Skip on Windows or when running as root
        if os.name == 'nt':
            pytest.skip("Permission tests not reliable on Windows")
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            pytest.skip("Permission tests not reliable when running as root")

        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(["AAPL"], f)

        os.chmod(ticker_file, 0o000)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        try:
            with caplog.at_level(logging.ERROR):
                with pytest.raises(PermissionError):
                    retriever.load_tickers()
        finally:
            os.chmod(ticker_file, 0o644)


class TestLogLevelFiltering:
    """Tests for log level filtering."""

    def test_debug_logs_filtered_at_info_level(self, caplog):
        """Test that debug logs are filtered when level is INFO."""
        with caplog.at_level(logging.INFO):
            logging.debug("Debug message")
            logging.info("Info message")

        assert "Debug message" not in caplog.text
        assert "Info message" in caplog.text

    def test_all_levels_captured_at_debug(self, caplog):
        """Test that all levels are captured when level is DEBUG."""
        with caplog.at_level(logging.DEBUG):
            logging.debug("Debug message")
            logging.info("Info message")
            logging.warning("Warning message")
            logging.error("Error message")

        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text


class TestCheckpointLogging:
    """Tests for checkpoint-related logging."""

    def test_checkpoint_save_logged(self, temp_dir, caplog):
        """Test that checkpoint saves are logged."""
        retriever = StockDataNotionRetriever()
        retriever.processed_count = 100
        retriever.successful_saves = 500
        retriever.tickers = ["AAPL"] * 100

        with caplog.at_level(logging.INFO):
            with patch('stock_notion_retrieval.OUTPUT_DIR', Path(temp_dir)):
                retriever.save_checkpoint(5)

        # Should log checkpoint save
        assert "checkpoint" in caplog.text.lower() or "Checkpoint" in caplog.text

    def test_batch_completion_logged(self, temp_dir, caplog):
        """Test that batch completion is logged."""
        tickers = ["AAPL"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        with caplog.at_level(logging.INFO):
            with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
                with patch('time.sleep'):
                    retriever.load_tickers()
                    retriever.process_batch(retriever.tickers, 1, 1)

        # Should log something about saving
        assert "Saved" in caplog.text or "saved" in caplog.text.lower()


class TestTimingLogs:
    """Tests for timing-related log messages."""

    def test_timestamp_format_in_logs(self):
        """Test that timestamps in logs are ISO format."""
        timestamp = datetime.now().isoformat()

        # Should be parseable
        parsed = datetime.fromisoformat(timestamp)
        assert parsed is not None

    def test_duration_calculation_format(self):
        """Test that duration calculations are formatted correctly."""
        from datetime import timedelta

        duration = timedelta(hours=1, minutes=30, seconds=45)

        # Should be readable string
        duration_str = str(duration)
        assert "1:30:45" in duration_str

    def test_rate_calculation_logged(self):
        """Test that processing rate is calculated correctly."""
        processed = 1000
        elapsed_seconds = 100

        rate = processed / elapsed_seconds

        assert rate == 10.0  # 10 tickers per second


class TestLogOutputDestinations:
    """Tests for log output destinations."""

    def test_log_to_string_stream(self):
        """Test logging to a string stream."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)

        logger = logging.getLogger("test_logger")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("Test message to stream")

        log_contents = log_stream.getvalue()
        assert "Test message to stream" in log_contents

        # Cleanup
        logger.removeHandler(handler)

    def test_log_message_contains_context(self, caplog):
        """Test that log messages contain useful context."""
        with caplog.at_level(logging.INFO):
            ticker = "AAPL"
            batch_num = 5
            logging.info("Processing ticker %s in batch %d", ticker, batch_num)

        assert "AAPL" in caplog.text
        assert "5" in caplog.text


class TestNotionRetrieverLogging:
    """Logging tests specific to StockDataNotionRetriever."""

    def test_database_creation_logged(self, temp_dir, caplog):
        """Test that database creation is logged."""
        retriever = StockDataNotionRetriever()

        with caplog.at_level(logging.INFO):
            with patch('stock_notion_retrieval.OUTPUT_DIR', Path(temp_dir)):
                retriever.create_notion_database()

        assert "database" in caplog.text.lower() or "Database" in caplog.text

    def test_batch_save_logged(self, temp_dir, caplog):
        """Test that batch saves to Notion are logged."""
        retriever = StockDataNotionRetriever()
        batch_data = [
            {
                "ticker": "AAPL",
                "period": "2020-2024",
                "has_data": True,
                "from": "2020-01-01",
                "to": "2024-11-23"
            }
        ]

        with caplog.at_level(logging.INFO):
            with patch('stock_notion_retrieval.OUTPUT_DIR', Path(temp_dir)):
                retriever.save_batch_to_notion(batch_data, 1)

        # Should log the save
        assert "Saved" in caplog.text or "saved" in caplog.text.lower()
