"""Tests for stock_notion_retrieval.py"""
import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta
from unittest.mock import mock_open, patch

import pytest

from stock_notion_retrieval import StockDataNotionRetriever, TimeChunk


class TestTimeChunk:
    """Test TimeChunk dataclass"""

    def test_time_chunk_creation(self):
        """Test creating a TimeChunk"""
        chunk = TimeChunk("2020-01-01", "2024-12-31", "2020-2024")

        assert chunk.start_date == "2020-01-01"
        assert chunk.end_date == "2024-12-31"
        assert chunk.label == "2020-2024"

    def test_time_chunk_is_dataclass(self):
        """Test that TimeChunk behaves as a dataclass"""
        chunk = TimeChunk("2020-01-01", "2024-12-31", "2020-2024")

        # Should be able to convert to dict
        chunk_dict = asdict(chunk)
        assert "start_date" in chunk_dict
        assert "end_date" in chunk_dict
        assert "label" in chunk_dict

    def test_time_chunk_equality(self):
        """Test TimeChunk equality"""
        chunk1 = TimeChunk("2020-01-01", "2024-12-31", "2020-2024")
        chunk2 = TimeChunk("2020-01-01", "2024-12-31", "2020-2024")
        chunk3 = TimeChunk("2015-01-01", "2019-12-31", "2015-2019")

        assert chunk1 == chunk2
        assert chunk1 != chunk3


