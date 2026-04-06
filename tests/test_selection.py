"""Tests for file selection with Insert key."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.panel import Panel


class TestInsertSelection(unittest.TestCase):
    """Test Insert key toggles selection."""

    def test_insert_selects_unselected_file(self):
        """Insert should select an unselected file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 1  # First file (after ..)

            panel.toggle_selection()

            self.assertIn('file.txt', panel.selected)

    def test_insert_deselects_selected_file(self):
        """Insert should deselect an already selected file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 1
            panel.toggle_selection()  # Select
            panel.toggle_selection()  # Deselect

            self.assertNotIn('file.txt', panel.selected)

    def test_cursor_advances_after_selection(self):
        """Cursor should move down after selection toggle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 1

            panel.toggle_selection()

            self.assertEqual(panel.cursor, 2)

    def test_cursor_stays_at_end_if_at_last_item(self):
        """Cursor should stay put if at the last item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = len(panel.entries) - 1  # Last item

            panel.toggle_selection()

            self.assertEqual(panel.cursor, len(panel.entries) - 1)

    def test_dotdot_cannot_be_selected(self):
        """The '..' entry should not be selectable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 0  # '..'

            panel.toggle_selection()

            self.assertNotIn('..', panel.selected)

    def test_selection_persists_after_cursor_move(self):
        """Selection should persist when cursor moves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 1
            panel.toggle_selection()

            panel.navigate_down()
            panel.navigate_down()

            self.assertIn('file1.txt', panel.selected)

    def test_selection_cleared_on_directory_change(self):
        """Selection should be cleared when changing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'subdir')
            subdir.mkdir()
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 2  # Select file.txt
            panel.toggle_selection()

            # Change to subdir
            panel.cursor = 1
            panel.enter()

            self.assertEqual(len(panel.selected), 0)


class TestKeyHandlingForInsert(unittest.TestCase):
    """Test Insert key handling in App."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_insert_key_triggers_toggle_selection(self, _mock_curs_set, _mock_has_colors):
        """Insert key should call panel.toggle_selection()."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        with mock.patch.object(app.active_panel, 'toggle_selection') as mock_toggle:
            app.handle_key(curses.KEY_IC)
            mock_toggle.assert_called_once()


class TestSpaceKeySelection(unittest.TestCase):
    """Test Space key toggles selection when command line is empty."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_space_toggles_selection_when_command_line_empty(
        self, _mock_curs_set, _mock_has_colors
    ):
        """Space should call toggle_selection() when command line is empty."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        with mock.patch.object(app.active_panel, 'toggle_selection') as mock_toggle:
            app.handle_key(ord(' '))
            mock_toggle.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_space_types_into_command_line_when_not_empty(
        self, _mock_curs_set, _mock_has_colors
    ):
        """Space should type into command line when it has text."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Type some text first
        app.handle_key(ord('l'))
        app.handle_key(ord('s'))

        # Space should go to command line, not toggle selection
        app.handle_key(ord(' '))

        self.assertEqual(app.command_line.input_text, 'ls ')
        self.assertEqual(len(app.active_panel.selected), 0)


if __name__ == '__main__':
    unittest.main()
