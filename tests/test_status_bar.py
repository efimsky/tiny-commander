"""Tests for StatusBar class."""

import stat
import time
import unittest
from pathlib import Path
from unittest import mock


def create_mock_panel(
    cursor: int = 0,
    entries_count: int = 10,
    selected_count: int = 0,
    is_active: bool = True,
    search_mode: bool = False,
    search_text: str = '',
    current_name: str = 'file.txt',
    current_size: int = 1024,
    current_mode: int = stat.S_IFREG | 0o644,
    current_mtime: float | None = None,
    is_directory: bool = False,
) -> mock.MagicMock:
    """Create a mock Panel object for testing."""
    panel = mock.MagicMock()
    panel.cursor = cursor
    panel.is_active = is_active
    panel.search_mode = search_mode
    panel.search_text = search_text
    panel.selected = set(f'file{i}.txt' for i in range(selected_count))

    # Create mock path that returns mock stat
    mock_path = mock.MagicMock(spec=Path)
    mock_file_path = mock.MagicMock()
    mock_stat_result = mock.MagicMock()
    mock_stat_result.st_size = current_size
    mock_stat_result.st_mode = current_mode
    mock_stat_result.st_mtime = current_mtime if current_mtime is not None else time.time()
    mock_file_path.lstat.return_value = mock_stat_result
    mock_file_path.is_dir.return_value = is_directory
    mock_path.__truediv__ = mock.MagicMock(return_value=mock_file_path)

    # Create mock entries
    entries = []
    for i in range(entries_count):
        entry = mock.MagicMock()
        entry.name = f'file{i}.txt'
        entries.append(entry)

    # Set up current entry
    if entries_count > 0 and cursor < entries_count:
        entries[cursor].name = current_name

    panel.entries = entries
    panel.path = mock_path
    # By default, no cached directory sizes
    panel.get_cached_dir_size = mock.MagicMock(return_value=None)

    return panel


