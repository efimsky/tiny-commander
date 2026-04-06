"""Tests for sort indicator display and reverse sort functionality."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr
from tnc.app import App


def _patch_curses(func):
    """Decorator to patch curses functions for tests."""
    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    return wrapper


class TestSortIndicator(unittest.TestCase):
    """Test sort indicator display in panel header."""

    @_patch_curses
    def test_get_sort_indicator_name_normal(self, *_):
        """Sort indicator for name, normal direction should be 'vn'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'name'
                panel.sort_reversed = False

                self.assertEqual(panel.get_sort_indicator(), 'vn')

    @_patch_curses
    def test_get_sort_indicator_size_normal(self, *_):
        """Sort indicator for size, normal direction should be 'vs'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'size'
                panel.sort_reversed = False

                self.assertEqual(panel.get_sort_indicator(), 'vs')

    @_patch_curses
    def test_get_sort_indicator_date_normal(self, *_):
        """Sort indicator for date, normal direction should be 'vd'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'date'
                panel.sort_reversed = False

                self.assertEqual(panel.get_sort_indicator(), 'vd')

    @_patch_curses
    def test_get_sort_indicator_extension_normal(self, *_):
        """Sort indicator for extension, normal direction should be 've'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'extension'
                panel.sort_reversed = False

                self.assertEqual(panel.get_sort_indicator(), 've')

    @_patch_curses
    def test_get_sort_indicator_name_reversed(self, *_):
        """Sort indicator for name, reversed should be '^n'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'name'
                panel.sort_reversed = True

                self.assertEqual(panel.get_sort_indicator(), '^n')

    @_patch_curses
    def test_get_sort_indicator_size_reversed(self, *_):
        """Sort indicator for size, reversed should be '^s'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'size'
                panel.sort_reversed = True

                self.assertEqual(panel.get_sort_indicator(), '^s')

    @_patch_curses
    def test_header_text_includes_sort_indicator(self, *_):
        """Header text should include sort indicator before path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'name'
                panel.sort_reversed = False

                header = panel.get_header_text()
                self.assertTrue(header.startswith('vn '))
                self.assertIn(tmpdir, header)

    @_patch_curses
    def test_header_text_truncation_preserves_indicator(self, *_):
        """When path is truncated, sort indicator should still be present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_order = 'size'
                panel.sort_reversed = True

                # Use very small max_width to force truncation
                header = panel.get_header_text(max_width=15)
                self.assertTrue(header.startswith('^s '))


class TestReverseSortFunctionality(unittest.TestCase):
    """Test reverse sort toggle functionality."""

    @_patch_curses
    def test_sort_reversed_default_false(self, *_):
        """Panel should have sort_reversed=False by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                self.assertFalse(panel.sort_reversed)

    @_patch_curses
    def test_toggle_sort_reverse_flips_flag(self, *_):
        """toggle_sort_reverse() should flip the sort_reversed flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                self.assertFalse(panel.sort_reversed)
                panel.toggle_sort_reverse()
                self.assertTrue(panel.sort_reversed)
                panel.toggle_sort_reverse()
                self.assertFalse(panel.sort_reversed)

    @_patch_curses
    def test_reverse_sort_name_z_to_a(self, *_):
        """Reversed name sort should be Z to A."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'apple.txt').write_text('')
            (Path(tmpdir) / 'banana.txt').write_text('')
            (Path(tmpdir) / 'cherry.txt').write_text('')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                # Switch to size first, then back to name, then reverse
                panel.sort_by('size')
                panel.sort_by('name')
                panel.toggle_sort_reverse()

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['cherry.txt', 'banana.txt', 'apple.txt'])

    @_patch_curses
    def test_reverse_sort_size_smallest_first(self, *_):
        """Reversed size sort should show smallest files first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'small.txt').write_text('a')
            (Path(tmpdir) / 'medium.txt').write_text('a' * 100)
            (Path(tmpdir) / 'large.txt').write_text('a' * 1000)

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_by('size')
                panel.toggle_sort_reverse()

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['small.txt', 'medium.txt', 'large.txt'])

    @_patch_curses
    def test_reverse_sort_date_oldest_first(self, *_):
        """Reversed date sort should show oldest files first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = Path(tmpdir) / 'old.txt'
            old_file.write_text('old')
            os.utime(old_file, (1000000, 1000000))

            new_file = Path(tmpdir) / 'new.txt'
            new_file.write_text('new')
            os.utime(new_file, (2000000, 2000000))

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_by('date')
                panel.toggle_sort_reverse()

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['old.txt', 'new.txt'])

    @_patch_curses
    def test_reverse_persists_after_refresh(self, *_):
        """Reversed sort should persist after panel refresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'apple.txt').write_text('')
            (Path(tmpdir) / 'banana.txt').write_text('')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                # Switch to size first, then back to name, then reverse
                panel.sort_by('size')
                panel.sort_by('name')
                panel.toggle_sort_reverse()
                panel.refresh()

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names[0], 'banana.txt')

    @_patch_curses
    def test_changing_sort_type_resets_reverse(self, *_):
        """Changing sort type should reset reverse flag to False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                # Start with size sort and enable reverse
                panel.sort_by('size')
                panel.toggle_sort_reverse()
                self.assertTrue(panel.sort_reversed)

                # Change to date - should reset reverse to False
                panel.sort_by('date')
                self.assertFalse(panel.sort_reversed)

    @_patch_curses
    def test_selecting_same_sort_type_toggles_reverse(self, *_):
        """Selecting the same sort type should toggle reverse flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                # Switch to size sort first (to reset state)
                panel.sort_by('size')
                self.assertEqual(panel.sort_order, 'size')
                self.assertFalse(panel.sort_reversed)

                # Select size again - should toggle to reversed
                panel.sort_by('size')
                self.assertTrue(panel.sort_reversed)

                # Select size again - should toggle back to normal
                panel.sort_by('size')
                self.assertFalse(panel.sort_reversed)

    @_patch_curses
    def test_directories_first_even_when_reversed(self, *_):
        """Directories should still come before files when reversed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'aaa_file.txt').write_text('')
            (Path(tmpdir) / 'zzz_dir').mkdir()

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_by('name')
                panel.toggle_sort_reverse()

                entries = [e for e in panel.entries if e.name != '..']
                self.assertEqual(entries[0].name, 'zzz_dir')


if __name__ == '__main__':
    unittest.main()
