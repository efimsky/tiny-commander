"""Tests for Enter key - change directory and open files."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.panel import Panel


class TestEnterOnDirectory(unittest.TestCase):
    """Test Enter key on directories."""

    def test_enter_on_directory_changes_path(self):
        """Enter on directory should change panel's current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'subdir')
            subdir.mkdir()
            Path(subdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            # Find the subdir entry and move cursor to it
            subdir_idx = next(
                i for i, e in enumerate(panel.entries)
                if e.name == 'subdir'
            )
            panel.cursor = subdir_idx

            panel.enter()

            self.assertEqual(panel.path, subdir.resolve())
            # Should have refreshed entries
            names = [e.name for e in panel.entries]
            self.assertIn('file.txt', names)

    def test_enter_refreshes_panel_after_directory_change(self):
        """Panel should refresh entries after changing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'subdir')
            subdir.mkdir()

            panel = Panel(tmpdir, width=40, height=20)
            original_entries = list(panel.entries)

            # Navigate to subdir
            subdir_idx = next(
                i for i, e in enumerate(panel.entries)
                if e.name == 'subdir'
            )
            panel.cursor = subdir_idx
            panel.enter()

            # Entries should be different
            self.assertNotEqual(panel.entries, original_entries)


class TestEnterOnParentDirectory(unittest.TestCase):
    """Test Enter on '..' entry."""

    def test_dotdot_navigates_to_parent(self):
        """Enter on '..' should go to parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'subdir')
            subdir.mkdir()

            panel = Panel(str(subdir), width=40, height=20)
            # '..' should be first entry
            self.assertEqual(panel.entries[0].name, '..')
            panel.cursor = 0

            panel.enter()

            self.assertEqual(panel.path, Path(tmpdir).resolve())

    def test_dotdot_at_root_stays_at_root(self):
        """Enter on '..' at root should stay at root."""
        panel = Panel('/', width=40, height=20)
        original_path = panel.path

        # There may or may not be a '..' at root depending on implementation
        if panel.entries and panel.entries[0].name == '..':
            panel.cursor = 0
            panel.enter()
            self.assertEqual(panel.path, original_path)


class TestEnterOnFile(unittest.TestCase):
    """Test Enter on files."""

    def test_enter_on_file_returns_edit_action(self):
        """Enter on file should indicate edit action needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'test.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            file_idx = next(
                i for i, e in enumerate(panel.entries)
                if e.name == 'test.txt'
            )
            panel.cursor = file_idx

            result = panel.enter()
            # Should return the file path for editing
            self.assertIsNotNone(result)
            self.assertTrue(str(result).endswith('test.txt'))


class TestCursorAfterDirectoryChange(unittest.TestCase):
    """Test cursor position after directory changes."""

    def test_cursor_resets_to_zero_after_directory_change(self):
        """Cursor should reset to 0 when entering a new directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'subdir')
            subdir.mkdir()
            for i in range(5):
                Path(subdir, f'file{i}.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 5  # Arbitrary position

            subdir_idx = next(
                i for i, e in enumerate(panel.entries)
                if e.name == 'subdir'
            )
            panel.cursor = subdir_idx
            panel.enter()

            self.assertEqual(panel.cursor, 0)

    def test_scroll_resets_after_directory_change(self):
        """Scroll offset should reset when entering a new directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'subdir')
            subdir.mkdir()

            panel = Panel(tmpdir, width=40, height=20)
            panel.scroll_offset = 10  # Arbitrary offset

            subdir_idx = next(
                i for i, e in enumerate(panel.entries)
                if e.name == 'subdir'
            )
            panel.cursor = subdir_idx
            panel.enter()

            self.assertEqual(panel.scroll_offset, 0)


class TestKeyHandlingForEnter(unittest.TestCase):
    """Test Enter key handling in App."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_enter_key_triggers_panel_enter(self, _mock_curs_set, _mock_has_colors):
        """Enter key should call panel.enter()."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Mock the enter method
        with mock.patch.object(app.active_panel, 'enter') as mock_enter:
            mock_enter.return_value = None
            app.handle_key(curses.KEY_ENTER)
            mock_enter.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_carriage_return_also_triggers_enter(self, _mock_curs_set, _mock_has_colors):
        """Carriage return should also work as Enter."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        with mock.patch.object(app.active_panel, 'enter') as mock_enter:
            mock_enter.return_value = None
            app.handle_key(ord('\r'))
            mock_enter.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_linefeed_also_triggers_enter(self, _mock_curs_set, _mock_has_colors):
        """Linefeed (\\n) should also work as Enter for ttyd compatibility."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)
        # Return -1 (no key) after initial key to ensure no Alt sequence
        mock_stdscr.getch.return_value = -1

        app = App(mock_stdscr)
        app.setup()

        with mock.patch.object(app.active_panel, 'enter') as mock_enter:
            mock_enter.return_value = None
            app.handle_key(ord('\n'))
            mock_enter.assert_called_once()


if __name__ == '__main__':
    unittest.main()
