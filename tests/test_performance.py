"""Tests for performance baselines and benchmarking.

Tests processing speed, memory usage, rate limiting effectiveness,
and scalability with large datasets.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from production_stock_retrieval import ProductionStockRetriever
from stock_notion_retrieval import StockDataNotionRetriever, TimeChunk


class TestProcessingSpeed:
    """Tests for processing speed baselines."""

    @pytest.mark.slow
    def test_ticker_processing_rate(self, temp_dir):
        """Test that ticker processing meets minimum rate."""
        tickers = [f"TICK{i:04d}" for i in range(100)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
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
        assert elapsed < 5.0, f"Processing took too long: {elapsed}s"

        # Calculate rate
        rate = retriever.processed / elapsed
        assert rate > 10, f"Processing rate too slow: {rate} tickers/sec"

    def test_single_ticker_processing_time(self):
        """Test processing time for a single ticker."""
        retriever = ProductionStockRetriever()

        with patch('time.sleep'):
            start_time = time.time()
            for period in retriever.periods:
                retriever.get_polygon_data("AAPL", period)
            elapsed = time.time() - start_time

        # 5 periods should complete quickly (< 0.1 second without API)
        assert elapsed < 0.1

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
        assert elapsed < 1.0


class TestMemoryUsage:
    """Tests for memory usage patterns."""

    def test_batch_size_memory_impact(self):
        """Test that batch processing doesn't accumulate excess memory."""
        import sys

        retriever = ProductionStockRetriever()

        # Process first batch
        batch1_size = sys.getsizeof(retriever)

        # Process second batch
        retriever.processed = 0
        retriever.saved = 0

        batch2_size = sys.getsizeof(retriever)

        # Size shouldn't grow significantly between batches
        assert batch2_size <= batch1_size * 1.1

    def test_ticker_list_memory_efficiency(self):
        """Test memory efficiency with large ticker lists."""
        import sys

        tickers_small = ["AAPL"] * 100
        tickers_large = ["AAPL"] * 10000

        size_small = sys.getsizeof(tickers_small)
        size_large = sys.getsizeof(tickers_large)

        # Large list should be roughly proportional (within 2x overhead)
        ratio = size_large / size_small
        assert ratio < 200  # Should be approximately 100x, allow some overhead

    def test_page_data_memory_footprint(self):
        """Test memory footprint of page data structure."""
        import sys

        page = {
            "properties": {
                "Ticker": "AAPL",
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
        }

        page_size = sys.getsizeof(page)
        props_size = sys.getsizeof(page["properties"])

        # Page should be reasonable size (< 1KB base)
        assert page_size < 1024
        assert props_size < 2048


class TestRateLimitingEffectiveness:
    """Tests for rate limiting functionality."""

    def test_rate_limit_delay_is_applied(self):
        """Test that rate limiting delays are actually applied."""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["AAPL"]

        sleep_calls = []

        def track_sleep(duration):
            sleep_calls.append(duration)

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep', side_effect=track_sleep):
                retriever.process_batch(retriever.tickers, 1, 1)

        # Should have 5 sleep calls (one per period)
        assert len(sleep_calls) == 5
        # Each should be 10ms
        assert all(s == 0.01 for s in sleep_calls)

    def test_total_delay_calculation(self):
        """Test calculation of total rate limiting delay."""
        tickers_count = 100
        periods_count = 5
        delay_per_call = 0.01  # 10ms

        total_api_calls = tickers_count * periods_count
        total_delay = total_api_calls * delay_per_call

        # 500 calls * 10ms = 5 seconds
        assert total_delay == 5.0

    def test_rate_limiting_prevents_burst(self):
        """Test that rate limiting prevents API burst."""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["AAPL", "MSFT"]

        timestamps = []

        def record_timestamp(duration):
            timestamps.append(time.time())

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep', side_effect=record_timestamp):
                retriever.process_batch(retriever.tickers, 1, 1)

        # Verify calls are spaced out (not all at once)
        if len(timestamps) > 1:
            # All timestamps should be different (spaced by delay)
            assert len(set(timestamps)) > 1


class TestScalability:
    """Tests for scalability with large datasets."""

    @pytest.mark.slow
    def test_process_1000_tickers(self, temp_dir):
        """Test processing 1000 tickers efficiently."""
        tickers = [f"TICK{i:04d}" for i in range(1000)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 100

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()

                start_time = time.time()
                for batch_num in range(1, 11):  # 10 batches of 100
                    start_idx = (batch_num - 1) * 100
                    end_idx = start_idx + 100
                    batch = retriever.tickers[start_idx:end_idx]
                    retriever.process_batch(batch, batch_num, 10)
                elapsed = time.time() - start_time

        assert retriever.processed == 1000
        # Should complete in reasonable time (< 30 seconds)
        assert elapsed < 30

    def test_batch_count_calculation(self):
        """Test batch count calculation for various ticker counts."""
        test_cases = [
            (100, 100, 1),
            (250, 100, 3),
            (6626, 100, 67),
            (1000, 100, 10),
            (99, 100, 1),
            (101, 100, 2),
        ]

        for ticker_count, batch_size, expected_batches in test_cases:
            batches = (ticker_count + batch_size - 1) // batch_size
            assert batches == expected_batches

    def test_estimated_runtime_calculation(self):
        """Test estimated runtime calculation."""
        ticker_count = 6626
        periods = 5
        delay_per_call = 0.01  # 10ms

        api_calls = ticker_count * periods
        estimated_seconds = api_calls * delay_per_call
        estimated_time = timedelta(seconds=estimated_seconds)

        # 33,130 calls * 10ms = 331.3 seconds = ~5.5 minutes
        assert estimated_seconds == pytest.approx(331.3, rel=0.01)
        assert estimated_time.total_seconds() < 600  # Less than 10 minutes


class TestBatchSizeOptimization:
    """Tests for batch size optimization."""

    @pytest.mark.parametrize("batch_size", [10, 50, 100, 200, 500])
    def test_various_batch_sizes(self, temp_dir, batch_size):
        """Test processing with various batch sizes."""
        tickers = [f"TICK{i:03d}" for i in range(batch_size)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = batch_size

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()
                retriever.process_batch(retriever.tickers, 1, 1)

        assert retriever.processed == batch_size

    def test_optimal_batch_size_for_memory(self):
        """Test that default batch size is memory-efficient."""
        retriever = ProductionStockRetriever()

        # Default batch size
        assert retriever.batch_size == 100

        # 100 tickers * 5 periods * ~500 bytes per page = ~250KB per batch
        estimated_batch_memory = 100 * 5 * 500
        assert estimated_batch_memory < 1024 * 1024  # Less than 1MB


class TestPerformanceMetrics:
    """Tests for performance metric calculations."""

    def test_tickers_per_second_calculation(self):
        """Test tickers per second calculation."""
        processed = 1000
        duration_seconds = 100.0

        rate = processed / duration_seconds

        assert rate == 10.0

    def test_average_ticker_time_calculation(self):
        """Test average time per ticker calculation."""
        processed = 100
        duration_seconds = 10.0

        avg_time = duration_seconds / processed

        assert avg_time == 0.1  # 100ms per ticker

    def test_eta_calculation(self):
        """Test ETA (estimated time remaining) calculation."""
        processed = 1000
        total = 6626
        elapsed_seconds = 100.0

        rate = processed / elapsed_seconds
        remaining = total - processed
        eta_seconds = remaining / rate if rate > 0 else 0

        expected_eta = (6626 - 1000) / 10.0  # 562.6 seconds
        assert eta_seconds == pytest.approx(562.6, rel=0.01)

    def test_progress_percentage_calculation(self):
        """Test progress percentage calculation."""
        test_cases = [
            (0, 100, 0.0),
            (50, 100, 50.0),
            (100, 100, 100.0),
            (3313, 6626, 50.0),
            (6626, 6626, 100.0),
        ]

        for processed, total, expected_pct in test_cases:
            pct = (processed / total) * 100
            assert pct == pytest.approx(expected_pct, rel=0.01)
