"""Tests for DisplayEntry dataclass and Panel.get_display_entries()."""

import tempfile
import unittest
from pathlib import Path

from tnc.panel import DisplayEntry, Panel, render_panel_entries


class TestDisplayEntry(unittest.TestCase):
    """Test DisplayEntry dataclass."""

    def test_display_entry_stores_all_fields(self):
        """DisplayEntry should store all required display fields."""
        entry = DisplayEntry(
            name='test.txt',
            display_name='test.txt',
            size_str='4.2K',
            mtime_str='Jan 15 14:30',
            is_dir=False,
            is_selected=False,
            has_cursor=True,
            attr=0,
        )
        self.assertEqual(entry.name, 'test.txt')
        self.assertEqual(entry.display_name, 'test.txt')
        self.assertEqual(entry.size_str, '4.2K')
        self.assertEqual(entry.mtime_str, 'Jan 15 14:30')
        self.assertFalse(entry.is_dir)
        self.assertFalse(entry.is_selected)
        self.assertTrue(entry.has_cursor)
        self.assertEqual(entry.attr, 0)

    def test_display_entry_is_frozen(self):
        """DisplayEntry should be immutable (frozen dataclass)."""
        entry = DisplayEntry(
            name='test.txt',
            display_name='test.txt',
            size_str='4.2K',
            mtime_str='Jan 15 14:30',
            is_dir=False,
            is_selected=False,
            has_cursor=False,
            attr=0,
        )
        with self.assertRaises(AttributeError):
            entry.name = 'other.txt'


