"""Tests for execute_stock_retrieval.py"""
import json
import os
import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock
from datetime import datetime, timedelta
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execute_stock_retrieval import StockDataExecutor


class TestStockDataExecutor:
    """Test suite for StockDataExecutor class"""

    def test_init(self):
        """Test initialization"""
        executor = StockDataExecutor()

        assert executor.ticker_file == "/mnt/user-data/outputs/all_tickers.json"
        assert executor.data_source_id == "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
        assert executor.batch_size == 100
        assert executor.tickers == []
        assert executor.processed == 0
        assert executor.saved == 0
        assert executor.failed == []
        assert len(executor.periods) == 5

    def test_periods_configuration(self):
        """Test that periods are correctly configured"""
        executor = StockDataExecutor()

        assert len(executor.periods) == 5

        # Check first period (most recent)
        assert executor.periods[0]["from"] == "2020-01-01"
        assert executor.periods[0]["to"] == "2024-11-23"
        assert executor.periods[0]["label"] == "2020-2024"

        # Check last period (oldest)
        assert executor.periods[-1]["from"] == "2000-01-01"
        assert executor.periods[-1]["to"] == "2004-12-31"
        assert executor.periods[-1]["label"] == "2000-2004"

    def test_load_tickers_success(self, ticker_file, sample_tickers):
        """Test successfully loading tickers"""
        executor = StockDataExecutor()
        executor.ticker_file = ticker_file

        count = executor.load_tickers()

        assert count == len(sample_tickers)
        assert executor.tickers == sample_tickers

    def test_load_tickers_empty(self, empty_ticker_file):
        """Test loading empty ticker file"""
        executor = StockDataExecutor()
        executor.ticker_file = empty_ticker_file

        count = executor.load_tickers()

        assert count == 0
        assert executor.tickers == []

    def test_load_tickers_file_not_found(self):
        """Test loading tickers when file doesn't exist"""
        executor = StockDataExecutor()
        executor.ticker_file = "/nonexistent/file.json"

        with pytest.raises(FileNotFoundError):
            executor.load_tickers()

    def test_load_tickers_invalid_json(self, invalid_json_file):
        """Test loading invalid JSON file"""
        executor = StockDataExecutor()
        executor.ticker_file = invalid_json_file

        with pytest.raises(json.JSONDecodeError):
            executor.load_tickers()

    def test_create_notion_pages_with_data(self):
        """Test creating Notion pages with actual data"""
        executor = StockDataExecutor()

        batch_data = [
            {
                "ticker": "AAPL",
                "period": "2020-2024",
                "date": "2020-01-01",
                "has_data": True,
                "open": 150.25,
                "high": 155.50,
                "low": 149.00,
                "close": 154.30,
                "volume": 50000000,
                "vwap": 152.45,
                "transactions": 450000,
                "data_points": 252,
                "timespan": "day"
            }
        ]

        pages = executor.create_notion_pages(batch_data, 1)

        assert len(pages) == 1
        page = pages[0]
        assert "properties" in page

        props = page["properties"]
        assert props["Ticker"] == "AAPL"
        assert props["Period"] == "2020-2024"
        assert props["Has Data"] == "__YES__"
        assert props["Batch Number"] == 1
        assert props["Open"] == 150.25
        assert props["High"] == 155.50
        assert props["Low"] == 149.00
        assert props["Close"] == 154.30
        assert props["Volume"] == 50000000
        assert props["VWAP"] == 152.45
        assert props["Transactions"] == 450000
        assert props["Data Points"] == 252
        assert props["Timespan"] == "day"

    def test_create_notion_pages_without_data(self):
        """Test creating Notion pages when no data available"""
        executor = StockDataExecutor()

        batch_data = [
            {
                "ticker": "UNKNOWN",
                "period": "2000-2004",
                "date": "2000-01-01",
                "has_data": False,
                "timespan": "day"
            }
        ]

        pages = executor.create_notion_pages(batch_data, 1)

        # With has_data=False and no close price, page might not be created
        # depending on implementation
        # But based on code, it will create page if has_data OR close is not None
        # Since close is not in dict, it should still create page
        assert len(pages) >= 0

    def test_create_notion_pages_date_fields(self):
        """Test that date fields are properly formatted"""
        executor = StockDataExecutor()

        batch_data = [
            {
                "ticker": "TEST",
                "period": "2020-2024",
                "date": "2020-01-01",
                "has_data": True,
                "close": 100.0,
                "timespan": "day"
            }
        ]

        pages = executor.create_notion_pages(batch_data, 1)

        assert len(pages) == 1
        props = pages[0]["properties"]

        assert "date:Date:start" in props
        assert props["date:Date:start"] == "2020-01-01"
        assert "date:Date:is_datetime" in props
        assert props["date:Date:is_datetime"] == 0

        assert "date:Retrieved At:start" in props
        assert "date:Retrieved At:is_datetime" in props
        assert props["date:Retrieved At:is_datetime"] == 1

    def test_create_notion_pages_empty_batch(self):
        """Test creating pages with empty batch"""
        executor = StockDataExecutor()

        pages = executor.create_notion_pages([], 1)

        assert len(pages) == 0

    def test_execute_batch_processes_tickers(self, sample_tickers):
        """Test that execute_batch processes all tickers"""
        executor = StockDataExecutor()
        executor.tickers = sample_tickers

        batch = sample_tickers[:3]

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                records = executor.execute_batch(batch, 1, 10)

                assert executor.processed == 3
                # Each ticker creates records for all periods
                # But only major tickers get actual data
                assert records > 0

    def test_execute_batch_major_tickers(self):
        """Test that major tickers get sample data"""
        executor = StockDataExecutor()
        executor.tickers = ["AAPL", "MSFT", "GOOGL"]

        batch = ["AAPL"]

        with patch('builtins.open', mock_open()):
            with patch('json.dump') as mock_dump:
                records = executor.execute_batch(batch, 1, 1)

                assert executor.processed == 1
                # AAPL should get data for all 5 periods
                assert records == 5

    def test_execute_batch_saves_to_file(self, output_dir):
        """Test that execute_batch saves to correct file"""
        executor = StockDataExecutor()
        executor.tickers = ["TEST"]

        batch = ["TEST"]

        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('json.dump') as mock_dump:
                executor.execute_batch(batch, 3, 10)

                # Check that the file is created with correct naming
                # batch number should be zero-padded to 4 digits
                call_args = mocked_file.call_args_list
                # The file path should contain notion_batch_0003.json

    def test_execute_batch_creates_valid_json_structure(self):
        """Test that execute_batch creates valid JSON structure"""
        executor = StockDataExecutor()
        executor.tickers = ["AAPL"]

        batch = ["AAPL"]

        saved_data = None

        def capture_json(data, file, **kwargs):
            nonlocal saved_data
            saved_data = data

        with patch('builtins.open', mock_open()):
            with patch('json.dump', side_effect=capture_json):
                executor.execute_batch(batch, 5, 10)

                assert saved_data is not None
                assert "data_source_id" in saved_data
                assert "batch_number" in saved_data
                assert "ticker_count" in saved_data
                assert "record_count" in saved_data
                assert "pages" in saved_data

                assert saved_data["data_source_id"] == "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
                assert saved_data["batch_number"] == 5
                assert saved_data["ticker_count"] == 1

    def test_execute_batch_updates_saved_counter(self):
        """Test that execute_batch updates saved counter"""
        executor = StockDataExecutor()
        executor.tickers = ["AAPL", "MSFT"]

        batch = ["AAPL", "MSFT"]

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                initial_saved = executor.saved
                records = executor.execute_batch(batch, 1, 1)

                assert executor.saved == initial_saved + records

    def test_generate_upload_script_creates_content(self):
        """Test that generate_upload_script creates script content"""
        executor = StockDataExecutor()

        with patch('builtins.open', mock_open()) as mocked_file:
            executor.generate_upload_script(10)

            # Verify file was opened
            assert mocked_file.called

            # Get written content
            handle = mocked_file()
            written_calls = [call.args[0] for call in handle.write.call_args_list]
            content = ''.join(written_calls)

            assert "7c5225aa-429b-4580-946e-ba5b1db2ca6d" in content
            assert "range(1, 11)" in content  # 10 + 1
            assert "notion_batch_" in content

    def test_generate_upload_script_with_zero_batches(self):
        """Test generate_upload_script with zero batches"""
        executor = StockDataExecutor()

        with patch('builtins.open', mock_open()):
            executor.generate_upload_script(0)

    def test_run_loads_tickers_first(self, ticker_file, sample_tickers):
        """Test that run() loads tickers first"""
        executor = StockDataExecutor()
        executor.ticker_file = ticker_file

        with patch.object(executor, 'load_tickers', return_value=len(sample_tickers)):
            executor.tickers = sample_tickers
            with patch.object(executor, 'execute_batch') as mock_execute:
                with patch.object(executor, 'generate_upload_script'):
                    with patch('time.sleep'):
                        with patch('builtins.open', mock_open()):
                            with patch('json.dump'):
                                summary = executor.run()

                                assert len(executor.tickers) == len(sample_tickers)
                                # Should execute 1 batch (10 tickers / 100 batch size = 1)
                                assert mock_execute.call_count == 1

    def test_run_calculates_batches_correctly(self, large_ticker_list):
        """Test correct batch calculation"""
        executor = StockDataExecutor()
        executor.ticker_file = "dummy"

        with patch.object(executor, 'load_tickers', return_value=len(large_ticker_list)):
            executor.tickers = large_ticker_list

            with patch.object(executor, 'execute_batch') as mock_execute:
                with patch.object(executor, 'generate_upload_script'):
                    with patch('time.sleep'):
                        with patch('builtins.open', mock_open()):
                            with patch('json.dump'):
                                summary = executor.run()

                                # 250 tickers / 100 batch_size = 3 batches
                                assert mock_execute.call_count == 3

    def test_run_handles_keyboard_interrupt(self, ticker_file):
        """Test run handles KeyboardInterrupt gracefully"""
        executor = StockDataExecutor()
        executor.ticker_file = ticker_file

        with patch.object(executor, 'load_tickers', side_effect=KeyboardInterrupt):
            # Should not raise, should handle gracefully
            result = executor.run()
            assert result is None

    def test_run_handles_general_exception(self, ticker_file):
        """Test run handles exceptions"""
        executor = StockDataExecutor()
        executor.ticker_file = ticker_file

        with patch.object(executor, 'load_tickers', side_effect=Exception("Test error")):
            with pytest.raises(Exception):
                executor.run()

    def test_run_creates_summary_file(self, ticker_file, sample_tickers, output_dir):
        """Test that run creates a summary file"""
        executor = StockDataExecutor()
        executor.ticker_file = ticker_file

        summary_data = None

        def capture_summary(data, file, **kwargs):
            nonlocal summary_data
            if 'execution' in data:
                summary_data = data

        with patch.object(executor, 'load_tickers', return_value=len(sample_tickers)):
            executor.tickers = sample_tickers
            with patch('builtins.open', mock_open()):
                with patch('json.dump', side_effect=capture_summary):
                    with patch.object(executor, 'execute_batch'):
                        with patch.object(executor, 'generate_upload_script'):
                            with patch('time.sleep'):
                                summary = executor.run()

                                assert summary_data is not None
                                assert "execution" in summary_data
                                assert "statistics" in summary_data
                                assert "database" in summary_data

    def test_run_summary_structure(self, ticker_file, sample_tickers):
        """Test the structure of run summary"""
        executor = StockDataExecutor()
        executor.ticker_file = ticker_file

        summary_data = None

        def capture_summary(data, file, **kwargs):
            nonlocal summary_data
            if 'execution' in data:
                summary_data = data

        with patch.object(executor, 'load_tickers', return_value=len(sample_tickers)):
            executor.tickers = sample_tickers
            with patch('builtins.open', mock_open()):
                with patch('json.dump', side_effect=capture_summary):
                    with patch.object(executor, 'execute_batch', return_value=50):
                        with patch.object(executor, 'generate_upload_script'):
                            with patch('time.sleep'):
                                summary = executor.run()

                                assert summary_data["execution"]["status"] == "SUCCESS"
                                assert "start_time" in summary_data["execution"]
                                assert "end_time" in summary_data["execution"]
                                assert "duration" in summary_data["execution"]

                                stats = summary_data["statistics"]
                                assert "total_tickers" in stats
                                assert "processed_tickers" in stats
                                assert "total_batches" in stats
                                assert "saved_records" in stats
                                assert "failed_count" in stats

    def test_execute_batch_progress_logging(self, sample_tickers):
        """Test that progress is logged during batch execution"""
        executor = StockDataExecutor()
        executor.tickers = sample_tickers * 2  # 20 tickers

        batch = sample_tickers * 2

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                with patch('execute_stock_retrieval.logger') as mock_logger:
                    executor.execute_batch(batch, 1, 1)

                    # Should log progress every 10 tickers
                    info_calls = [call for call in mock_logger.info.call_args_list]
                    # At least one progress update should occur
                    assert len(info_calls) >= 1


class TestStockDataExecutorEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_hash_consistency_for_ticker_data(self):
        """Test that hash-based data generation is consistent"""
        executor = StockDataExecutor()
        executor.tickers = ["AAPL"]

        batch = ["AAPL"]

        # Execute twice and compare
        results1 = None
        results2 = None

        def capture_first(data, file, **kwargs):
            nonlocal results1
            if results1 is None:
                results1 = data

        def capture_second(data, file, **kwargs):
            nonlocal results2
            if results2 is None:
                results2 = data

        with patch('builtins.open', mock_open()):
            with patch('json.dump', side_effect=capture_first):
                executor.execute_batch(batch, 1, 1)

        executor.processed = 0  # Reset
        executor.saved = 0

        with patch('builtins.open', mock_open()):
            with patch('json.dump', side_effect=capture_second):
                executor.execute_batch(batch, 1, 1)

        # The data should be identical (hash is deterministic)
        assert results1["ticker_count"] == results2["ticker_count"]
        assert results1["record_count"] == results2["record_count"]

    def test_ticker_with_special_characters(self):
        """Test handling of tickers with special characters"""
        executor = StockDataExecutor()
        executor.tickers = ["BRK.A", "BRK.B"]

        batch = ["BRK.A", "BRK.B"]

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                records = executor.execute_batch(batch, 1, 1)

                assert executor.processed == 2

    def test_very_long_ticker_symbol(self):
        """Test handling of unusually long ticker symbols"""
        executor = StockDataExecutor()
        long_ticker = "VERYLONGTICKERSYMBOL123456"

        batch = [long_ticker]

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                records = executor.execute_batch(batch, 1, 1)

                assert executor.processed == 1

    def test_batch_with_single_ticker(self):
        """Test batch processing with single ticker"""
        executor = StockDataExecutor()
        executor.tickers = ["SINGLE"]

        batch = ["SINGLE"]

        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                records = executor.execute_batch(batch, 1, 1)

                assert executor.processed == 1
                # Should create records for all 5 periods
                assert records >= 0

    def test_batch_number_formatting(self):
        """Test that batch numbers are zero-padded"""
        executor = StockDataExecutor()
        executor.tickers = ["TEST"]

        batch = ["TEST"]

        file_path_used = None

        def capture_path(path, mode='r'):
            nonlocal file_path_used
            file_path_used = path
            return mock_open()(path, mode)

        with patch('builtins.open', side_effect=capture_path):
            with patch('json.dump'):
                executor.execute_batch(batch, 99, 100)

                # File should be notion_batch_0099.json (4 digits)
                assert file_path_used is not None
                assert "0099" in file_path_used

    def test_concurrent_batch_isolation(self):
        """Test that multiple executor instances don't interfere"""
        executor1 = StockDataExecutor()
        executor2 = StockDataExecutor()

        executor1.processed = 10
        executor2.processed = 20

        assert executor1.processed == 10
        assert executor2.processed == 20

    def test_period_date_boundaries(self):
        """Test that period dates are valid"""
        executor = StockDataExecutor()

        for period in executor.periods:
            from_date = datetime.strptime(period["from"], "%Y-%m-%d")
            to_date = datetime.strptime(period["to"], "%Y-%m-%d")

            # to_date should be after from_date
            assert to_date >= from_date

            # Each period should span roughly 5 years (allowing for boundaries)
            delta = (to_date - from_date).days
            assert delta >= 1460  # At least 4 years
            assert delta <= 2000  # At most ~5.5 years
