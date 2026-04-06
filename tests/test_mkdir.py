"""Tests for F7 mkdir operation."""

import curses
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.file_ops import mkdir, MkdirResult


class TestMkdirBasic(unittest.TestCase):
    """Test basic mkdir operations."""

    def test_mkdir_creates_directory(self):
        """mkdir should create a new directory."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, 'newdir')

            self.assertTrue(result.success)
            self.assertTrue(Path(parent_dir, 'newdir').is_dir())

    def test_mkdir_with_spaces_works(self):
        """mkdir should handle names with spaces."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, 'my folder')

            self.assertTrue(result.success)
            self.assertTrue(Path(parent_dir, 'my folder').is_dir())

    def test_mkdir_unicode_name(self):
        """mkdir should handle unicode names."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, 'папка')

            self.assertTrue(result.success)
            self.assertTrue(Path(parent_dir, 'папка').is_dir())


class TestMkdirValidation(unittest.TestCase):
    """Test mkdir input validation."""

    def test_mkdir_empty_name_rejected(self):
        """Empty directory name should be rejected."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, '')

            self.assertFalse(result.success)
            self.assertIn('name', result.error.lower())

    def test_mkdir_whitespace_only_rejected(self):
        """Whitespace-only name should be rejected."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, '   ')

            self.assertFalse(result.success)

    def test_mkdir_existing_name_fails(self):
        """Creating directory with existing name should fail."""
        with tempfile.TemporaryDirectory() as parent_dir:
            Path(parent_dir, 'existing').mkdir()

            result = mkdir(parent_dir, 'existing')

            self.assertFalse(result.success)
            self.assertIn('exists', result.error.lower())

    def test_mkdir_invalid_characters_rejected(self):
        """Names with path separators should be rejected."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, 'invalid/name')

            self.assertFalse(result.success)

    def test_mkdir_dot_rejected(self):
        """'.' as directory name should be rejected."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, '.')

            self.assertFalse(result.success)
            self.assertIn('invalid', result.error.lower())

    def test_mkdir_dotdot_rejected(self):
        """'..' as directory name should be rejected."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, '..')

            self.assertFalse(result.success)
            self.assertIn('invalid', result.error.lower())

    def test_mkdir_null_byte_rejected(self):
        """Names with null bytes should be rejected."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = mkdir(parent_dir, 'bad\0name')

            self.assertFalse(result.success)
            self.assertIn('invalid', result.error.lower())


class TestMkdirErrorHandling(unittest.TestCase):
    """Test mkdir error handling."""

    def test_mkdir_permission_denied(self):
        """mkdir in read-only directory should fail gracefully."""
        with tempfile.TemporaryDirectory() as parent_dir:
            os.chmod(parent_dir, 0o555)

            try:
                result = mkdir(parent_dir, 'newdir')
                self.assertFalse(result.success)
                self.assertIn('permission', result.error.lower())
            finally:
                os.chmod(parent_dir, 0o755)


class TestMkdirResult(unittest.TestCase):
    """Test MkdirResult dataclass."""

    def test_mkdir_result_success(self):
        """MkdirResult should track success state."""
        result = MkdirResult(success=True, created_name='newdir')
        self.assertTrue(result.success)
        self.assertEqual(result.created_name, 'newdir')

    def test_mkdir_result_failure(self):
        """MkdirResult should track error message."""
        result = MkdirResult(success=False, error='Test error')
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Test error')


class TestF7KeyBinding(unittest.TestCase):
    """Test F7 key triggers mkdir."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_f7_returns_mkdir_action(self, _mock_curs_set, _mock_has_colors):
        """F7 should return MKDIR action."""
        from tnc.app import App, Action

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        result = app.handle_key(curses.KEY_F7)
        self.assertEqual(result, Action.MKDIR)


class TestPanelMkdir(unittest.TestCase):
    """Test mkdir through Panel."""

    def test_panel_create_directory(self):
        """Panel.create_directory should create dir and refresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from tnc.panel import Panel

            panel = Panel(tmpdir, width=40, height=20)
            result = panel.create_directory('newdir')

            self.assertTrue(result.success)
            self.assertTrue(Path(tmpdir, 'newdir').is_dir())
            # Panel should have refreshed
            names = [e.name for e in panel.entries]
            self.assertIn('newdir', names)

    def test_panel_cursor_moves_to_new_directory(self):
        """Cursor should move to newly created directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from tnc.panel import Panel

            panel = Panel(tmpdir, width=40, height=20)
            panel.create_directory('newdir')

            current_entry = panel.entries[panel.cursor]
            self.assertEqual(current_entry.name, 'newdir')


class TestMkdirErrorDisplay(unittest.TestCase):
    """Test error display during mkdir operations."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('tnc.app.input_dialog', return_value='newdir')
    @mock.patch('tnc.app.show_error_dialog')
    def test_mkdir_with_permission_error_shows_dialog(
        self, mock_error_dialog, _mock_input, _mock_curs_set, _mock_has_colors
    ):
        """Mkdir operation should show error dialog when permission denied."""
        from tnc.app import App
        from tnc.file_ops import MkdirResult

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_stdscr = mock.MagicMock()
            mock_stdscr.getmaxyx.return_value = (24, 80)

            app = App(mock_stdscr)
            app.setup()

            app.active_panel.change_directory(Path(tmpdir))

            # Mock create_directory to return an error
            with mock.patch.object(app.active_panel, 'create_directory') as mock_mkdir:
                mock_mkdir.return_value = MkdirResult(
                    success=False,
                    error='Permission denied'
                )

                app._prompt_mkdir()

            # Verify show_error_dialog was called
            mock_error_dialog.assert_called_once()
            call_args = mock_error_dialog.call_args[0]
            self.assertIn('Permission denied', call_args[2])  # message


if __name__ == '__main__':
    unittest.main()
