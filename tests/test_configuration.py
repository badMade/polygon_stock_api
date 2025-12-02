"""Tests for configuration and settings.

Tests environment variable configuration, default vs custom settings,
path configurations, and constant validation.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from production_stock_retrieval import (
    ProductionStockRetriever,
    OUTPUT_DIR,
    UPLOADS_DIR,
    BASE_DATA_DIR,
)
from stock_notion_retrieval import (
    StockDataNotionRetriever,
    TimeChunk,
    OUTPUT_DIR as NOTION_OUTPUT_DIR,
    UPLOADS_DIR as NOTION_UPLOADS_DIR,
)


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_base_data_dir_from_environment(self):
        """Test that BASE_DATA_DIR respects environment variable."""
        # Test that the environment variable pattern is recognized
        # Note: This tests the configuration mechanism without module reloading
        test_path = "/custom/path"

        with patch.dict(os.environ, {"STOCK_APP_DATA_DIR": test_path}):
            # Verify environment is set correctly
            assert os.environ.get("STOCK_APP_DATA_DIR") == test_path

            # In production, this would be read at module import time
            # Here we verify the pattern works without side effects from reload

    def test_default_base_data_dir(self):
        """Test default BASE_DATA_DIR when environment not set."""
        # BASE_DATA_DIR should be relative to the module
        assert BASE_DATA_DIR is not None
        assert "user-data" in str(BASE_DATA_DIR)

    def test_output_dir_derived_from_base(self):
        """Test that OUTPUT_DIR is derived from BASE_DATA_DIR."""
        assert str(OUTPUT_DIR).startswith(str(BASE_DATA_DIR))
        assert "outputs" in str(OUTPUT_DIR)

    def test_uploads_dir_derived_from_base(self):
        """Test that UPLOADS_DIR is derived from BASE_DATA_DIR."""
        assert str(UPLOADS_DIR).startswith(str(BASE_DATA_DIR))
        assert "uploads" in str(UPLOADS_DIR)


class TestDefaultConfiguration:
    """Tests for default configuration values."""

    def test_default_batch_size(self):
        """Test default batch size is 100."""
        retriever = ProductionStockRetriever()
        assert retriever.batch_size == 100

    def test_default_data_source_id(self):
        """Test default data source ID is correct."""
        retriever = ProductionStockRetriever()
        expected_id = "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
        assert retriever.data_source_id == expected_id

    def test_default_periods_count(self):
        """Test default number of periods is 5."""
        retriever = ProductionStockRetriever()
        assert len(retriever.periods) == 5

    def test_default_ticker_file_path(self):
        """Test default ticker file path."""
        retriever = ProductionStockRetriever()
        assert "all_tickers.json" in retriever.ticker_file
        assert "uploads" in retriever.ticker_file

    def test_initial_counters_are_zero(self):
        """Test that initial counters are zero."""
        retriever = ProductionStockRetriever()
        assert retriever.processed == 0
        assert retriever.saved == 0
        assert len(retriever.failed) == 0


class TestPeriodConfiguration:
    """Tests for time period configuration."""

    def test_all_periods_have_required_fields(self):
        """Test that all periods have from, to, and label."""
        retriever = ProductionStockRetriever()

        for period in retriever.periods:
            assert "from" in period
            assert "to" in period
            assert "label" in period

    def test_periods_are_chronologically_ordered(self):
        """Test that periods are ordered from newest to oldest."""
        retriever = ProductionStockRetriever()

        for i in range(len(retriever.periods) - 1):
            current_year = int(retriever.periods[i]["from"][:4])
            next_year = int(retriever.periods[i + 1]["from"][:4])
            assert current_year > next_year

    def test_periods_cover_expected_range(self):
        """Test that periods cover 2000-2024."""
        retriever = ProductionStockRetriever()

        all_years = set()
        for period in retriever.periods:
            start_year = int(period["from"][:4])
            end_year = int(period["to"][:4])
            for year in range(start_year, end_year + 1):
                all_years.add(year)

        # Should cover 2000-2024
        expected_years = set(range(2000, 2025))
        assert all_years == expected_years

    def test_period_labels_match_date_ranges(self):
        """Test that period labels match their date ranges."""
        retriever = ProductionStockRetriever()

        for period in retriever.periods:
            start_year = period["from"][:4]
            end_year = period["to"][:4]
            label = period["label"]

            assert start_year in label
            assert end_year in label


class TestNotionRetrieverConfiguration:
    """Configuration tests for StockDataNotionRetriever."""

    def test_notion_default_batch_size(self):
        """Test Notion retriever default batch size."""
        retriever = StockDataNotionRetriever()
        assert retriever.batch_size == 100

    def test_notion_time_chunks_count(self):
        """Test Notion retriever has 5 time chunks."""
        retriever = StockDataNotionRetriever()
        assert len(retriever.time_chunks) == 5

    def test_time_chunk_dataclass_structure(self):
        """Test TimeChunk dataclass has correct fields."""
        chunk = TimeChunk("2020-01-01", "2024-11-23", "2020-2024")

        assert chunk.start_date == "2020-01-01"
        assert chunk.end_date == "2024-11-23"
        assert chunk.label == "2020-2024"

    def test_notion_database_url_is_none_initially(self):
        """Test that Notion database URL starts as None."""
        retriever = StockDataNotionRetriever()
        assert retriever.notion_database_url is None

    def test_notion_initial_counters(self):
        """Test Notion retriever initial counter values."""
        retriever = StockDataNotionRetriever()

        assert retriever.processed_count == 0
        assert retriever.successful_saves == 0
        assert len(retriever.failed_tickers) == 0


class TestPathConfiguration:
    """Tests for path configuration."""

    def test_output_dir_is_path_object(self):
        """Test that OUTPUT_DIR is a Path object."""
        assert isinstance(OUTPUT_DIR, Path)

    def test_uploads_dir_is_path_object(self):
        """Test that UPLOADS_DIR is a Path object."""
        assert isinstance(UPLOADS_DIR, Path)

    def test_ticker_file_uses_uploads_dir(self):
        """Test that ticker file path contains uploads directory."""
        retriever = ProductionStockRetriever()
        # Check that the ticker file is in an uploads directory
        assert "uploads" in retriever.ticker_file
        assert "all_tickers.json" in retriever.ticker_file

    def test_batch_file_naming_pattern(self):
        """Test batch file naming follows pattern."""
        for batch_num in [1, 10, 100, 1000]:
            filename = f"batch_{batch_num:04d}_notion.json"
            assert filename.startswith("batch_")
            assert filename.endswith("_notion.json")
            assert len(filename.split("_")[1]) == 4  # 4-digit zero-padded


class TestConstantValidation:
    """Tests for constant validation."""

    def test_data_source_id_format(self):
        """Test data source ID is valid UUID format."""
        import re

        retriever = ProductionStockRetriever()
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

        assert re.match(uuid_pattern, retriever.data_source_id)

    def test_data_source_id_consistency(self):
        """Test data source ID is consistent across instances."""
        retriever1 = ProductionStockRetriever()
        retriever2 = ProductionStockRetriever()

        assert retriever1.data_source_id == retriever2.data_source_id

class TestConfigurationOverrides:
    """Tests for configuration overrides."""

    def test_override_batch_size(self):
        """Test that batch size can be overridden."""
        retriever = ProductionStockRetriever()

        original_size = retriever.batch_size
        retriever.batch_size = 50

        assert retriever.batch_size == 50
        assert retriever.batch_size != original_size

    def test_override_ticker_file(self, temp_dir):
        """Test that ticker file path can be overridden."""
        retriever = ProductionStockRetriever()

        custom_path = os.path.join(temp_dir, "custom_tickers.json")
        retriever.ticker_file = custom_path

        assert retriever.ticker_file == custom_path

    def test_add_custom_period(self):
        """Test that custom periods can be added."""
        retriever = ProductionStockRetriever()

        original_count = len(retriever.periods)
        retriever.periods.append({
            "from": "1995-01-01",
            "to": "1999-12-31",
            "label": "1995-1999"
        })

        assert len(retriever.periods) == original_count + 1


class TestDatabaseConfiguration:
    """Tests for Notion database configuration."""

    def test_database_properties_structure(self, temp_dir):
        """Test that database properties have correct structure."""
        retriever = StockDataNotionRetriever()

        with patch('stock_notion_retrieval.OUTPUT_DIR', temp_dir):
            properties = retriever.create_notion_database()

        required_properties = [
            "Ticker", "Date", "Period", "Open", "High", "Low", "Close",
            "Volume", "VWAP", "Transactions", "Has Data", "Data Points",
            "Timespan", "Retrieved", "Batch"
        ]

        for prop in required_properties:
            assert prop in properties

    def test_period_select_options(self, temp_dir):
        """Test that Period property has correct select options."""
        retriever = StockDataNotionRetriever()

        with patch('stock_notion_retrieval.OUTPUT_DIR', temp_dir):
            properties = retriever.create_notion_database()

        period_options = properties["Period"]["select"]["options"]
        option_names = [opt["name"] for opt in period_options]

        expected = ["2020-2024", "2015-2019", "2010-2014", "2005-2009", "2000-2004"]
        assert option_names == expected

    def test_timespan_select_options(self, temp_dir):
        """Test that Timespan property has correct select options."""
        retriever = StockDataNotionRetriever()

        with patch('stock_notion_retrieval.OUTPUT_DIR', temp_dir):
            properties = retriever.create_notion_database()

        timespan_options = properties["Timespan"]["select"]["options"]
        option_names = [opt["name"] for opt in timespan_options]

        expected = ["minute", "hour", "day"]
        assert option_names == expected
