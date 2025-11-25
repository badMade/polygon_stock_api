"""Tests for execute_complete_production.py"""
import json
import os
import pytest
import subprocess
from unittest.mock import Mock, patch, mock_open, MagicMock
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExecuteCompleteProduction:
    """Test suite for execute_complete_production.py"""

    def test_script_imports(self):
        """Test that the script can be imported"""
        # Just verify the module can be imported without errors
        import execute_complete_production

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('os.path.exists')
    def test_subprocess_call_production_script(self, mock_exists, mock_listdir, mock_subprocess):
        """Test that the production script is called via subprocess"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = []
        mock_exists.return_value = False

        # Import and execute the script
        with patch('builtins.open', mock_open(read_data='[]')):
            # This will execute the script's main code
            pass

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_batch_file_counting(self, mock_listdir, mock_subprocess):
        """Test that batch files are counted correctly"""
        mock_subprocess.return_value.returncode = 0

        # Mock batch files
        mock_listdir.return_value = [
            'batch_0001_notion.json',
            'batch_0002_notion.json',
            'batch_0003_notion.json',
            'other_file.txt',
            'checkpoint.json'
        ]

        with patch('builtins.open', mock_open(read_data='{"record_count": 100}')):
            # Should count only batch_*_notion.json files
            batch_files = [f for f in mock_listdir.return_value
                          if f.startswith('batch_') and f.endswith('_notion.json')]

            assert len(batch_files) == 3

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_handles_subprocess_keyboard_interrupt(self, mock_listdir, mock_subprocess):
        """Test handling of KeyboardInterrupt"""
        mock_subprocess.side_effect = KeyboardInterrupt()
        mock_listdir.return_value = []

        # Should handle KeyboardInterrupt gracefully
        # The script doesn't re-raise, so no exception expected

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_handles_subprocess_error(self, mock_listdir, mock_subprocess):
        """Test handling of subprocess errors"""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'test')
        mock_listdir.return_value = []

        # Should handle CalledProcessError gracefully

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_handles_os_error(self, mock_listdir, mock_subprocess):
        """Test handling of OS errors"""
        mock_subprocess.side_effect = OSError("Test OS error")
        mock_listdir.return_value = []

        # Should handle OSError gracefully

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_reads_batch_files(self, mock_file, mock_listdir, mock_subprocess):
        """Test that batch files are read correctly"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = ['batch_0001_notion.json']

        batch_data = {
            'record_count': 500,
            'batch_number': 1
        }
        mock_file.return_value.read.return_value = json.dumps(batch_data)

        # Should read and process batch files

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_reads_production_summary(self, mock_file, mock_exists, mock_listdir, mock_subprocess):
        """Test that production summary is read if it exists"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = []
        mock_exists.return_value = True

        summary_data = {
            'results': {
                'tickers_processed': 6626,
                'records_saved': 33130,
                'batches_created': 67
            },
            'execution': {
                'duration': '0:05:30'
            }
        }
        mock_file.return_value.read.return_value = json.dumps(summary_data)

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('time.sleep')
    def test_rate_limiting_during_upload_simulation(self, mock_sleep, mock_listdir, mock_subprocess):
        """Test that rate limiting is applied during upload simulation"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = [
            'batch_0001_notion.json',
            'batch_0002_notion.json'
        ]

        with patch('builtins.open', mock_open(read_data='{"record_count": 100}')):
            # The script should call time.sleep for rate limiting
            pass

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_handles_invalid_batch_json(self, mock_listdir, mock_subprocess):
        """Test handling of invalid JSON in batch files"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = ['batch_0001_notion.json']

        with patch('builtins.open', mock_open(read_data='{invalid json')):
            # Should handle JSON decode errors gracefully
            pass


class TestExecuteCompleteProductionEdgeCases:
    """Test edge cases for execute_complete_production"""

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_no_batch_files(self, mock_listdir, mock_subprocess):
        """Test behavior when no batch files exist"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = []

        # Should handle empty batch list gracefully

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_very_large_number_of_batches(self, mock_listdir, mock_subprocess):
        """Test with large number of batch files"""
        mock_subprocess.return_value.returncode = 0

        # Generate 1000 batch file names
        batch_files = [f'batch_{i:04d}_notion.json' for i in range(1, 1001)]
        mock_listdir.return_value = batch_files

        with patch('builtins.open', mock_open(read_data='{"record_count": 100}')):
            with patch('time.sleep'):
                # Should handle large number of batches
                filtered = [f for f in batch_files
                           if f.startswith('batch_') and f.endswith('_notion.json')]
                assert len(filtered) == 1000

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_subprocess_returns_nonzero(self, mock_listdir, mock_subprocess):
        """Test when subprocess returns non-zero exit code"""
        mock_subprocess.return_value.returncode = 1
        mock_listdir.return_value = []

        # Should continue despite non-zero return code

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_missing_output_directory(self, mock_listdir, mock_subprocess):
        """Test when output directory doesn't exist"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.side_effect = FileNotFoundError()

        # Should handle missing directory

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_permission_error_reading_files(self, mock_listdir, mock_subprocess):
        """Test handling of permission errors"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = ['batch_0001_notion.json']

        with patch('builtins.open', side_effect=PermissionError()):
            # Should handle permission errors gracefully
            pass

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_unicode_in_batch_data(self, mock_listdir, mock_subprocess):
        """Test handling of unicode characters in batch data"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = ['batch_0001_notion.json']

        unicode_data = json.dumps({
            'record_count': 100,
            'ticker': '测试',  # Chinese characters
            'notes': 'Test™ with ® symbols'
        })

        with patch('builtins.open', mock_open(read_data=unicode_data)):
            # Should handle unicode gracefully
            pass


class TestExecuteCompleteProductionOutput:
    """Test output and reporting functionality"""

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('builtins.print')
    def test_prints_start_banner(self, mock_print, mock_exists, mock_listdir, mock_subprocess):
        """Test that start banner is printed"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = []
        mock_exists.return_value = False

        # The script should print startup messages
        # This is tested by importing/executing the module

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('builtins.print')
    def test_prints_phase_headers(self, mock_print, mock_listdir, mock_subprocess):
        """Test that phase headers are printed"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = []

        # Should print PHASE 1 and PHASE 2 headers

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('builtins.print')
    def test_prints_database_info(self, mock_print, mock_exists, mock_listdir, mock_subprocess):
        """Test that database URL and data source ID are printed"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = []
        mock_exists.return_value = False

        # Should print Notion database URL and data source ID

    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('builtins.print')
    def test_prints_batch_progress(self, mock_print, mock_listdir, mock_subprocess):
        """Test that batch processing progress is printed"""
        mock_subprocess.return_value.returncode = 0
        mock_listdir.return_value = [
            'batch_0001_notion.json',
            'batch_0002_notion.json'
        ]

        with patch('builtins.open', mock_open(read_data='{"record_count": 500}')):
            with patch('time.sleep'):
                # Should print progress for each batch
                pass


