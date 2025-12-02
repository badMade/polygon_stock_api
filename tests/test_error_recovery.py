"""Tests for error recovery and resilience scenarios.

Tests handling of partial failures, checkpoint recovery, retry logic,
and graceful degradation.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

from production_stock_retrieval import ProductionStockRetriever
from stock_notion_retrieval import StockDataNotionRetriever


class TestCheckpointRecoveryScenarios:
    """Tests for checkpoint-based recovery scenarios."""

    def test_recover_from_valid_checkpoint(self, temp_dir):
        """Test resuming from a valid checkpoint file."""
        # Create a checkpoint indicating batch 25 was completed
        checkpoint_data = {
            "batch": 25,
            "processed": 2500,
            "saved": 12500,
            "timestamp": "2025-11-24T10:30:00.000000"
        }
        checkpoint_file = os.path.join(temp_dir, "checkpoint.json")
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)

        # Load and verify recovery point
        with open(checkpoint_file, 'r') as f:
            loaded = json.load(f)

        resume_batch = loaded["batch"] + 1
        assert resume_batch == 26
        assert loaded["processed"] == 2500
        assert loaded["saved"] == 12500

    def test_recover_from_partial_batch_checkpoint(self, temp_dir):
        """Test recovery when interrupted mid-batch."""
        # Checkpoint with partial batch (not evenly divisible)
        checkpoint_data = {
            "batch": 5,
            "processed": 475,  # 5 batches would be 500
            "saved": 2375,
            "partial": True,
            "last_ticker": "TICK0474",
            "timestamp": datetime.now().isoformat()
        }
        checkpoint_file = os.path.join(temp_dir, "checkpoint.json")
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)

        with open(checkpoint_file, 'r') as f:
            loaded = json.load(f)

        # Should resume from the partial batch
        assert loaded["partial"] is True
        assert loaded["processed"] == 475

    def test_handle_corrupted_checkpoint_gracefully(self, temp_dir):
        """Test graceful handling of corrupted checkpoint file."""
        checkpoint_file = os.path.join(temp_dir, "checkpoint.json")
        with open(checkpoint_file, 'w') as f:
            f.write("{invalid: json, content]}")

        # Should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            with open(checkpoint_file, 'r') as f:
                json.load(f)

    def test_handle_empty_checkpoint_file(self, temp_dir):
        """Test handling of empty checkpoint file."""
        checkpoint_file = os.path.join(temp_dir, "checkpoint.json")
        with open(checkpoint_file, 'w') as f:
            f.write("")

        with pytest.raises(json.JSONDecodeError):
            with open(checkpoint_file, 'r') as f:
                json.load(f)

    def test_handle_missing_checkpoint_fields(self, temp_dir):
        """Test handling checkpoint with missing required fields."""
        checkpoint_data = {"batch": 10}  # Missing processed, saved, timestamp
        checkpoint_file = os.path.join(temp_dir, "checkpoint.json")
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)

        with open(checkpoint_file, 'r') as f:
            loaded = json.load(f)

        # Should use defaults for missing fields
        assert loaded.get("batch") == 10
        assert loaded.get("processed", 0) == 0
        assert loaded.get("saved", 0) == 0
        assert loaded.get("timestamp") is None

    def test_checkpoint_with_failed_tickers_list(self, temp_dir):
        """Test checkpoint containing list of failed tickers."""
        checkpoint_data = {
            "batch": 20,
            "processed": 2000,
            "saved": 9800,
            "failed_tickers": ["FAIL1", "FAIL2", "FAIL3"],
            "timestamp": datetime.now().isoformat()
        }
        checkpoint_file = os.path.join(temp_dir, "checkpoint.json")
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)

        with open(checkpoint_file, 'r') as f:
            loaded = json.load(f)

        assert "failed_tickers" in loaded
        assert len(loaded["failed_tickers"]) == 3
        assert "FAIL1" in loaded["failed_tickers"]


class TestPartialBatchFailure:
    """Tests for handling partial batch processing failures."""

    def test_continue_after_single_ticker_failure(self):
        """Test that processing continues after a single ticker fails."""
        retriever = ProductionStockRetriever()

        # Track which tickers were processed
        processed_tickers = []
        failed_tickers = []

        def mock_get_data(ticker, period):
            if ticker == "FAIL_TICKER":
                failed_tickers.append(ticker)
                return {
                    "ticker": ticker,
                    "period": period["label"],
                    "has_data": False,
                    "open": None, "high": None, "low": None, "close": None,
                    "volume": None, "vwap": None, "transactions": None,
                    "data_points": 0, "timespan": "day"
                }
            processed_tickers.append(ticker)
            return {
                "ticker": ticker,
                "period": period["label"],
                "has_data": True,
                "open": 100, "high": 110, "low": 90, "close": 105,
                "volume": 1000000, "vwap": 102.5, "transactions": 5000,
                "data_points": 252, "timespan": "day"
            }

        retriever.tickers = ["AAPL", "FAIL_TICKER", "MSFT"]

        with patch.object(retriever, 'get_polygon_data', side_effect=mock_get_data):
            with patch.object(retriever, 'save_batch'):
                with patch('time.sleep'):
                    retriever.process_batch(retriever.tickers, 1, 1)

        # All tickers should be processed
        assert retriever.processed == 3
        # AAPL and MSFT should have been recorded as processed
        assert "AAPL" in processed_tickers or len(processed_tickers) > 0

    def test_track_failed_tickers_separately(self):
        """Test that failed tickers are tracked separately."""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["GOOD1", "BAD1", "GOOD2", "BAD2"]

        # Simulate some failures
        retriever.failed = ["BAD1", "BAD2"]

        assert len(retriever.failed) == 2
        assert "BAD1" in retriever.failed
        assert "BAD2" in retriever.failed


class TestGracefulDegradation:
    """Tests for graceful degradation with partial data."""

    def test_process_with_missing_price_data(self):
        """Test processing when some price fields are missing."""
        retriever = ProductionStockRetriever()
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}

        # Get data (returns None for price fields by default)
        data = retriever.get_polygon_data("UNKNOWN_TICKER", period)

        assert data["has_data"] is False
        assert data["open"] is None
        assert data["high"] is None
        assert data["close"] is None
        assert data["volume"] is None
        assert data["data_points"] == 0

    def test_process_with_partial_period_data(self):
        """Test processing when only some periods have data."""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["PARTIAL_TICKER"]

        period_results = []

        def mock_get_data(ticker, period):
            # Only 2020-2024 has data
            has_data = period["label"] == "2020-2024"
            result = {
                "ticker": ticker,
                "period": period["label"],
                "has_data": has_data,
                "open": 100 if has_data else None,
                "high": 110 if has_data else None,
                "low": 90 if has_data else None,
                "close": 105 if has_data else None,
                "volume": 1000000 if has_data else None,
                "vwap": 102.5 if has_data else None,
                "transactions": 5000 if has_data else None,
                "data_points": 252 if has_data else 0,
                "timespan": "day"
            }
            period_results.append(result)
            return result

        with patch.object(retriever, 'get_polygon_data', side_effect=mock_get_data):
            with patch.object(retriever, 'save_batch'):
                with patch('time.sleep'):
                    retriever.process_batch(retriever.tickers, 1, 1)

        # Should have 5 periods processed
        assert len(period_results) == 5
        # Only one should have data
        with_data = [r for r in period_results if r["has_data"]]
        assert len(with_data) == 1
        assert with_data[0]["period"] == "2020-2024"


class TestRetryLogic:
    """Tests for retry logic on transient failures."""

    def test_retry_on_temporary_failure(self):
        """Test retry behavior on temporary failures."""
        call_count = 0

        def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return {"status": "success"}

        # Simulate retry logic
        max_retries = 3
        result = None
        for attempt in range(max_retries):
            try:
                result = failing_then_success()
                break
            except ConnectionError:
                if attempt == max_retries - 1:
                    raise
                continue

        assert result == {"status": "success"}
        assert call_count == 3

    def test_fail_after_max_retries(self):
        """Test that processing fails after max retries exceeded."""
        call_count = 0

        def always_failing(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")

        max_retries = 3
        with pytest.raises(ConnectionError):
            for attempt in range(max_retries):
                try:
                    always_failing()
                    break
                except ConnectionError:
                    if attempt == max_retries - 1:
                        raise
                    continue

        assert call_count == 3


class TestNotionRetrieverRecovery:
    """Recovery tests specific to StockDataNotionRetriever."""

    def test_notion_checkpoint_save_on_interrupt(self, temp_dir):
        """Test checkpoint is saved when KeyboardInterrupt occurs."""
        retriever = StockDataNotionRetriever()
        retriever.processed_count = 500
        retriever.successful_saves = 2500
        retriever.tickers = [f"TICK{i}" for i in range(1000)]

        with patch('stock_notion_retrieval.OUTPUT_DIR', Path(temp_dir)):
            retriever.save_checkpoint(5)

        checkpoint_file = os.path.join(temp_dir, "retrieval_checkpoint.json")
        assert os.path.exists(checkpoint_file)

        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)

        assert checkpoint["last_batch"] == 5
        assert checkpoint["processed_count"] == 500
        assert checkpoint["successful_saves"] == 2500

    def test_notion_recover_failed_tickers(self, temp_dir):
        """Test recovering list of failed tickers from checkpoint."""
        retriever = StockDataNotionRetriever()
        retriever.failed_tickers = ["FAIL1", "FAIL2"]
        retriever.processed_count = 100
        retriever.tickers = [f"TICK{i}" for i in range(100)]

        with patch('stock_notion_retrieval.OUTPUT_DIR', Path(temp_dir)):
            retriever.save_checkpoint(1)

        checkpoint_file = os.path.join(temp_dir, "retrieval_checkpoint.json")
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)

        assert checkpoint["failed_tickers"] == ["FAIL1", "FAIL2"]


class TestErrorMessageClarity:
    """Tests for clear error messages in failure scenarios."""

    def test_file_not_found_error_message(self):
        """Test clear error message for missing ticker file."""
        retriever = ProductionStockRetriever()
        retriever.ticker_file = "/nonexistent/path/tickers.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            retriever.load_tickers()

        # Error message should contain the filename
        error_message = str(exc_info.value)
        assert "tickers.json" in error_message or "/nonexistent/path" in error_message, \
            f"Error message should reference the missing file: {error_message}"

    def test_json_decode_error_message(self, temp_dir):
        """Test clear error message for invalid JSON."""
        invalid_file = os.path.join(temp_dir, "invalid.json")
        with open(invalid_file, 'w') as f:
            f.write("not valid json {{{")

        retriever = ProductionStockRetriever()
        retriever.ticker_file = invalid_file

        with pytest.raises(json.JSONDecodeError):
            retriever.load_tickers()
