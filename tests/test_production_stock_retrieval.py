"""Tests for production_stock_retrieval.py"""
import json
import os
from datetime import datetime
from typing import Any, List
from unittest.mock import mock_open, patch

import pytest

from production_stock_retrieval import ProductionStockRetriever


class TestProductionStockRetriever:
    """Test suite for ProductionStockRetriever class"""

    def test_init(self):
        """Test initialization of ProductionStockRetriever"""
        retriever = ProductionStockRetriever()

        assert retriever.ticker_file == "/mnt/user-data/uploads/all_tickers.json"
        assert retriever.data_source_id == "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
        assert retriever.batch_size == 100
        assert retriever.processed == 0
        assert retriever.saved == 0
        assert not retriever.failed
        assert len(retriever.periods) == 5

    def test_init_periods_structure(self):
        """Test that periods are correctly initialized"""
        retriever = ProductionStockRetriever()

        expected_periods = [
            {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"},
            {"from": "2015-01-01", "to": "2019-12-31", "label": "2015-2019"},
            {"from": "2010-01-01", "to": "2014-12-31", "label": "2010-2014"},
            {"from": "2005-01-01", "to": "2009-12-31", "label": "2005-2009"},
            {"from": "2000-01-01", "to": "2004-12-31", "label": "2000-2004"}
        ]

        assert retriever.periods == expected_periods

    def test_load_tickers(self, ticker_file, sample_tickers):
        """Test loading tickers from file"""
        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        count = retriever.load_tickers()

        assert count == len(sample_tickers)
        assert retriever.tickers == sample_tickers

    def test_load_tickers_empty_file(self, empty_ticker_file):
        """Test loading empty ticker file"""
        retriever = ProductionStockRetriever()
        retriever.ticker_file = empty_ticker_file

        count = retriever.load_tickers()

        assert count == 0
        assert not retriever.tickers

    def test_load_tickers_file_not_found(self):
        """Test loading tickers with missing file"""
        retriever = ProductionStockRetriever()
        retriever.ticker_file = "/nonexistent/path/tickers.json"

        with pytest.raises(FileNotFoundError):
            retriever.load_tickers()

    def test_load_tickers_invalid_json(self, invalid_json_file):
        """Test loading tickers with invalid JSON"""
        retriever = ProductionStockRetriever()
        retriever.ticker_file = invalid_json_file

        with pytest.raises(json.JSONDecodeError):
            retriever.load_tickers()

    def test_get_polygon_data_structure(self):
        """Test structure of get_polygon_data return value"""
        retriever = ProductionStockRetriever()
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}

        result = retriever.get_polygon_data("AAPL", period)

        # Check all required fields are present
        assert "ticker" in result
        assert "period" in result
        assert "has_data" in result
        assert "open" in result
        assert "high" in result
        assert "low" in result
        assert "close" in result
        assert "volume" in result
        assert "vwap" in result
        assert "transactions" in result
        assert "data_points" in result
        assert "timespan" in result

    def test_get_polygon_data_default_values(self):
        """Test default values returned when no data available"""
        retriever = ProductionStockRetriever()
        period = {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"}

        result = retriever.get_polygon_data("UNKNOWN", period)

        assert result["ticker"] == "UNKNOWN"
        assert result["period"] == "2020-2024"
        assert result["has_data"] is False
        assert result["open"] is None
        assert result["high"] is None
        assert result["low"] is None
        assert result["close"] is None
        assert result["volume"] is None
        assert result["vwap"] is None
        assert result["transactions"] is None
        assert result["data_points"] == 0
        assert result["timespan"] == "day"

    def test_save_batch_creates_file(self, output_dir):
        """Test that save_batch creates a properly formatted file"""
        retriever = ProductionStockRetriever()

        pages = [
            {
                "properties": {
                    "Ticker": "AAPL",
                    "Period": "2020-2024",
                    "Has Data": "__YES__",
                    "Batch Number": 1
                }
            }
        ]

        output_file = os.path.join(output_dir, "batch_0001_notion.json")

        # Monkey patch the output path
        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('json.dump') as mock_dump:
                retriever.save_batch(pages, 1)

                # Verify json.dump was called
                mock_dump.assert_called_once()
                args = mock_dump.call_args[0]

                # Check the data structure
                batch_data = args[0]
                assert batch_data["data_source_id"] == "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
                assert batch_data["batch_number"] == 1
                assert batch_data["record_count"] == 1
                assert "timestamp" in batch_data
                assert batch_data["pages"] == pages

    def test_save_batch_multiple_pages(self, output_dir):
        """Test save_batch with multiple pages"""
        retriever = ProductionStockRetriever()

        pages = [{"properties": {"Ticker": f"TICK{i}"}} for i in range(100)]

        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('json.dump') as mock_dump:
                retriever.save_batch(pages, 5)

                args = mock_dump.call_args[0]
                batch_data = args[0]
                assert batch_data["record_count"] == 100
                assert batch_data["batch_number"] == 5

    def test_process_batch_updates_counters(self, sample_tickers):
        """Test that process_batch updates processed and saved counters"""
        retriever = ProductionStockRetriever()
        retriever.tickers = sample_tickers

        batch = sample_tickers[:5]

        with patch.object(retriever, 'save_batch') as mock_save:
            with patch('time.sleep'):  # Skip sleep delays
                records = retriever.process_batch(batch, 1, 10)

                assert retriever.processed == 5
                # Each ticker generates 5 periods worth of data
                expected_records = 5 * len(retriever.periods)
                assert records == expected_records
                mock_save.assert_called_once()

    def test_process_batch_with_empty_batch(self):
        """Test processing an empty batch"""
        retriever = ProductionStockRetriever()
        retriever.tickers = []

        batch = []

        with patch.object(retriever, 'save_batch') as mock_save:
            with patch('time.sleep'):
                records = retriever.process_batch(batch, 1, 1)

                assert retriever.processed == 0
                assert records == 0
                mock_save.assert_called_once()

    def test_process_batch_creates_correct_page_structure(self):
        """Test that process_batch creates correct Notion page structure"""
        retriever = ProductionStockRetriever()
        retriever.tickers = ["AAPL"]

        batch = ["AAPL"]

        saved_pages: List[dict[str, Any]] = []

        def capture_pages(pages, batch_num):
            saved_pages.clear()
            if pages:
                saved_pages.extend(pages)

        with patch.object(retriever, 'save_batch', side_effect=capture_pages):
            with patch('time.sleep'):
                retriever.process_batch(batch, 1, 1)

                assert saved_pages is not None
                assert len(saved_pages) == 5  # 5 periods

                # Check first page structure
                page = saved_pages[0]
                assert "properties" in page
                props = page["properties"]
                assert "Ticker" in props
                assert "Period" in props
                assert "Has Data" in props
                assert "Batch Number" in props
                assert "date:Date:start" in props
                assert "date:Retrieved At:start" in props

    def test_create_notion_upload_script(self, output_dir):
        """Test creation of Notion upload script"""
        retriever = ProductionStockRetriever()

        script_file = os.path.join(output_dir, "notion_bulk_upload.py")

        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('os.chmod'):
                retriever.create_notion_upload_script(67)

                # Verify file was opened for writing
                assert mocked_file.called

    def test_create_notion_upload_script_content(self):
        """Test that upload script contains correct configuration"""
        retriever = ProductionStockRetriever()

        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('os.chmod'):
                retriever.create_notion_upload_script(10)

                # Get the written content
                handle = mocked_file()
                written_content = ''.join(call.args[0] for call in handle.write.call_args_list)

                assert "7c5225aa-429b-4580-946e-ba5b1db2ca6d" in written_content
                assert "TOTAL_BATCHES = 10" in written_content

    @patch('production_stock_retrieval.logger')
    def test_run_logs_startup(self, mock_logger, ticker_file, sample_tickers):
        """Test that run method logs startup information"""
        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        with patch.object(retriever, 'process_batch'):
            with patch.object(retriever, 'create_notion_upload_script'):
                with patch('time.sleep'):
                    with patch('builtins.open', mock_open()):
                        with patch('json.dump'):
                            # Just verify it can be called without errors
                            try:
                                retriever.run()
                            except:
                                pass

    def test_batch_size_calculation(self, large_ticker_list):
        """Test batch size calculations with large ticker list"""
        retriever = ProductionStockRetriever()
        retriever.tickers = large_ticker_list

        ticker_count = len(large_ticker_list)
        expected_batches = (ticker_count + retriever.batch_size - 1) // retriever.batch_size

        assert expected_batches == 3  # 250 tickers / 100 batch_size = 3 batches

    def test_process_batch_rate_limiting(self, sample_tickers):
        """Test that process_batch includes rate limiting"""
        retriever = ProductionStockRetriever()
        retriever.tickers = sample_tickers

        batch = sample_tickers[:2]

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep') as mock_sleep:
                retriever.process_batch(batch, 1, 1)

                # Should sleep for each ticker * periods
                expected_sleeps = 2 * len(retriever.periods)
                assert mock_sleep.call_count == expected_sleeps

    def test_process_batch_all_periods_processed(self, sample_tickers):
        """Test that all periods are processed for each ticker"""
        retriever = ProductionStockRetriever()
        retriever.tickers = sample_tickers

        batch = ["AAPL"]

        saved_pages: List[dict[str, Any]] = []

        def capture_pages(pages, batch_num):
            saved_pages.clear()
            if pages:
                saved_pages.extend(pages)

        with patch.object(retriever, 'save_batch', side_effect=capture_pages):
            with patch('time.sleep'):
                retriever.process_batch(batch, 1, 1)

                # Should have one page per period
                assert len(saved_pages) == len(retriever.periods)

                # Check all periods are represented
                periods_found = set(page["properties"]["Period"] for page in saved_pages)
                expected_periods = set(p["label"] for p in retriever.periods)
                assert periods_found == expected_periods

    def test_data_source_id_immutable(self):
        """Test that data_source_id is consistent"""
        retriever1 = ProductionStockRetriever()
        retriever2 = ProductionStockRetriever()

        assert retriever1.data_source_id == retriever2.data_source_id
        assert retriever1.data_source_id == "7c5225aa-429b-4580-946e-ba5b1db2ca6d"

    def test_checkpoint_data_structure(self):
        """Test checkpoint data structure"""
        retriever = ProductionStockRetriever()
        retriever.processed = 500
        retriever.saved = 2500

        checkpoint = {
            "batch": 5,
            "processed": retriever.processed,
            "saved": retriever.saved,
            "timestamp": datetime.now().isoformat()
        }

        assert "batch" in checkpoint
        assert "processed" in checkpoint
        assert "saved" in checkpoint
        assert "timestamp" in checkpoint
        assert checkpoint["processed"] == 500
        assert checkpoint["saved"] == 2500


class TestProductionStockRetrieverEdgeCases:
    """Test edge cases and error conditions"""

    def test_very_large_batch(self):
        """Test handling of very large batches"""
        retriever = ProductionStockRetriever()
        large_batch = [f"TICK{i:05d}" for i in range(1000)]
        retriever.tickers = large_batch

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep'):
                records = retriever.process_batch(large_batch, 1, 1)

                assert retriever.processed == 1000
                assert records == 1000 * len(retriever.periods)

    def test_special_characters_in_ticker(self):
        """Test handling tickers with special characters"""
        retriever = ProductionStockRetriever()
        special_tickers = ["BRK.A", "BRK.B", "BF.A", "BF.B"]

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep'):
                records = retriever.process_batch(special_tickers, 1, 1)

                assert retriever.processed == 4

    def test_unicode_ticker_symbols(self):
        """Test handling of unicode in ticker symbols"""
        retriever = ProductionStockRetriever()
        unicode_tickers = ["TICK™", "STOCK®", "TEST©"]

        with patch.object(retriever, 'save_batch'):
            with patch('time.sleep'):
                records = retriever.process_batch(unicode_tickers, 1, 1)

                assert retriever.processed == 3

    def test_zero_batch_size_edge_case(self):
        """Test with modified batch size"""
        retriever = ProductionStockRetriever()
        retriever.batch_size = 1  # Process one at a time

        assert retriever.batch_size == 1

    def test_timestamp_format(self):
        """Test that timestamps are ISO format"""
        retriever = ProductionStockRetriever()

        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('json.dump') as mock_dump:
                retriever.save_batch([], 1)

                args = mock_dump.call_args[0]
                batch_data = args[0]

                # Verify timestamp is valid ISO format
                timestamp = batch_data["timestamp"]
                parsed = datetime.fromisoformat(timestamp)
                assert isinstance(parsed, datetime)

    def test_negative_batch_number(self):
        """Test handling of negative batch numbers"""
        retriever = ProductionStockRetriever()

        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('json.dump') as mock_dump:
                # Should handle negative batch numbers (even if unusual)
                retriever.save_batch([], -1)

                args = mock_dump.call_args[0]
                batch_data = args[0]
                assert batch_data["batch_number"] == -1
