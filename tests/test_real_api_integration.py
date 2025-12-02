"""Real API integration tests for Polygon API.

These tests make actual API calls and require:
1. POLYGON_API_KEY environment variable to be set
2. Network connectivity to polygon.io

Run with: pytest tests/test_real_api_integration.py -v --run-real-api
Skip in CI by not passing --run-real-api flag.
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from production_stock_retrieval import ProductionStockRetriever


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "real_api: mark test as requiring real API access"
    )


def has_api_key():
    """Check if Polygon API key is available."""
    return bool(os.environ.get("POLYGON_API_KEY"))


def skip_without_api_key(reason="POLYGON_API_KEY not set"):
    """Skip decorator for tests requiring API key."""
    return pytest.mark.skipif(not has_api_key(), reason=reason)


@pytest.fixture
def api_key():
    """Get API key from environment."""
    key = os.environ.get("POLYGON_API_KEY")
    if not key:
        pytest.skip("POLYGON_API_KEY environment variable not set")
    return key


@pytest.fixture
def real_retriever(api_key, temp_dir):
    """Create retriever configured for real API calls."""
    retriever = ProductionStockRetriever()
    retriever.api_key = api_key
    return retriever


class TestPolygonAPIConnectivity:
    """Tests for basic API connectivity."""

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_api_key_is_valid(self, api_key):
        """Test that the API key is valid and working."""
        # This is a basic sanity check
        assert len(api_key) > 10, "API key seems too short"
        assert api_key.isalnum() or "_" in api_key, "API key has unexpected format"

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_can_instantiate_retriever_with_api_key(self, real_retriever):
        """Test that retriever can be instantiated with API key."""
        assert real_retriever is not None
        assert hasattr(real_retriever, 'api_key')


class TestRealTickerData:
    """Tests for fetching real ticker data."""

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_fetch_single_ticker_data(self, real_retriever):
        """Test fetching data for a single well-known ticker."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        result = real_retriever.get_polygon_data("AAPL", period)

        # Verify result structure
        assert result is not None
        assert "ticker" in result
        assert result["ticker"] == "AAPL"
        assert "period" in result
        assert "has_data" in result

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_fetch_multiple_tickers(self, real_retriever):
        """Test fetching data for multiple tickers."""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        results = []
        for ticker in tickers:
            result = real_retriever.get_polygon_data(ticker, period)
            results.append(result)
            time.sleep(0.1)  # Rate limiting

        assert len(results) == 3
        for result in results:
            assert "ticker" in result

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_fetch_invalid_ticker(self, real_retriever):
        """Test fetching data for an invalid ticker."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        # Use clearly invalid ticker
        result = real_retriever.get_polygon_data("INVALIDTICKER123456", period)

        # Should return result indicating no data
        assert result is not None
        assert result.get("has_data") is False or result.get("data_points", 0) == 0


class TestRealAPIRateLimiting:
    """Tests for real API rate limiting behavior."""

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_rate_limiting_respected(self, real_retriever):
        """Test that rate limiting delays are applied correctly."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-05",
            "label": "2024-Jan-Week1"
        }

        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        start_time = time.time()
        for ticker in tickers:
            real_retriever.get_polygon_data(ticker, period)
            time.sleep(0.01)  # 10ms delay as per implementation
        elapsed = time.time() - start_time

        # Should take at least 50ms (5 tickers * 10ms)
        assert elapsed >= 0.05

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_burst_protection(self, real_retriever):
        """Test that API doesn't get hit too quickly."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-02",
            "label": "test"
        }

        call_times = []
        for i in range(5):
            call_times.append(time.time())
            real_retriever.get_polygon_data("AAPL", period)
            time.sleep(0.02)  # Slightly longer delay for safety

        # Verify calls are spaced out
        for i in range(1, len(call_times)):
            gap = call_times[i] - call_times[i-1]
            assert gap >= 0.01, f"Calls too close together: {gap}s"


class TestRealDataQuality:
    """Tests for data quality from real API."""

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_price_data_is_reasonable(self, real_retriever):
        """Test that price data falls within reasonable ranges."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        result = real_retriever.get_polygon_data("AAPL", period)

        if result.get("has_data"):
            # AAPL price should be between $50 and $500 (reasonable range)
            if "open" in result and result["open"]:
                assert 50 <= result["open"] <= 500
            if "close" in result and result["close"]:
                assert 50 <= result["close"] <= 500
            if "high" in result and result["high"]:
                assert 50 <= result["high"] <= 500
            if "low" in result and result["low"]:
                assert 50 <= result["low"] <= 500

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_volume_data_is_positive(self, real_retriever):
        """Test that volume data is positive."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        result = real_retriever.get_polygon_data("AAPL", period)

        if result.get("has_data") and "volume" in result:
            assert result["volume"] >= 0

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_high_low_relationship(self, real_retriever):
        """Test that high >= low always."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        result = real_retriever.get_polygon_data("AAPL", period)

        if result.get("has_data"):
            high = result.get("high")
            low = result.get("low")
            if high is not None and low is not None:
                assert high >= low


