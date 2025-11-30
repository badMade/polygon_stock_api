"""Tests for execute_complete_production.py."""

import importlib
import json
import os
import subprocess
import sys
from datetime import datetime
from unittest.mock import mock_open, patch, MagicMock

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
    mock_run, mock_listdir, mock_makedirs, mock_sleep, capsys
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
@patch("execute_complete_production.os.listdir", return_value=[])
def test_main_uses_summary_file(capsys):
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
@patch("execute_complete_production.os.path.exists", return_value=True)
@patch("execute_complete_production.subprocess.run")
def test_main_handles_missing_directory_during_listing(
    mock_run, capsys
):
    """Handle missing output directory during batch listing without raising."""

    mock_run.return_value.returncode = 0

    execute_complete_production.main()

    captured = capsys.readouterr().out
    assert "Output directory missing" in captured
    assert "Found 0 batch files to upload" in captured


class TestHelperFunctions:
    """Tests for individual helper functions in execute_complete_production."""

    def test_print_start_banner(self, capsys):
        """Test that start banner prints expected content."""
        start_time = datetime(2025, 11, 24, 5, 0, 0)

        execute_complete_production._print_start_banner(start_time)

        captured = capsys.readouterr().out
        assert "STARTING COMPLETE PRODUCTION RUN" in captured
        assert "6,626 TICKERS" in captured
        assert "2025-11-24" in captured

    def test_get_batch_files_filters_correctly(self, temp_dir):
        """Test that _get_batch_files only returns batch files."""
        # Create various files
        batch_files = ["batch_0001_notion.json", "batch_0002_notion.json"]
        other_files = ["checkpoint.json", "summary.json", "batch_incomplete.json"]

        for f in batch_files + other_files:
            with open(os.path.join(temp_dir, f), 'w') as file:
                file.write("{}")

        with patch.object(
            execute_complete_production, 'OUTPUT_DIRECTORY', temp_dir
        ):
            result = execute_complete_production._get_batch_files()

        assert len(result) == 2
        assert all(f.startswith("batch_") and f.endswith("_notion.json")
                   for f in result)

    def test_get_batch_files_empty_directory(self, temp_dir):
        """Test _get_batch_files with no batch files."""
        with patch.object(
            execute_complete_production, 'OUTPUT_DIRECTORY', temp_dir
        ):
            result = execute_complete_production._get_batch_files()

        assert result == []

    def test_process_batches_calculates_total_records(self, temp_dir):
        """Test that _process_batches sums records correctly."""
        # Create batch files with known record counts
        for i, count in enumerate([100, 200, 300], 1):
            filepath = os.path.join(temp_dir, f"batch_{i:04d}_notion.json")
            with open(filepath, 'w') as f:
                json.dump({"record_count": count}, f)

        batch_files = [f"batch_{i:04d}_notion.json" for i in range(1, 4)]

        with patch.object(
            execute_complete_production, 'OUTPUT_DIRECTORY', temp_dir
        ):
            with patch('execute_complete_production.time.sleep'):
                total = execute_complete_production._process_batches(batch_files)

        assert total == 600


