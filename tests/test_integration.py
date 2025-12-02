"""Integration tests for end-to-end workflow testing.

Tests the complete pipeline from ticker loading through batch processing
to file generation and checkpoint recovery.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from production_stock_retrieval import ProductionStockRetriever, OUTPUT_DIR, UPLOADS_DIR
from stock_notion_retrieval import StockDataNotionRetriever


class TestEndToEndWorkflow:
    """End-to-end integration tests for the complete data retrieval pipeline."""

    @pytest.mark.integration
    def test_complete_ticker_to_batch_file_workflow(self, temp_dir):
        """Test complete workflow from ticker loading to batch file creation."""
        # Setup: Create ticker file
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        # Create retriever and configure paths
        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 5  # Process all in one batch

        # Mock the output directory
        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                # Load tickers
                count = retriever.load_tickers()
                assert count == 5

                # Process batch
                batch = retriever.tickers[:5]
                records = retriever.process_batch(batch, 1, 1)

                # Verify records created (5 tickers * 5 periods = 25)
                assert records == 25
                assert retriever.processed == 5
                assert retriever.saved == 25

    @pytest.mark.integration
    def test_multi_batch_processing_workflow(self, temp_dir):
        """Test processing multiple batches sequentially."""
        # Setup: Create ticker file with 15 tickers
        tickers = [f"TICK{i:03d}" for i in range(15)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 5  # 3 batches of 5

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()

                total_records = 0
                for batch_num in range(1, 4):
                    start_idx = (batch_num - 1) * retriever.batch_size
                    end_idx = start_idx + retriever.batch_size
                    batch = retriever.tickers[start_idx:end_idx]
                    records = retriever.process_batch(batch, batch_num, 3)
                    total_records += records

                # Verify all tickers processed
                assert retriever.processed == 15
                # 15 tickers * 5 periods = 75 records
                assert total_records == 75

    @pytest.mark.integration
    def test_workflow_with_checkpoint_creation(self, temp_dir):
        """Test that checkpoints are created during batch processing."""
        tickers = [f"TICK{i:03d}" for i in range(100)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 10

        checkpoint_created = False
        original_open = open

        def mock_open_checkpoint(*args, **kwargs):
            nonlocal checkpoint_created
            if 'checkpoint.json' in str(args[0]) and 'w' in str(args[1:]):
                checkpoint_created = True
            return original_open(*args, **kwargs)

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                with patch('builtins.open', side_effect=mock_open_checkpoint):
                    retriever.load_tickers()

                    # Process 10 batches to trigger checkpoint (every 10 batches)
                    for batch_num in range(1, 11):
                        start_idx = (batch_num - 1) * retriever.batch_size
                        end_idx = start_idx + retriever.batch_size
                        batch = retriever.tickers[start_idx:end_idx]
                        retriever.process_batch(batch, batch_num, 10)

    @pytest.mark.integration
    def test_batch_file_structure_integrity(self, temp_dir):
        """Test that generated batch files have correct structure."""
        tickers = ["AAPL", "MSFT"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 2

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()
                retriever.process_batch(retriever.tickers, 1, 1)

        # Read and validate batch file
        batch_file = os.path.join(temp_dir, "batch_0001_notion.json")
        assert os.path.exists(batch_file)

        with open(batch_file, 'r') as f:
            batch_data = json.load(f)

        # Validate structure
        assert "data_source_id" in batch_data
        assert batch_data["data_source_id"] == "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
        assert "batch_number" in batch_data
        assert batch_data["batch_number"] == 1
        assert "record_count" in batch_data
        assert batch_data["record_count"] == 10  # 2 tickers * 5 periods
        assert "timestamp" in batch_data
        assert "pages" in batch_data
        assert len(batch_data["pages"]) == 10


class TestNotionRetrieverIntegration:
    """Integration tests for StockDataNotionRetriever."""

    @pytest.mark.integration
    def test_complete_notion_workflow(self, temp_dir):
        """Test complete workflow for Notion retriever."""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 3

        with patch('stock_notion_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                # Load tickers
                loaded = retriever.load_tickers()
                assert loaded == tickers

                # Create database structure
                props = retriever.create_notion_database()
                assert "Ticker" in props
                assert "Period" in props

                # Process batch
                retriever.process_batch(retriever.tickers, 1, 1)

                # Verify processing
                assert retriever.processed_count == 3

    @pytest.mark.integration
    def test_notion_retriever_with_checkpoint_save(self, temp_dir):
        """Test that NotionRetriever saves checkpoints correctly."""
        tickers = [f"TICK{i:02d}" for i in range(25)]
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(tickers, f)

        retriever = StockDataNotionRetriever()
        retriever.ticker_file = ticker_file
        retriever.batch_size = 5

        with patch('stock_notion_retrieval.OUTPUT_DIR', Path(temp_dir)):
            with patch('time.sleep'):
                retriever.load_tickers()

                # Process 5 batches (checkpoint at batch 5)
                for batch_num in range(1, 6):
                    start_idx = (batch_num - 1) * retriever.batch_size
                    end_idx = start_idx + retriever.batch_size
                    batch = retriever.tickers[start_idx:end_idx]
                    retriever.process_batch(batch, batch_num, 5)

        # Verify checkpoint file
        checkpoint_file = os.path.join(temp_dir, "retrieval_checkpoint.json")
        assert os.path.exists(checkpoint_file)

        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)

        assert checkpoint["last_batch"] == 5
        assert checkpoint["processed_count"] == 25


class TestCrossModuleIntegration:
    """Tests for integration between different modules."""

    @pytest.mark.integration
    def test_batch_file_format_compatibility(self, temp_dir):
        """Test that batch files from ProductionRetriever are correctly formatted."""
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

        # Read batch file and verify it can be parsed
        batch_file = os.path.join(temp_dir, "batch_0001_notion.json")
        with open(batch_file, 'r') as f:
            batch_data = json.load(f)

        # Verify pages have required Notion properties
        for page in batch_data["pages"]:
            props = page["properties"]
            assert "Ticker" in props
            assert "Period" in props
            assert "Has Data" in props
            assert "Batch Number" in props
            assert "date:Date:start" in props
            assert "date:Retrieved At:start" in props

    @pytest.mark.integration
    def test_multiple_period_data_consistency(self, temp_dir):
        """Test that all periods are consistently processed for each ticker."""
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

        # Group pages by ticker
        ticker_periods = {}
        for page in batch_data["pages"]:
            ticker = page["properties"]["Ticker"]
            period = page["properties"]["Period"]
            if ticker not in ticker_periods:
                ticker_periods[ticker] = set()
            ticker_periods[ticker].add(period)

        # Each ticker should have all 5 periods
        expected_periods = {"2020-2024", "2015-2019", "2010-2014", "2005-2009", "2000-2004"}
        for ticker, periods in ticker_periods.items():
            assert periods == expected_periods, f"Ticker {ticker} missing periods"
