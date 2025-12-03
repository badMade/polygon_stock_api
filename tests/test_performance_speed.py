"""Tests for processing speed baselines.

Tests processing time for tickers, batches, and file operations.
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from production_stock_retrieval import ProductionStockRetriever

# CI-aware timing multiplier to prevent flaky tests in CI environments
CI_MULTIPLIER = 2.0 if os.getenv("CI") else 1.0


class TestProcessingSpeed:
    """Tests for processing speed baselines."""

    @pytest.mark.slow
    def test_ticker_processing_rate(self, temp_dir):
        """Test that ticker processing meets minimum rate."""
        tickers = [f"TICK{i:04d}" for i in range(100)]
        ticker_file = Path(temp_dir) / "tickers.json"
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 100

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):  # Skip rate limiting for speed test
                retriever.load_tickers()

                start_time = time.time()
                retriever.process_batch(retriever.tickers, 1, 1)
                elapsed = time.time() - start_time

        # Should process 100 tickers in reasonable time (< 5 seconds without API)
        # Use CI multiplier for CI environments
        threshold = 5.0 * CI_MULTIPLIER
        assert elapsed < threshold, f"Processing took too long: {elapsed}s (threshold: {threshold}s)"

        # Calculate rate
        rate = retriever.processed / elapsed
        min_rate = 10 / CI_MULTIPLIER  # Reduce rate expectation in CI
        assert rate > min_rate, f"Processing rate too slow: {rate} tickers/sec (min: {min_rate})"

    def test_single_ticker_processing_time(self):
        """Test processing time for a single ticker."""
        retriever = ProductionStockRetriever()

        with patch('time.sleep'):
            start_time = time.time()
            for period in retriever.periods:
                retriever.get_polygon_data("AAPL", period)
            elapsed = time.time() - start_time

        # 5 periods should complete quickly (< 0.1 second without API)
        threshold = 0.1 * CI_MULTIPLIER
        assert elapsed < threshold, f"Processing took too long: {elapsed}s (threshold: {threshold}s)"

    def test_batch_file_write_speed(self, temp_dir):
        """Test speed of writing batch files."""
        retriever = ProductionStockRetriever()

        # Create large batch of pages
        pages = [
            {
                "properties": {
                    "Ticker": f"TICK{i:04d}",
                    "Period": "2020-2024",
                    "Has Data": "__YES__"
                }
            }
            for i in range(500)
        ]

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            start_time = time.time()
            retriever.save_batch(pages, 1)
            elapsed = time.time() - start_time

        # Writing 500 pages should be fast (< 1 second)
        threshold = 1.0 * CI_MULTIPLIER
        assert elapsed < threshold, f"File write took too long: {elapsed}s (threshold: {threshold}s)"

    def test_json_serialization_speed(self, temp_dir):
        """Test speed of JSON serialization for batch data."""
        from datetime import datetime

        # Create realistic batch data
        pages = []
        for i in range(500):
            pages.append({
                "properties": {
                    "Ticker": f"TICK{i:04d}",
                    "Period": "2020-2024",
                    "Has Data": "__YES__",
                    "Batch Number": 1,
                    "date:Date:start": "2020-01-01",
                    "date:Date:is_datetime": 0,
                    "date:Retrieved At:start": datetime.now().isoformat(),
                    "date:Retrieved At:is_datetime": 1,
                    "Open": 150.25,
                    "High": 155.50,
                    "Low": 149.00,
                    "Close": 154.30,
                    "Volume": 50000000,
                    "VWAP": 152.45,
                    "Transactions": 450000,
                    "Data Points": 252,
                    "Timespan": "day"
                }
            })

        batch_data = {
            "data_source_id": "test-id",
            "batch_number": 1,
            "record_count": len(pages),
            "timestamp": datetime.now().isoformat(),
            "pages": pages
        }

        start_time = time.time()
        json_str = json.dumps(batch_data, indent=2)
        elapsed = time.time() - start_time

        # JSON serialization should be fast
        threshold = 0.5 * CI_MULTIPLIER
        assert elapsed < threshold, f"JSON serialization took too long: {elapsed}s (threshold: {threshold}s)"
        assert len(json_str) > 0

    def test_ticker_list_loading_speed(self, temp_dir):
        """Test speed of loading ticker list from file."""
        tickers = [f"TICK{i:04d}" for i in range(7000)]
        ticker_file = Path(temp_dir) / "tickers.json"
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        start_time = time.time()
        retriever.load_tickers()
        elapsed = time.time() - start_time

        # Loading 7000 tickers should be fast
        threshold = 1.0 * CI_MULTIPLIER
        assert elapsed < threshold, f"Ticker loading took too long: {elapsed}s (threshold: {threshold}s)"
        assert len(retriever.tickers) == 7000
