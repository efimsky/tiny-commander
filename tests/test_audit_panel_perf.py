"""Regression and performance tests for panel, status_bar, and utils audit issues.

Covers:
- #82: Panel.refresh() cursor/scroll clamping and selection pruning
- #107: format_size() PiB/EiB scaling
- #109: Panel.entry_at_point() rejects bottom border clicks
- #117: Eliminating redundant stat/lstat/resolve syscalls in Panel and StatusBar
- #93: Panel._do_create_entry() cursor positioning via created_name
- #110: Panel.apply_search_filter() cursor at '/' (no '..' entry)
- #111: Panel.visible_rows >= 1 and Panel.get_header_text() width invariants
"""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.colors import PAIR_BROKEN_LINK, PAIR_SYMLINK, get_attr
from tnc.file_ops import MkdirResult
from tnc.panel import Panel
from tnc.status_bar import StatusBar
from tnc.utils import format_size


class TestRefreshClampingAndPruning(unittest.TestCase):
    """Issue #82: Panel.refresh() clamps cursor/scroll and prunes vanished selections."""

    def test_refresh_clamps_cursor_when_entries_shrink(self):
        """Cursor past end after external file removal should clamp to last entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ('a.txt', 'b.txt', 'c.txt', 'd.txt', 'e.txt'):
                Path(tmpdir, name).touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = len(panel.entries) - 1  # index 5 ('e.txt')

            for name in ('c.txt', 'd.txt', 'e.txt'):
                Path(tmpdir, name).unlink()

            panel.refresh()

            self.assertEqual(panel.cursor, len(panel.entries) - 1)
            self.assertEqual(panel.entries[panel.cursor].name, 'b.txt')

    def test_refresh_clamps_cursor_when_all_files_removed(self):
        """When all files are removed, cursor clamps to 0 ('..')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'only.txt').touch()
            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 1

            Path(tmpdir, 'only.txt').unlink()
            panel.refresh()

            self.assertEqual(panel.cursor, 0)
            self.assertEqual(len(panel.entries), 1)

    def test_refresh_clamps_scroll_offset_and_keeps_cursor_visible(self):
        """Scroll offset must clamp to valid range and keep cursor visible after shrink."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(20):
                Path(tmpdir, f'f{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)  # visible_rows == 8, 21 entries
            panel.cursor = 20
            panel.scroll_offset = 13

            # Delete 9 files -> 12 entries remain (max_scroll = 12 - 8 = 4)
            for i in range(11, 20):
                Path(tmpdir, f'f{i:02d}.txt').unlink()

            panel.refresh()

            self.assertEqual(panel.cursor, len(panel.entries) - 1)
            max_scroll = max(0, len(panel.entries) - panel.visible_rows)
            self.assertGreaterEqual(panel.scroll_offset, 0)
            self.assertLessEqual(panel.scroll_offset, max_scroll)
            self.assertGreaterEqual(panel.cursor, panel.scroll_offset)
            self.assertLess(panel.cursor, panel.scroll_offset + panel.visible_rows)

    def test_refresh_prunes_vanished_entries_from_selected(self):
        """Deleted or missing filenames must be pruned from panel.selected on refresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'keep.txt').touch()
            Path(tmpdir, 'gone.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.selected = {'keep.txt', 'gone.txt', 'never_existed.txt'}

            Path(tmpdir, 'gone.txt').unlink()
            panel.refresh()

            self.assertEqual(panel.selected, {'keep.txt'})


class TestFormatSizeLargeUnits(unittest.TestCase):
    """Issue #107: format_size() handles PiB and EiB without 1024x overflow."""

    def test_format_size_petabytes(self):
        """1024**5 bytes should format as '1.0P', not '1024.0P'."""
        self.assertEqual(format_size(1024**5), '1.0P')
        self.assertEqual(format_size(5 * 1024**5), '5.0P')

    def test_format_size_exabytes(self):
        """1024**6 bytes should format as '1.0E'."""
        self.assertEqual(format_size(1024**6), '1.0E')

    def test_format_size_terabytes_boundary(self):
        """Values just below 1 PiB still format in TB."""
        self.assertEqual(format_size(1023 * 1024**4), '1023.0T')


class TestEntryAtPointBottomBorder(unittest.TestCase):
    """Issue #109: Clicking bottom border row must return None."""

    def test_entry_at_point_bottom_border_returns_none(self):
        """Clicking the bottom border must not select off-screen entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(25):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)  # visible_rows == 8 (rows 1..8)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Row 8 is the last visible entry row (index 7)
            self.assertEqual(panel.entry_at_point(10, 8), 7)
            # Row 9 is the bottom border (render_height - 1)
            self.assertIsNone(panel.entry_at_point(10, 9))

    def test_entry_at_point_bottom_border_with_offset_returns_none(self):
        """Bottom border check must work when render_y > 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(25):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=5, y=3)

            # Entry rows: y=4..11; bottom border: y=12
            self.assertEqual(panel.entry_at_point(10, 11), 7)
            self.assertIsNone(panel.entry_at_point(10, 12))

    def test_entry_at_point_tiny_height_returns_none(self):
        """Panel with height <= 2 has no entry rows; all clicks return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()
            panel = Panel(tmpdir, width=40, height=2)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            self.assertIsNone(panel.entry_at_point(10, 0))
            self.assertIsNone(panel.entry_at_point(10, 1))


class TestSyscallPerformance(unittest.TestCase):
    """Issue #117: Avoid redundant stat/lstat/resolve calls in Panel and StatusBar."""

    def test_get_cached_dir_size_empty_cache_zero_syscalls(self):
        """When _dir_size_cache is empty, get_cached_dir_size makes 0 resolve/stat calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'sub').mkdir()
            panel = Panel(tmpdir, width=40, height=20)

            orig_resolve = Path.resolve
            orig_stat = Path.stat
            with mock.patch.object(Path, 'resolve', autospec=True, side_effect=orig_resolve) as mock_resolve, \
                 mock.patch.object(Path, 'stat', autospec=True, side_effect=orig_stat) as mock_stat:
                result = panel.get_cached_dir_size('sub')

            self.assertIsNone(result)
            self.assertEqual(mock_resolve.call_count, 0)
            self.assertEqual(mock_stat.call_count, 0)

    def test_get_cached_dir_size_hit_non_symlink_avoids_resolve(self):
        """Cache hit on a regular dir avoids Path.resolve()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = Path(tmpdir, 'sub')
            sub.mkdir()
            (sub / 'data.txt').write_text('hello')
            panel = Panel(tmpdir, width=40, height=20)
            expected = panel.measure_dir_size('sub')

            orig_resolve = Path.resolve
            with mock.patch.object(Path, 'resolve', autospec=True, side_effect=orig_resolve) as mock_resolve:
                cached = panel.get_cached_dir_size('sub')

            self.assertEqual(cached, expected)
            self.assertEqual(mock_resolve.call_count, 0)

    def test_get_cached_dir_size_miss_non_symlink_avoids_resolve(self):
        """Cache miss on an unmeasured regular dir also avoids Path.resolve()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sub1 = Path(tmpdir, 'sub1')
            sub1.mkdir()
            (sub1 / 'data.txt').write_text('hello')
            Path(tmpdir, 'sub2').mkdir()

            panel = Panel(tmpdir, width=40, height=20)
            panel.measure_dir_size('sub1')

            orig_resolve = Path.resolve
            with mock.patch.object(Path, 'resolve', autospec=True, side_effect=orig_resolve) as mock_resolve:
                cached = panel.get_cached_dir_size('sub2')

            self.assertIsNone(cached)
            self.assertEqual(mock_resolve.call_count, 0)

    def test_get_cached_dir_size_symlink_to_measured_dir_hits(self):
        """Symlink to a measured directory still finds the cached size via resolve fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real_dir = Path(tmpdir, 'real')
            real_dir.mkdir()
            (real_dir / 'data.txt').write_text('hello')
            link_dir = Path(tmpdir, 'link')
            link_dir.symlink_to(real_dir)

            panel = Panel(tmpdir, width=40, height=20)
            expected = panel.measure_dir_size('real')

            self.assertEqual(panel.get_cached_dir_size('link'), expected)

    def test_get_display_entries_minimal_syscalls_regular_entries(self):
        """Each non-symlink entry should do exactly 1 lstat, 0 stat, 0 resolve."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                (Path(tmpdir) / f'file{i}.txt').write_text('x')
            for i in range(2):
                (Path(tmpdir) / f'dir{i}').mkdir()

            panel = Panel(tmpdir, width=60, height=20)

            orig_lstat = Path.lstat
            orig_stat = Path.stat
            orig_resolve = Path.resolve
            with mock.patch.object(Path, 'lstat', autospec=True, side_effect=orig_lstat) as mock_lstat, \
                 mock.patch.object(Path, 'stat', autospec=True, side_effect=orig_stat) as mock_stat, \
                 mock.patch.object(Path, 'resolve', autospec=True, side_effect=orig_resolve) as mock_resolve:
                entries = panel.get_display_entries()

            self.assertEqual(len(entries), 8)  # '..' + 2 dirs + 5 files
            self.assertEqual(mock_resolve.call_count, 0)
            self.assertEqual(mock_lstat.call_count, 7)  # 1 per non-'..' entry
            follow_stat_calls = [
                c for c in mock_stat.call_args_list
                if c.kwargs.get('follow_symlinks', True)
            ]
            self.assertEqual(len(follow_stat_calls), 1)   # Only for '..' parent mtime

    def test_get_display_entries_symlink_calls_stat_once_per_link(self):
        """Valid and broken symlinks should each call stat() only once, not twice."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir, 'target.sh')
            target.write_text('#!/bin/sh\n')
            target.chmod(0o755)
            valid_link = Path(tmpdir, 'valid_link')
            valid_link.symlink_to(target)
            broken_link = Path(tmpdir, 'broken_link')
            broken_link.symlink_to('/nonexistent/target/path')

            panel = Panel(tmpdir, width=60, height=20)

            stat_targets: list[str] = []
            orig_stat = Path.stat

            def tracking_stat(self_path, *args, **kwargs):
                if kwargs.get('follow_symlinks', True):
                    stat_targets.append(self_path.name)
                return orig_stat(self_path, *args, **kwargs)

            with mock.patch.object(Path, 'stat', autospec=True, side_effect=tracking_stat):
                entries = panel.get_display_entries()

            by_name = {e.name: e for e in entries}
            self.assertEqual(stat_targets.count('valid_link'), 1)
            self.assertEqual(stat_targets.count('broken_link'), 1)
            self.assertEqual(stat_targets.count('target.sh'), 0)
            self.assertEqual(by_name['valid_link'].display_name, '*valid_link')
            self.assertEqual(by_name['valid_link'].attr, get_attr(PAIR_SYMLINK))
            self.assertEqual(by_name['broken_link'].attr, get_attr(PAIR_BROKEN_LINK))

    def test_refresh_size_and_date_sort_reuses_scandir_stat(self):
        """Sorting by size or date in refresh() should use DirEntry.stat(), not Path.stat()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f_small = Path(tmpdir, 'small.txt')
            f_small.write_text('a')
            os.utime(f_small, (1000, 1000))
            f_large = Path(tmpdir, 'large.txt')
            f_large.write_text('a' * 100)
            os.utime(f_large, (2000, 2000))

            panel = Panel(tmpdir, width=60, height=20)
            orig_stat = Path.stat

            with mock.patch.object(Path, 'stat', autospec=True, side_effect=orig_stat) as mock_stat:
                panel.sort_by('size')
                self.assertEqual(mock_stat.call_count, 0)
                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['large.txt', 'small.txt'])

                panel.sort_by('date')
                self.assertEqual(mock_stat.call_count, 0)
                names = [e.name for e in panel.entries if e.name != '..']
                self.assertEqual(names, ['large.txt', 'small.txt'])

    def test_external_file_edit_visible_without_refresh(self):
        """No stale cross-render stat caching: external size edits show immediately on render."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir, 'mutable.txt')
            file_path.write_text('hi')

            panel = Panel(tmpdir, width=60, height=20)
            before = next(e for e in panel.get_display_entries() if e.name == 'mutable.txt')
            self.assertEqual(before.size_str, '2')

            file_path.write_text('hello world!')
            after = next(e for e in panel.get_display_entries() if e.name == 'mutable.txt')
            self.assertEqual(after.size_str, '12')

    def test_status_bar_render_skips_resolve_and_stat_when_cache_empty(self):
        """StatusBar.render() on a real panel dir/file does 1 lstat, 0 stat, 0 resolve."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'subdir').mkdir()
            (Path(tmpdir) / 'alpha.txt').write_text('abc')
            panel = Panel(tmpdir, width=80, height=20)
            status_bar = StatusBar()
            win = mock.MagicMock()

            orig_lstat = Path.lstat
            orig_stat = Path.stat
            orig_resolve = Path.resolve

            for idx in (1, 2):  # 1 = subdir, 2 = alpha.txt
                panel.cursor = idx
                with mock.patch.object(Path, 'lstat', autospec=True, side_effect=orig_lstat) as mock_lstat, \
                     mock.patch.object(Path, 'stat', autospec=True, side_effect=orig_stat) as mock_stat, \
                     mock.patch.object(Path, 'resolve', autospec=True, side_effect=orig_resolve) as mock_resolve:
                    status_bar.render(win, 22, 80, panel)

                follow_stat_calls = [
                    c for c in mock_stat.call_args_list
                    if c.kwargs.get('follow_symlinks', True)
                ]
                self.assertEqual(mock_lstat.call_count, 1)
                self.assertEqual(len(follow_stat_calls), 0)
                self.assertEqual(mock_resolve.call_count, 0)


class TestDoCreateEntryUsesCreatedName(unittest.TestCase):
    """Issue #93: Panel._do_create_entry finds cursor index via result.created_name."""

    def test_create_directory_with_whitespace_positions_cursor_on_trimmed_name(self):
        """Creating '  newdir  ' strips name; cursor should move to 'newdir'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'aaa').mkdir()
            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 0

            result = panel.create_directory('  newdir  ')

            self.assertTrue(result.success)
            self.assertEqual(result.created_name, 'newdir')
            self.assertEqual(panel.entries[panel.cursor].name, 'newdir')

    def test_do_create_entry_prefers_created_name_over_raw_name(self):
        """_do_create_entry looks up result.created_name when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'aaa').touch()
            Path(tmpdir, 'canonical').mkdir()
            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 0

            create_func = mock.MagicMock(
                return_value=MkdirResult(success=True, created_name='canonical')
            )
            panel._do_create_entry('raw_input', create_func)

            self.assertEqual(panel.entries[panel.cursor].name, 'canonical')


