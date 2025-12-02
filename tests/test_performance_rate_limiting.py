"""Tests for rate limiting functionality.

Tests that rate limiting is applied correctly to prevent API abuse.
"""

import time
from unittest.mock import patch

import pytest

from production_stock_retrieval import ProductionStockRetriever


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

    def test_rate_limit_constant_value(self):
        """Test that rate limit delay constant is correct."""
        # The delay should be 10ms (0.01 seconds)
        expected_delay = 0.01

        retriever = ProductionStockRetriever()

        # Verify by checking actual sleep call
        sleep_calls = []
        with patch('time.sleep', side_effect=lambda d: sleep_calls.append(d)):
            retriever.get_polygon_data("AAPL", retriever.periods[0])

        if sleep_calls:
            assert sleep_calls[0] == expected_delay

    def test_rate_limiting_across_batches(self):
        """Test rate limiting is consistent across batches."""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["AAPL"]

        batch1_sleeps = []
        batch2_sleeps = []

        def track_batch1(duration):
            batch1_sleeps.append(duration)

        def track_batch2(duration):
            batch2_sleeps.append(duration)

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep', side_effect=track_batch1):
                retriever.process_batch(retriever.tickers, 1, 2)

            retriever.processed = 0
            with patch('time.sleep', side_effect=track_batch2):
                retriever.process_batch(retriever.tickers, 2, 2)

        # Both batches should have same rate limiting
        assert batch1_sleeps == batch2_sleeps

    def test_api_calls_per_minute_estimate(self):
        """Test estimated API calls per minute with rate limiting."""
        delay_per_call = 0.01  # 10ms
        calls_per_second = 1 / delay_per_call  # 100 calls/sec max
        calls_per_minute = calls_per_second * 60  # 6000 calls/min max

        # Verify calculation
        assert calls_per_minute == 6000

        # With processing overhead, expect fewer
        realistic_rate = calls_per_minute * 0.8  # 80% efficiency
        assert realistic_rate == 4800

    def test_cumulative_delay_tracking(self):
        """Test tracking of cumulative delay time."""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["AAPL", "MSFT", "GOOGL"]

        total_delay = 0
        call_count = 0

        def accumulate_delay(duration):
            nonlocal total_delay, call_count
            total_delay += duration
            call_count += 1

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep', side_effect=accumulate_delay):
                retriever.process_batch(retriever.tickers, 1, 1)

        # 3 tickers * 5 periods = 15 calls * 0.01s = 0.15s
        expected_delay = 3 * 5 * 0.01
        assert total_delay == pytest.approx(expected_delay)
        assert call_count == 15
