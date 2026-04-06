"""Tests for command line prompt showing active panel directory."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.command_line import CommandLine


class TestPromptShowsActiveDirectory(unittest.TestCase):
    """Test prompt displays current directory."""

    def test_prompt_shows_directory(self):
        """Prompt should show the current directory."""
        cmdline = CommandLine('/home/user/documents')
        display = cmdline.get_display_text(width=80)
        self.assertIn('/home/user/documents>', display)

    def test_prompt_updates_on_set_path(self):
        """Prompt should update when path is changed."""
        cmdline = CommandLine('/home/user/left')
        cmdline.set_path('/home/user/right')
        display = cmdline.get_display_text(width=80)
        self.assertIn('/home/user/right>', display)


class TestPromptTruncation(unittest.TestCase):
    """Test prompt truncates long paths."""

    def test_long_path_truncated_to_fit_width(self):
        """Long paths should be truncated to fit available width."""
        cmdline = CommandLine('/very/long/path/that/exceeds/width')
        display = cmdline.get_display_text(width=30)
        self.assertLessEqual(len(display), 30)

    def test_truncated_path_shows_end(self):
        """Truncated paths should show the end of path."""
        cmdline = CommandLine('/home/user/documents/projects')
        display = cmdline.get_display_text(width=30)
        # Should show '...' prefix and end of path
        self.assertIn('...', display)
        self.assertIn('>', display)

    def test_truncated_path_preserves_prompt_symbol(self):
        """Truncation should always preserve the > prompt."""
        cmdline = CommandLine('/very/long/path/that/exceeds/width')
        display = cmdline.get_display_text(width=20)
        self.assertIn('>', display)


class TestPromptWithInput(unittest.TestCase):
    """Test prompt with command input text."""

    def test_prompt_with_input_shows_both(self):
        """Prompt should show directory and input text."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'ls -la'
        display = cmdline.get_display_text(width=80)
        self.assertIn('/tmp>', display)
        self.assertIn('ls -la', display)

    def test_long_input_causes_prompt_truncation(self):
        """Long input should cause prompt to be truncated."""
        cmdline = CommandLine('/home/user/documents')
        cmdline.input_text = 'echo hello world testing long command'
        display = cmdline.get_display_text(width=50)
        # Should fit within width
        self.assertLessEqual(len(display), 50)
        # Input should be preserved
        self.assertIn('echo hello world', display)


class TestPromptIntegrationWithApp(unittest.TestCase):
    """Test prompt integrates with App for active panel."""

    def test_app_has_command_line(self):
        """App should have a command_line attribute."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()
            self.assertIsNotNone(app.command_line)

    def test_command_line_path_matches_active_panel(self):
        """Command line path should match active panel."""
        from tnc.app import App
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir) / 'left'
            right_dir = Path(tmpdir) / 'right'
            left_dir.mkdir()
            right_dir.mkdir()

            with mock.patch('curses.curs_set'), \
                 mock.patch('curses.has_colors', return_value=False), \
                 mock.patch('os.getcwd', return_value=str(left_dir)):
                stdscr = mock.MagicMock()
                stdscr.getmaxyx.return_value = (24, 80)
                app = App(stdscr)
                app.setup()
                # Command line should show active panel's path (convert Path to str)
                self.assertEqual(app.command_line.path, str(app.active_panel.path))

    def test_switch_panel_updates_command_line_path(self):
        """Tab should update command line path to new active panel."""
        from tnc.app import App
        import curses
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir) / 'left'
            right_dir = Path(tmpdir) / 'right'
            left_dir.mkdir()
            right_dir.mkdir()

            with mock.patch('curses.curs_set'), \
                 mock.patch('curses.has_colors', return_value=False), \
                 mock.patch('os.getcwd', return_value=str(left_dir)):
                stdscr = mock.MagicMock()
                stdscr.getmaxyx.return_value = (24, 80)
                app = App(stdscr)
                app.setup()
                # Set right panel to a different path
                app.right_panel.path = str(right_dir)

                # Switch panel (Tab key)
                app.handle_key(ord('\t'))

                # Command line should now show right panel's path
                self.assertEqual(app.command_line.path, str(right_dir))

    def test_navigate_to_dir_updates_command_line_path(self):
        """Entering a directory should update command line path."""
        from tnc.app import App
        import curses
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()

            with mock.patch('curses.curs_set'), \
                 mock.patch('curses.has_colors', return_value=False), \
                 mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = mock.MagicMock()
                stdscr.getmaxyx.return_value = (24, 80)
                app = App(stdscr)
                app.setup()

                # Move cursor to subdir entry (skip '..' entry) and press Enter
                app.handle_key(curses.KEY_DOWN)
                app.handle_key(ord('\r'))

                # Command line should now show subdir path
                self.assertIn('subdir', app.command_line.path)


if __name__ == '__main__':
    unittest.main()
