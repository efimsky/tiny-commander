"""Tests for confirmation dialog behavior (default Yes, [Y/n] format)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.app import App


class TestDeleteConfirmationKeys(unittest.TestCase):
    """Test delete confirmation accepts correct keys."""

    def _create_app_with_file(self, tmpdir: str) -> tuple[App, Path]:
        """Helper to create an App with a test file."""
        test_file = Path(tmpdir) / 'test.txt'
        test_file.write_text('content')

        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False), \
             mock.patch('os.getcwd', return_value=tmpdir):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            # Move cursor to the file (skip '..')
            app.active_panel.cursor = 1

            return app, test_file

    def test_enter_key_confirms_delete(self):
        """Enter key should confirm delete (default Yes)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            # Mock getch to return Enter key
            app.stdscr.getch.return_value = ord('\n')

            app._prompt_delete()

            self.assertFalse(test_file.exists(), "Enter should delete the file")

    def test_carriage_return_confirms_delete(self):
        """Carriage return should also confirm delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            # Mock getch to return carriage return
            app.stdscr.getch.return_value = ord('\r')

            app._prompt_delete()

            self.assertFalse(test_file.exists(), "CR should delete the file")

    def test_y_key_confirms_delete(self):
        """Lowercase y should confirm delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            app.stdscr.getch.return_value = ord('y')

            app._prompt_delete()

            self.assertFalse(test_file.exists(), "y should delete the file")

    def test_Y_key_confirms_delete(self):
        """Uppercase Y should confirm delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            app.stdscr.getch.return_value = ord('Y')

            app._prompt_delete()

            self.assertFalse(test_file.exists(), "Y should delete the file")

    def test_n_key_declines_delete(self):
        """Lowercase n should decline delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            app.stdscr.getch.return_value = ord('n')

            app._prompt_delete()

            self.assertTrue(test_file.exists(), "n should NOT delete the file")

    def test_N_key_declines_delete(self):
        """Uppercase N should decline delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            app.stdscr.getch.return_value = ord('N')

            app._prompt_delete()

            self.assertTrue(test_file.exists(), "N should NOT delete the file")

    def test_escape_key_declines_delete(self):
        """Escape key should decline delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            # Escape key is 27
            app.stdscr.getch.return_value = 27

            app._prompt_delete()

            self.assertTrue(test_file.exists(), "Escape should NOT delete the file")

    def test_other_keys_ignored_then_cancel(self):
        """Other keys should be ignored, then cancel should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app, test_file = self._create_app_with_file(tmpdir)

            # Press 'x' (random key), then 'n' to exit the dialog
            # The dialog ignores invalid keys and keeps waiting, so we need
            # to eventually press a valid key to exit
            app.stdscr.getch.side_effect = [ord('x'), ord('n')]

            app._prompt_delete()

            self.assertTrue(test_file.exists(), "File should NOT be deleted after cancel")


class TestDeleteConfirmationPromptFormat(unittest.TestCase):
    """Test delete confirmation shows [Y/n] format."""

    def test_single_file_prompt_format(self):
        """Single file prompt should show [Y/n] format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'myfile.txt'
            test_file.write_text('content')

            with mock.patch('curses.curs_set'), \
                 mock.patch('curses.has_colors', return_value=False), \
                 mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = mock.MagicMock()
                stdscr.getmaxyx.return_value = (24, 80)
                stdscr.getch.return_value = ord('n')  # Don't actually delete

                app = App(stdscr)
                app.setup()
                app.active_panel.cursor = 1

                app._prompt_delete()

                # Check addstr was called with [Y/n] format somewhere in the dialog
                calls = stdscr.addstr.call_args_list
                all_text = ' '.join(str(c) for c in calls)
                self.assertIn('Delete', all_text, "Should have a Delete prompt")
                self.assertIn('[Y/n]', all_text, "Dialog should show [Y/n] format")

    def test_multiple_files_prompt_format(self):
        """Multiple files prompt should show [Y/n] format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').write_text('1')
            Path(tmpdir, 'file2.txt').write_text('2')

            with mock.patch('curses.curs_set'), \
                 mock.patch('curses.has_colors', return_value=False), \
                 mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = mock.MagicMock()
                stdscr.getmaxyx.return_value = (24, 80)
                stdscr.getch.return_value = ord('n')  # Don't actually delete

                app = App(stdscr)
                app.setup()
                # Select multiple files
                app.active_panel.selected = {'file1.txt', 'file2.txt'}

                app._prompt_delete()

                # Check addstr was called with [Y/n] format somewhere in the dialog
                calls = stdscr.addstr.call_args_list
                all_text = ' '.join(str(c) for c in calls)
                self.assertIn('Delete', all_text, "Should have a Delete prompt")
                self.assertIn('[Y/n]', all_text, "Dialog should show [Y/n] format")


if __name__ == '__main__':
    unittest.main()
