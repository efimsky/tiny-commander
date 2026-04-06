"""Tests for file execution functionality (Issue #133)."""

import curses
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr

from tnc.app import App


class TestIsExecutable(unittest.TestCase):
    """Test the _is_executable helper method."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_executable_file_returns_true(self, _mask, _curs, _colors):
        """Executable file should return True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exec_file = Path(tmpdir) / 'script.sh'
            exec_file.write_text('#!/bin/sh\necho hello')
            exec_file.chmod(exec_file.stat().st_mode | stat.S_IXUSR)

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            self.assertTrue(app._is_executable(exec_file))

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_non_executable_file_returns_false(self, _mask, _curs, _colors):
        """Non-executable file should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            regular_file = Path(tmpdir) / 'readme.txt'
            regular_file.write_text('hello')

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            self.assertFalse(app._is_executable(regular_file))

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_nonexistent_file_returns_false(self, _mask, _curs, _colors):
        """Nonexistent file should return False (not raise exception)."""
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        self.assertFalse(app._is_executable(Path('/nonexistent/file')))

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_directory_with_execute_bit_returns_true(self, _mask, _curs, _colors):
        """Directory with execute bit should return True (directories have +x)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            # Directories typically have execute bit for traversal
            self.assertTrue(app._is_executable(Path(tmpdir)))


class TestExecuteFile(unittest.TestCase):
    """Test the _execute_file method."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    @mock.patch('curses.endwin')
    @mock.patch('subprocess.run')
    @mock.patch('termios.tcgetattr')
    @mock.patch('termios.tcsetattr')
    @mock.patch('tty.setraw')
    @mock.patch('sys.stdin')
    @mock.patch('builtins.print')
    def test_execute_file_runs_subprocess(
        self, mock_print, mock_stdin, mock_setraw, mock_tcsetattr,
        mock_tcgetattr, mock_run, mock_endwin, _mask, _curs, _colors
    ):
        """Execute file should call subprocess.run with the file path."""
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = 'x'

        with tempfile.TemporaryDirectory() as tmpdir:
            exec_file = Path(tmpdir) / 'script.sh'
            exec_file.write_text('#!/bin/sh\necho hello')
            exec_file.chmod(exec_file.stat().st_mode | stat.S_IXUSR)

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()
            app._execute_file(exec_file)

            # Verify subprocess.run was called with correct arguments
            mock_run.assert_called_once_with(
                [str(exec_file)], cwd=str(exec_file.parent)
            )

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    @mock.patch('curses.endwin')
    @mock.patch('subprocess.run')
    @mock.patch('termios.tcgetattr')
    @mock.patch('termios.tcsetattr')
    @mock.patch('tty.setraw')
    @mock.patch('sys.stdin')
    @mock.patch('builtins.print')
    def test_execute_file_suspends_curses(
        self, mock_print, mock_stdin, mock_setraw, mock_tcsetattr,
        mock_tcgetattr, mock_run, mock_endwin, _mask, _curs, _colors
    ):
        """Execute file should call curses.endwin() before running."""
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = 'x'

        with tempfile.TemporaryDirectory() as tmpdir:
            exec_file = Path(tmpdir) / 'script.sh'
            exec_file.write_text('#!/bin/sh\necho hello')
            exec_file.chmod(exec_file.stat().st_mode | stat.S_IXUSR)

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()
            app._execute_file(exec_file)

            mock_endwin.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    @mock.patch('curses.endwin')
    @mock.patch('subprocess.run')
    @mock.patch('termios.tcgetattr')
    @mock.patch('termios.tcsetattr')
    @mock.patch('tty.setraw')
    @mock.patch('sys.stdin')
    @mock.patch('builtins.print')
    def test_execute_file_waits_for_keypress(
        self, mock_print, mock_stdin, mock_setraw, mock_tcsetattr,
        mock_tcgetattr, mock_run, mock_endwin, _mask, _curs, _colors
    ):
        """Execute file should wait for a keypress after execution."""
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = 'x'

        with tempfile.TemporaryDirectory() as tmpdir:
            exec_file = Path(tmpdir) / 'script.sh'
            exec_file.write_text('#!/bin/sh\necho hello')
            exec_file.chmod(exec_file.stat().st_mode | stat.S_IXUSR)

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()
            app._execute_file(exec_file)

            # Verify it reads a single character
            mock_stdin.read.assert_called_with(1)


class TestEnterKeyExecutesFile(unittest.TestCase):
    """Test that Enter key triggers file execution for executables."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_enter_on_executable_calls_execute_file(self, _mask, _curs, _colors):
        """Enter on executable file should trigger execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exec_file = Path(tmpdir) / 'script.sh'
            exec_file.write_text('#!/bin/sh\necho hello')
            exec_file.chmod(exec_file.stat().st_mode | stat.S_IXUSR)

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            # Navigate to temp directory
            app.active_panel.path = Path(tmpdir)
            app.active_panel.refresh()

            # Mock panel.enter() to return the executable file path
            with mock.patch.object(app.active_panel, 'enter', return_value=exec_file):
                with mock.patch.object(app, '_execute_file') as mock_exec:
                    app.handle_key(ord('\n'))
                    mock_exec.assert_called_once_with(exec_file)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_enter_on_non_executable_does_not_execute(self, _mask, _curs, _colors):
        """Enter on non-executable file should not trigger execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            regular_file = Path(tmpdir) / 'readme.txt'
            regular_file.write_text('hello')

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            # Mock panel.enter() to return the non-executable file path
            with mock.patch.object(app.active_panel, 'enter', return_value=regular_file):
                with mock.patch.object(app, '_execute_file') as mock_exec:
                    app.handle_key(ord('\n'))
                    mock_exec.assert_not_called()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_enter_on_directory_does_not_execute(self, _mask, _curs, _colors):
        """Enter on directory should not trigger execution (enter() returns None)."""
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Mock panel.enter() to return None (directory case)
        with mock.patch.object(app.active_panel, 'enter', return_value=None):
            with mock.patch.object(app, '_execute_file') as mock_exec:
                app.handle_key(ord('\n'))
                mock_exec.assert_not_called()


