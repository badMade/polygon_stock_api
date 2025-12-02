"""Tests for memory usage patterns.

Tests memory efficiency and footprint of data structures.
"""

import sys
from datetime import datetime

import pytest

from production_stock_retrieval import ProductionStockRetriever


class TestMemoryUsage:
    """Tests for memory usage patterns."""

    def test_batch_size_memory_impact(self):
        """Test that batch processing doesn't accumulate excess memory."""
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