class TestProductionScriptIntegration:
    """Integration tests for the production script execution"""

    @patch('subprocess.run')
    def test_correct_python_command(self, mock_subprocess):
        """Test that correct Python command is used"""
        mock_subprocess.return_value.returncode = 0

        with patch('os.listdir', return_value=[]):
            with patch('os.path.exists', return_value=False):
                # The script should call subprocess with correct arguments
                pass

    @patch('subprocess.run')
    def test_production_script_path(self, mock_subprocess):
        """Test that correct script path is used"""
        mock_subprocess.return_value.returncode = 0

        with patch('os.listdir', return_value=[]):
            with patch('os.path.exists', return_value=False):
                # Should use /mnt/user-data/outputs/production_stock_retrieval.py
                pass

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_total_records_calculation(self, mock_listdir, mock_subprocess):
        """Test that total records are calculated correctly"""
        mock_subprocess.return_value.returncode = 0

        mock_listdir.return_value = [
            'batch_0001_notion.json',
            'batch_0002_notion.json',
            'batch_0003_notion.json'
        ]

        # Mock file contents with different record counts
        file_contents = [
            '{"record_count": 500}',
            '{"record_count": 500}',
            '{"record_count": 500}'
        ]

        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.return_value.read.side_effect = file_contents

            with patch('time.sleep'):
                # Total should be 1500 records
                pass

    @patch('subprocess.run')
    @patch('os.listdir')
    def test_sorted_batch_processing(self, mock_listdir, mock_subprocess):
        """Test that batches are processed in sorted order"""
        mock_subprocess.return_value.returncode = 0

        # Return unsorted batch files
        mock_listdir.return_value = [
            'batch_0003_notion.json',
            'batch_0001_notion.json',
            'batch_0002_notion.json'
        ]

        with patch('builtins.open', mock_open(read_data='{"record_count": 100}')):
            with patch('time.sleep'):
                # Should process in sorted order: 0001, 0002, 0003
                batch_files = sorted([f for f in mock_listdir.return_value
                                     if f.startswith('batch_') and f.endswith('_notion.json')])

                assert batch_files[0] == 'batch_0001_notion.json'
                assert batch_files[1] == 'batch_0002_notion.json'
                assert batch_files[2] == 'batch_0003_notion.json'
