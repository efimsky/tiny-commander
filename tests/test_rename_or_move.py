"""Tests for F6 Rename/Move (issue #76) and move_single_entry."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.app import App
from tnc.file_ops import MoveResult, move_single_entry


def _make_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock stdscr that uses Enter as a safe default dialog key."""
    stdscr = mock.MagicMock()
    stdscr.getmaxyx.return_value = (rows, cols)
    stdscr.getch.return_value = ord('\n')
    return stdscr


class TestMoveSingleEntry(unittest.TestCase):
    """Unit tests for tnc.file_ops.move_single_entry."""

    def test_rename_file_in_place(self) -> None:
        """Same parent directory with different basename renames file in place."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'old.txt')
            dst = Path(tmpdir, 'new.txt')
            src.write_text('hello')

            result = move_single_entry(src, dst)

            self.assertTrue(result.success)
            self.assertEqual(result.moved_files, ['old.txt'])
            self.assertFalse(src.exists())
            self.assertEqual(dst.read_text(), 'hello')

    def test_rename_directory_in_place(self) -> None:
        """Same parent directory with different basename renames directory in place."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'olddir')
            dst = Path(tmpdir, 'newdir')
            src.mkdir()
            (src / 'inside.txt').write_text('nested')

            result = move_single_entry(src, dst)

            self.assertTrue(result.success)
            self.assertEqual(result.moved_files, ['olddir'])
            self.assertFalse(src.exists())
            self.assertTrue(dst.is_dir())
            self.assertEqual((dst / 'inside.txt').read_text(), 'nested')

    def test_move_different_directory_same_basename(self) -> None:
        """Different directory with same basename moves file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir, 'src')
            dst_dir = Path(tmpdir, 'dst')
            src_dir.mkdir()
            dst_dir.mkdir()
            src = src_dir / 'file.txt'
            dst = dst_dir / 'file.txt'
            src.write_text('data')

            result = move_single_entry(src, dst)

            self.assertTrue(result.success)
            self.assertEqual(result.moved_files, ['file.txt'])
            self.assertFalse(src.exists())
            self.assertEqual(dst.read_text(), 'data')

    def test_move_and_rename_different_directory_and_basename(self) -> None:
        """Different directory and basename moves and renames in one step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir, 'src')
            dst_dir = Path(tmpdir, 'dst')
            src_dir.mkdir()
            dst_dir.mkdir()
            src = src_dir / 'orig.txt'
            dst = dst_dir / 'renamed.txt'
            src.write_text('payload')

            result = move_single_entry(src, dst)

            self.assertTrue(result.success)
            self.assertEqual(result.moved_files, ['orig.txt'])
            self.assertFalse(src.exists())
            self.assertEqual(dst.read_text(), 'payload')

    def test_same_path_returns_cancelled_noop(self) -> None:
        """Unchanged source and destination returns cancelled no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'same.txt')
            src.write_text('keep')

            result = move_single_entry(src, src)

            self.assertFalse(result.success)
            self.assertTrue(result.cancelled)
            self.assertEqual(result.error, '')
            self.assertEqual(src.read_text(), 'keep')

    def test_case_only_rename_real_case_insensitive_fs(self) -> None:
        """Case-only rename on case-insensitive FS succeeds without overwrite prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'Foo.txt')
            src.write_text('case-test')
            dst = Path(tmpdir, 'foo.txt')
            if not dst.exists():
                self.skipTest('Filesystem is case-sensitive')

            prompt = mock.Mock(return_value=False)
            result = move_single_entry(src, dst, confirm_overwrite=prompt)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(result.moved_files, ['Foo.txt'])
            prompt.assert_not_called()
            self.assertIn('foo.txt', os.listdir(tmpdir))
            self.assertNotIn('Foo.txt', os.listdir(tmpdir))
            self.assertEqual(dst.read_text(), 'case-test')

    def test_case_only_rename_mocked_case_insensitive_regular_file(self) -> None:
        """Simulated case-insensitive case-only rename uses os.rename and skips leftover check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'Foo.txt')
            src.write_text('content')
            dst = Path(tmpdir, 'foo.txt')
            src_stat = src.lstat()

            real_exists = Path.exists
            real_lstat = Path.lstat

            def fake_exists(self_path: Path) -> bool:
                if self_path.name == 'foo.txt' and self_path.parent == src.parent.resolve():
                    return True
                return real_exists(self_path)

            def fake_lstat(self_path: Path) -> os.stat_result:
                if self_path.name == 'foo.txt' and self_path.parent == src.parent.resolve():
                    return src_stat
                return real_lstat(self_path)

            prompt = mock.Mock(return_value=False)
            with mock.patch.object(Path, 'exists', fake_exists), \
                 mock.patch.object(Path, 'lstat', fake_lstat), \
                 mock.patch('tnc.file_ops.os.rename') as mock_rename:
                result = move_single_entry(src, dst, confirm_overwrite=prompt)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            prompt.assert_not_called()
            mock_rename.assert_called_once()

    def test_case_only_rename_mocked_broken_symlink(self) -> None:
        """Case-only rename of a broken symlink on case-insensitive FS succeeds cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'BrokenLink')
            src.symlink_to('/nonexistent/target')
            dst = Path(tmpdir, 'brokenlink')
            src_lstat = src.lstat()

            real_is_symlink = Path.is_symlink
            real_lstat = Path.lstat

            def fake_is_symlink(self_path: Path) -> bool:
                if self_path.name == 'brokenlink' and self_path.parent == src.parent.resolve():
                    return True
                return real_is_symlink(self_path)

            def fake_lstat(self_path: Path) -> os.stat_result:
                if self_path.name == 'brokenlink' and self_path.parent == src.parent.resolve():
                    return src_lstat
                return real_lstat(self_path)

            prompt = mock.Mock(return_value=False)
            with mock.patch.object(Path, 'is_symlink', fake_is_symlink), \
                 mock.patch.object(Path, 'lstat', fake_lstat), \
                 mock.patch('tnc.file_ops.os.rename') as mock_rename:
                result = move_single_entry(src, dst, confirm_overwrite=prompt)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            prompt.assert_not_called()
            mock_rename.assert_called_once()

    def test_overwrite_declined_cancels_and_leaves_files_untouched(self) -> None:
        """If confirm_overwrite returns False, operation cancels without mutating disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'a.txt')
            dst = Path(tmpdir, 'b.txt')
            src.write_text('source')
            dst.write_text('existing')

            prompt = mock.Mock(return_value=False)
            result = move_single_entry(src, dst, confirm_overwrite=prompt)

            prompt.assert_called_once()
            self.assertFalse(result.success)
            self.assertTrue(result.cancelled)
            self.assertEqual(src.read_text(), 'source')
            self.assertEqual(dst.read_text(), 'existing')

    def test_overwrite_confirmed_replaces_file(self) -> None:
        """If confirm_overwrite returns True, destination file is overwritten."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'a.txt')
            dst = Path(tmpdir, 'b.txt')
            src.write_text('new-data')
            dst.write_text('old-data')

            result = move_single_entry(src, dst, confirm_overwrite=lambda _p: True)

            self.assertTrue(result.success)
            self.assertFalse(src.exists())
            self.assertEqual(dst.read_text(), 'new-data')

    def test_overwrite_confirmed_replaces_directory_without_nesting(self) -> None:
        """Overwriting existing directory replaces it directly instead of nesting inside."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'src_dir')
            dst = Path(tmpdir, 'dst_dir')
            src.mkdir()
            (src / 'fresh.txt').write_text('fresh')
            dst.mkdir()
            (dst / 'stale.txt').write_text('stale')

            result = move_single_entry(src, dst, confirm_overwrite=lambda _p: True)

            self.assertTrue(result.success)
            self.assertFalse(src.exists())
            self.assertTrue((dst / 'fresh.txt').exists())
            self.assertFalse((dst / 'stale.txt').exists())
            self.assertFalse((dst / 'src_dir').exists())

    def test_overwrite_file_over_symlink_preserves_symlink_target(self) -> None:
        """Overwriting a symlink destination replaces only the symlink, not its target."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir, 'target.txt')
            target.write_text('untouched')
            src = Path(tmpdir, 'src.txt')
            src.write_text('replacement')
            dst = Path(tmpdir, 'link.txt')
            dst.symlink_to(target)

            result = move_single_entry(src, dst, confirm_overwrite=lambda _p: True)

            self.assertTrue(result.success)
            self.assertFalse(src.exists())
            self.assertFalse(dst.is_symlink())
            self.assertEqual(dst.read_text(), 'replacement')
            self.assertEqual(target.read_text(), 'untouched')

    def test_overwrite_rollback_restores_destination_on_failure(self) -> None:
        """If shutil.move raises during confirmed overwrite, sidecar rollback restores dest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'src.txt')
            dst = Path(tmpdir, 'dst.txt')
            src.write_text('new')
            dst.write_text('original')

            with mock.patch('tnc.file_ops.shutil.move', side_effect=OSError('disk full')):
                result = move_single_entry(src, dst, confirm_overwrite=lambda _p: True)

            self.assertFalse(result.success)
            self.assertEqual(src.read_text(), 'new')
            self.assertEqual(dst.read_text(), 'original')

    def test_type_mismatch_refuses_without_prompting(self) -> None:
        """Incompatible source/dest types are refused without invoking confirm_overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # file over directory
            src_file = Path(tmpdir, 'f.txt')
            src_file.write_text('file')
            dst_dir = Path(tmpdir, 'd')
            dst_dir.mkdir()
            (dst_dir / 'keep.txt').write_text('keep')

            prompt = mock.Mock(return_value=True)
            res1 = move_single_entry(src_file, dst_dir, confirm_overwrite=prompt)
            self.assertFalse(res1.success)
            self.assertIn('refusing to move', res1.error.lower())
            prompt.assert_not_called()
            self.assertTrue((dst_dir / 'keep.txt').exists())

            # directory over file
            src_dir = Path(tmpdir, 'src_d')
            src_dir.mkdir()
            dst_file = Path(tmpdir, 'dst_f.txt')
            dst_file.write_text('stay')
            res2 = move_single_entry(src_dir, dst_file, confirm_overwrite=prompt)
            self.assertFalse(res2.success)
            self.assertIn('refusing to move', res2.error.lower())
            prompt.assert_not_called()
            self.assertEqual(dst_file.read_text(), 'stay')

            # symlink over directory (external canary untouched)
            canary = Path(tmpdir, 'canary.txt')
            canary.write_text('canary')
            src_link = Path(tmpdir, 'slink')
            src_link.symlink_to(canary)
            res3 = move_single_entry(src_link, dst_dir, confirm_overwrite=prompt)
            self.assertFalse(res3.success)
            self.assertIn('refusing to move', res3.error.lower())
            prompt.assert_not_called()
            self.assertEqual(canary.read_text(), 'canary')
            self.assertTrue(src_link.is_symlink())

    def test_broken_symlink_at_dest_replaced_without_prompt(self) -> None:
        """Distinct broken symlink at destination is unlinked and replaced."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'src.txt')
            src.write_text('hello')
            dst = Path(tmpdir, 'broken')
            dst.symlink_to('/nonexistent/missing')

            prompt = mock.Mock(return_value=False)
            result = move_single_entry(src, dst, confirm_overwrite=prompt)

            self.assertTrue(result.success)
            prompt.assert_not_called()
            self.assertFalse(src.exists())
            self.assertEqual(dst.read_text(), 'hello')

    def test_move_directory_into_own_subdirectory_fails(self) -> None:
        """Moving a directory into its own subdirectory is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir, 'parent')
            sub = parent / 'sub'
            sub.mkdir(parents=True)

            result = move_single_entry(parent, sub / 'moved_parent')

            self.assertFalse(result.success)
            self.assertIn('subdirectory', result.error.lower())
            self.assertTrue(parent.is_dir())

    def test_nonexistent_dest_parent_fails(self) -> None:
        """Nonexistent destination parent directory reports clear error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'file.txt')
            src.write_text('x')
            dst = Path(tmpdir, 'no_such_dir', 'file.txt')

            result = move_single_entry(src, dst)

            self.assertFalse(result.success)
            self.assertIn('does not exist', result.error.lower())
            self.assertTrue(src.exists())

    def test_dest_parent_not_directory_fails(self) -> None:
        """Destination parent that is a regular file reports clear error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'file.txt')
            src.write_text('x')
            blocker = Path(tmpdir, 'not_a_dir')
            blocker.write_text('blocker')
            dst = blocker / 'file.txt'

            result = move_single_entry(src, dst)

            self.assertFalse(result.success)
            self.assertIn('not a directory', result.error.lower())
            self.assertTrue(src.exists())

    def test_missing_source_fails(self) -> None:
        """Missing source file reports File not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'missing.txt')
            dst = Path(tmpdir, 'dest.txt')

            result = move_single_entry(src, dst)

            self.assertFalse(result.success)
            self.assertIn('file not found', result.error.lower())

    def test_move_symlink_preserves_symlink_and_target(self) -> None:
        """Moving/renaming a symlink preserves symlink identity and leaves target intact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir, 'target.txt')
            target.write_text('original')
            src = Path(tmpdir, 'link1')
            src.symlink_to(target)
            dst = Path(tmpdir, 'link2')

            result = move_single_entry(src, dst)

            self.assertTrue(result.success)
            self.assertFalse(src.is_symlink())
            self.assertTrue(dst.is_symlink())
            self.assertEqual(os.readlink(dst), str(target))
            self.assertEqual(target.read_text(), 'original')

    def test_cross_device_leftover_source_reports_error(self) -> None:
        """If shutil.move copies dest but leaves source behind, report failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir, 'src')
            dst_dir = Path(tmpdir, 'dst')
            src_dir.mkdir()
            dst_dir.mkdir()
            src = src_dir / 'file.txt'
            src.write_text('data')
            dst = dst_dir / 'file.txt'

            def copy_without_unlink(s: str, d: str) -> None:
                shutil.copy2(s, d)

            with mock.patch('tnc.file_ops.shutil.move', side_effect=copy_without_unlink):
                result = move_single_entry(src, dst)

            self.assertFalse(result.success)
            self.assertTrue(
                'original' in result.error.lower() or 'source' in result.error.lower()
            )
            self.assertTrue(src.exists())
            self.assertTrue(dst.exists())

    def test_permission_error_and_same_file_error_messages(self) -> None:
        """PermissionError and SameFileError yield clear messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, 'a.txt')
            src.write_text('a')
            dst = Path(tmpdir, 'b.txt')

            with mock.patch('tnc.file_ops.shutil.move', side_effect=PermissionError()):
                res_perm = move_single_entry(src, dst)
            self.assertFalse(res_perm.success)
            self.assertIn('permission denied', res_perm.error.lower())

            with mock.patch(
                'tnc.file_ops.shutil.move',
                side_effect=shutil.SameFileError('same file'),
            ):
                res_same = move_single_entry(src, dst)
            self.assertFalse(res_same.success)
            self.assertIn('same file', res_same.error.lower())