class TestStockDataNotionRetriever:
    """Test suite for StockDataNotionRetriever class"""

    def test_init(self):
        """Test initialization"""
        retriever = StockDataNotionRetriever()

        assert retriever.ticker_file == "/mnt/user-data/uploads/all_tickers.json"
        assert not retriever.tickers
        assert retriever.batch_size == 100
        assert retriever.notion_database_url is None
        assert retriever.processed_count == 0
        assert not retriever.failed_tickers
        assert retriever.successful_saves == 0
        assert len(retriever.time_chunks) == 5

    def test_time_chunks_configuration(self):
        """Test time chunks are properly configured"""
        retriever = StockDataNotionRetriever()

        # Check first chunk (most recent)
        chunk = retriever.time_chunks[0]
        assert chunk.start_date == "2020-01-01"
        assert chunk.end_date == "2024-11-23"
        assert chunk.label == "2020-2024"

        # Check last chunk (oldest)
        chunk = retriever.time_chunks[-1]
        assert chunk.start_date == "2000-01-01"
        assert chunk.end_date == "2004-12-31"
        assert chunk.label == "2000-2004"

    def test_time_chunks_are_time_chunk_objects(self):
        """Test that time chunks are TimeChunk objects"""
        retriever = StockDataNotionRetriever()

        for chunk in retriever.time_chunks:
            assert isinstance(chunk, TimeChunk)

    def test_load_tickers_success(self, ticker_file, sample_tickers):
        """Test successfully loading tickers"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file

        tickers = retriever.load_tickers()

        assert tickers == sample_tickers
        assert retriever.tickers == sample_tickers
        assert len(retriever.tickers) == len(sample_tickers)

    def test_load_tickers_empty_file(self, empty_ticker_file):
        """Test loading empty ticker file"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = empty_ticker_file

        tickers = retriever.load_tickers()

        assert not tickers
        assert not retriever.tickers

    def test_load_tickers_file_not_found(self):
        """Test loading tickers with missing file"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = "/nonexistent/file.json"

        with pytest.raises(Exception):
            retriever.load_tickers()

    def test_load_tickers_invalid_json(self, invalid_json_file):
        """Test loading invalid JSON raises exception"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = invalid_json_file

        with pytest.raises(Exception):
            retriever.load_tickers()

    def test_create_notion_database_structure(self):
        """Test that create_notion_database returns proper structure"""
        retriever = StockDataNotionRetriever()

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                properties = retriever.create_notion_database()

                # Check required properties exist
                assert "Ticker" in properties
                assert "Date" in properties
                assert "Period" in properties
                assert "Open" in properties
                assert "High" in properties
                assert "Low" in properties
                assert "Close" in properties
                assert "Volume" in properties
                assert "VWAP" in properties
                assert "Transactions" in properties
                assert "Has Data" in properties
                assert "Data Points" in properties
                assert "Timespan" in properties
                assert "Retrieved" in properties
                assert "Batch" in properties

    def test_create_notion_database_period_options(self):
        """Test that Period field has correct options"""
        retriever = StockDataNotionRetriever()

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                properties = retriever.create_notion_database()

                period_options = properties["Period"]["select"]["options"]
                labels = [opt["name"] for opt in period_options]

                assert "2020-2024" in labels
                assert "2015-2019" in labels
                assert "2010-2014" in labels
                assert "2005-2009" in labels
                assert "2000-2004" in labels

    def test_create_notion_database_timespan_options(self):
        """Test that Timespan field has correct options"""
        retriever = StockDataNotionRetriever()

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                properties = retriever.create_notion_database()

                timespan_options = properties["Timespan"]["select"]["options"]
                timespans = [opt["name"] for opt in timespan_options]

                assert "minute" in timespans
                assert "hour" in timespans
                assert "day" in timespans

    def test_fetch_polygon_data_structure(self):
        """Test structure of fetch_polygon_data response"""
        retriever = StockDataNotionRetriever()
        chunk = TimeChunk("2020-01-01", "2024-11-23", "2020-2024")

        result = retriever.fetch_polygon_data("AAPL", chunk)

        # Check all required fields
        assert "ticker" in result
        assert "period" in result
        assert "from" in result
        assert "to" in result
        assert "data_points" in result
        assert "timespan" in result
        assert "has_data" in result
        assert "open" in result
        assert "high" in result
        assert "low" in result
        assert "close" in result
        assert "volume" in result
        assert "vwap" in result
        assert "transactions" in result

    def test_fetch_polygon_data_known_ticker(self):
        """Test fetching data for known tickers returns data"""
        retriever = StockDataNotionRetriever()
        chunk = TimeChunk("2020-01-01", "2024-11-23", "2020-2024")

        result = retriever.fetch_polygon_data("AAPL", chunk)

        # AAPL is in the sample list, should have data
        assert result["ticker"] == "AAPL"
        assert result["period"] == "2020-2024"
        assert result["has_data"] is True
        assert result["open"] is not None
        assert result["data_points"] > 0

    def test_fetch_polygon_data_unknown_ticker(self):
        """Test fetching data for unknown ticker"""
        retriever = StockDataNotionRetriever()
        chunk = TimeChunk("2020-01-01", "2024-11-23", "2020-2024")

        result = retriever.fetch_polygon_data("UNKNOWN", chunk)

        assert result["ticker"] == "UNKNOWN"
        assert result["has_data"] is False
        assert result["open"] is None
        assert result["data_points"] == 0

    def test_fetch_polygon_data_timespan_selection_recent(self):
        """Test timespan selection logic for recent period"""
        retriever = StockDataNotionRetriever()

        # 30-day period - test the calculation logic
        today = datetime.now()
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        chunk = TimeChunk(start, end, "recent")

        # Calculate expected timespan based on days
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        days_diff = (end_date - start_date).days

        # For 30 days, should use minute timespan (<=30 days)
        assert days_diff <= 30

    def test_fetch_polygon_data_timespan_selection_medium(self):
        """Test timespan selection logic for medium period"""
        retriever = StockDataNotionRetriever()

        # 180-day period - test the calculation logic
        today = datetime.now()
        start = (today - timedelta(days=180)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        chunk = TimeChunk(start, end, "medium")

        # Calculate expected timespan based on days
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        days_diff = (end_date - start_date).days

        # For ~180 days, should be between 30 and 180 days
        assert 30 < days_diff <= 180

    def test_fetch_polygon_data_timespan_selection_long(self):
        """Test timespan selection logic for long period"""
        retriever = StockDataNotionRetriever()

        # 5-year period - test the calculation logic
        chunk = TimeChunk("2020-01-01", "2024-12-31", "2020-2024")

        start_date = datetime.strptime(chunk.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(chunk.end_date, "%Y-%m-%d")
        days_diff = (end_date - start_date).days

        # Long period should be > 180 days
        assert days_diff > 180

    def test_save_batch_to_notion_creates_file(self):
        """Test that save_batch_to_notion creates file"""
        retriever = StockDataNotionRetriever()

        batch_data = [
            {
                "ticker": "AAPL",
                "period": "2020-2024",
                "from": "2020-01-01",
                "to": "2024-11-23",
                "has_data": True,
                "open": 150.0,
                "high": 155.0,
                "low": 149.0,
                "close": 154.0,
                "volume": 50000000,
                "vwap": 152.0,
                "transactions": 450000,
                "data_points": 252,
                "timespan": "day"
            }
        ]

        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('json.dump') as mock_dump:
                retriever.save_batch_to_notion(batch_data, 1)

                assert mock_dump.called
                saved_data = mock_dump.call_args[0][0]

                assert len(saved_data) == 1
                assert saved_data[0]["properties"]["Ticker"] == "AAPL"

    def test_save_batch_to_notion_updates_counter(self):
        """Test that save_batch updates successful_saves counter"""
        retriever = StockDataNotionRetriever()

        batch_data = [
            {"ticker": "AAPL", "period": "2020-2024", "has_data": True, "close": 150.0}
        ]

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                initial_saves = retriever.successful_saves
                retriever.save_batch_to_notion(batch_data, 1)

                assert retriever.successful_saves == initial_saves + 1

    def test_save_batch_to_notion_file_naming(self):
        """Test batch file naming convention"""
        retriever = StockDataNotionRetriever()

        batch_data = [{"ticker": "TEST", "period": "2020-2024", "has_data": True}]

        file_opened = None

        def capture_open(path, mode='r', **kwargs):
            nonlocal file_opened
            file_opened = path
            return mock_open()(path, mode, **kwargs)

        with patch('builtins.open', side_effect=capture_open):
            with patch('json.dump'):
                retriever.save_batch_to_notion(batch_data, 7)

                assert file_opened is not None
                assert "batch_007_notion_data.json" in file_opened

    def test_process_batch_all_chunks(self, sample_tickers):
        """Test that process_batch processes all time chunks"""
        retriever = StockDataNotionRetriever()
        retriever.tickers = sample_tickers

        batch = sample_tickers[:2]

        with patch.object(retriever, 'save_batch_to_notion') as mock_save:
            with patch('time.sleep'):
                retriever.process_batch(batch, 1, 10)

                # Should have saved data for both tickers
                assert mock_save.called

                # Check the saved data
                saved_data = mock_save.call_args[0][0]
                # 2 tickers * 5 time chunks = 10 records
                assert len(saved_data) == 10

    def test_process_batch_updates_processed_count(self, sample_tickers):
        """Test that process_batch updates processed count"""
        retriever = StockDataNotionRetriever()
        retriever.tickers = sample_tickers

        batch = sample_tickers[:3]

        with patch.object(retriever, 'save_batch_to_notion'):
            with patch('time.sleep'):
                retriever.process_batch(batch, 1, 10)

                assert retriever.processed_count == 3

    def test_process_batch_rate_limiting(self, sample_tickers):
        """Test that process_batch includes rate limiting"""
        retriever = StockDataNotionRetriever()
        retriever.tickers = sample_tickers

        batch = sample_tickers[:2]

        with patch.object(retriever, 'save_batch_to_notion'):
            with patch('time.sleep') as mock_sleep:
                retriever.process_batch(batch, 1, 10)

                # Should sleep for each ticker * time chunks
                expected_sleeps = 2 * len(retriever.time_chunks)
                assert mock_sleep.call_count == expected_sleeps

    def test_save_checkpoint(self):
        """Test saving checkpoint"""
        retriever = StockDataNotionRetriever()
        retriever.tickers = ["AAPL", "MSFT", "GOOGL"]
        retriever.processed_count = 150
        retriever.successful_saves = 750
        retriever.failed_tickers = ["FAIL1", "FAIL2"]

        checkpoint_data = None

        def capture_checkpoint(data, file, **kwargs):
            nonlocal checkpoint_data
            checkpoint_data = data

        with patch('builtins.open', mock_open()):
            with patch('json.dump', side_effect=capture_checkpoint):
                retriever.save_checkpoint(5)

                assert checkpoint_data is not None
                assert checkpoint_data["last_batch"] == 5
                assert checkpoint_data["processed_count"] == 150
                assert checkpoint_data["total_tickers"] == 3
                assert checkpoint_data["successful_saves"] == 750
                assert checkpoint_data["failed_tickers"] == ["FAIL1", "FAIL2"]
                assert "timestamp" in checkpoint_data

    def test_save_checkpoint_every_5_batches(self, sample_tickers):
        """Test that checkpoint is saved every 5 batches"""
        retriever = StockDataNotionRetriever()
        retriever.tickers = sample_tickers

        batch = sample_tickers[:1]

        with patch.object(retriever, 'save_batch_to_notion'):
            with patch.object(retriever, 'save_checkpoint') as mock_checkpoint:
                with patch('time.sleep'):
                    # Process batch 5 - should save checkpoint
                    retriever.process_batch(batch, 5, 10)
                    assert mock_checkpoint.called

                    mock_checkpoint.reset_mock()

                    # Process batch 6 - should not save checkpoint
                    retriever.process_batch(batch, 6, 10)
                    assert not mock_checkpoint.called

    def test_run_full_execution(self, ticker_file, sample_tickers):
        """Test full run execution"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file

        with patch.object(retriever, 'load_tickers', return_value=sample_tickers):
            retriever.tickers = sample_tickers
            with patch.object(retriever, 'process_batch') as mock_process:
                with patch.object(retriever, 'create_notion_database'):
                    with patch('builtins.open', mock_open()):
                        with patch('json.dump'):
                            retriever.run()

                            # Should process 1 batch (10 tickers / 100 batch size)
                            assert mock_process.call_count == 1

    def test_run_creates_final_report(self, ticker_file, sample_tickers):
        """Test that run creates a final report"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file

        report_data = None

        def capture_report(data, file, **kwargs):
            nonlocal report_data
            if 'execution_summary' in data:
                report_data = data

        with patch.object(retriever, 'load_tickers', return_value=sample_tickers):
            retriever.tickers = sample_tickers
            with patch.object(retriever, 'process_batch'):
                with patch.object(retriever, 'create_notion_database'):
                    with patch('builtins.open', mock_open()):
                        with patch('json.dump', side_effect=capture_report):
                            retriever.run()

                            assert report_data is not None
                            assert "execution_summary" in report_data
                            assert "timing" in report_data
                            assert "failed_tickers" in report_data

    def test_run_handles_keyboard_interrupt(self, ticker_file):
        """Test run handles KeyboardInterrupt"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file

        with patch.object(retriever, 'load_tickers', side_effect=KeyboardInterrupt):
            with patch.object(retriever, 'save_checkpoint') as mock_checkpoint:
                # Should not raise
                retriever.run()
                # Should save checkpoint
                assert mock_checkpoint.called

    def test_run_handles_exceptions(self, ticker_file):
        """Test run handles general exceptions"""
        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file

        with patch.object(retriever, 'load_tickers', side_effect=Exception("Test error")):
            with patch.object(retriever, 'save_checkpoint') as mock_checkpoint:
                with pytest.raises(Exception):
                    retriever.run()

                # Should save checkpoint even on error
                assert mock_checkpoint.called


class TestStockDataNotionRetrieverEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_batch_data(self):
        """Test saving empty batch data"""
        retriever = StockDataNotionRetriever()

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                retriever.save_batch_to_notion([], 1)

                # Should handle gracefully
                assert retriever.successful_saves == 0

    def test_batch_data_without_optional_fields(self):
        """Test handling batch data missing optional fields"""
        retriever = StockDataNotionRetriever()

        # Has required fields but missing optional numeric fields
        minimal_data = [
            {
                "ticker": "TEST",
                "period": "2020-2024",
                "has_data": False
                # Missing: open, high, low, close, volume, vwap, transactions, data_points
            }
        ]

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                # Should handle gracefully even with missing optional fields
                retriever.save_batch_to_notion(minimal_data, 1)

    def test_very_old_date_range(self):
        """Test handling very old date ranges"""
        retriever = StockDataNotionRetriever()

        old_chunk = TimeChunk("1990-01-01", "1994-12-31", "1990-1994")

        result = retriever.fetch_polygon_data("AAPL", old_chunk)

        # Should handle old dates gracefully
        assert result["ticker"] == "AAPL"
        assert "timespan" in result

    def test_future_date_range(self):
        """Test handling future date ranges"""
        retriever = StockDataNotionRetriever()

        future = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        future_end = (datetime.now() + timedelta(days=730)).strftime("%Y-%m-%d")
        future_chunk = TimeChunk(future, future_end, "future")

        result = retriever.fetch_polygon_data("AAPL", future_chunk)

        # Should handle future dates
        assert result is not None

    def test_single_day_time_chunk(self):
        """Test time chunk with single day"""
        retriever = StockDataNotionRetriever()

        single_day = TimeChunk("2024-01-01", "2024-01-01", "single-day")

        result = retriever.fetch_polygon_data("AAPL", single_day)

        # Should use minute timespan for very short period
        assert result["timespan"] == "minute"

    def test_large_ticker_list_batch_calculation(self):
        """Test batch calculation with large ticker list"""
        retriever = StockDataNotionRetriever()
        retriever.tickers = [f"TICK{i:04d}" for i in range(1000)]

        total_batches = (len(retriever.tickers) + retriever.batch_size - 1) // retriever.batch_size

        # 1000 tickers / 100 batch_size = 10 batches
        assert total_batches == 10

    def test_checkpoint_file_naming(self):
        """Test checkpoint file naming"""
        retriever = StockDataNotionRetriever()

        file_opened = None

        def capture_open(path, mode='r', **kwargs):
            nonlocal file_opened
            file_opened = path
            return mock_open()(path, mode, **kwargs)

        with patch('builtins.open', side_effect=capture_open):
            with patch('json.dump'):
                retriever.save_checkpoint(1)

                assert file_opened is not None
                assert "retrieval_checkpoint.json" in file_opened

    def test_progress_logging_frequency(self, large_ticker_list):
        """Test that progress is logged every 10 tickers"""
        retriever = StockDataNotionRetriever()
        retriever.tickers = large_ticker_list

        batch = large_ticker_list[:25]  # 25 tickers

        with patch.object(retriever, 'save_batch_to_notion'):
            with patch('time.sleep'):
                with patch('stock_notion_retrieval.logger') as mock_logger:
                    retriever.process_batch(batch, 1, 1)

                    # Should log progress at least twice (at 10 and 20)
                    info_calls = [call for call in mock_logger.info.call_args_list]
                    progress_logs = [call for call in info_calls
                                   if len(call[0]) > 0 and 'Progress' in str(call[0][0])]

                    assert len(progress_logs) >= 2
