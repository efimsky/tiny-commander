"""Tests for Open in Finder feature (macOS only)."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr, find_entry_index
from tnc.app import Action, App


class TestOpenInFinderKeybinding(unittest.TestCase):
    """Test Alt+O keybinding triggers Open in Finder action."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_alt_o_returns_open_in_finder_action_on_macos(self, _curs_set, _has_colors):
        """Alt+O should return OPEN_IN_FINDER action on macOS."""
        with mock.patch('sys.platform', 'darwin'):
            app = App(create_mock_stdscr())
            app.setup()

            # Simulate Alt+O: Escape followed by 'o'
            # First, handle Escape - it will check for next key
            app.stdscr.nodelay.return_value = None
            app.stdscr.getch.return_value = ord('o')  # Next key after Escape

            action = app.handle_key(27)  # Escape key

            self.assertEqual(action, Action.OPEN_IN_FINDER)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_alt_o_returns_none_on_linux(self, _curs_set, _has_colors):
        """Alt+O should return NONE action on Linux (silent no-op)."""
        with mock.patch('sys.platform', 'linux'):
            app = App(create_mock_stdscr())
            app.setup()

            # Simulate Alt+O: Escape followed by 'o'
            app.stdscr.nodelay.return_value = None
            app.stdscr.getch.return_value = ord('o')

            action = app.handle_key(27)

            self.assertEqual(action, Action.NONE)


class TestOpenInFinderExecution(unittest.TestCase):
    """Test Open in Finder calls subprocess correctly."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    @mock.patch('sys.platform', 'darwin')
    def test_open_in_finder_calls_open_command_for_file(
        self, mock_run, _endwin, _curs_set, _has_colors
    ):
        """Should call 'open -R' with file path on macOS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.open_in_finder()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertEqual(args[0], 'open')
                self.assertEqual(args[1], '-R')
                self.assertIn('test.txt', args[2])

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    @mock.patch('sys.platform', 'darwin')
    def test_open_in_finder_calls_open_command_for_directory(
        self, mock_run, _endwin, _curs_set, _has_colors
    ):
        """Should call 'open -R' with directory path on macOS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.active_panel.cursor = find_entry_index(app.active_panel, 'subdir')

                app.open_in_finder()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertEqual(args[0], 'open')
                self.assertEqual(args[1], '-R')
                self.assertIn('subdir', args[2])

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.endwin')
    @mock.patch('tnc.app.subprocess.run')
    @mock.patch('sys.platform', 'darwin')
    def test_open_in_finder_reveals_current_dir_for_dotdot(
        self, mock_run, _endwin, _curs_set, _has_colors
    ):
        """When '..' is selected, should reveal current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Resolve symlinks (macOS /var -> /private/var)
            resolved_tmpdir = str(Path(tmpdir).resolve())
            with mock.patch('os.getcwd', return_value=resolved_tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.active_panel.cursor = 0  # '..' is always first

                app.open_in_finder()

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                self.assertEqual(args[0], 'open')
                self.assertEqual(args[1], '-R')
                # Should reveal the current directory, not parent
                self.assertEqual(args[2], resolved_tmpdir)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('tnc.app.subprocess.run')
    @mock.patch('sys.platform', 'linux')
    def test_open_in_finder_noop_on_linux(self, mock_run, _curs_set, _has_colors):
        """Should do nothing on Linux."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.active_panel.cursor = find_entry_index(app.active_panel, 'test.txt')

                app.open_in_finder()

                mock_run.assert_not_called()


class TestOpenInFinderMenu(unittest.TestCase):
    """Test Open in Finder menu item."""

    @mock.patch('tnc.menu.sys.platform', 'darwin')
    def test_menu_contains_open_in_finder_on_macos(self):
        """File menu should contain 'Open in Finder' on macOS."""
        from tnc.menu import MenuBar

        menu_bar = MenuBar()
        file_menu = next(m for m in menu_bar.menus if m.name == 'File')
        item_names = [item.name for item in file_menu.items]

        self.assertIn('Open in Finder', item_names)

    @mock.patch('tnc.menu.sys.platform', 'linux')
    def test_menu_does_not_contain_open_in_finder_on_linux(self):
        """File menu should NOT contain 'Open in Finder' on Linux."""
        from tnc.menu import MenuBar

        menu_bar = MenuBar()
        file_menu = next(m for m in menu_bar.menus if m.name == 'File')
        item_names = [item.name for item in file_menu.items]

        self.assertNotIn('Open in Finder', item_names)


class TestOpenInFinderActionMap(unittest.TestCase):
    """Test MENU_ACTION_MAP contains open_in_finder."""

    def test_menu_action_map_contains_open_in_finder(self):
        """MENU_ACTION_MAP should map 'open_in_finder' to Action."""
        from tnc.app import MENU_ACTION_MAP, Action

        self.assertIn('open_in_finder', MENU_ACTION_MAP)
        self.assertEqual(MENU_ACTION_MAP['open_in_finder'], Action.OPEN_IN_FINDER)


if __name__ == '__main__':
    unittest.main()
