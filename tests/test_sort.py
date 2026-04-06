"""Tests for sort options in panel."""

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


class TestSortOptions(unittest.TestCase):
    """Test sort options in panel."""

    @_patch_curses
    def test_sort_by_name_alphabetical(self, *_):
        """Default sort should be alphabetical by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'cherry.txt').write_text('')
            (Path(tmpdir) / 'apple.txt').write_text('')
            (Path(tmpdir) / 'banana.txt').write_text('')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                # Switch to size first, then back to name to test sort_by('name')
                panel.sort_by('size')
                panel.sort_by('name')

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['apple.txt', 'banana.txt', 'cherry.txt'])

    @_patch_curses
    def test_sort_by_size_largest_first(self, *_):
        """Sort by size should show largest files first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'small.txt').write_text('a')
            (Path(tmpdir) / 'medium.txt').write_text('a' * 100)
            (Path(tmpdir) / 'large.txt').write_text('a' * 1000)

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_by('size')

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['large.txt', 'medium.txt', 'small.txt'])

    @_patch_curses
    def test_sort_by_date_most_recent_first(self, *_):
        """Sort by date should show most recently modified first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = Path(tmpdir) / 'old.txt'
            old_file.write_text('old')
            os.utime(old_file, (1000000, 1000000))  # Old timestamp

            new_file = Path(tmpdir) / 'new.txt'
            new_file.write_text('new')
            os.utime(new_file, (2000000, 2000000))  # Newer timestamp

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_by('date')

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['new.txt', 'old.txt'])

    @_patch_curses
    def test_sort_by_extension_groups_extensions(self, *_):
        """Sort by extension should group files by their extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'a.txt').write_text('')
            (Path(tmpdir) / 'b.py').write_text('')
            (Path(tmpdir) / 'c.txt').write_text('')
            (Path(tmpdir) / 'd.py').write_text('')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_by('extension')

                names = [e.name for e in panel.entries if e.name != '..']
                extensions = [n.split('.')[-1] for n in names]
                self.assertEqual(extensions, sorted(extensions))

    @_patch_curses
    def test_directories_always_first_all_sorts(self, *_):
        """Directories should always come before files in any sort order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'aaa_file.txt').write_text('x' * 1000)
            (Path(tmpdir) / 'zzz_dir').mkdir()

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                for sort_type in ['name', 'size', 'date', 'extension']:
                    panel.sort_by(sort_type)

                    entries = [e for e in panel.entries if e.name != '..']
                    self.assertEqual(
                        entries[0].name, 'zzz_dir',
                        f"Directory not first with sort_by('{sort_type}')"
                    )

    @_patch_curses
    def test_dotdot_always_first_all_sorts(self, *_):
        """'..' entry should always be first in any sort order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test.txt').write_text('')
            (Path(tmpdir) / 'subdir').mkdir()

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                for sort_type in ['name', 'size', 'date', 'extension']:
                    panel.sort_by(sort_type)
                    self.assertEqual(
                        panel.entries[0].name, '..',
                        f"'..' not first with sort_by('{sort_type}')"
                    )

    @_patch_curses
    def test_sort_persists_after_refresh(self, *_):
        """Sort order should persist after panel refresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'small.txt').write_text('a')
            (Path(tmpdir) / 'large.txt').write_text('a' * 1000)

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                panel.sort_by('size')
                panel.refresh()

                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names[0], 'large.txt')

    @_patch_curses
    def test_sort_order_tracked(self, *_):
        """Panel should track current sort order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                panel = app.active_panel

                self.assertEqual(panel.sort_order, 'name')

                panel.sort_by('size')
                self.assertEqual(panel.sort_order, 'size')

                panel.sort_by('date')
                self.assertEqual(panel.sort_order, 'date')


if __name__ == '__main__':
    unittest.main()
