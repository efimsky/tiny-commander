"""Tests for F3 view file with pager."""

import curses
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr, find_entry_index
from tnc.app import Action, App


class TestViewFilePager(unittest.TestCase):
    """Test F3 view file calls pager."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_view_calls_pager_with_file(self, mock_run, _endwin, _curs_set, _has_colors):
        """F3 should call pager with the file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.pager = 'less'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.view_current_file()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertIn('less', args)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_view_uses_env_pager_first(self, mock_run, _endwin, _curs_set, _has_colors):
        """PAGER env should take precedence over config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir), \
                 mock.patch.dict(os.environ, {'PAGER': 'more'}):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.pager = 'less'  # Config says less
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.view_current_file()

                args = mock_run.call_args[0][0]
                self.assertIn('more', args)  # But env wins

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_view_handles_pager_with_arguments(self, mock_run, _endwin, _curs_set, _has_colors):
        """Pager with arguments like 'less -R' should be parsed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.pager = 'less -R'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.view_current_file()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertEqual(args[0], 'less')
                self.assertEqual(args[1], '-R')
                self.assertIn('test.txt', args[2])


class TestViewFileValidation(unittest.TestCase):
    """Test validation before viewing."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_view_directory_returns_error(self, _curs_set, _has_colors):
        """Cannot view a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.pager = 'less'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'subdir')

                result = app.view_current_file()

                self.assertFalse(result.success)
                self.assertIn('directory', result.error.lower())

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_view_dotdot_returns_error(self, _curs_set, _has_colors):
        """Cannot view '..' entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.pager = 'less'
                app.active_panel.cursor = 0  # Cursor on '..'

                result = app.view_current_file()

                self.assertFalse(result.success)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_view_no_pager_returns_error(self, _curs_set, _has_colors):
        """Should return error if no pager configured and user cancels setup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir), \
                 mock.patch.dict(os.environ, {}, clear=True), \
                 mock.patch('tnc.config.shutil.which', return_value=None):
                stdscr = create_mock_stdscr()
                # Use Escape (27) to cancel dialogs - 'q' is not a valid dialog key
                stdscr.getch.return_value = 27  # Escape to cancel dialogs
                app = App(stdscr)
                app.setup()
                app.config.pager = None
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                result = app.view_current_file()

                self.assertFalse(result.success)
                self.assertIn('cancelled', result.error.lower())


class TestViewFileResult(unittest.TestCase):
    """Test view file result handling."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    def test_view_returns_success_result(self, mock_run, _endwin, _curs_set, _has_colors):
        """Successful view should return success result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                mock_run.return_value = mock.MagicMock(returncode=0)
                app = App(create_mock_stdscr())
                app.setup()
                app.config.pager = 'less'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                result = app.view_current_file()

                self.assertTrue(result.success)


class TestF3KeyBinding(unittest.TestCase):
    """Test F3 key triggers view."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_f3_returns_view_action(self, _curs_set, _has_colors):
        """F3 key should return VIEW action."""
        app = App(create_mock_stdscr())
        app.setup()

        action = app.handle_key(curses.KEY_F3)

        self.assertEqual(action, Action.VIEW)


class TestViewPagerNotFound(unittest.TestCase):
    """Test handling of missing pager."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run', side_effect=FileNotFoundError())
    def test_view_pager_not_found_returns_error(self, _mock_run, _endwin, _curs_set, _has_colors):
        """Should return error if pager executable not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.config.pager = 'nonexistent_pager'
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                result = app.view_current_file()

                self.assertFalse(result.success)
                self.assertIn('not found', result.error.lower())


if __name__ == '__main__':
    unittest.main()
