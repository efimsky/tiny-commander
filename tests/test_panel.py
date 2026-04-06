"""Tests for the Panel class - directory listing and navigation."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.panel import Panel


class TestPanelInit(unittest.TestCase):
    """Test Panel initialization."""

    def test_panel_resolves_path(self):
        """Panel should resolve relative paths to absolute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            self.assertTrue(panel.path.is_absolute())

    def test_panel_stores_dimensions(self):
        """Panel should store width and height."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=50, height=25)
            self.assertEqual(panel.width, 50)
            self.assertEqual(panel.height, 25)

    def test_panel_starts_inactive(self):
        """Panel should start as inactive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            self.assertFalse(panel.is_active)

    def test_panel_cursor_starts_at_zero(self):
        """Panel cursor should start at position 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            self.assertEqual(panel.cursor, 0)


class TestPanelRefresh(unittest.TestCase):
    """Test Panel.refresh() directory listing."""

    def test_refresh_lists_directory_contents(self):
        """Refresh should populate entries with directory contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            # Entries should include '..' and the two files
            names = [e.name for e in panel.entries]
            self.assertIn('..', names)
            self.assertIn('file1.txt', names)
            self.assertIn('file2.txt', names)

    def test_refresh_adds_parent_directory_entry(self):
        """Refresh should add '..' as first entry (except at root)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            self.assertEqual(panel.entries[0].name, '..')

    def test_refresh_no_parent_entry_at_root(self):
        """Root directory should not have '..' entry (Issue #51)."""
        panel = Panel('/', width=40, height=20)
        names = [e.name for e in panel.entries]
        self.assertNotIn('..', names)

    def test_refresh_sorts_directories_first(self):
        """Directories should come before files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mixed files and directories
            Path(tmpdir, 'zzzfile.txt').touch()
            Path(tmpdir, 'aaadir').mkdir()
            Path(tmpdir, 'bbbfile.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            entries = [e for e in panel.entries if e.name != '..']

            # Find first file
            first_file_idx = next(
                (i for i, e in enumerate(entries) if not e.is_dir()),
                len(entries)
            )

            # All entries before first file should be directories
            for i in range(first_file_idx):
                self.assertTrue(entries[i].is_dir())

    def test_refresh_sorts_alphabetically_case_insensitive(self):
        """Entries should be sorted alphabetically (case-insensitive)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'Zebra.txt').touch()
            Path(tmpdir, 'apple.txt').touch()
            Path(tmpdir, 'Banana.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            file_names = [e.name for e in panel.entries if e.name != '..']
            self.assertEqual(file_names, ['apple.txt', 'Banana.txt', 'Zebra.txt'])

    def test_refresh_handles_empty_directory(self):
        """Empty directory should only have '..' entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            self.assertEqual(len(panel.entries), 1)
            self.assertEqual(panel.entries[0].name, '..')

    def test_refresh_handles_permission_error(self):
        """Permission error should set error message."""
        with mock.patch.object(Path, 'iterdir', side_effect=PermissionError()):
            panel = Panel('/restricted', width=40, height=20)
            self.assertEqual(panel.error_message, 'Permission denied')

    def test_refresh_handles_file_not_found(self):
        """Non-existent directory should set error message."""
        panel = Panel('/nonexistent/path/that/does/not/exist', width=40, height=20)
        self.assertIsNotNone(panel.error_message)


class TestPanelHeaderText(unittest.TestCase):
    """Test Panel.get_header_text() path display."""

    def test_get_header_text_includes_sort_indicator_and_path(self):
        """Header should include sort indicator and full path when it fits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=100, height=20)
            header = panel.get_header_text()
            # Default sort is name, normal direction = 'vn'
            self.assertTrue(header.startswith('vn '))
            self.assertIn(str(panel.path), header)

    def test_get_header_text_truncates_long_path(self):
        """Long paths should be truncated from the left, preserving indicator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            header = panel.get_header_text(max_width=15)
            # Should start with indicator, then truncated path
            self.assertTrue(header.startswith('vn '))
            self.assertIn('...', header)
            self.assertLessEqual(len(header), 15)

    def test_get_header_text_preserves_end_of_path(self):
        """Truncated header should preserve the end of the path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            path_end = panel.path.name
            header = panel.get_header_text(max_width=20)
            # The end of the path should be visible
            self.assertTrue(header.endswith(path_end) or '...' in header)


class TestPanelResize(unittest.TestCase):
    """Test Panel.resize() dimension updates."""

    def test_resize_updates_dimensions(self):
        """Resize should update width and height."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            panel.resize(60, 30)
            self.assertEqual(panel.width, 60)
            self.assertEqual(panel.height, 30)

    def test_resize_adjusts_scroll_if_needed(self):
        """Resize should adjust scroll to keep cursor visible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files
            for i in range(50):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=30)
            panel.cursor = 25
            panel.scroll_offset = 20

            # Resize to smaller height
            panel.resize(40, 10)

            # Scroll should adjust so cursor is visible
            visible_rows = panel.height - 2
            self.assertGreaterEqual(panel.cursor, panel.scroll_offset)
            self.assertLess(panel.cursor, panel.scroll_offset + visible_rows)


class TestPanelRendering(unittest.TestCase):
    """Test Panel rendering."""

    def test_render_calls_addstr_for_border(self):
        """Render should draw border characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=10)
            mock_win = mock.MagicMock()

            panel.render(mock_win, 0, 0)

            # Verify addstr was called
            self.assertTrue(mock_win.addstr.called)

    def test_render_shows_error_message_when_set(self):
        """Render should display error message if set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=10)
            panel.error_message = 'Test error'
            mock_win = mock.MagicMock()

            panel.render(mock_win, 0, 0)

            # Find call that contains error message
            calls = [str(c) for c in mock_win.addstr.call_args_list]
            self.assertTrue(any('Test error' in c for c in calls))


if __name__ == '__main__':
    unittest.main()
