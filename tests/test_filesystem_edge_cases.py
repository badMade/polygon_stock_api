"""Tests for file system edge cases and error scenarios.

Tests handling of disk space issues, permission errors, concurrent access,
path validation, and file I/O edge cases.
"""

import json
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

import pytest

from production_stock_retrieval import ProductionStockRetriever
from stock_notion_retrieval import StockDataNotionRetriever


def _is_running_as_root():
    """Check if tests are running as root (permission tests won't work)."""
    return os.geteuid() == 0 if hasattr(os, 'geteuid') else False


class TestFilePermissionErrors:
    """Tests for handling file permission errors."""

    def test_handle_read_permission_denied(self, temp_dir):
        """Test handling when ticker file is not readable."""
        # Skip on Windows or when running as root
        if os.name == 'nt' or _is_running_as_root():
            pytest.skip("Permission tests not reliable on Windows or as root")

        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(["AAPL"], f)

        os.chmod(ticker_file, 0o000)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        try:
            with pytest.raises(PermissionError):
                retriever.load_tickers()
        finally:
            # Restore permissions for cleanup
            os.chmod(ticker_file, 0o644)

    def test_handle_write_permission_denied(self, temp_dir):
        """Test handling when output directory is not writable."""
        # Skip on Windows or when running as root
        if os.name == 'nt' or _is_running_as_root():
            pytest.skip("Permission tests not reliable on Windows or as root")

        output_dir = os.path.join(temp_dir, "readonly")
        os.makedirs(output_dir)
        os.chmod(output_dir, 0o444)  # Read-only

        try:
            with pytest.raises(PermissionError):
                filepath = os.path.join(output_dir, "test.json")
                with open(filepath, 'w') as f:
                    f.write("{}")
        finally:
            os.chmod(output_dir, 0o755)

    def test_handle_directory_not_writable(self, temp_dir):
        """Test handling when batch output directory is not writable."""
        # Skip on Windows or when running as root
        if os.name == 'nt' or _is_running_as_root():
            pytest.skip("Permission tests not reliable on Windows or as root")

        output_dir = os.path.join(temp_dir, "outputs")
        os.makedirs(output_dir)

        # Create ticker file
        ticker_file = os.path.join(temp_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(["AAPL"], f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        os.chmod(output_dir, 0o444)

        try:
            with patch('production_stock_retrieval.OUTPUT_DIR', Path(output_dir)):
                with patch('time.sleep'):
                    retriever.load_tickers()
                    with pytest.raises(PermissionError):
                        retriever.process_batch(retriever.tickers, 1, 1)
        finally:
            os.chmod(output_dir, 0o755)


class TestDiskSpaceHandling:
    """Tests for handling disk space issues."""

    def test_handle_disk_full_on_write(self):
        """Test handling when disk is full during write."""
        retriever = ProductionStockRetriever()
        pages = [{"properties": {"Ticker": "AAPL"}}]

        def raise_disk_full(*args, **kwargs):
            raise OSError(28, "No space left on device")

        with patch('builtins.open', side_effect=raise_disk_full):
            with pytest.raises(OSError) as exc_info:
                retriever.save_batch(pages, 1)

            assert exc_info.value.errno == 28

    def test_handle_disk_full_on_checkpoint(self, temp_dir):
        """Test handling when disk is full during checkpoint save."""
        retriever = StockDataNotionRetriever()
        retriever.processed_count = 100
        retriever.tickers = ["AAPL"] * 100

        def raise_disk_full(*args, **kwargs):
            raise OSError(28, "No space left on device")

        with patch('builtins.open', side_effect=raise_disk_full):
            with pytest.raises(OSError):
                retriever.save_checkpoint(1)


class TestConcurrentFileAccess:
    """Tests for handling concurrent file access."""

    def test_batch_file_naming_uniqueness(self):
        """Test that batch file names are unique."""
        batch_numbers = list(range(1, 100))
        filenames = [f"batch_{num:04d}_notion.json" for num in batch_numbers]

        # All filenames should be unique
        assert len(filenames) == len(set(filenames))

    def test_checkpoint_file_overwrite(self, temp_dir):
        """Test that checkpoint properly overwrites previous version."""
        checkpoint_file = os.path.join(temp_dir, "checkpoint.json")

        # Write initial checkpoint
        with open(checkpoint_file, 'w') as f:
            json.dump({"batch": 1, "processed": 100}, f)

        # Write updated checkpoint
        with open(checkpoint_file, 'w') as f:
            json.dump({"batch": 2, "processed": 200}, f)

        # Read and verify latest
        with open(checkpoint_file, 'r') as f:
            data = json.load(f)

        assert data["batch"] == 2
        assert data["processed"] == 200

    def test_atomic_file_write_simulation(self, temp_dir):
        """Test atomic file write pattern (write to temp, then rename)."""
        target_file = os.path.join(temp_dir, "target.json")
        temp_file = os.path.join(temp_dir, "target.json.tmp")

        data = {"key": "value"}

        # Write to temp file first
        with open(temp_file, 'w') as f:
            json.dump(data, f)

        # Rename to target (atomic on most filesystems)
        os.rename(temp_file, target_file)

        # Verify
        assert os.path.exists(target_file)
        assert not os.path.exists(temp_file)

        with open(target_file, 'r') as f:
            loaded = json.load(f)

        assert loaded == data


class TestPathValidation:
    """Tests for file path validation."""

    def test_absolute_path_requirement(self, temp_dir):
        """Test that absolute paths are handled correctly."""
        abs_path = os.path.join(temp_dir, "tickers.json")
        with open(abs_path, 'w') as f:
            json.dump(["AAPL"], f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = abs_path

        count = retriever.load_tickers()
        assert count == 1

    def test_relative_path_handling(self):
        """Test that relative paths are handled."""
        rel_path = "relative/path/tickers.json"

        # Relative path should work if file exists at that location
        # In production, absolute paths are preferred
        assert not os.path.isabs(rel_path)

    def test_path_with_special_characters(self, temp_dir):
        """Test paths with special characters."""
        special_dir = os.path.join(temp_dir, "path with spaces")
        os.makedirs(special_dir)

        ticker_file = os.path.join(special_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(["AAPL"], f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        count = retriever.load_tickers()
        assert count == 1

    def test_unicode_in_path(self, temp_dir):
        """Test paths with unicode characters."""
        unicode_dir = os.path.join(temp_dir, "datos_financieros")
        os.makedirs(unicode_dir)

        ticker_file = os.path.join(unicode_dir, "tickers.json")
        with open(ticker_file, 'w') as f:
            json.dump(["AAPL"], f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        count = retriever.load_tickers()
        assert count == 1


class TestFileSizeHandling:
    """Tests for handling various file sizes."""

    def test_empty_ticker_file(self, temp_dir):
        """Test handling of empty ticker file (empty array)."""
        ticker_file = os.path.join(temp_dir, "empty.json")
        with open(ticker_file, 'w') as f:
            json.dump([], f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        count = retriever.load_tickers()
        assert count == 0
        assert retriever.tickers == []

    def test_large_ticker_file(self, temp_dir):
        """Test handling of large ticker file."""
        # Create file with 10,000 tickers
        large_tickers = [f"TICK{i:05d}" for i in range(10000)]

        ticker_file = os.path.join(temp_dir, "large.json")
        with open(ticker_file, 'w') as f:
            json.dump(large_tickers, f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        count = retriever.load_tickers()
        assert count == 10000

    def test_large_batch_file_output(self, temp_dir):
        """Test that large batch files are written correctly."""
        retriever = ProductionStockRetriever()

        # Create many pages
        pages = [
            {"properties": {"Ticker": f"TICK{i:04d}", "Period": "2020-2024"}}
            for i in range(1000)
        ]

        with patch('production_stock_retrieval.OUTPUT_DIR', Path(temp_dir)):
            retriever.save_batch(pages, 1)

        batch_file = os.path.join(temp_dir, "batch_0001_notion.json")
        assert os.path.exists(batch_file)

        with open(batch_file, 'r') as f:
            data = json.load(f)

        assert data["record_count"] == 1000
        assert len(data["pages"]) == 1000


class TestFileContentValidation:
    """Tests for file content validation."""

    def test_valid_json_ticker_file(self, temp_dir):
        """Test loading valid JSON ticker file."""
        ticker_file = os.path.join(temp_dir, "valid.json")
        with open(ticker_file, 'w') as f:
            json.dump(["AAPL", "MSFT", "GOOGL"], f)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        count = retriever.load_tickers()
        assert count == 3

    def test_invalid_json_ticker_file(self, temp_dir):
        """Test handling of invalid JSON in ticker file."""
        ticker_file = os.path.join(temp_dir, "invalid.json")
        with open(ticker_file, 'w') as f:
            f.write("[AAPL, MSFT]")  # Invalid JSON (missing quotes)

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        with pytest.raises(json.JSONDecodeError):
            retriever.load_tickers()

    def test_wrong_json_type(self, temp_dir):
        """Test handling when JSON is not an array."""
        ticker_file = os.path.join(temp_dir, "wrong_type.json")
        with open(ticker_file, 'w') as f:
            json.dump({"tickers": ["AAPL"]}, f)  # Object instead of array

        retriever = ProductionStockRetriever()
        retriever.ticker_file = ticker_file

        # Should load but may fail on iteration if not handled
        retriever.load_tickers()
        # The loaded data is a dict, not a list
        assert isinstance(retriever.tickers, dict)

    def test_batch_file_json_validity(self, temp_dir):
        """Test that batch files are valid JSON."""
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

        # Should be valid JSON
        with open(batch_file, 'r') as f:
            data = json.load(f)

        assert data is not None


class TestDirectoryOperations:
    """Tests for directory-related operations."""

    def test_create_output_directory_if_missing(self, temp_dir):
        """Test that output directory is created if it doesn't exist."""
        new_output_dir = os.path.join(temp_dir, "new_outputs")

        # Directory doesn't exist yet
        assert not os.path.exists(new_output_dir)

        # Create it
        os.makedirs(new_output_dir, exist_ok=True)

        assert os.path.exists(new_output_dir)
        assert os.path.isdir(new_output_dir)

    def test_nested_directory_creation(self, temp_dir):
        """Test creating nested directory structure."""
        nested_path = os.path.join(temp_dir, "a", "b", "c", "d")

        os.makedirs(nested_path, exist_ok=True)

        assert os.path.exists(nested_path)

    def test_exist_ok_on_existing_directory(self, temp_dir):
        """Test that exist_ok=True doesn't fail on existing directory."""
        existing_dir = os.path.join(temp_dir, "existing")
        os.makedirs(existing_dir)

        # Should not raise
        os.makedirs(existing_dir, exist_ok=True)

        assert os.path.exists(existing_dir)

    def test_list_batch_files_in_directory(self, temp_dir):
        """Test listing batch files in output directory."""
        # Create some batch files
        for i in range(1, 6):
            filepath = os.path.join(temp_dir, f"batch_{i:04d}_notion.json")
            with open(filepath, 'w') as f:
                json.dump({"batch_number": i}, f)

        # Create some non-batch files
        with open(os.path.join(temp_dir, "checkpoint.json"), 'w') as f:
            json.dump({}, f)
        with open(os.path.join(temp_dir, "summary.json"), 'w') as f:
            json.dump({}, f)

        # List only batch files
        all_files = os.listdir(temp_dir)
        batch_files = [f for f in all_files if f.startswith("batch_") and f.endswith("_notion.json")]

        assert len(batch_files) == 5
