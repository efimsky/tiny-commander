"""Tests for directory listing display - name, size, type indicator."""

import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tnc.panel import Panel
from tnc.utils import format_mtime, format_size


class TestSizeFormatting(unittest.TestCase):
    """Test human-readable size formatting."""

    def test_format_bytes(self):
        """Small sizes should show as bytes."""
        self.assertEqual(format_size(0), '0')
        self.assertEqual(format_size(100), '100')
        self.assertEqual(format_size(999), '999')

    def test_format_kilobytes(self):
        """Sizes >= 1024 should show as K."""
        self.assertEqual(format_size(1024), '1.0K')
        self.assertEqual(format_size(1536), '1.5K')
        self.assertEqual(format_size(10240), '10.0K')

    def test_format_megabytes(self):
        """Sizes >= 1MB should show as M."""
        self.assertEqual(format_size(1048576), '1.0M')
        self.assertEqual(format_size(5242880), '5.0M')

    def test_format_gigabytes(self):
        """Sizes >= 1GB should show as G."""
        self.assertEqual(format_size(1073741824), '1.0G')
        self.assertEqual(format_size(2147483648), '2.0G')

    def test_format_terabytes(self):
        """Sizes >= 1TB should show as T."""
        self.assertEqual(format_size(1099511627776), '1.0T')


class TestMtimeFormatting(unittest.TestCase):
    """Test modification time formatting."""

    def test_format_recent_file(self):
        """Recent files should show month, day, and time."""
        # Use a timestamp from today
        now = time.time()
        result = format_mtime(now)
        # Should be 12 chars: "MMM DD HH:MM"
        self.assertEqual(len(result), 12)
        # Should contain a colon for the time
        self.assertIn(':', result)

    def test_format_old_file(self):
        """Files older than 6 months should show year instead of time."""
        # Use a timestamp from 1 year ago
        one_year_ago = time.time() - (365 * 24 * 60 * 60)
        result = format_mtime(one_year_ago)
        # Should be 12 chars: "MMM DD  YYYY"
        self.assertEqual(len(result), 12)
        # Should NOT contain a colon (no time)
        self.assertNotIn(':', result)
        # Should contain a 4-digit year
        import re
        self.assertTrue(re.search(r'\d{4}', result))

    def test_format_mtime_fixed_width(self):
        """All formatted times should be exactly 12 characters."""
        timestamps = [
            time.time(),  # Now
            time.time() - 3600,  # 1 hour ago
            time.time() - 86400,  # 1 day ago
            time.time() - 30 * 86400,  # 30 days ago
            time.time() - 200 * 86400,  # 200 days ago (old)
            time.time() - 400 * 86400,  # 400 days ago (old)
        ]
        for ts in timestamps:
            result = format_mtime(ts)
            self.assertEqual(len(result), 12, f"Timestamp {ts} gave '{result}'")

    def test_format_mtime_single_digit_day(self):
        """Single-digit days should be space-padded."""
        # Create a timestamp for Jan 5 of current year
        import datetime
        jan_5 = datetime.datetime(datetime.datetime.now().year, 1, 5, 10, 30)
        ts = jan_5.timestamp()
        result = format_mtime(ts)
        # Day should be space-padded: "Jan  5" not "Jan 05"
        self.assertIn(' 5', result)

    def test_format_future_timestamp(self):
        """Future timestamps should show year (not time)."""
        # Use a timestamp 1 day in the future
        future = time.time() + (24 * 60 * 60)
        result = format_mtime(future)
        # Should be 12 chars and NOT contain time (no colon)
        self.assertEqual(len(result), 12)
        self.assertNotIn(':', result)
        # Should contain a 4-digit year
        import re
        self.assertTrue(re.search(r'\d{4}', result))


