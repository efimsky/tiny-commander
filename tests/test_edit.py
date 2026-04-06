"""Tests for F4 edit file with editor."""

import curses
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr, find_entry_index
from tnc.app import Action, App


class TestEditFileCalls(unittest.TestCase):
    """Test F4 edit file calls editor."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_edit_calls_editor_with_file(self, mock_run, _endwin, _curs_set, _has_colors):
        """F4 should call editor with the file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'nano'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.edit_current_file()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertIn('nano', args)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_edit_uses_env_editor_first(self, mock_run, _endwin, _curs_set, _has_colors):
        """EDITOR env should take precedence over config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir), \
                 mock.patch.dict(os.environ, {'EDITOR': 'vim'}):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'nano'  # Config says nano
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.edit_current_file()

                args = mock_run.call_args[0][0]
                self.assertIn('vim', args)  # But env wins

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_edit_handles_editor_with_arguments(self, mock_run, _endwin, _curs_set, _has_colors):
        """Editor with arguments like 'code --wait' should be parsed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'code --wait'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.edit_current_file()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertEqual(args[0], 'code')
                self.assertEqual(args[1], '--wait')
                self.assertIn('test.txt', args[2])

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_edit_textedit_maps_to_open_e(self, mock_run, _endwin, _curs_set, _has_colors):
        """TextEdit should be mapped to 'open -e' command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'TextEdit'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.edit_current_file()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertEqual(args[0], 'open')
                self.assertEqual(args[1], '-e')
                self.assertIn('test.txt', args[2])


class TestEditFileValidation(unittest.TestCase):
    """Test validation before editing."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_edit_directory_returns_error(self, _curs_set, _has_colors):
        """Cannot edit a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'nano'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'subdir')

                result = app.edit_current_file()

                self.assertFalse(result.success)
                self.assertIn('directory', result.error.lower())

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_edit_dotdot_returns_error(self, _curs_set, _has_colors):
        """Cannot edit '..' entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'nano'
                app.active_panel.cursor = 0  # Cursor on '..'

                result = app.edit_current_file()

                self.assertFalse(result.success)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_edit_no_editor_returns_error(self, _curs_set, _has_colors):
        """Should return error if no editor configured and user cancels setup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir), \
                 mock.patch.dict(os.environ, {}, clear=True), \
                 mock.patch('tnc.config.shutil.which', return_value=None):
                stdscr = create_mock_stdscr()
                # Use 'n' or Escape (27) to dismiss dialogs - 'q' is not a valid dialog key
                stdscr.getch.return_value = 27  # Escape to cancel dialogs
                app = App(stdscr)
                app.setup()
                app.config.editor = None
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                result = app.edit_current_file()

                self.assertFalse(result.success)
                self.assertIn('cancelled', result.error.lower())


class TestEditFileResult(unittest.TestCase):
    """Test edit file result handling."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_edit_returns_success_result(self, mock_run, _endwin, _curs_set, _has_colors):
        """Successful edit should return success result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                mock_run.return_value = mock.MagicMock(returncode=0)
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'nano'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                result = app.edit_current_file()

                self.assertTrue(result.success)


class TestEditRefreshesPanel(unittest.TestCase):
    """Test that panel is refreshed after edit."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_edit_refreshes_active_panel(self, mock_run, _endwin, _curs_set, _has_colors):
        """Panel should refresh after edit to show any changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'nano'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                with mock.patch.object(app.active_panel, 'refresh') as mock_refresh:
                    app.edit_current_file()
                    mock_refresh.assert_called_once()


class TestF4KeyBinding(unittest.TestCase):
    """Test F4 key triggers edit."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_f4_returns_edit_action(self, _curs_set, _has_colors):
        """F4 key should return EDIT action."""
        app = App(create_mock_stdscr())
        app.setup()

        action = app.handle_key(curses.KEY_F4)

        self.assertEqual(action, Action.EDIT)


class TestEditEditorNotFound(unittest.TestCase):
    """Test handling of missing editor."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run', side_effect=FileNotFoundError())
    def test_edit_editor_not_found_returns_error(self, _mock_run, _endwin, _curs_set, _has_colors):
        """Should return error if editor executable not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.editor = 'nonexistent_editor'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                result = app.edit_current_file()

                self.assertFalse(result.success)
                self.assertIn('not found', result.error.lower())


if __name__ == '__main__':
    unittest.main()
