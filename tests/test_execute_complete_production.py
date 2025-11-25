"""Tests for execute_complete_production.py."""

import importlib
import json
import sys
from unittest.mock import mock_open, patch

import execute_complete_production


def test_import_has_no_side_effects(monkeypatch):
    """Ensure importing the module does not execute the workflow."""

    monkeypatch.delitem(sys.modules, "execute_complete_production", raising=False)

    with patch("subprocess.run") as mock_run:
        imported = importlib.import_module("execute_complete_production")

    assert imported is not None
    mock_run.assert_not_called()


@patch("execute_complete_production.time.sleep")
@patch("execute_complete_production.os.path.exists", return_value=False)
@patch("execute_complete_production.os.listdir")
@patch("execute_complete_production.subprocess.run")
def test_main_runs_retrieval_and_processes_batches(
    mock_run, mock_listdir, mock_exists, mock_sleep, capsys
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
    assert mock_sleep.call_count == 2

    captured = capsys.readouterr().out
    assert "Batch 1/2: batch_0001_notion.json" in captured
    assert "Batch 2/2: batch_0002_notion.json" in captured
    assert "Total records: 500" in captured


@patch("execute_complete_production.time.sleep")
@patch("execute_complete_production.os.listdir", return_value=[])
def test_main_uses_summary_file(mock_listdir, mock_sleep, capsys):
    """Ensure summary data is printed when available."""

    summary_data = {
        "results": {
            "tickers_processed": 6626,
            "records_saved": 33130,
            "batches_created": 67,
        },
        "execution": {"duration": "0:05:30"},
    }

    with patch("execute_complete_production.os.path.exists", return_value=True):
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


@patch("execute_complete_production.os.listdir", side_effect=FileNotFoundError())
@patch("execute_complete_production.subprocess.run")
def test_main_handles_missing_output_directory(mock_run, mock_listdir, capsys):
    """Gracefully handle missing output directory without raising."""

    mock_run.return_value.returncode = 0

    execute_complete_production.main()

    captured = capsys.readouterr().out
    assert "Found 0 batch files to upload" in captured