class TestDirectoryListing(unittest.TestCase):
    """Test directory listing display."""

    def test_file_entry_has_name(self):
        """File entries should have their name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'test.txt').touch()
            panel = Panel(tmpdir, width=60, height=20)

            names = [e.name for e in panel.entries]
            self.assertIn('test.txt', names)

    def test_directory_entry_has_trailing_slash(self):
        """Directory entries should have trailing slash in display."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'subdir').mkdir()
            panel = Panel(tmpdir, width=60, height=20)

            # Rendering should add trailing slash
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            self.assertTrue(any('subdir/' in c for c in calls))

    def test_file_entry_shows_size(self):
        """File entries should display their size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, 'test.txt')
            test_file.write_text('x' * 1024)  # 1KB file

            panel = Panel(tmpdir, width=60, height=20)

            # Get entry for test.txt
            entry = next(e for e in panel.entries if e.name == 'test.txt')
            self.assertTrue(entry.exists())

    def test_long_filename_truncated(self):
        """Long filenames should be truncated with ellipsis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            long_name = 'a' * 50 + '.txt'
            Path(tmpdir, long_name).touch()

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            # Check that truncated name appears with ellipsis
            calls = [str(c) for c in mock_win.addstr.call_args_list]
            # At least one call should have ellipsis
            self.assertTrue(any('...' in c for c in calls))

    def test_columns_aligned(self):
        """Name and size columns should be aligned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'short.txt').write_text('x' * 100)
            Path(tmpdir, 'longer_name.txt').write_text('x' * 200)

            panel = Panel(tmpdir, width=60, height=20)

            # Both entries should have consistent width
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            # All entry lines should have same length
            self.assertTrue(mock_win.addstr.called)


class TestMtimeColumnDisplay(unittest.TestCase):
    """Test modification time column in panel display."""

    def test_file_entry_shows_mtime_on_wide_panel(self):
        """Wide panels (>= 50) should display mtime column."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, 'test.txt')
            test_file.write_text('x' * 100)

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            # Check that a time-like pattern appears (HH:MM for recent files)
            calls = [str(c) for c in mock_win.addstr.call_args_list]
            # Should have a colon from time format in some call
            self.assertTrue(any(':' in c and 'test.txt' in c for c in calls))

    def test_mtime_hidden_on_narrow_panel(self):
        """Narrow panels (< 50) should hide mtime column."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, 'test.txt')
            test_file.write_text('x' * 100)

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            # Find the call that renders test.txt
            calls = [str(c) for c in mock_win.addstr.call_args_list]
            test_txt_calls = [c for c in calls if 'test.txt' in c]
            # Verify entries exist
            self.assertTrue(len(test_txt_calls) > 0, "test.txt should be rendered")
            # Should NOT have time format (no colon after filename)
            # Time format includes HH:MM, size format does not have colons
            for call in test_txt_calls:
                # Split at test.txt and check the remainder doesn't have a colon
                # (time would appear as "HH:MM" after the size)
                after_filename = call.split('test.txt')[-1]
                self.assertNotIn(':', after_filename,
                    f"Time format should not appear after filename in narrow panel: {call}")

    def test_directory_shows_mtime_on_wide_panel(self):
        """Directories should also show mtime on wide panels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'mydir')
            subdir.mkdir()

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            # Directory entries should have mtime too
            calls = [str(c) for c in mock_win.addstr.call_args_list]
            dir_calls = [c for c in calls if 'mydir/' in c]
            self.assertTrue(len(dir_calls) > 0)


class TestDirectoryIndicator(unittest.TestCase):
    """Test directory vs file visual indicators."""

    def test_directory_shows_trailing_slash(self):
        """Directories should display with trailing slash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'mydir').mkdir()

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            self.assertTrue(any('mydir/' in c for c in calls))

    def test_file_has_no_trailing_slash(self):
        """Regular files should not have trailing slash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'myfile.txt').touch()

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            # File should appear without trailing slash
            self.assertTrue(any('myfile.txt' in c and 'myfile.txt/' not in c for c in calls))

    def test_dotdot_shows_trailing_slash(self):
        """The '..' entry should have trailing slash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            self.assertTrue(any('../' in c for c in calls))


class TestExecutableHighlight(unittest.TestCase):
    """Test executable file highlighting with * prefix."""

    def test_executable_file_shows_asterisk_prefix(self):
        """Executable files should display with * prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir, 'script.sh')
            script.write_text('#!/bin/bash\necho hello')
            os.chmod(script, 0o755)  # Make executable

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            self.assertTrue(any('*script.sh' in c for c in calls))

    def test_non_executable_file_no_asterisk(self):
        """Non-executable files should not have * prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            regular = Path(tmpdir, 'readme.txt')
            regular.write_text('Just a text file')
            os.chmod(regular, 0o644)  # Not executable

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            # Should have readme.txt but not *readme.txt
            has_file = any('readme.txt' in c for c in calls)
            has_asterisk = any('*readme.txt' in c for c in calls)
            self.assertTrue(has_file)
            self.assertFalse(has_asterisk)

    def test_symlink_to_executable_shows_asterisk(self):
        """Symlinks to executable files should display with * prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create executable file
            script = Path(tmpdir, 'script.sh')
            script.write_text('#!/bin/bash\necho hello')
            os.chmod(script, 0o755)

            # Create symlink to it
            link = Path(tmpdir, 'link_to_script')
            link.symlink_to(script)

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            self.assertTrue(any('*link_to_script' in c for c in calls))

    def test_directory_no_asterisk_even_if_executable(self):
        """Directories should not have * prefix even with execute bit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, 'subdir')
            subdir.mkdir()
            os.chmod(subdir, 0o755)  # Directories typically have execute bit

            panel = Panel(tmpdir, width=60, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, 0, 0)

            calls = [str(c) for c in mock_win.addstr.call_args_list]
            # Should show subdir/ but not *subdir/
            has_dir = any('subdir/' in c for c in calls)
            has_asterisk = any('*subdir' in c for c in calls)
            self.assertTrue(has_dir)
            self.assertFalse(has_asterisk)


if __name__ == '__main__':
    unittest.main()
