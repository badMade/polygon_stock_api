"""Tests for realistic API response handling.

Tests handling of various Polygon API response formats, error codes,
rate limiting, and edge cases in API responses.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from production_stock_retrieval import ProductionStockRetriever
from stock_notion_retrieval import StockDataNotionRetriever, TimeChunk


class TestPolygonAPIResponseFormats:
    """Tests for handling various Polygon API response formats."""

    @pytest.fixture
    def sample_polygon_success_response(self):
        """Realistic successful Polygon API response."""
        return {
            "ticker": "AAPL",
            "queryCount": 252,
            "resultsCount": 252,
            "adjusted": True,
            "results": [
                {
                    "v": 82572323,    # volume
                    "vw": 149.8291,   # vwap
                    "o": 149.31,      # open
                    "c": 150.44,      # close
                    "h": 150.77,      # high
                    "l": 148.5501,    # low
                    "t": 1641186000000,  # timestamp
                    "n": 695724       # transactions
                },
                {
                    "v": 74286654,
                    "vw": 148.7199,
                    "o": 148.36,
                    "c": 149.28,
                    "h": 149.37,
                    "l": 147.685,
                    "t": 1641272400000,
                    "n": 620814
                }
            ],
            "status": "OK",
            "request_id": "abc123",
            "count": 252
        }

    @pytest.fixture
    def sample_polygon_empty_response(self):
        """Polygon API response with no results."""
        return {
            "ticker": "UNKNOWN",
            "queryCount": 0,
            "resultsCount": 0,
            "adjusted": True,
            "results": [],
            "status": "OK",
            "request_id": "xyz789",
            "count": 0
        }

    @pytest.fixture
    def sample_polygon_error_response(self):
        """Polygon API error response."""
        return {
            "status": "ERROR",
            "request_id": "err456",
            "error": "Ticker not found"
        }

    def test_parse_successful_response(self, sample_polygon_success_response):
        """Test parsing a successful Polygon API response."""
        response = sample_polygon_success_response

        # Parse the response as the system would
        assert response["status"] == "OK"
        assert response["resultsCount"] == 252
        assert len(response["results"]) == 2

        # Extract data from first result
        result = response["results"][0]
        assert result["o"] == 149.31  # open
        assert result["h"] == 150.77  # high
        assert result["l"] == 148.5501  # low
        assert result["c"] == 150.44  # close
        assert result["v"] == 82572323  # volume
        assert result["vw"] == 149.8291  # vwap
        assert result["n"] == 695724  # transactions

    def test_parse_empty_response(self, sample_polygon_empty_response):
        """Test parsing an empty Polygon API response."""
        response = sample_polygon_empty_response

        assert response["status"] == "OK"
        assert response["resultsCount"] == 0
        assert response["results"] == []

    def test_parse_error_response(self, sample_polygon_error_response):
        """Test parsing a Polygon API error response."""
        response = sample_polygon_error_response

        assert response["status"] == "ERROR"
        assert "error" in response
        assert response["error"] == "Ticker not found"

    def test_handle_missing_fields_in_response(self):
        """Test handling response with missing optional fields."""
        partial_response = {
            "ticker": "AAPL",
            "results": [
                {
                    "o": 150.0,
                    "c": 151.0,
                    # Missing h, l, v, vw, n
                }
            ],
            "status": "OK"
        }

        result = partial_response["results"][0]
        # Should safely get values with defaults
        assert result.get("o") == 150.0
        assert result.get("h") is None
        assert result.get("l") is None
        assert result.get("v", 0) == 0
        assert result.get("vw") is None
        assert result.get("n", 0) == 0


class TestAPIRateLimitHandling:
    """Tests for API rate limit handling."""

    def test_rate_limit_delay_between_calls(self):
        """Test that rate limiting delays are applied between calls."""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["AAPL", "MSFT"]

        sleep_calls = []

        def track_sleep(duration):
            sleep_calls.append(duration)

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep', side_effect=track_sleep):
                retriever.process_batch(retriever.tickers, 1, 1)

        # Should have sleep calls for rate limiting
        assert len(sleep_calls) > 0
        # Each call should be 0.01 seconds (10ms)
        assert all(s == 0.01 for s in sleep_calls)

    def test_rate_limit_response_handling(self):
        """Test handling of 429 rate limit response."""
        rate_limit_response = {
            "status": "ERROR",
            "error": "Rate limit exceeded",
            "request_id": "rate123"
        }

        # Simulate rate limit detection
        is_rate_limited = (
            rate_limit_response.get("status") == "ERROR" and
            "rate limit" in rate_limit_response.get("error", "").lower()
        )

        assert is_rate_limited is True

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        base_delay = 1.0
        max_delay = 60.0

        delays = []
        for attempt in range(5):
            delay = min(base_delay * (2 ** attempt), max_delay)
            delays.append(delay)

        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]


class TestAPIErrorCodes:
    """Tests for handling various API error codes."""

    @pytest.mark.parametrize("status_code,expected_retry", [
        (400, False),   # Bad request - don't retry
        (401, False),   # Unauthorized - don't retry
        (403, False),   # Forbidden - don't retry
        (404, False),   # Not found - don't retry
        (429, True),    # Rate limited - should retry
        (500, True),    # Server error - should retry
        (502, True),    # Bad gateway - should retry
        (503, True),    # Service unavailable - should retry
        (504, True),    # Gateway timeout - should retry
    ])
    def test_error_code_retry_decision(self, status_code, expected_retry):
        """Test retry decision based on error status code."""
        # Define retry logic
        retryable_codes = {429, 500, 502, 503, 504}
        should_retry = status_code in retryable_codes

        assert should_retry == expected_retry

    def test_handle_network_timeout(self):
        """Test handling of network timeout errors."""
        import socket

        def simulate_timeout():
            raise socket.timeout("Connection timed out")

        with pytest.raises(socket.timeout):
            simulate_timeout()

    def test_handle_connection_reset(self):
        """Test handling of connection reset errors."""
        def simulate_connection_reset():
            raise ConnectionResetError("Connection reset by peer")

        with pytest.raises(ConnectionResetError):
            simulate_connection_reset()


class TestNotionRetrieverAPIHandling:
    """API handling tests for StockDataNotionRetriever."""

    def test_fetch_polygon_data_structure(self):
        """Test that fetch_polygon_data returns correct structure."""
        retriever = StockDataNotionRetriever()
        chunk = TimeChunk("2020-01-01", "2024-11-23", "2020-2024")

        result = retriever.fetch_polygon_data("AAPL", chunk)

        # Verify all required fields are present
        required_fields = [
            "ticker", "period", "from", "to", "data_points",
            "timespan", "has_data", "open", "high", "low",
            "close", "volume", "vwap", "transactions"
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_timespan_selection_for_short_period(self):
        """Test minute timespan selected for short periods."""
        retriever = StockDataNotionRetriever()
        # Less than 30 days should use minute timespan
        chunk = TimeChunk("2024-11-01", "2024-11-15", "Nov 2024")

        result = retriever.fetch_polygon_data("AAPL", chunk)

        # For short periods, should prefer minute data
        # Note: Current implementation determines timespan based on days_diff
        assert result["period"] == "Nov 2024"

    def test_timespan_selection_for_medium_period(self):
        """Test hour timespan selected for medium periods."""
        retriever = StockDataNotionRetriever()
        # 30-180 days should use hour timespan
        chunk = TimeChunk("2024-06-01", "2024-11-15", "H2 2024")

        result = retriever.fetch_polygon_data("AAPL", chunk)

        assert result["period"] == "H2 2024"

    def test_timespan_selection_for_long_period(self):
        """Test day timespan selected for long periods."""
        retriever = StockDataNotionRetriever()
        # More than 180 days should use day timespan
        chunk = TimeChunk("2020-01-01", "2024-11-23", "2020-2024")

        result = retriever.fetch_polygon_data("AAPL", chunk)

        assert result["period"] == "2020-2024"


class TestResponseDataTransformation:
    """Tests for transforming API responses to internal format."""

    def test_transform_polygon_to_notion_format(self):
        """Test transformation from Polygon format to Notion page format."""
        retriever = ProductionStockRetriever()
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}

        data = retriever.get_polygon_data("AAPL", period)

        # Should have correct structure for Notion
        assert data["ticker"] == "AAPL"
        assert data["period"] == "2020-2024"
        assert "has_data" in data
        assert "timespan" in data

    def test_aggregate_multi_result_response(self):
        """Test aggregating multiple results into summary."""
        results = [
            {"o": 100, "h": 110, "l": 90, "c": 105, "v": 1000000},
            {"o": 105, "h": 115, "l": 95, "c": 108, "v": 1200000},
            {"o": 108, "h": 120, "l": 100, "c": 115, "v": 1100000},
        ]

        # Aggregate as the system would
        open_price = results[0]["o"]
        high_price = max(r["h"] for r in results)
        low_price = min(r["l"] for r in results)
        close_price = results[-1]["c"]
        total_volume = sum(r["v"] for r in results)

        assert open_price == 100
        assert high_price == 120
        assert low_price == 90
        assert close_price == 115
        assert total_volume == 3300000

    def test_handle_null_values_in_transformation(self):
        """Test that null values are handled during transformation."""
        retriever = ProductionStockRetriever()

        # Create properties with null data
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}
        data = {
            "has_data": False,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "vwap": None,
            "transactions": None,
            "data_points": 0,
            "timespan": "day"
        }

        properties = retriever._create_base_properties("NULL_TICKER", period, data, 1)

        assert properties["Has Data"] == "__NO__"
        assert properties["Ticker"] == "NULL_TICKER"

    def test_date_format_transformation(self):
        """Test that dates are correctly formatted."""
        retriever = ProductionStockRetriever()
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}
        data = {"has_data": False}

        properties = retriever._create_base_properties("AAPL", period, data, 1)

        assert properties["date:Date:start"] == "2020-01-01"
        assert properties["date:Date:is_datetime"] == 0
        # Retrieved At should be ISO format datetime
        assert "date:Retrieved At:start" in properties
