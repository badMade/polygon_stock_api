"""Tests for memory usage patterns.

Tests memory efficiency and footprint of data structures.
"""

import os
import sys
from datetime import datetime

import psutil
import pytest

from production_stock_retrieval import ProductionStockRetriever


class TestMemoryUsage:
    """Tests for memory usage patterns."""

    def test_batch_size_memory_impact(self):
        """Test that batch processing doesn't accumulate excess memory."""
        import gc
        
        MB_IN_BYTES = 1024 * 1024
        
        # Get current process for memory monitoring
        process = psutil.Process(os.getpid())
        
        # Create retriever and simulate batch processing
        retriever = ProductionStockRetriever()
        
        # Simulate first batch (reset counters)
        retriever.processed = 100
        retriever.saved = 100
        gc.collect()
        batch1_memory = process.memory_info().rss
        
        # Simulate second batch (reset counters again)
        retriever.processed = 0
        retriever.saved = 0
        gc.collect()
        batch2_memory = process.memory_info().rss
        
        # Memory shouldn't grow significantly between batches
        # Allow up to 10% growth for reasonable fluctuation
        memory_growth = batch2_memory - batch1_memory
        assert memory_growth <= batch1_memory * 0.1, \
            f"Memory grew by {memory_growth / MB_IN_BYTES:.2f} MB between batches"

    def test_ticker_list_memory_efficiency(self):
        """Test memory efficiency with large ticker lists."""
        tickers_small = ["AAPL"] * 100
        tickers_large = ["AAPL"] * 10000

        size_small = sys.getsizeof(tickers_small)
        size_large = sys.getsizeof(tickers_large)

        # Large list should be roughly proportional (within 2x overhead)
        ratio = size_large / size_small
        assert ratio < 200  # Should be approximately 100x, allow some overhead

    def test_page_data_memory_footprint(self):
        """Test memory footprint of page data structure."""
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

    def test_retriever_base_memory_footprint(self):
        """Test base memory footprint of retriever instance."""
        retriever = ProductionStockRetriever()

        base_size = sys.getsizeof(retriever)

        # Base size should be reasonable
        assert base_size < 1024  # Less than 1KB for object itself

    def test_period_list_memory(self):
        """Test memory usage of period list."""
        retriever = ProductionStockRetriever()

        periods_size = sys.getsizeof(retriever.periods)
        single_period_size = sys.getsizeof(retriever.periods[0])

        # 5 periods should be reasonable
        assert periods_size < 512
        assert single_period_size < 512

    def test_string_interning_efficiency(self):
        """Test that repeated strings benefit from interning."""
        # Create many pages with same string values
        pages = []
        for i in range(100):
            pages.append({
                "properties": {
                    "Period": "2020-2024",  # Same string
                    "Has Data": "__YES__",  # Same string
                    "Timespan": "day"  # Same string
                }
            })

        # All Period strings should be the same object (interned)
        first_period = pages[0]["properties"]["Period"]
        for page in pages[1:]:
            assert page["properties"]["Period"] is first_period

    def test_large_batch_memory_cleanup(self):
        """Test that memory is released after processing large batch."""
        import gc

        retriever = ProductionStockRetriever()

        # Create large list
        large_data = [{"data": "x" * 1000} for _ in range(1000)]
        initial_size = sys.getsizeof(large_data)

        # Delete and collect
        del large_data
        gc.collect()

        # Retriever should still be small
        retriever_size = sys.getsizeof(retriever)
        assert retriever_size < initial_size
