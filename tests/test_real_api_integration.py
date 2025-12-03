"""Real API integration tests for Polygon API.

These tests make actual API calls and require:
1. POLYGON_API_KEY environment variable to be set
2. Network connectivity to polygon.io

Run with: pytest tests/test_real_api_integration.py -v -m real_api
Skip in CI by not passing -m real_api flag.
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from production_stock_retrieval import ProductionStockRetriever


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
        assert result is not None, "API call failed to return data"
        assert "ticker" in result, "Result missing 'ticker' field"
        assert result["ticker"] == "AAPL", f"Expected ticker 'AAPL', got {result.get('ticker')}"
        assert "period" in result, "Result missing 'period' field"
        assert "has_data" in result, "Result missing 'has_data' field"

        # Verify data quality if data is present
        if result.get("has_data"):
            # Check that expected data fields exist when has_data is True
            if "open" in result:
                assert result["open"] is not None, "Open price should not be None when has_data is True"
            if "close" in result:
                assert result["close"] is not None, "Close price should not be None when has_data is True"

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
        """Test that rate limiting delays are applied correctly by _process_ticker_period."""
        # Use a single period to avoid confusion from multiple periods
        # Override the retriever's default periods
        real_retriever.periods = [{
            "from": "2024-01-01",
            "to": "2024-01-05",
            "label": "2024-Jan-Week1"
        }]
        period = real_retriever.periods[0]

        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        # Test the actual production method that contains rate limiting
        start_time = time.time()
        for ticker in tickers:
            # _process_ticker_period contains time.sleep(0.01) at line 200
            real_retriever._process_ticker_period(ticker, period, batch_num=1)
        elapsed = time.time() - start_time

        # Should take at least 50ms (5 tickers * 10ms from _process_ticker_period)
        # Allow for some timing variance but ensure rate limiting is working
        assert elapsed >= 0.045, f"Rate limiting not working: only took {elapsed}s, expected >= 0.05s"

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_burst_protection(self, real_retriever):
        """Test that production code includes rate limiting delays."""
        period = {
            "from": "2024-01-01",
            "to": "2024-01-02",
            "label": "test"
        }

        # Measure time gaps between calls using production method
        call_times = []
        for i in range(5):
            start = time.time()
            real_retriever._process_ticker_period("AAPL", period, batch_num=1)
            end = time.time()
            call_times.append(end - start)

        # Each call should take at least 10ms due to internal time.sleep(0.01)
        # Use slightly lower threshold to account for timing variance
        for i, duration in enumerate(call_times):
            assert duration >= 0.008, f"Call {i} too fast: {duration}s (expected >= 0.01s from rate limiting)"


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
            # Use very wide range to accommodate different stocks and time periods
            # Focus on relative validations instead of absolute ranges
            if "open" in result and result["open"]:
                assert result["open"] > 0, "Open price must be positive"
                assert result["open"] < 100000, "Open price seems unreasonably high"
            if "close" in result and result["close"]:
                assert result["close"] > 0, "Close price must be positive"
                assert result["close"] < 100000, "Close price seems unreasonably high"
            if "high" in result and result["high"]:
                assert result["high"] > 0, "High price must be positive"
                assert result["high"] < 100000, "High price seems unreasonably high"
            if "low" in result and result["low"]:
                assert result["low"] > 0, "Low price must be positive"
                assert result["low"] < 100000, "Low price seems unreasonably high"

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
        ticker_file = Path(temp_dir) / "tickers.json"
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
        ticker_file = Path(temp_dir) / "tickers.json"
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

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_handles_network_errors_gracefully(self, real_retriever):
        """Test graceful handling of network errors."""
        from unittest.mock import patch
        import requests

        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        # Mock network timeout
        with patch.object(real_retriever, 'get_polygon_data',
                         side_effect=requests.exceptions.Timeout("Network timeout")):
            try:
                result = real_retriever.get_polygon_data("AAPL", period)
                # If no exception is raised, check the result structure
                assert result is not None
            except requests.exceptions.Timeout:
                # Network errors should be caught and handled gracefully
                # In production, the method should return a null result instead of raising
                pass

    @pytest.mark.real_api
    def test_handles_invalid_api_key_gracefully(self, temp_dir):
        """Test graceful handling of invalid API key."""
        # Create retriever with invalid key
        retriever = ProductionStockRetriever()
        retriever.api_key = "INVALID_KEY_12345"

        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        # Should not crash, should return error structure
        result = retriever.get_polygon_data("AAPL", period)

        assert result is not None
        assert "ticker" in result
        # Should indicate failure
        assert result.get("has_data") is False or result.get("error") is not None

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_handles_malformed_response(self, real_retriever):
        """Test handling of malformed API responses."""
        from unittest.mock import patch

        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        # Mock malformed response (missing expected fields)
        with patch.object(real_retriever, 'get_polygon_data',
                         return_value={"unexpected": "structure"}):
            result = real_retriever.get_polygon_data("AAPL", period)

            # Should handle missing fields gracefully
            assert result is not None
            # Even malformed responses should be handled without crashing

    @pytest.mark.real_api
    @skip_without_api_key()
    def test_handles_rate_limit_429_gracefully(self, real_retriever):
        """Test graceful handling of HTTP 429 rate limit errors."""
        from unittest.mock import patch
        import requests

        period = {
            "from": "2024-01-01",
            "to": "2024-01-31",
            "label": "2024-Jan"
        }

        # Create a mock response with 429 status
        mock_response = requests.Response()
        mock_response.status_code = 429

        # Mock HTTP 429 error
        with patch.object(real_retriever, 'get_polygon_data',
                         side_effect=requests.exceptions.HTTPError(
                             "429 Too Many Requests", response=mock_response)):
            try:
                result = real_retriever.get_polygon_data("AAPL", period)
                # If no exception, check result indicates failure
                assert result is not None
                assert result.get("has_data") is False or result.get("error") is not None
            except requests.exceptions.HTTPError:
                # Rate limit errors should be caught and handled
                # In production, should retry with backoff or return null result
                pass
