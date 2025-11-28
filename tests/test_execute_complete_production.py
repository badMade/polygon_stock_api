"""Tests for execute_complete_production.py."""

import importlib
import json
import sys
from unittest.mock import mock_open, patch

import pytest

import execute_complete_production


def test_import_has_no_side_effects(monkeypatch):
    """Ensure importing the module does not execute the workflow."""

    monkeypatch.delitem(
        sys.modules, "execute_complete_production", raising=False
        )

    with patch("subprocess.run") as mock_run:
        imported = importlib.import_module("execute_complete_production")

    assert hasattr(imported, "main")
    mock_run.assert_not_called()


@patch("execute_complete_production.time.sleep")
@patch("execute_complete_production.os.makedirs")
@patch("execute_complete_production.os.path.exists", return_value=False)
@patch("execute_complete_production.os.listdir")
@patch("execute_complete_production.subprocess.run")
def test_main_runs_retrieval_and_processes_batches(
    mock_run, mock_listdir, mock_exists, mock_makedirs, mock_sleep, capsys
):
    """Verify main executes retrieval and processes batches in order."""

    mock_run.return_value.returncode = 0
    mock_listdir.return_value = [
        "batch_0002_notion.json",
        "batch_0001_notion.json",
    ]

    batch_payloads = ["{\"record_count\": 300}", "{\"record_count\": 200}"]
    mocked_open = mock_open()
    mocked_open.return_value.read.side_effect = batch_payloads

    with patch("execute_complete_production.open", mocked_open):
        execute_complete_production.main()

    mock_run.assert_called_once_with(
        ["python", execute_complete_production.PRODUCTION_SCRIPT_PATH],
        capture_output=False,
        text=True,
        check=True,
    )
    mock_makedirs.assert_called_once_with(
        execute_complete_production.OUTPUT_DIRECTORY, exist_ok=True
    )
    assert mock_sleep.call_count == 2

    captured = capsys.readouterr().out
    assert "Batch 1/2: batch_0001_notion.json" in captured
    assert "Batch 2/2: batch_0002_notion.json" in captured
    assert "Total records: 500" in captured


@patch("execute_complete_production.time.sleep")
@patch("execute_complete_production.os.makedirs")
@patch("execute_complete_production.os.listdir", return_value=[])
def test_main_uses_summary_file(mock_listdir, mock_makedirs, mock_sleep, capsys):
    """Ensure summary data is printed when available."""

    summary_data = {
        "results": {
            "tickers_processed": 6626,
            "records_saved": 33130,
            "batches_created": 67,
        },
        "execution": {"duration": "0:05:30"},
    }

    with patch(
        "execute_complete_production.os.path.exists", side_effect=[True, True]
    ):
        with patch(
            "execute_complete_production.open",
            mock_open(read_data=json.dumps(summary_data)),
        ):
            execute_complete_production.main()

    captured = capsys.readouterr().out
    assert "Tickers processed: 6,626" in captured
    assert "Records created: 33,130" in captured
    assert "Batch files: 67" in captured
    assert "Total duration: 0:05:30" in captured


@patch(
    "execute_complete_production.os.listdir", side_effect=FileNotFoundError()
    )
@patch("execute_complete_production.os.makedirs")
@patch("execute_complete_production.os.path.exists", return_value=True)
@patch("execute_complete_production.subprocess.run")
def test_main_handles_missing_directory_during_listing(
    mock_run, mock_exists, mock_makedirs, mock_listdir, capsys
):
    """Handle missing output directory during batch listing without raising."""

    mock_run.return_value.returncode = 0

    execute_complete_production.main()

    captured = capsys.readouterr().out
    assert "Output directory missing" in captured
    assert "Found 0 batch files to upload" in captured


@patch("execute_complete_production.time.sleep")
def test_process_batches_sums_records_and_sorts_files(mock_sleep, tmp_path):
    """_process_batches returns the total record count in sorted order."""

    batch_data = {
        "batch_0002_notion.json": {"record_count": 300},
        "batch_0001_notion.json": {"record_count": 200},
    }
    batch_files = list(batch_data.keys())

    output_dir = tmp_path
    for filename, payload in batch_data.items():
        (output_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    with patch("execute_complete_production.OUTPUT_DIRECTORY", str(output_dir)):
        total_records = execute_complete_production._process_batches(batch_files)

    assert total_records == 500
    mock_sleep.assert_called()


@patch("execute_complete_production.time.sleep")
def test_process_batches_handles_missing_file(mock_sleep, tmp_path, capsys):
    """_process_batches logs an error and continues when a file is missing."""

    missing_file = "batch_9999_notion.json"

    with patch("execute_complete_production.OUTPUT_DIRECTORY", str(tmp_path)):
        total_records = execute_complete_production._process_batches([missing_file])

    assert total_records == 0
    captured = capsys.readouterr().out
    assert "Error processing" in captured
    assert missing_file in captured
    mock_sleep.assert_not_called()


@patch("execute_complete_production.time.sleep")
def test_process_batches_skips_invalid_json_and_continues(
    mock_sleep, tmp_path, capsys
):
    """Invalid JSON files are skipped while valid files still count."""

    invalid_file = tmp_path / "batch_0001_notion.json"
    valid_file = tmp_path / "batch_0002_notion.json"
    invalid_file.write_text("{invalid_json}", encoding="utf-8")
    valid_file.write_text(json.dumps({"record_count": 150}), encoding="utf-8")

    with patch("execute_complete_production.OUTPUT_DIRECTORY", str(tmp_path)):
        total_records = execute_complete_production._process_batches(
            [invalid_file.name, valid_file.name]
        )

    assert total_records == 150
    captured = capsys.readouterr().out
    assert "Error processing" in captured
    assert "Batch 2/2" in captured


@patch("execute_complete_production.time.sleep")
def test_process_batches_empty_list_returns_zero(mock_sleep, capsys):
    """No batch files results in zero total records and informative output."""

    total_records = execute_complete_production._process_batches([])

    assert total_records == 0
    captured = capsys.readouterr().out
    assert "Found 0 batch files to upload" in captured
    mock_sleep.assert_not_called()