class TestApplySearchFilterAtRoot(unittest.TestCase):
    """Issue #110: Quick search at '/' (no '..' entry) selects index 0."""

    def test_apply_search_filter_without_dotdot_selects_first_match(self):
        """At '/', cursor should land on index 0 when multiple matches exist."""
        panel = Panel('/', width=40, height=20)
        panel._all_entries = [Path('/apple'), Path('/apricot'), Path('/berry')]
        panel.search_mode = True
        panel.search_text = 'ap'

        panel.apply_search_filter()

        self.assertEqual([e.name for e in panel.entries], ['apple', 'apricot'])
        self.assertEqual(panel.cursor, 0)

    def test_apply_search_filter_with_dotdot_selects_index_one(self):
        """In non-root dirs with '..', cursor skips '..' and lands on index 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'alpha.txt').touch()
            Path(tmpdir, 'apricot.txt').touch()
            panel = Panel(tmpdir, width=40, height=20)

            panel.start_search()
            panel.handle_search_char('a')

            self.assertEqual(panel.entries[0].name, '..')
            self.assertEqual(panel.cursor, 1)
            self.assertEqual(panel.entries[panel.cursor].name, 'alpha.txt')


class TestTinyPanelVisibleRowsAndHeaderText(unittest.TestCase):
    """Issue #111: visible_rows >= 1 and get_header_text() respects max_width."""

    def test_visible_rows_clamped_to_at_least_one(self):
        """visible_rows should never be <= 0 even on tiny panel heights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for height, expected in ((0, 1), (1, 1), (2, 1), (3, 1), (10, 8)):
                panel = Panel(tmpdir, width=40, height=height)
                self.assertEqual(panel.visible_rows, expected)

    def test_page_navigation_works_on_height_two(self):
        """Page down/up on height=2 must move forward/backward by 1, not reverse."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'a.txt').touch()
            Path(tmpdir, 'b.txt').touch()
            panel = Panel(tmpdir, width=40, height=2)

            panel.navigate_page_down()
            self.assertEqual(panel.cursor, 1)
            panel.navigate_page_up()
            self.assertEqual(panel.cursor, 0)

    def test_get_header_text_respects_all_max_widths(self):
        """len(get_header_text(max_width=w)) <= w for all w >= 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deep = Path(tmpdir) / 'very' / 'deep' / 'nested' / 'folder'
            deep.mkdir(parents=True)
            panel = Panel(str(deep), width=40, height=20)

            self.assertEqual(panel.get_header_text(max_width=0), '')
            self.assertEqual(panel.get_header_text(max_width=1), 'v')
            self.assertEqual(panel.get_header_text(max_width=2), 'vn')
            self.assertEqual(panel.get_header_text(max_width=3), 'vn')
            self.assertEqual(panel.get_header_text(max_width=4), 'vn r')
            self.assertEqual(panel.get_header_text(max_width=6), 'vn der')
            self.assertEqual(panel.get_header_text(max_width=7), 'vn ...r')

            for w in range(0, 30):
                header = panel.get_header_text(max_width=w)
                self.assertLessEqual(
                    len(header), w,
                    f'Header {header!r} (len={len(header)}) exceeded max_width={w}',
                )


if __name__ == '__main__':
    unittest.main()
