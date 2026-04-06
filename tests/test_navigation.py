"""Tests for arrow key navigation in panels."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.panel import Panel


class TestNavigateDown(unittest.TestCase):
    """Test down arrow navigation."""

    def test_navigate_down_moves_cursor(self):
        """Down arrow should move cursor down."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            self.assertEqual(panel.cursor, 0)

            panel.navigate_down()
            self.assertEqual(panel.cursor, 1)

    def test_navigate_down_at_bottom_stays_at_bottom(self):
        """Down arrow at last item should stay at bottom."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            # Move to last item
            panel.cursor = len(panel.entries) - 1
            last_pos = panel.cursor

            panel.navigate_down()
            self.assertEqual(panel.cursor, last_pos)

    def test_navigate_down_scrolls_when_needed(self):
        """Down arrow should scroll when cursor goes beyond visible area."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files
            for i in range(30):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            visible_rows = panel.height - 2  # Subtract border rows

            # Move cursor to last visible row
            for _ in range(visible_rows):
                panel.navigate_down()

            # Scroll offset should have increased
            self.assertGreater(panel.scroll_offset, 0)


class TestNavigateUp(unittest.TestCase):
    """Test up arrow navigation."""

    def test_navigate_up_moves_cursor(self):
        """Up arrow should move cursor up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 2

            panel.navigate_up()
            self.assertEqual(panel.cursor, 1)

    def test_navigate_up_at_top_stays_at_top(self):
        """Up arrow at first item should stay at top."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            self.assertEqual(panel.cursor, 0)

            panel.navigate_up()
            self.assertEqual(panel.cursor, 0)

    def test_navigate_up_scrolls_when_needed(self):
        """Up arrow should scroll when cursor goes above visible area."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(30):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            # Position cursor and scroll
            panel.cursor = 20
            panel.scroll_offset = 15

            # Navigate up multiple times
            for _ in range(10):
                panel.navigate_up()

            # Scroll offset should have decreased
            self.assertLess(panel.scroll_offset, 15)


class TestScrollBehavior(unittest.TestCase):
    """Test scrolling behavior."""

    def test_cursor_stays_visible_after_navigation(self):
        """Cursor should always be in visible area after navigation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            visible_rows = panel.height - 2

            # Navigate through all entries
            for _ in range(len(panel.entries)):
                panel.navigate_down()
                self.assertGreaterEqual(panel.cursor, panel.scroll_offset)
                self.assertLess(panel.cursor, panel.scroll_offset + visible_rows)

    def test_scroll_offset_stays_valid(self):
        """Scroll offset should never be negative or too large."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)

            # Navigate up from top
            for _ in range(5):
                panel.navigate_up()
                self.assertGreaterEqual(panel.scroll_offset, 0)

            # Navigate down past bottom
            for _ in range(20):
                panel.navigate_down()
                max_offset = max(0, len(panel.entries) - (panel.height - 2))
                self.assertLessEqual(panel.scroll_offset, max_offset)


class TestNavigateToTop(unittest.TestCase):
    """Test Home key navigation (navigate_to_top)."""

    def test_navigate_to_top_moves_cursor_to_first(self):
        """Home should move cursor to first entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 5

            panel.navigate_to_top()
            self.assertEqual(panel.cursor, 0)

    def test_navigate_to_top_at_top_stays_at_top(self):
        """Home at first item should stay at top."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            self.assertEqual(panel.cursor, 0)

            panel.navigate_to_top()
            self.assertEqual(panel.cursor, 0)

    def test_navigate_to_top_adjusts_scroll(self):
        """Home should adjust scroll to show first entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            panel.cursor = 30
            panel.scroll_offset = 25

            panel.navigate_to_top()
            self.assertEqual(panel.cursor, 0)
            self.assertEqual(panel.scroll_offset, 0)

    def test_navigate_to_top_empty_panel(self):
        """Home on empty panel should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            # Only '..' entry exists
            panel.navigate_to_top()
            self.assertEqual(panel.cursor, 0)


class TestNavigateToBottom(unittest.TestCase):
    """Test End key navigation (navigate_to_bottom)."""

    def test_navigate_to_bottom_moves_cursor_to_last(self):
        """End should move cursor to last entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            self.assertEqual(panel.cursor, 0)

            panel.navigate_to_bottom()
            self.assertEqual(panel.cursor, len(panel.entries) - 1)

    def test_navigate_to_bottom_at_bottom_stays_at_bottom(self):
        """End at last item should stay at bottom."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = len(panel.entries) - 1
            last_pos = panel.cursor

            panel.navigate_to_bottom()
            self.assertEqual(panel.cursor, last_pos)

    def test_navigate_to_bottom_adjusts_scroll(self):
        """End should adjust scroll to show last entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            visible_rows = panel.height - 2

            panel.navigate_to_bottom()
            # Cursor should be visible
            self.assertGreaterEqual(panel.cursor, panel.scroll_offset)
            self.assertLess(panel.cursor, panel.scroll_offset + visible_rows)

    def test_navigate_to_bottom_empty_panel(self):
        """End on empty panel should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            # Only '..' entry exists
            panel.navigate_to_bottom()
            self.assertEqual(panel.cursor, 0)


class TestNavigatePageUp(unittest.TestCase):
    """Test Page Up navigation."""

    def test_navigate_page_up_moves_by_visible_rows(self):
        """Page Up should move cursor up by visible rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            visible_rows = panel.height - 2
            panel.cursor = 30

            panel.navigate_page_up()
            self.assertEqual(panel.cursor, 30 - visible_rows)

    def test_navigate_page_up_clamps_to_zero(self):
        """Page Up near top should clamp cursor to 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            panel.cursor = 3  # Less than page size

            panel.navigate_page_up()
            self.assertEqual(panel.cursor, 0)

    def test_navigate_page_up_adjusts_scroll(self):
        """Page Up should adjust scroll appropriately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            visible_rows = panel.height - 2
            panel.cursor = 30
            panel.scroll_offset = 25

            panel.navigate_page_up()
            # Cursor should be visible
            self.assertGreaterEqual(panel.cursor, panel.scroll_offset)
            self.assertLess(panel.cursor, panel.scroll_offset + visible_rows)

    def test_navigate_page_up_at_top(self):
        """Page Up at top should stay at 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 0

            panel.navigate_page_up()
            self.assertEqual(panel.cursor, 0)


class TestNavigatePageDown(unittest.TestCase):
    """Test Page Down navigation."""

    def test_navigate_page_down_moves_by_visible_rows(self):
        """Page Down should move cursor down by visible rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            visible_rows = panel.height - 2
            panel.cursor = 5

            panel.navigate_page_down()
            self.assertEqual(panel.cursor, 5 + visible_rows)

    def test_navigate_page_down_clamps_to_last(self):
        """Page Down near bottom should clamp cursor to last entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            panel.cursor = len(panel.entries) - 3  # Near the end

            panel.navigate_page_down()
            self.assertEqual(panel.cursor, len(panel.entries) - 1)

    def test_navigate_page_down_adjusts_scroll(self):
        """Page Down should adjust scroll appropriately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            visible_rows = panel.height - 2
            panel.cursor = 5

            panel.navigate_page_down()
            # Cursor should be visible
            self.assertGreaterEqual(panel.cursor, panel.scroll_offset)
            self.assertLess(panel.cursor, panel.scroll_offset + visible_rows)

    def test_navigate_page_down_at_bottom(self):
        """Page Down at bottom should stay at last entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = len(panel.entries) - 1
            last_pos = panel.cursor

            panel.navigate_page_down()
            self.assertEqual(panel.cursor, last_pos)


class TestKeyHandling(unittest.TestCase):
    """Test key event handling for navigation."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_down_arrow_key_navigates(self, _mock_curs_set, _mock_has_colors):
        """KEY_DOWN should call navigate_down."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        initial_cursor = app.active_panel.cursor
        app.handle_key(curses.KEY_DOWN)
        self.assertEqual(app.active_panel.cursor, initial_cursor + 1)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_up_arrow_key_navigates(self, _mock_curs_set, _mock_has_colors):
        """KEY_UP should call navigate_up."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Move down first so we can go up
        app.active_panel.cursor = 2
        app.handle_key(curses.KEY_UP)
        self.assertEqual(app.active_panel.cursor, 1)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_home_key_navigates_to_top(self, _mock_curs_set, _mock_has_colors):
        """KEY_HOME should call navigate_to_top."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        app.active_panel.cursor = 5
        app.handle_key(curses.KEY_HOME)
        self.assertEqual(app.active_panel.cursor, 0)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_end_key_navigates_to_bottom(self, _mock_curs_set, _mock_has_colors):
        """KEY_END should call navigate_to_bottom."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        app.handle_key(curses.KEY_END)
        self.assertEqual(
            app.active_panel.cursor,
            len(app.active_panel.entries) - 1
        )

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_page_up_key_navigates(self, _mock_curs_set, _mock_has_colors):
        """KEY_PPAGE should call navigate_page_up."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        app.active_panel.cursor = 10
        app.handle_key(curses.KEY_PPAGE)
        # Should move up by visible rows (clamped to 0)
        self.assertLess(app.active_panel.cursor, 10)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_page_down_key_navigates(self, _mock_curs_set, _mock_has_colors):
        """KEY_NPAGE should call navigate_page_down."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        initial_cursor = app.active_panel.cursor
        app.handle_key(curses.KEY_NPAGE)
        # Should move down by visible rows (or to end)
        self.assertGreater(app.active_panel.cursor, initial_cursor)


if __name__ == '__main__':
    unittest.main()
