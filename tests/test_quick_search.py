"""Tests for quick search with /."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr
from tnc.app import App


class QuickSearchTestCase(unittest.TestCase):
    """Base class for quick search tests with common setup."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.has_colors_patcher = mock.patch('curses.has_colors', return_value=False)
        self.curs_set_patcher = mock.patch('curses.curs_set')
        self.has_colors_patcher.start()
        self.curs_set_patcher.start()

    def tearDown(self) -> None:
        """Clean up patches."""
        self.has_colors_patcher.stop()
        self.curs_set_patcher.stop()

    def create_app_in_dir(self, tmpdir: str) -> App:
        """Create and setup an App instance with the given directory."""
        with mock.patch('os.getcwd', return_value=tmpdir):
            app = App(create_mock_stdscr())
            app.setup()
            return app


class TestQuickSearchActivation(QuickSearchTestCase):
    """Test quick search activation."""

    def test_slash_activates_search_mode(self) -> None:
        """/ key should activate search mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self.create_app_in_dir(tmpdir)

            self.assertFalse(app.active_panel.search_mode)
            app.handle_key(ord('/'))
            self.assertTrue(app.active_panel.search_mode)


class TestQuickSearchFiltering(QuickSearchTestCase):
    """Test search filtering behavior."""

    def test_typing_filters_entries(self) -> None:
        """Typing should filter visible entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'apple.txt').write_text('')
            (Path(tmpdir) / 'apricot.txt').write_text('')
            (Path(tmpdir) / 'banana.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            panel.handle_search_char('a')
            panel.handle_search_char('p')

            names = [e.name for e in panel.entries]

            self.assertIn('apple.txt', names)
            self.assertIn('apricot.txt', names)
            self.assertNotIn('banana.txt', names)

    def test_search_is_case_insensitive(self) -> None:
        """Search should be case-insensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'README.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            panel.handle_search_char('r')
            panel.handle_search_char('e')
            panel.handle_search_char('a')

            names = [e.name for e in panel.entries]

            self.assertIn('README.txt', names)

    def test_empty_search_shows_all(self) -> None:
        """Empty search should show all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test1.txt').write_text('')
            (Path(tmpdir) / 'test2.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            all_entries = len(panel.entries)
            app.handle_key(ord('/'))

            self.assertEqual(len(panel.entries), all_entries)

    def test_no_match_shows_dotdot(self) -> None:
        """No match should show only '..' entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            panel.search_text = 'xyznonexistent'
            panel.apply_search_filter()

            self.assertEqual(len(panel.entries), 1)
            self.assertEqual(panel.entries[0].name, '..')


class TestQuickSearchNavigation(QuickSearchTestCase):
    """Test search navigation."""

    def test_enter_selects_and_exits_search(self) -> None:
        """Enter should select first match and exit search mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'apple.txt').write_text('')
            (Path(tmpdir) / 'banana.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            panel.handle_search_char('a')
            panel.exit_search(confirm=True)

            self.assertFalse(panel.search_mode)
            self.assertEqual(panel.entries[panel.cursor].name, 'apple.txt')

    def test_escape_cancels_search(self) -> None:
        """Escape should cancel search and restore view."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test1.txt').write_text('')
            (Path(tmpdir) / 'test2.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            original_entries_count = len(panel.entries)

            app.handle_key(ord('/'))
            panel.handle_search_char('x')
            panel.handle_search_char('y')
            panel.handle_search_char('z')
            panel.exit_search(confirm=False)

            self.assertFalse(panel.search_mode)
            self.assertEqual(len(panel.entries), original_entries_count)


class TestQuickSearchEditing(QuickSearchTestCase):
    """Test search text editing."""

    def test_backspace_removes_search_char(self) -> None:
        """Backspace should remove last character from search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            panel.handle_search_char('a')
            panel.handle_search_char('b')
            panel.handle_search_backspace()

            self.assertEqual(panel.search_text, 'a')

    def test_backspace_on_empty_exits_search(self) -> None:
        """Backspace on empty search should exit search mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            self.assertTrue(panel.search_mode)
            panel.handle_search_backspace()

            self.assertFalse(panel.search_mode)


class TestQuickSearchDisplay(QuickSearchTestCase):
    """Test search display."""

    def test_search_text_stored(self) -> None:
        """Search text should be stored in panel."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            panel.handle_search_char('t')
            panel.handle_search_char('e')
            panel.handle_search_char('s')
            panel.handle_search_char('t')

            self.assertEqual(panel.search_text, 'test')


class TestQuickSearchKeyIntegration(QuickSearchTestCase):
    """Test key handling routes to search methods via App."""

    def test_typing_in_search_mode_filters(self) -> None:
        """Typing printable characters should filter entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'apple.txt').write_text('')
            (Path(tmpdir) / 'banana.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))  # Activate search
            app.handle_key(ord('a'))  # Type 'a'
            app.handle_key(ord('p'))  # Type 'p'

            self.assertEqual(panel.search_text, 'ap')
            names = [e.name for e in panel.entries]
            self.assertIn('apple.txt', names)
            self.assertNotIn('banana.txt', names)

    def test_enter_in_search_mode_exits(self) -> None:
        """Enter key should exit search mode with confirmation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            app.handle_key(ord('t'))
            self.assertTrue(panel.search_mode)

            app.handle_key(curses.KEY_ENTER)
            self.assertFalse(panel.search_mode)

    def test_escape_in_search_mode_cancels(self) -> None:
        """Escape key should cancel search mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            app.handle_key(ord('x'))
            self.assertTrue(panel.search_mode)

            app.handle_key(27)  # Escape
            self.assertFalse(panel.search_mode)
            # Should restore all entries
            self.assertGreater(len(panel.entries), 1)

    def test_backspace_in_search_mode_removes_char(self) -> None:
        """Backspace should remove last character from search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            app.handle_key(ord('a'))
            app.handle_key(ord('b'))
            self.assertEqual(panel.search_text, 'ab')

            app.handle_key(curses.KEY_BACKSPACE)
            self.assertEqual(panel.search_text, 'a')

    def test_navigation_works_in_search_mode(self) -> None:
        """Arrow keys should still navigate in search mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'a1.txt').write_text('')
            (Path(tmpdir) / 'a2.txt').write_text('')
            (Path(tmpdir) / 'a3.txt').write_text('')

            app = self.create_app_in_dir(tmpdir)
            panel = app.active_panel

            app.handle_key(ord('/'))
            app.handle_key(ord('a'))

            initial_cursor = panel.cursor
            app.handle_key(curses.KEY_DOWN)
            self.assertEqual(panel.cursor, initial_cursor + 1)


if __name__ == '__main__':
    unittest.main()