class TestSubprocessHandling:
    """Tests for subprocess execution and error handling."""

    @patch("execute_complete_production.subprocess.run")
    def test_run_production_retrieval_success(self, mock_run, capsys):
        """Test successful subprocess execution."""
        mock_run.return_value.returncode = 0

        execute_complete_production._run_production_retrieval()

        captured = capsys.readouterr().out
        assert "Data retrieval completed successfully" in captured

    @patch("execute_complete_production.subprocess.run")
    def test_run_production_retrieval_called_process_error(
        self, mock_run, capsys
    ):
        """Test CalledProcessError handling."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["python", "script.py"]
        )

        execute_complete_production._run_production_retrieval()

        captured = capsys.readouterr().out
        assert "Data retrieval failed with return code: 1" in captured

    @patch("execute_complete_production.subprocess.run")
    def test_run_production_retrieval_os_error(self, mock_run, capsys):
        """Test OSError handling when script not found."""
        mock_run.side_effect = OSError("Script not found")

        execute_complete_production._run_production_retrieval()

        captured = capsys.readouterr().out
        assert "OS error during retrieval" in captured

    @patch("execute_complete_production.subprocess.run")
    def test_run_production_retrieval_keyboard_interrupt(
        self, mock_run, capsys
    ):
        """Test KeyboardInterrupt handling."""
        mock_run.side_effect = KeyboardInterrupt()

        execute_complete_production._run_production_retrieval()

        captured = capsys.readouterr().out
        assert "Process interrupted by user" in captured


class TestFinalReport:
    """Tests for final report generation."""

    def test_print_final_report_with_summary_file(self, temp_dir, capsys):
        """Test report when summary file exists."""
        summary_data = {
            "results": {
                "tickers_processed": 6626,
                "records_saved": 33130,
                "batches_created": 67,
            },
            "execution": {"duration": "0:05:30"},
        }

        summary_path = os.path.join(temp_dir, "production_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(summary_data, f)

        start_time = datetime.now()

        with patch.object(
            execute_complete_production, 'SUMMARY_FILE', summary_path
        ):
            execute_complete_production._print_final_report(start_time, 67, 33130)

        captured = capsys.readouterr().out
        assert "Tickers processed: 6,626" in captured
        assert "Records created: 33,130" in captured
        assert "Batch files: 67" in captured
        assert "Total duration: 0:05:30" in captured

    def test_print_final_report_without_summary_file(self, capsys):
        """Test report when summary file does not exist."""
        start_time = datetime.now()

        with patch.object(
            execute_complete_production, 'SUMMARY_FILE', '/nonexistent/path.json'
        ):
            execute_complete_production._print_final_report(start_time, 10, 5000)

        captured = capsys.readouterr().out
        assert "Batch files created: 10" in captured
        assert "Total records: 5,000" in captured

    def test_print_final_report_with_corrupted_summary(self, temp_dir, capsys):
        """Test report handling corrupted summary file."""
        summary_path = os.path.join(temp_dir, "production_summary.json")
        with open(summary_path, 'w') as f:
            f.write("{invalid json")

        start_time = datetime.now()

        with patch.object(
            execute_complete_production, 'SUMMARY_FILE', summary_path
        ):
            execute_complete_production._print_final_report(start_time, 5, 2500)

        captured = capsys.readouterr().out
        assert "Error reading summary file" in captured
        assert "Batch files created: 5" in captured


class TestIntegration:
    """Integration tests for the complete pipeline."""

    @pytest.mark.integration
    @patch("execute_complete_production.time.sleep")
    @patch("execute_complete_production.subprocess.run")
    def test_full_pipeline_execution(
        self, mock_run, mock_sleep, temp_dir, capsys
    ):
        """Test complete pipeline from start to finish."""
        mock_run.return_value.returncode = 0

        # Create batch files
        for i in range(1, 4):
            filepath = os.path.join(temp_dir, f"batch_{i:04d}_notion.json")
            with open(filepath, 'w') as f:
                json.dump({"record_count": 500}, f)

        with patch.object(
            execute_complete_production, 'OUTPUT_DIRECTORY', temp_dir
        ):
            with patch.object(
                execute_complete_production, 'SUMMARY_FILE',
                os.path.join(temp_dir, "summary.json")
            ):
                execute_complete_production.main()

        captured = capsys.readouterr().out
        assert "STARTING COMPLETE PRODUCTION RUN" in captured
        assert "PHASE 1: Data Retrieval" in captured
        assert "PHASE 2: Upload to Notion" in captured
        assert "FINAL REPORT" in captured
        assert "PRODUCTION RUN COMPLETE" in captured

    @pytest.mark.integration
    def test_pipeline_with_output_directory_creation_failure(self, capsys):
        """Test pipeline handles directory creation failure."""
        with patch(
            "execute_complete_production.os.makedirs",
            side_effect=OSError("Permission denied")
        ):
            execute_complete_production.main()

        captured = capsys.readouterr().out
        assert "Unable to create output directory" in captured