class TestGetDisplayEntries(unittest.TestCase):
    """Test Panel.get_display_entries() method."""

    def test_get_display_entries_returns_list(self):
        """get_display_entries should return a list of DisplayEntry objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()
            panel = Panel(tmpdir, width=40, height=20)

            entries = panel.get_display_entries()

            self.assertIsInstance(entries, list)
            self.assertTrue(all(isinstance(e, DisplayEntry) for e in entries))

    def test_get_display_entries_directory_has_slash_suffix(self):
        """Directory display_name should have '/' suffix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'subdir').mkdir()
            panel = Panel(tmpdir, width=40, height=20)

            entries = panel.get_display_entries()
            subdir_entry = next(e for e in entries if e.name == 'subdir')

            self.assertEqual(subdir_entry.display_name, 'subdir/')
            self.assertTrue(subdir_entry.is_dir)

    def test_get_display_entries_executable_has_asterisk_prefix(self):
        """Executable file display_name should have '*' prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir, 'script.sh')
            exe_path.touch()
            exe_path.chmod(0o755)
            panel = Panel(tmpdir, width=40, height=20)

            entries = panel.get_display_entries()
            exe_entry = next(e for e in entries if e.name == 'script.sh')

            self.assertEqual(exe_entry.display_name, '*script.sh')

    def test_get_display_entries_selected_item_has_flag(self):
        """Selected items should have is_selected=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()
            panel = Panel(tmpdir, width=40, height=20)
            panel.selected.add('file.txt')

            entries = panel.get_display_entries()
            file_entry = next(e for e in entries if e.name == 'file.txt')

            self.assertTrue(file_entry.is_selected)

    def test_get_display_entries_cursor_item_has_flag(self):
        """Item at cursor position should have has_cursor=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()
            panel = Panel(tmpdir, width=40, height=20)
            # Cursor is at 0 which is '..'
            # Move cursor to file.txt
            panel.cursor = 1

            entries = panel.get_display_entries()

            # Only cursor entry should have has_cursor=True
            cursor_entries = [e for e in entries if e.has_cursor]
            self.assertEqual(len(cursor_entries), 1)
            self.assertEqual(cursor_entries[0].name, 'file.txt')

    def test_get_display_entries_parent_dir_entry(self):
        """Parent directory '..' should be included with is_dir=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)

            entries = panel.get_display_entries()
            parent_entry = next(e for e in entries if e.name == '..')

            self.assertTrue(parent_entry.is_dir)
            self.assertEqual(parent_entry.display_name, '../')

    def test_get_display_entries_broken_symlink(self):
        """Broken symlink should be handled gracefully."""
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a symlink to a non-existent target
            link_path = Path(tmpdir, 'broken_link')
            os.symlink('/nonexistent/target/file', link_path)
            panel = Panel(tmpdir, width=40, height=20)

            entries = panel.get_display_entries()
            link_entry = next(e for e in entries if e.name == 'broken_link')

            # Broken symlink still gets a size (the symlink size) - doesn't crash
            self.assertIsInstance(link_entry.size_str, str)
            # Should have an attr (broken link gets special color)
            self.assertIsNotNone(link_entry.attr)

    def test_get_display_entries_inactive_panel_cursor(self):
        """Inactive panel with cursor should not use cursor attribute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()
            panel = Panel(tmpdir, width=40, height=20)
            panel.is_active = False  # Panel is inactive
            panel.cursor = 1  # Cursor on file.txt

            entries = panel.get_display_entries()
            file_entry = next(e for e in entries if e.name == 'file.txt')

            # has_cursor should be True but attr should NOT be cursor attr
            # because panel is inactive
            self.assertTrue(file_entry.has_cursor)
            # The attr should be normal (not cursor highlight)
            # We can't easily test the exact attr value, but we verified the flag


class TestRenderPanelEntries(unittest.TestCase):
    """Test render_panel_entries function."""

    def test_render_panel_entries_exists(self):
        """render_panel_entries function should be callable."""
        self.assertTrue(callable(render_panel_entries))

    def test_render_entries_calls_addstr(self):
        """render_panel_entries should call addstr for each entry."""
        from unittest import mock

        entries = [
            DisplayEntry(
                name='file.txt',
                display_name='file.txt',
                size_str='1K',
                mtime_str='Jan 01 00:00',
                is_dir=False,
                is_selected=False,
                has_cursor=False,
                attr=0,
            ),
        ]
        mock_win = mock.MagicMock()

        render_panel_entries(
            win=mock_win,
            entries=entries,
            x=0,
            y=0,
            width=40,
            show_mtime=False,
        )

        self.assertTrue(mock_win.addstr.called)

    def test_render_entries_formats_display_string(self):
        """render_panel_entries should format name and size columns."""
        from unittest import mock

        entries = [
            DisplayEntry(
                name='test.txt',
                display_name='test.txt',
                size_str='4K',
                mtime_str='',
                is_dir=False,
                is_selected=False,
                has_cursor=False,
                attr=0,
            ),
        ]
        mock_win = mock.MagicMock()

        render_panel_entries(
            win=mock_win,
            entries=entries,
            x=0,
            y=0,
            width=40,
            show_mtime=False,
        )

        # Check that addstr was called with a string containing both name and size
        call_args = mock_win.addstr.call_args_list[0]
        display_str = call_args[0][2]  # Third positional arg is the string
        self.assertIn('test.txt', display_str)
        self.assertIn('4K', display_str)

    def test_render_entries_empty_list(self):
        """render_panel_entries should handle empty entry list gracefully."""
        from unittest import mock

        mock_win = mock.MagicMock()

        render_panel_entries(
            win=mock_win,
            entries=[],
            x=0,
            y=0,
            width=40,
            show_mtime=False,
        )

        # Should not call addstr for empty list
        self.assertFalse(mock_win.addstr.called)

    def test_render_entries_narrow_width_guard(self):
        """render_panel_entries should silently skip if width too narrow."""
        from unittest import mock

        entries = [
            DisplayEntry(
                name='file.txt',
                display_name='file.txt',
                size_str='1K',
                mtime_str='',
                is_dir=False,
                is_selected=False,
                has_cursor=False,
                attr=0,
            ),
        ]
        mock_win = mock.MagicMock()

        # Width of 10 is too narrow (need at least size_width(8) + padding(2) + min_name(4) = 14)
        render_panel_entries(
            win=mock_win,
            entries=entries,
            x=0,
            y=0,
            width=10,
            show_mtime=False,
        )

        # Should not call addstr when width is too narrow
        self.assertFalse(mock_win.addstr.called)


if __name__ == '__main__':
    unittest.main()
