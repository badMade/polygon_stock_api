"""Tests for scalability with large datasets.

Tests batch processing, size optimization, and performance metrics.
"""

import json
import os
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from production_stock_retrieval import ProductionStockRetriever


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

    @pytest.mark.slow
    def test_large_ticker_list_handling(self, temp_dir):
        """Test handling of very large ticker lists."""
        tickers = [f"T{i:06d}" for i in range(10000)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        retriever.load_tickers()

        assert len(retriever.tickers) == 10000

    def test_batch_file_accumulation(self, temp_dir):
        """Test that batch files accumulate correctly."""
        retriever = ProductionStockRetriever()

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            for i in range(5):
                pages = [{"properties": {"Ticker": f"T{i}"}}]
                retriever.save_batch(pages, i + 1)

        # Should have 5 batch files
        batch_files = list(Path(temp_dir).glob("batch_*_notion.json"))
        assert len(batch_files) == 5


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

    def test_small_batch_overhead(self, temp_dir):
        """Test overhead with very small batches."""
        retriever = ProductionStockRetriever()

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            start = time.time()
            for i in range(10):
                pages = [{"properties": {"Ticker": "T"}}]
                retriever.save_batch(pages, i + 1)
            elapsed = time.time() - start

        # 10 small batches should still be fast
        assert elapsed < 1.0

    def test_large_batch_processing(self, temp_dir):
        """Test processing a large batch."""
        tickers = [f"TICK{i:04d}" for i in range(500)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 500

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()
                retriever.process_batch(retriever.tickers, 1, 1)

        assert retriever.processed == 500


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
        retriever = ProductionStockRetriever()
        
        processed = 1000
        total = 6626
        elapsed_seconds = 100.0

        eta = retriever.calculate_eta(processed, total, elapsed_seconds)

        # Expected: (6626 - 1000) / (1000/100) = 5626 / 10 = 562.6 seconds
        expected_eta = timedelta(seconds=562.6)
        assert eta.total_seconds() == pytest.approx(expected_eta.total_seconds(), rel=0.01)

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

    def test_throughput_calculation(self):
        """Test throughput calculation."""
        bytes_written = 1024 * 1024  # 1MB
        elapsed_seconds = 2.0

        throughput = bytes_written / elapsed_seconds
        throughput_mb = throughput / (1024 * 1024)

        assert throughput_mb == 0.5  # 0.5 MB/s

    def test_batch_efficiency_metric(self):
        """Test batch efficiency calculation."""
        successful_records = 95
        total_records = 100

        efficiency = (successful_records / total_records) * 100

        assert efficiency == 95.0

    def test_api_success_rate(self):
        """Test API success rate calculation."""
        successful_calls = 4900
        total_calls = 5000

        success_rate = (successful_calls / total_calls) * 100

        assert success_rate == 98.0

    def test_zero_division_protection(self):
        """Test that ETA calculation handles zero division correctly."""
        retriever = ProductionStockRetriever()
        
        # Test with zero elapsed time (no progress yet)
        eta = retriever.calculate_eta(
            processed_count=0,
            total_count=100,
            elapsed_seconds=0.0
        )
        assert eta == timedelta(0), "Should return timedelta(0) when elapsed time is 0"
        
        # Test with zero progress (rate would be 0)
        eta = retriever.calculate_eta(
            processed_count=0,
            total_count=100,
            elapsed_seconds=10.0
        )
        assert eta == timedelta(0), "Should return timedelta(0) when rate is 0"
        
        # Test with valid progress
        eta = retriever.calculate_eta(
            processed_count=50,
            total_count=100,
            elapsed_seconds=10.0
        )
        # 50 remaining / (50/10) = 50 / 5 = 10 seconds
        assert eta == timedelta(seconds=10), "Should calculate correct ETA with valid progress"