class TestDoubleClickExecutesFile(unittest.TestCase):
    """Test that double-click triggers file execution for executables."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_double_click_on_executable_calls_execute_file(self, mock_mousemask, _curs, _colors):
        """Double-click on executable file should trigger execution."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            exec_file = Path(tmpdir) / 'script.sh'
            exec_file.write_text('#!/bin/sh\necho hello')
            exec_file.chmod(exec_file.stat().st_mode | stat.S_IXUSR)

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            # Configure panel positions
            app.left_panel.render_x = 0
            app.left_panel.render_y = 0
            app.left_panel.render_width = 40
            app.left_panel.render_height = 21

            with mock.patch.object(app.left_panel, 'entry_at_point', return_value=1):
                with mock.patch.object(app.left_panel, 'enter', return_value=exec_file):
                    with mock.patch.object(app, '_execute_file') as mock_exec:
                        app.handle_mouse(10, 5, curses.BUTTON1_DOUBLE_CLICKED)
                        mock_exec.assert_called_once_with(exec_file)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_double_click_on_non_executable_does_not_execute(self, mock_mousemask, _curs, _colors):
        """Double-click on non-executable file should not trigger execution."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            regular_file = Path(tmpdir) / 'readme.txt'
            regular_file.write_text('hello')

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            # Configure panel positions
            app.left_panel.render_x = 0
            app.left_panel.render_y = 0
            app.left_panel.render_width = 40
            app.left_panel.render_height = 21

            with mock.patch.object(app.left_panel, 'entry_at_point', return_value=1):
                with mock.patch.object(app.left_panel, 'enter', return_value=regular_file):
                    with mock.patch.object(app, '_execute_file') as mock_exec:
                        app.handle_mouse(10, 5, curses.BUTTON1_DOUBLE_CLICKED)
                        mock_exec.assert_not_called()


class TestMiddleClickExecutesFile(unittest.TestCase):
    """Test that middle-click triggers file execution for executables."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_middle_click_on_executable_calls_execute_file(self, mock_mousemask, _curs, _colors):
        """Middle-click on executable file should trigger execution."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            exec_file = Path(tmpdir) / 'script.sh'
            exec_file.write_text('#!/bin/sh\necho hello')
            exec_file.chmod(exec_file.stat().st_mode | stat.S_IXUSR)

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            with mock.patch.object(app.active_panel, 'enter', return_value=exec_file):
                with mock.patch.object(app, '_execute_file') as mock_exec:
                    app.handle_mouse(10, 5, curses.BUTTON2_CLICKED)
                    mock_exec.assert_called_once_with(exec_file)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_middle_click_on_non_executable_does_not_execute(self, mock_mousemask, _curs, _colors):
        """Middle-click on non-executable file should not trigger execution."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            regular_file = Path(tmpdir) / 'readme.txt'
            regular_file.write_text('hello')

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            with mock.patch.object(app.active_panel, 'enter', return_value=regular_file):
                with mock.patch.object(app, '_execute_file') as mock_exec:
                    app.handle_mouse(10, 5, curses.BUTTON2_CLICKED)
                    mock_exec.assert_not_called()


if __name__ == '__main__':
    unittest.main()