class TestStatusBarRender(unittest.TestCase):
    """Test StatusBar rendering."""

    def test_render_basic_file_info(self):
        """Status bar should render file name, size, and permissions."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(
            cursor=5,
            entries_count=23,
            current_name='readme.txt',
            current_size=4096,
            current_mode=stat.S_IFREG | 0o644,
        )

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        # Verify addstr was called
        mock_win.addstr.assert_called()
        call_args = mock_win.addstr.call_args[0]

        # Check position
        self.assertEqual(call_args[0], 22)  # y position
        self.assertEqual(call_args[1], 0)   # x position

        # Check content contains expected elements
        content = call_args[2]
        self.assertIn('[Left]', content)
        self.assertIn('readme.txt', content)
        self.assertIn('4.0K', content)
        self.assertIn('-rw-r--r--', content)
        self.assertIn('6 of 23', content)  # cursor is 0-indexed, display is 1-indexed

    def test_render_right_panel_indicator(self):
        """Status bar should show [Right] for inactive left panel."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        # When left panel is not active, we're showing right panel
        panel = create_mock_panel(is_active=True)

        # Create a mock for the "other" panel scenario
        # The status bar should detect based on which panel is passed
        status_bar = StatusBar()

        # Test with is_left=False
        status_bar.render(mock_win, 22, 80, panel, is_left=False)

        content = mock_win.addstr.call_args[0][2]
        self.assertIn('[Right]', content)

    def test_render_with_selection_count(self):
        """Status bar should show selection count when files are selected."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(
            cursor=5,
            entries_count=23,
            selected_count=3,
        )

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        self.assertIn('3 selected', content)

    def test_render_no_selection_count_when_zero(self):
        """Status bar should not show selection count when nothing selected."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(selected_count=0)

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        self.assertNotIn('selected', content)

    def test_render_search_mode(self):
        """Status bar should show search text in search mode."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(
            search_mode=True,
            search_text='test',
        )

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        self.assertIn('/test', content)

    def test_render_directory_permissions(self):
        """Status bar should show directory permissions correctly."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(
            current_name='projects',
            current_mode=stat.S_IFDIR | 0o755,
            is_directory=True,
        )

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        self.assertIn('drwxr-xr-x', content)

    def test_render_truncates_long_filename(self):
        """Status bar should truncate long filenames."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        long_name = 'a' * 100 + '.txt'
        panel = create_mock_panel(current_name=long_name)

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        # Content should fit in 80 chars
        self.assertLessEqual(len(content), 80)

    def test_render_narrow_terminal(self):
        """Status bar should handle narrow terminals gracefully."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(current_name='very_long_filename_that_should_be_truncated.txt')

        status_bar = StatusBar()
        # Width less than 50 (the reserved space for other elements)
        status_bar.render(mock_win, 22, 40, panel)

        # Should not raise an exception
        mock_win.addstr.assert_called()
        content = mock_win.addstr.call_args[0][2]
        # Content should fit in 40 chars
        self.assertLessEqual(len(content), 40)
        # Filename should still be partially visible (min 10 chars guaranteed)
        self.assertIn('very_lo...', content)

    def test_render_empty_panel(self):
        """Status bar should handle empty panel gracefully."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(entries_count=0)
        panel.entries = []

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        # Should not raise an exception
        mock_win.addstr.assert_called()

    def test_render_parent_directory(self):
        """Status bar should handle '..' entry specially."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(current_name='..')

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        self.assertIn('..', content)

    def test_render_oserror_shows_placeholder(self):
        """Status bar should show placeholders when stat fails."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(current_name='broken_file.txt')

        # Make lstat raise OSError
        panel.path.__truediv__.return_value.lstat.side_effect = OSError("Permission denied")

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        self.assertIn('?', content)
        self.assertIn('??????????', content)

    def test_render_shows_mtime(self):
        """Status bar should show modification time for files."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        # Use current time so format_mtime returns "MMM DD HH:MM" with colon
        panel = create_mock_panel(
            cursor=5,
            entries_count=23,
            current_name='readme.txt',
            current_size=4096,
            current_mtime=time.time(),
        )

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        # Recent files show time with colon (HH:MM)
        self.assertIn(':', content)

    def test_render_mtime_hidden_on_narrow_terminal(self):
        """Status bar should hide mtime on narrow terminals."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(
            current_name='file.txt',
            current_mtime=time.time(),
        )

        status_bar = StatusBar()
        # Use narrow width (< 70)
        status_bar.render(mock_win, 22, 60, panel)

        content = mock_win.addstr.call_args[0][2]
        # On narrow terminal, mtime should be hidden
        # The format "HH:MM" contains a colon, which should not appear
        # (unless it's in the filename, which it isn't here)
        self.assertNotIn(':', content)

    def test_render_parent_directory_no_mtime(self):
        """Status bar should not show mtime for '..' entry."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(
            current_name='..',
            current_mtime=time.time(),
        )

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        # '..' should not have mtime (no colon from time format)
        self.assertNotIn(':', content)

    def test_render_oserror_shows_mtime_placeholder(self):
        """Status bar should show mtime placeholder when stat fails."""
        from tnc.status_bar import StatusBar

        mock_win = mock.MagicMock()
        panel = create_mock_panel(current_name='broken_file.txt')

        # Make lstat raise OSError
        panel.path.__truediv__.return_value.lstat.side_effect = OSError("Permission denied")

        status_bar = StatusBar()
        status_bar.render(mock_win, 22, 80, panel)

        content = mock_win.addstr.call_args[0][2]
        # Should have 12-char mtime placeholder (matching format_mtime width)
        self.assertIn('????????????', content)


class TestStatusBarFormatting(unittest.TestCase):
    """Test StatusBar formatting helpers."""

    def test_format_position(self):
        """Position should be formatted as 'X of Y'."""
        from tnc.status_bar import StatusBar

        status_bar = StatusBar()
        result = status_bar._format_position(5, 23)
        self.assertEqual(result, '6 of 23')  # 0-indexed to 1-indexed

    def test_format_position_single_entry(self):
        """Position with single entry."""
        from tnc.status_bar import StatusBar

        status_bar = StatusBar()
        result = status_bar._format_position(0, 1)
        self.assertEqual(result, '1 of 1')


if __name__ == '__main__':
    unittest.main()