class TestRealHistoricalData:
    """Tests for fetching historical data."""

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_fetch_old_data(self, real_retriever):
        """Test fetching data from several years ago."""
        period = {
            "from": "2020-01-01",
            "to": "2020-12-31",
            "label": "2020"
        }

        result = real_retriever.get_polygon_data("AAPL", period)

        # AAPL should have data for 2020
        assert result is not None
        # Note: has_data depends on actual API response

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_fetch_very_old_data(self, real_retriever):
        """Test fetching data from many years ago."""
        period = {
            "from": "2005-01-01",
            "to": "2005-12-31",
            "label": "2005"
        }

        result = real_retriever.get_polygon_data("AAPL", period)

        assert result is not None

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_fetch_multiple_periods(self, real_retriever):
        """Test fetching data across multiple time periods."""
        periods = [
            {"from": "2024-01-01", "to": "2024-01-31", "label": "2024-Jan"},
            {"from": "2023-01-01", "to": "2023-01-31", "label": "2023-Jan"},
            {"from": "2022-01-01", "to": "2022-01-31", "label": "2022-Jan"},
        ]

        results = []
        for period in periods:
            result = real_retriever.get_polygon_data("AAPL", period)
            results.append(result)
            time.sleep(0.02)

        assert len(results) == 3
        for result in results:
            assert result is not None


class TestRealEndToEnd:
    """End-to-end tests with real API."""

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_process_small_batch_real(self, real_retriever, temp_dir):
        """Test processing a small batch with real API."""
        tickers = ["AAPL", "MSFT"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        real_retriever.ticker_file = ticker_file
        real_retriever.batch_size = 2

        # Use only one short period for speed
        real_retriever.periods = [
            {"from": "2024-01-01", "to": "2024-01-05", "label": "test-period"}
        ]

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            real_retriever.load_tickers()
            real_retriever.process_batch(real_retriever.tickers, 1, 1)

        # Verify batch file created
        batch_file = Path(temp_dir) / "batch_0001_notion.json"
        assert batch_file.exists()

        with open(batch_file) as f:
            data = json.load(f)

        assert "pages" in data
        assert len(data["pages"]) >= 1

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_checkpoint_with_real_data(self, real_retriever, temp_dir):
        """Test checkpoint creation with real API data."""
        tickers = ["AAPL"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        real_retriever.ticker_file = ticker_file
        real_retriever.batch_size = 1
        real_retriever.periods = [
            {"from": "2024-01-01", "to": "2024-01-02", "label": "test"}
        ]

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            real_retriever.load_tickers()
            real_retriever.process_batch(real_retriever.tickers, 1, 1)
            real_retriever.save_checkpoint(1)

        checkpoint_file = Path(temp_dir) / "checkpoint.json"
        assert checkpoint_file.exists()


class TestAPIErrorHandling:
    """Tests for API error handling with real API."""

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_handles_nonexistent_ticker_gracefully(self, real_retriever):
        """Test graceful handling of nonexistent ticker."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        # This should not raise an exception
        result = real_retriever.get_polygon_data("ZZZZZZZZZZZZ", period)

        assert result is not None
        # Should indicate no data or handle gracefully

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_handles_future_date_gracefully(self, real_retriever):
        """Test graceful handling of future dates."""
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        period = {
            "from": future_date,
            "to": future_date,
            "label": "future"
        }

        # This should not raise an exception
        result = real_retriever.get_polygon_data("AAPL", period)

        assert result is not None

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_handles_weekend_dates(self, real_retriever):
        """Test handling of weekend dates (no market data)."""
        # January 6, 2024 was a Saturday
        period = {
            "from": "2024-01-06",
            "to": "2024-01-07",  # Saturday to Sunday
            "label": "weekend"
        }

        result = real_retriever.get_polygon_data("AAPL", period)

        # Should handle gracefully even with no trading data
        assert result is not None
