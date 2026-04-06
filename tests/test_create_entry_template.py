"""Tests for Panel._do_create_entry template method."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.file_ops import CreateFileResult, MkdirResult
from tnc.panel import Panel


class TestDoCreateEntry(unittest.TestCase):
    """Test Panel._do_create_entry template method."""

    def test_do_create_entry_calls_create_func(self):
        """_do_create_entry should call the provided create function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_func = mock.MagicMock(return_value=MkdirResult(success=True, created_name='test'))

            panel._do_create_entry('test', mock_func)

            mock_func.assert_called_once_with(panel.path, 'test')

    def test_do_create_entry_refreshes_on_success(self):
        """_do_create_entry should refresh panel on success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            panel.refresh = mock.MagicMock()
            mock_func = mock.MagicMock(return_value=MkdirResult(success=True, created_name='test'))

            panel._do_create_entry('test', mock_func)

            panel.refresh.assert_called_once()

    def test_do_create_entry_no_refresh_on_failure(self):
        """_do_create_entry should not refresh panel on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            panel.refresh = mock.MagicMock()
            mock_func = mock.MagicMock(return_value=MkdirResult(success=False, error='error'))

            panel._do_create_entry('test', mock_func)

            panel.refresh.assert_not_called()

    def test_do_create_entry_moves_cursor_to_new_entry(self):
        """_do_create_entry should move cursor to newly created entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            # Create a real directory to test cursor positioning
            Path(tmpdir, 'newdir').mkdir()

            mock_func = mock.MagicMock(return_value=MkdirResult(success=True, created_name='newdir'))
            panel._do_create_entry('newdir', mock_func)

            # Cursor should be on the new entry
            current_entry = panel.entries[panel.cursor]
            self.assertEqual(current_entry.name, 'newdir')

    def test_do_create_entry_returns_result(self):
        """_do_create_entry should return the result from create function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            expected_result = MkdirResult(success=True, created_name='test')
            mock_func = mock.MagicMock(return_value=expected_result)

            result = panel._do_create_entry('test', mock_func)

            self.assertEqual(result, expected_result)


class TestCreateDirectoryUsesTemplate(unittest.TestCase):
    """Test that create_directory uses the template."""

    def test_create_directory_creates_directory(self):
        """create_directory should create directory and move cursor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)

            result = panel.create_directory('newdir')

            self.assertTrue(result.success)
            self.assertTrue((Path(tmpdir) / 'newdir').is_dir())
            # Cursor should be on new directory
            current_entry = panel.entries[panel.cursor]
            self.assertEqual(current_entry.name, 'newdir')


class TestCreateFileUsesTemplate(unittest.TestCase):
    """Test that create_file uses the template."""

    def test_create_file_creates_file(self):
        """create_file should create file and move cursor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)

            result = panel.create_file('newfile.txt')

            self.assertTrue(result.success)
            self.assertTrue((Path(tmpdir) / 'newfile.txt').is_file())
            # Cursor should be on new file
            current_entry = panel.entries[panel.cursor]
            self.assertEqual(current_entry.name, 'newfile.txt')


if __name__ == '__main__':
    unittest.main()
