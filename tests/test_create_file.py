"""Tests for file creation functionality."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.file_ops import CreateFileResult, create_file


class TestCreateFile(unittest.TestCase):
    """Tests for create_file function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_create_simple_file(self) -> None:
        """Test creating a simple file."""
        result = create_file(self.test_path, 'test.txt')

        self.assertTrue(result.success)
        self.assertEqual(result.created_name, 'test.txt')
        self.assertTrue((self.test_path / 'test.txt').exists())
        self.assertTrue((self.test_path / 'test.txt').is_file())

    def test_create_file_empty(self) -> None:
        """Test that created file is empty."""
        create_file(self.test_path, 'empty.txt')

        file_path = self.test_path / 'empty.txt'
        self.assertEqual(file_path.stat().st_size, 0)

    def test_create_file_with_extension(self) -> None:
        """Test creating file with various extensions."""
        for ext in ['.py', '.md', '.json', '.yaml']:
            result = create_file(self.test_path, f'file{ext}')
            self.assertTrue(result.success)
            self.assertTrue((self.test_path / f'file{ext}').exists())

    def test_create_file_no_extension(self) -> None:
        """Test creating file without extension."""
        result = create_file(self.test_path, 'Makefile')

        self.assertTrue(result.success)
        self.assertTrue((self.test_path / 'Makefile').exists())

    def test_reject_empty_name(self) -> None:
        """Test that empty name is rejected."""
        result = create_file(self.test_path, '')

        self.assertFalse(result.success)
        self.assertIn('empty', result.error.lower())

    def test_reject_whitespace_only_name(self) -> None:
        """Test that whitespace-only name is rejected."""
        result = create_file(self.test_path, '   ')

        self.assertFalse(result.success)
        self.assertIn('empty', result.error.lower())

    def test_reject_path_separator(self) -> None:
        """Test that name with path separator is rejected."""
        result = create_file(self.test_path, 'sub/file.txt')

        self.assertFalse(result.success)
        self.assertIn('separator', result.error.lower())

    def test_reject_existing_file(self) -> None:
        """Test that creating file that already exists fails."""
        # Create file first
        existing = self.test_path / 'existing.txt'
        existing.touch()

        result = create_file(self.test_path, 'existing.txt')

        self.assertFalse(result.success)
        self.assertIn('exists', result.error.lower())

    def test_reject_broken_symlink(self) -> None:
        """Test that creating file where broken symlink exists fails."""
        import os
        # Create a symlink pointing to non-existent target
        broken_link = self.test_path / 'broken_link.txt'
        os.symlink('/nonexistent/target', broken_link)

        # Verify it's a broken symlink
        self.assertTrue(broken_link.is_symlink())
        self.assertFalse(broken_link.exists())  # exists() returns False for broken symlinks

        result = create_file(self.test_path, 'broken_link.txt')

        self.assertFalse(result.success)
        self.assertIn('exists', result.error.lower())

    def test_reject_dot(self) -> None:
        """Test that '.' is rejected."""
        result = create_file(self.test_path, '.')

        self.assertFalse(result.success)

    def test_reject_dotdot(self) -> None:
        """Test that '..' is rejected."""
        result = create_file(self.test_path, '..')

        self.assertFalse(result.success)

    def test_reject_null_byte(self) -> None:
        """Test that name with null byte is rejected."""
        result = create_file(self.test_path, 'file\x00name')

        self.assertFalse(result.success)

    def test_create_hidden_file(self) -> None:
        """Test creating a hidden file (starts with dot)."""
        result = create_file(self.test_path, '.hidden')

        self.assertTrue(result.success)
        self.assertTrue((self.test_path / '.hidden').exists())

    def test_create_file_unicode_name(self) -> None:
        """Test creating file with unicode characters."""
        result = create_file(self.test_path, 'fichier.txt')

        self.assertTrue(result.success)
        self.assertTrue((self.test_path / 'fichier.txt').exists())

    def test_permission_denied(self) -> None:
        """Test handling of permission denied."""
        # Create a directory with no write permission
        no_write_dir = self.test_path / 'no_write'
        no_write_dir.mkdir()
        no_write_dir.chmod(0o444)

        try:
            result = create_file(no_write_dir, 'test.txt')
            self.assertFalse(result.success)
            self.assertIn('permission', result.error.lower())
        finally:
            no_write_dir.chmod(0o755)


class TestCreateFileResult(unittest.TestCase):
    """Tests for CreateFileResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result attributes."""
        result = CreateFileResult(success=True, created_name='test.txt')

        self.assertTrue(result.success)
        self.assertEqual(result.created_name, 'test.txt')
        self.assertEqual(result.error, '')

    def test_error_result(self) -> None:
        """Test error result attributes."""
        result = CreateFileResult(success=False, error='File exists')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'File exists')
        self.assertEqual(result.created_name, '')


class TestCreateFileErrorDisplay(unittest.TestCase):
    """Test error display during create file operations."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('tnc.app.input_dialog', return_value='newfile.txt')
    @mock.patch('tnc.app.show_error_dialog')
    def test_create_file_with_permission_error_shows_dialog(
        self, mock_error_dialog, _mock_input, _mock_curs_set, _mock_has_colors
    ):
        """Create file operation should show error dialog when permission denied."""
        from tnc.app import App

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_stdscr = mock.MagicMock()
            mock_stdscr.getmaxyx.return_value = (24, 80)

            app = App(mock_stdscr)
            app.setup()

            app.active_panel.change_directory(Path(tmpdir))

            # Mock create_file to return an error
            with mock.patch.object(app.active_panel, 'create_file') as mock_create:
                mock_create.return_value = CreateFileResult(
                    success=False,
                    error='Permission denied'
                )

                app._prompt_create_file()

            # Verify show_error_dialog was called
            mock_error_dialog.assert_called_once()
            call_args = mock_error_dialog.call_args[0]
            self.assertIn('Permission denied', call_args[2])  # message


if __name__ == '__main__':
    unittest.main()
