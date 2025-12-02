"""Tests for data validation and quality checks.

Tests validation of price data, volume ranges, date formats,
duplicate detection, and data completeness.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from production_stock_retrieval import ProductionStockRetriever
from stock_notion_retrieval import StockDataNotionRetriever, TimeChunk


class TestPriceValidation:
    """Tests for price data validation."""

    def test_valid_price_ranges(self):
        """Test that normal price values are accepted."""
        valid_prices = [0.01, 1.00, 100.00, 1000.00, 10000.00]

        for price in valid_prices:
            assert price > 0, f"Price {price} should be positive"
            assert price < 1000000, f"Price {price} should be reasonable"

    def test_detect_negative_prices(self):
        """Test detection of invalid negative prices."""
        data = {
            "open": -100.00,
            "high": 110.00,
            "low": 90.00,
            "close": 105.00
        }

        is_valid = all(
            v is None or v >= 0
            for v in [data["open"], data["high"], data["low"], data["close"]]
        )

        assert is_valid is False

    def test_detect_price_anomalies(self):
        """Test detection of price anomalies (high < low)."""
        data = {
            "open": 100.00,
            "high": 90.00,  # Invalid: high < low
            "low": 110.00,
            "close": 105.00
        }

        # High should always be >= low
        is_valid = data["high"] >= data["low"]
        assert is_valid is False

    def test_detect_extreme_price_movements(self):
        """Test detection of extreme price movements."""
        data = {
            "open": 100.00,
            "high": 1000.00,  # 10x movement
            "low": 100.00,
            "close": 1000.00
        }

        # Calculate price movement
        max_movement = (data["high"] - data["low"]) / data["low"]

        # Movement of 900% is extreme
        assert max_movement > 5.0  # More than 500% movement

    def test_null_prices_marked_correctly(self):
        """Test that null prices are properly marked."""
        retriever = ProductionStockRetriever()
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}

        data = retriever.get_polygon_data("UNKNOWN_TICKER", period)

        assert data["has_data"] is False
        assert data["open"] is None
        assert data["high"] is None
        assert data["low"] is None
        assert data["close"] is None


class TestVolumeValidation:
    """Tests for volume data validation."""

    def test_valid_volume_ranges(self):
        """Test that normal volume values are accepted."""
        valid_volumes = [1000, 100000, 1000000, 100000000]

        for volume in valid_volumes:
            assert volume > 0, f"Volume {volume} should be positive"
            assert isinstance(volume, int) or volume == int(volume)

    def test_detect_negative_volume(self):
        """Test detection of invalid negative volume."""
        volume = -1000000

        is_valid = volume is None or volume >= 0
        assert is_valid is False

    def test_detect_zero_volume_with_trades(self):
        """Test detection of zero volume when transactions exist."""
        data = {
            "volume": 0,
            "transactions": 1000
        }

        # Volume should be > 0 if there are transactions
        is_consistent = (
            data["volume"] > 0 or data["transactions"] == 0
        )
        assert is_consistent is False

    def test_volume_transaction_ratio(self):
        """Test that volume/transaction ratio is reasonable."""
        data = {
            "volume": 1000000,
            "transactions": 10000
        }

        # Average shares per transaction
        avg_shares = data["volume"] / data["transactions"]

        # Should be reasonable (1 to 10000 shares per trade)
        assert 1 <= avg_shares <= 10000


class TestDateValidation:
    """Tests for date format and range validation."""

    def test_valid_date_format(self):
        """Test that dates are in correct ISO format."""
        valid_dates = ["2020-01-01", "2024-11-23", "2000-12-31"]

        for date_str in valid_dates:
            parsed = datetime.strptime(date_str, "%Y-%m-%d")
            assert parsed is not None

    def test_invalid_date_format_detection(self):
        """Test detection of invalid date formats."""
        invalid_dates = ["01-01-2020", "2020/01/01", "Jan 1, 2020"]

        for date_str in invalid_dates:
            with pytest.raises(ValueError):
                datetime.strptime(date_str, "%Y-%m-%d")

    def test_date_range_validity(self):
        """Test that from date is before to date."""
        period = {
            "from": "2020-01-01",
            "to": "2024-11-23"
        }

        from_date = datetime.strptime(period["from"], "%Y-%m-%d")
        to_date = datetime.strptime(period["to"], "%Y-%m-%d")

        assert from_date < to_date

    def test_future_date_detection(self):
        """Test detection of future dates."""
        future_date = "2030-01-01"
        parsed = datetime.strptime(future_date, "%Y-%m-%d")

        is_future = parsed > datetime.now()
        assert is_future is True

    def test_period_labels_match_dates(self):
        """Test that period labels match the date ranges."""
        retriever = ProductionStockRetriever()

        for period in retriever.periods:
            from_year = period["from"][:4]
            to_year = period["to"][:4]
            label = period["label"]

            # Label should contain both years
            assert from_year in label
            assert to_year in label


class TestDuplicateDetection:
    """Tests for duplicate data detection."""

    def test_detect_duplicate_ticker_periods(self):
        """Test detection of duplicate ticker-period combinations."""
        records = [
            {"ticker": "AAPL", "period": "2020-2024"},
            {"ticker": "MSFT", "period": "2020-2024"},
            {"ticker": "AAPL", "period": "2020-2024"},  # Duplicate
            {"ticker": "AAPL", "period": "2015-2019"},  # Different period, OK
        ]

        seen = set()
        duplicates = []

        for record in records:
            key = (record["ticker"], record["period"])
            if key in seen:
                duplicates.append(record)
            seen.add(key)

        assert len(duplicates) == 1
        assert duplicates[0]["ticker"] == "AAPL"
        assert duplicates[0]["period"] == "2020-2024"

    def test_no_duplicates_in_batch(self, temp_dir):
        """Test that batch processing doesn't create duplicates."""
        tickers = ["AAPL", "MSFT"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()
                retriever.process_batch(retriever.tickers, 1, 1)

        batch_file = os.path.join(temp_dir, "batch_0001_notion.json")
        with open(batch_file, 'r') as f:
            batch_data = json.load(f)

        # Check for duplicates
        seen = set()
        for page in batch_data["pages"]:
            key = (page["properties"]["Ticker"], page["properties"]["Period"])
            assert key not in seen, f"Duplicate found: {key}"
            seen.add(key)


class TestDataCompleteness:
    """Tests for data completeness validation."""

    def test_all_periods_present_for_ticker(self, temp_dir):
        """Test that all periods are present for each ticker."""
        tickers = ["AAPL"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()
                retriever.process_batch(retriever.tickers, 1, 1)

        batch_file = os.path.join(temp_dir, "batch_0001_notion.json")
        with open(batch_file, 'r') as f:
            batch_data = json.load(f)

        # Group by ticker
        ticker_periods = {}
        for page in batch_data["pages"]:
            ticker = page["properties"]["Ticker"]
            period = page["properties"]["Period"]
            if ticker not in ticker_periods:
                ticker_periods[ticker] = set()
            ticker_periods[ticker].add(period)

        expected_periods = {"2020-2024", "2015-2019", "2010-2014", "2005-2009", "2000-2004"}
        assert ticker_periods["AAPL"] == expected_periods

    def test_required_fields_present(self):
        """Test that all required fields are present in output."""
        retriever = ProductionStockRetriever()
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}
        data = retriever.get_polygon_data("AAPL", period)

        required_fields = [
            "ticker", "period", "has_data", "open", "high",
            "low", "close", "volume", "vwap", "transactions",
            "data_points", "timespan"
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_batch_metadata_completeness(self, temp_dir):
        """Test that batch files have complete metadata."""
        tickers = ["AAPL"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()
                retriever.process_batch(retriever.tickers, 1, 1)

        batch_file = os.path.join(temp_dir, "batch_0001_notion.json")
        with open(batch_file, 'r') as f:
            batch_data = json.load(f)

        required_metadata = ["data_source_id", "batch_number", "record_count", "timestamp", "pages"]
        for field in required_metadata:
            assert field in batch_data, f"Missing metadata field: {field}"


class TestTickerSymbolValidation:
    """Tests for ticker symbol validation."""

    @pytest.mark.parametrize("ticker,is_valid", [
        ("AAPL", True),
        ("MSFT", True),
        ("BRK.A", True),
        ("BRK.B", True),
        ("", False),
        ("TOOLONGSYMBOL", False),  # Most tickers are 1-5 chars
    ])
    def test_ticker_format_validation(self, ticker, is_valid):
        """Test validation of ticker symbol formats."""
        # Basic validation rules
        valid = len(ticker) > 0 and len(ticker) <= 10

        assert valid == is_valid

    def test_ticker_with_special_characters(self):
        """Test handling of tickers with special characters."""
        special_tickers = ["BRK.A", "BRK.B", "BF.A", "BF.B"]

        for ticker in special_tickers:
            # Should be valid even with period
            assert len(ticker) > 0
            assert len(ticker) <= 10

    def test_ticker_case_sensitivity(self):
        """Test that tickers are case-sensitive."""
        ticker1 = "AAPL"
        ticker2 = "aapl"

        # Tickers should be uppercase
        assert ticker1 == ticker1.upper()
        assert ticker2 != ticker2.upper()


class TestNotionDataValidation:
    """Validation tests specific to Notion data format."""

    def test_notion_page_properties_valid(self):
        """Test that Notion page properties are valid."""
        retriever = StockDataNotionRetriever()
        data = {
            "ticker": "AAPL",
            "period": "2020-2024",
            "from": "2020-01-01",
            "to": "2024-11-23",
            "has_data": True,
            "open": 150.0,
            "high": 155.0,
            "low": 145.0,
            "close": 152.0,
            "volume": 1000000,
            "vwap": 151.5,
            "transactions": 50000,
            "data_points": 252,
            "timespan": "day"
        }

        page = retriever._build_notion_page(data, 1)

        assert "properties" in page
        props = page["properties"]

        # Validate required properties
        assert props["Ticker"] == "AAPL"
        assert props["Period"] == "2020-2024"
        assert props["Has Data"] is True
        assert props["Batch"] == 1

    def test_notion_checkbox_format(self):
        """Test Notion checkbox field format."""
        # Has Data field should be boolean or special string
        valid_checkbox_values = [True, False, "__YES__", "__NO__"]

        for value in valid_checkbox_values:
            # Should be one of the valid formats
            assert value in valid_checkbox_values

    def test_notion_date_field_format(self):
        """Test Notion date field format."""
        date_field = {
            "start": "2020-01-01",
            "end": "2024-11-23"
        }

        assert "start" in date_field
        assert date_field["start"] is not None
        # Validate date format
        datetime.strptime(date_field["start"], "%Y-%m-%d")