class TestAppDoMoveSingleAndMulti(unittest.TestCase):
    """Integration tests for App.do_move() F6 RenMov workflows."""

    def _setup_app(
        self, left_dir: Path, right_dir: Path
    ) -> tuple[App, mock.MagicMock]:
        stdscr = _make_stdscr()
        app = App(stdscr)
        app.setup()
        app.left_panel.change_directory(left_dir)
        app.right_panel.change_directory(right_dir)
        return app, stdscr

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_single_entry_prefills_other_panel_path(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Single-entry F6 opens input_dialog pre-filled with <other_panel.path>/<source>."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()
            (left_dir / 'note.txt').write_text('hi')

            app, _ = self._setup_app(left_dir, right_dir)
            app.left_panel.cursor = 1

            with mock.patch('tnc.app.input_dialog', return_value='') as mock_input:
                result = app.do_move()

            expected_default = str(app.right_panel.path / 'note.txt')
            mock_input.assert_called_once()
            self.assertEqual(mock_input.call_args.kwargs.get('default_value'), expected_default)
            self.assertTrue(result.cancelled)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_edit_basename_only_renames_in_place_and_refreshes_both_panels(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Keeping source parent dir and changing basename renames in place and positions cursor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            shared = Path(tmpdir, 'shared')
            shared.mkdir()
            (shared / 'aaa.txt').write_text('a')
            (shared / 'old.txt').write_text('body')
            (shared / 'zzz.txt').write_text('z')

            app, _ = self._setup_app(shared, shared)
            app.left_panel.selected = {'old.txt'}
            target_path = str(app.left_panel.path / 'mid.txt')

            with mock.patch('tnc.app.input_dialog', return_value=target_path), \
                 mock.patch('tnc.app.show_summary') as mock_summary:
                result = app.do_move()

            self.assertTrue(result.success)
            self.assertFalse((shared / 'old.txt').exists())
            self.assertEqual((shared / 'mid.txt').read_text(), 'body')
            self.assertEqual(app.left_panel.selected, set())
            self.assertEqual(
                app.left_panel.entries[app.left_panel.cursor].name, 'mid.txt'
            )
            self.assertIn('mid.txt', [e.name for e in app.right_panel.entries])
            self.assertNotIn('old.txt', [e.name for e in app.right_panel.entries])
            mock_summary.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_bare_relative_filename_renames_in_source_dir(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Entering a bare relative filename renames inside source_panel.path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()
            (left_dir / 'old.txt').write_text('rel')

            app, _ = self._setup_app(left_dir, right_dir)
            app.left_panel.cursor = 1

            with mock.patch('tnc.app.input_dialog', return_value='renamed.txt'), \
                 mock.patch('tnc.app.show_summary'):
                result = app.do_move()

            self.assertTrue(result.success)
            self.assertFalse((left_dir / 'old.txt').exists())
            self.assertEqual((left_dir / 'renamed.txt').read_text(), 'rel')
            self.assertFalse((right_dir / 'renamed.txt').exists())

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_trailing_slash_directory_moves_preserving_source_name(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Entering a directory path ending with '/' keeps source filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()
            (left_dir / 'item.txt').write_text('trail')

            app, _ = self._setup_app(left_dir, right_dir)
            app.left_panel.cursor = 1

            with mock.patch('tnc.app.input_dialog', return_value=f'{right_dir}/'), \
                 mock.patch('tnc.app.show_summary'):
                result = app.do_move()

            self.assertTrue(result.success)
            self.assertFalse((left_dir / 'item.txt').exists())
            self.assertEqual((right_dir / 'item.txt').read_text(), 'trail')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_move_and_rename_updates_both_panels(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Changing both directory and basename moves+renames and refreshes both panels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()
            (left_dir / 'draft.txt').write_text('final-body')

            app, _ = self._setup_app(left_dir, right_dir)
            app.left_panel.cursor = 1
            dest_target = str(app.right_panel.path / 'final.txt')

            with mock.patch('tnc.app.input_dialog', return_value=dest_target), \
                 mock.patch('tnc.app.show_summary'):
                result = app.do_move()

            self.assertTrue(result.success)
            self.assertFalse((left_dir / 'draft.txt').exists())
            self.assertEqual((right_dir / 'final.txt').read_text(), 'final-body')
            self.assertNotIn('draft.txt', [e.name for e in app.left_panel.entries])
            self.assertIn('final.txt', [e.name for e in app.right_panel.entries])

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_empty_whitespace_esc_and_unchanged_are_silent_noops(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Empty, whitespace-only, Esc (''), and unchanged paths cancel silently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            shared = Path(tmpdir, 'shared')
            shared.mkdir()
            (shared / 'stay.txt').write_text('unchanged')

            app, _ = self._setup_app(shared, shared)
            app.left_panel.cursor = 1

            for entered in ('', '   ', str(app.left_panel.path / 'stay.txt')):
                with mock.patch('tnc.app.input_dialog', return_value=entered), \
                     mock.patch('tnc.app.show_summary') as mock_summary:
                    result = app.do_move()

                self.assertFalse(result.success)
                self.assertTrue(result.cancelled)
                self.assertEqual((shared / 'stay.txt').read_text(), 'unchanged')
                mock_summary.assert_not_called()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_on_dotdot_is_noop(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Pressing F6 on '..' returns Nothing to move without opening dialog."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()

            app, _ = self._setup_app(left_dir, right_dir)
            app.left_panel.cursor = 0

            with mock.patch('tnc.app.input_dialog') as mock_input:
                result = app.do_move()

            self.assertFalse(result.success)
            self.assertIn('Nothing to move', result.error)
            mock_input.assert_not_called()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_overwrite_prompt_decline_and_accept(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Existing dest calls confirm_dialog(default_yes=False); decline cancels, accept overwrites."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()
            (left_dir / 'item.txt').write_text('new-content')
            (right_dir / 'item.txt').write_text('old-content')

            app, _ = self._setup_app(left_dir, right_dir)
            app.left_panel.cursor = 1
            dest_target = str(app.right_panel.path / 'item.txt')

            with mock.patch('tnc.app.input_dialog', return_value=dest_target), \
                 mock.patch('tnc.app.confirm_dialog', return_value=False) as mock_confirm, \
                 mock.patch('tnc.app.show_summary') as mock_summary:
                res_decline = app.do_move()

            self.assertTrue(res_decline.cancelled)
            self.assertEqual(mock_confirm.call_args.kwargs.get('default_yes'), False)
            self.assertEqual((left_dir / 'item.txt').read_text(), 'new-content')
            self.assertEqual((right_dir / 'item.txt').read_text(), 'old-content')
            mock_summary.assert_not_called()

            with mock.patch('tnc.app.input_dialog', return_value=dest_target), \
                 mock.patch('tnc.app.confirm_dialog', return_value=True) as mock_confirm, \
                 mock.patch('tnc.app.show_summary') as mock_summary:
                res_accept = app.do_move()

            self.assertTrue(res_accept.success)
            self.assertEqual(mock_confirm.call_args.kwargs.get('default_yes'), False)
            self.assertFalse((left_dir / 'item.txt').exists())
            self.assertEqual((right_dir / 'item.txt').read_text(), 'new-content')
            mock_summary.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_f6_multi_selection_preserves_directory_confirm_flow(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Multi-file selection still uses confirm_dialog + move_files_with_overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()
            (left_dir / 'a.txt').write_text('a')
            (left_dir / 'b.txt').write_text('b')

            app, stdscr = self._setup_app(left_dir, right_dir)
            stdscr.getch.return_value = ord('y')
            app.left_panel.selected = {'a.txt', 'b.txt'}

            with mock.patch('tnc.app.input_dialog') as mock_input:
                result = app.do_move()

            mock_input.assert_not_called()
            self.assertTrue(result.success)
            self.assertEqual((right_dir / 'a.txt').read_text(), 'a')
            self.assertEqual((right_dir / 'b.txt').read_text(), 'b')
            self.assertFalse((left_dir / 'a.txt').exists())
            self.assertFalse((left_dir / 'b.txt').exists())

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_menu_prompt_rename_continues_working(
        self, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ) -> None:
        """Menu-driven File -> Rename (_prompt_rename) remains intact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            left_dir = Path(tmpdir, 'left')
            right_dir = Path(tmpdir, 'right')
            left_dir.mkdir()
            right_dir.mkdir()
            (left_dir / 'before.txt').write_text('menu-rename')

            app, _ = self._setup_app(left_dir, right_dir)
            app.left_panel.cursor = 1

            with mock.patch('tnc.app.input_dialog', return_value='after.txt'):
                app._prompt_rename()

            self.assertFalse((left_dir / 'before.txt').exists())
            self.assertEqual((left_dir / 'after.txt').read_text(), 'menu-rename')


if __name__ == '__main__':
    unittest.main()
