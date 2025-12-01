"""Shared test fixtures and utilities.

Provides pytest fixtures and helper functions for testing the stock
retrieval and Notion integration components.
"""
# pylint: disable=redefined-outer-name
import json
import os
import tempfile
from datetime import datetime

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_tickers():
    """Sample ticker list for testing"""
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX", "AMD", "INTC"]


@pytest.fixture
def large_ticker_list():
    """Large ticker list for batch testing"""
    return [f"TICK{i:04d}" for i in range(250)]


@pytest.fixture
def ticker_file(temp_dir, sample_tickers):
    """Create a temporary ticker JSON file"""
    filepath = os.path.join(temp_dir, "test_tickers.json")
    with open(filepath, 'w') as f:
        json.dump(sample_tickers, f)
    return filepath


@pytest.fixture
def empty_ticker_file(temp_dir):
    """Create an empty ticker JSON file"""
    filepath = os.path.join(temp_dir, "empty_tickers.json")
    with open(filepath, 'w') as f:
        json.dump([], f)
    return filepath


@pytest.fixture
def invalid_json_file(temp_dir):
    """Create a file with invalid JSON"""
    filepath = os.path.join(temp_dir, "invalid.json")
    with open(filepath, 'w') as f:
        f.write("{invalid json content")
    return filepath


@pytest.fixture
def sample_periods():
    """Standard time periods for testing"""
    return [
        {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"},
        {"from": "2015-01-01", "to": "2019-12-31", "label": "2015-2019"},
        {"from": "2010-01-01", "to": "2014-12-31", "label": "2010-2014"},
        {"from": "2005-01-01", "to": "2009-12-31", "label": "2005-2009"},
        {"from": "2000-01-01", "to": "2004-12-31", "label": "2000-2004"}
    ]


@pytest.fixture
def sample_polygon_data():
    """Sample Polygon API response data"""
    return {
        "ticker": "AAPL",
        "period": "2020-2024",
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


@pytest.fixture
def sample_null_data():
    """Sample data for ticker with no data"""
    return {
        "ticker": "NULL",
        "period": "2000-2004",
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


@pytest.fixture
def sample_batch_data():
    """Sample batch data for Notion"""
    return {
        "data_source_id": "7c5225aa-429b-4580-946e-ba5b1db2ca6d",
        "batch_number": 1,
        "record_count": 5,
        "timestamp": datetime.now().isoformat(),
        "pages": [
            {
                "properties": {
                    "Ticker": "AAPL",
                    "Period": "2020-2024",
                    "Has Data": "__YES__",
                    "Batch Number": 1,
                    "date:Date:start": "2020-01-01",
                    "date:Date:is_datetime": 0,
                    "date:Retrieved At:start": datetime.now().isoformat(),
                    "date:Retrieved At:is_datetime": 1,
                    "Open": 150.25,
                    "High": 155.50,
                    "Low": 149.00,
                    "Close": 154.30,
                    "Volume": 50000000,
                    "VWAP": 152.45,
                    "Transactions": 450000,
                    "Data Points": 252,
                    "Timespan": "day"
                }
            }
        ]
    }


@pytest.fixture
def mock_checkpoint_data():
    """Sample checkpoint data"""
    return {
        "batch": 10,
        "processed": 1000,
        "saved": 5000,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def output_dir(temp_dir):
    """Create output directory for test files"""
    output_path = os.path.join(temp_dir, "outputs")
    os.makedirs(output_path, exist_ok=True)
    return output_path


@pytest.fixture
def batch_file(output_dir, sample_batch_data):
    """Create a sample batch file"""
    filepath = os.path.join(output_dir, "batch_0001_notion.json")
    with open(filepath, 'w') as f:
        json.dump(sample_batch_data, f, indent=2)
    return filepath


@pytest.fixture
def multiple_batch_files(output_dir):
    """Create multiple batch files for testing"""
    files = []
    for i in range(1, 6):
        filepath = os.path.join(output_dir, f"batch_{i:04d}_notion.json")
        data = {
            "data_source_id": "7c5225aa-429b-4580-946e-ba5b1db2ca6d",
            "batch_number": i,
            "record_count": 100 * i,
            "timestamp": datetime.now().isoformat(),
            "pages": []
        }
        with open(filepath, 'w') as f:
            json.dump(data, f)
        files.append(filepath)
    return files


@pytest.fixture
def mock_logger(monkeypatch):
    """Mock logger to capture log messages"""
    log_messages = []

    class MockLogger:
        def info(self, msg):
            log_messages.append(('INFO', msg))

        def warning(self, msg):
            log_messages.append(('WARNING', msg))

        def error(self, msg):
            log_messages.append(('ERROR', msg))

    return MockLogger(), log_messages


def assert_valid_json_file(filepath):
    """Assert a file exists and contains valid JSON.

    Args:
        filepath: Path to the JSON file to validate.

    Returns:
        dict: Parsed JSON data from the file.

    Raises:
        AssertionError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    assert os.path.exists(filepath), f"File {filepath} does not exist"
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data


def assert_batch_file_structure(filepath):
    """Validate batch file has the correct structure.

    Verifies that the file contains valid JSON with all required
    batch metadata fields.

    Args:
        filepath: Path to the batch JSON file to validate.

    Returns:
        dict: Parsed batch data from the file.

    Raises:
        AssertionError: If required fields are missing or malformed.
    """
    data = assert_valid_json_file(filepath)
    assert "data_source_id" in data
    assert "batch_number" in data
    assert "record_count" in data
    assert "timestamp" in data
    assert "pages" in data
    assert isinstance(data["pages"], list)
    return data
