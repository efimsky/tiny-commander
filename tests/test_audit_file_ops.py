"""Audit tests for tnc.file_ops fixes (#83, #84, #86, #87, #88, #89, #118)."""

import os
import signal
import socket
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc import file_ops
from tnc.file_ops import (
    OverwriteChoice,
    OverwriteHandler,
    calculate_dir_size,
    chmod_recursive,
    copy_files,
    copy_files_with_overwrite,
    delete_files,
    move_files_with_overwrite,
    rename_file,
)


class RecordingOverwriteHandler(OverwriteHandler):
    """Test handler recording prompt arguments and returning scripted choices."""

    def __init__(self, choices: list[OverwriteChoice]) -> None:
        self.choices = list(choices)
        self.calls: list[tuple[str, int, int, float, float, int, int]] = []

    @property
    def prompt_count(self) -> int:
        return len(self.calls)

    def prompt(
        self,
        filename: str,
        source_size: int,
        dest_size: int,
        source_mtime: float,
        dest_mtime: float,
        current: int,
        total: int,
    ) -> OverwriteChoice:
        self.calls.append((
            filename, source_size, dest_size, source_mtime, dest_mtime, current, total
        ))
        if self.calls and len(self.calls) <= len(self.choices):
            return self.choices[len(self.calls) - 1]
        return OverwriteChoice.NO


class TestChmodRecursiveSymlinks(unittest.TestCase):
    """Issue #83: chmod_recursive must skip symlinks and never follow them."""

    def test_skips_symlink_to_external_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ext_file = root / 'external.txt'
            ext_file.write_text('external')
            os.chmod(ext_file, 0o644)

            tree = root / 'tree'
            tree.mkdir()
            inner = tree / 'inner.txt'
            inner.write_text('inner')
            os.chmod(inner, 0o644)
            link = tree / 'ext_link'
            link.symlink_to(ext_file)

            result = chmod_recursive(tree, 0o700, file_mode=0o600)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(stat.S_IMODE(inner.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(ext_file.stat().st_mode), 0o644)
            self.assertNotIn(str(link), result.changed_files)

    def test_skips_symlink_to_external_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ext_dir = root / 'external_dir'
            ext_dir.mkdir()
            ext_inner = ext_dir / 'secret.txt'
            ext_inner.write_text('secret')
            os.chmod(ext_dir, 0o755)
            os.chmod(ext_inner, 0o644)

            tree = root / 'tree'
            tree.mkdir()
            (tree / 'dir_link').symlink_to(ext_dir)

            result = chmod_recursive(tree, 0o700, file_mode=0o600)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(stat.S_IMODE(ext_dir.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(ext_inner.stat().st_mode), 0o644)

    def test_skips_broken_symlink_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tree = Path(tmpdir) / 'tree'
            tree.mkdir()
            real_file = tree / 'real.txt'
            real_file.write_text('ok')
            os.chmod(real_file, 0o644)
            (tree / 'broken').symlink_to('/nonexistent/target')

            result = chmod_recursive(tree, 0o700, file_mode=0o600)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(result.errors, [])
            self.assertEqual(stat.S_IMODE(real_file.stat().st_mode), 0o600)

    def test_top_level_symlink_skipped_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ext_file = root / 'external.txt'
            ext_file.write_text('external')
            os.chmod(ext_file, 0o644)
            link = root / 'link.txt'
            link.symlink_to(ext_file)

            result = chmod_recursive(link, 0o700, file_mode=0o600)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(result.changed_files, [])
            self.assertEqual(stat.S_IMODE(ext_file.stat().st_mode), 0o644)

    def test_top_level_broken_symlink_skipped_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            link = Path(tmpdir) / 'broken'
            link.symlink_to('/nonexistent/target')

            result = chmod_recursive(link, 0o755)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(result.changed_files, [])


class TestSymlinkOverwriteTypeGuard(unittest.TestCase):
    """Issue #84: symlinks must not overwrite real directories or files."""

    def test_copy_symlink_over_directory_refused(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            target = Path(src_dir) / 'real.txt'
            target.write_text('target')
            (Path(src_dir) / 'item').symlink_to(target)

            dest_item = Path(dst_dir) / 'item'
            dest_item.mkdir()
            precious = dest_item / 'precious.txt'
            precious.write_text('keep me')

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = copy_files_with_overwrite(['item'], src_dir, dst_dir, handler)

            self.assertFalse(result.success)
            self.assertIn('symlink', result.error.lower())
            self.assertIn('directory', result.error.lower())
            self.assertEqual(handler.prompt_count, 0)
            self.assertTrue(dest_item.is_dir())
            self.assertFalse(dest_item.is_symlink())
            self.assertEqual(precious.read_text(), 'keep me')

    def test_move_symlink_over_directory_refused(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            target = Path(src_dir) / 'real.txt'
            target.write_text('target')
            src_link = Path(src_dir) / 'item'
            src_link.symlink_to(target)

            dest_item = Path(dst_dir) / 'item'
            dest_item.mkdir()
            precious = dest_item / 'precious.txt'
            precious.write_text('keep me')

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = move_files_with_overwrite(['item'], src_dir, dst_dir, handler)

            self.assertFalse(result.success)
            self.assertIn('symlink', result.error.lower())
            self.assertIn('directory', result.error.lower())
            self.assertEqual(handler.prompt_count, 0)
            self.assertTrue(src_link.is_symlink())
            self.assertTrue(dest_item.is_dir())
            self.assertEqual(precious.read_text(), 'keep me')

    def test_copy_symlink_over_file_refused(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            (Path(src_dir) / 'item').symlink_to('/some/target')
            dest_file = Path(dst_dir) / 'item'
            dest_file.write_text('real file')

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = copy_files_with_overwrite(['item'], src_dir, dst_dir, handler)

            self.assertFalse(result.success)
            self.assertIn('symlink', result.error.lower())
            self.assertEqual(handler.prompt_count, 0)
            self.assertFalse(dest_file.is_symlink())
            self.assertEqual(dest_file.read_text(), 'real file')

    def test_copy_file_over_valid_symlink_prompts_and_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            (Path(src_dir) / 'item').write_text('new file')
            real_target = Path(dst_dir) / 'target.txt'
            real_target.write_text('target')
            dest_link = Path(dst_dir) / 'item'
            dest_link.symlink_to(real_target)

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = copy_files_with_overwrite(['item'], src_dir, dst_dir, handler)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(handler.prompt_count, 1)
            self.assertFalse(dest_link.is_symlink())
            self.assertEqual(dest_link.read_text(), 'new file')
            self.assertEqual(real_target.read_text(), 'target')

    def test_copy_symlink_over_valid_symlink_prompts_and_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            t1 = Path(src_dir) / 't1.txt'
            t1.write_text('one')
            (Path(src_dir) / 'item').symlink_to(t1)

            t2 = Path(dst_dir) / 't2.txt'
            t2.write_text('two')
            dest_link = Path(dst_dir) / 'item'
            dest_link.symlink_to(t2)

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = copy_files_with_overwrite(['item'], src_dir, dst_dir, handler)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(handler.prompt_count, 1)
            self.assertTrue(dest_link.is_symlink())
            self.assertEqual(os.readlink(dest_link), str(t1))


class TestRenameFileSymlinks(unittest.TestCase):
    """Issue #86: rename_file must use lstat samestat, not target samefile."""

    def test_rename_symlink_over_distinct_symlink_with_same_target_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / 'target.txt'
            target.write_text('shared')
            link1 = Path(tmpdir) / 'link1'
            link2 = Path(tmpdir) / 'link2'
            link1.symlink_to(target)
            link2.symlink_to(target)

            result = rename_file(tmpdir, 'link1', 'link2')

            self.assertFalse(result.success)
            self.assertIn('exists', result.error.lower())
            self.assertTrue(link1.is_symlink())
            self.assertTrue(link2.is_symlink())

    def test_rename_symlink_over_its_target_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / 'target.txt'
            target.write_text('content')
            link = Path(tmpdir) / 'link'
            link.symlink_to(target)

            result = rename_file(tmpdir, 'link', 'target.txt')

            self.assertFalse(result.success)
            self.assertIn('exists', result.error.lower())
            self.assertTrue(link.is_symlink())
            self.assertTrue(target.is_file())

    def test_case_only_rename_broken_symlink_simulated_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_link = Path(tmpdir) / 'BrokenLink'
            old_link.symlink_to('/nonexistent/target')
            old_lstat = old_link.lstat()

            real_is_symlink = Path.is_symlink
            real_lstat = Path.lstat

            def fake_is_symlink(self_path: Path) -> bool:
                if self_path.name == 'brokenlink':
                    return True
                return real_is_symlink(self_path)

            def fake_lstat(self_path: Path) -> os.stat_result:
                if self_path.name == 'brokenlink':
                    return old_lstat
                return real_lstat(self_path)

            with mock.patch.object(Path, 'is_symlink', fake_is_symlink), \
                 mock.patch.object(Path, 'lstat', fake_lstat), \
                 mock.patch.object(Path, 'rename') as mock_rename:
                result = rename_file(tmpdir, 'BrokenLink', 'brokenlink')

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            mock_rename.assert_called_once()

    def test_case_only_rename_broken_symlink_real_case_insensitive_fs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_link = Path(tmpdir) / 'BrokenLink'
            old_link.symlink_to('/nonexistent/target')
            probe = Path(tmpdir) / 'brokenlink'
            if not probe.is_symlink():
                self.skipTest('Filesystem is case-sensitive')

            result = rename_file(tmpdir, 'BrokenLink', 'brokenlink')

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertIn('brokenlink', os.listdir(tmpdir))


class TestSpecialFilesDeleteAndCopy(unittest.TestCase):
    """Issue #87: delete_files unlinks special files; _copy_item refuses them."""

    def test_delete_fifo_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fifo = Path(tmpdir) / 'myfifo'
            os.mkfifo(fifo)

            result = delete_files(['myfifo'], tmpdir)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertFalse(fifo.exists())
            self.assertFalse(fifo.is_symlink())

    def test_delete_unix_socket_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = Path(tmpdir) / 's.sock'
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                srv.bind(str(sock_path))
            finally:
                srv.close()

            result = delete_files(['s.sock'], tmpdir)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertFalse(sock_path.exists())

    def test_copy_fifo_fails_without_hanging(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            fifo = Path(src_dir) / 'myfifo'
            os.mkfifo(fifo)

            def on_timeout(_signum: int, _frame: object) -> None:
                raise TimeoutError('copy_files hung on FIFO')

            old_handler = signal.signal(signal.SIGALRM, on_timeout)
            signal.setitimer(signal.ITIMER_REAL, 0.3)
            try:
                result = copy_files(['myfifo'], src_dir, dst_dir)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)

            self.assertFalse(result.success)
            self.assertIn('special file', result.error.lower())
            self.assertFalse((Path(dst_dir) / 'myfifo').exists())

    def test_copy_directory_containing_fifo_fails_without_hanging(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            sub = Path(src_dir) / 'sub'
            sub.mkdir()
            (sub / 'ok.txt').write_text('ok')
            os.mkfifo(sub / 'pipe')

            def on_timeout(_signum: int, _frame: object) -> None:
                raise TimeoutError('copy_files hung on FIFO inside dir')

            old_handler = signal.signal(signal.SIGALRM, on_timeout)
            signal.setitimer(signal.ITIMER_REAL, 0.3)
            try:
                result = copy_files(['sub'], src_dir, dst_dir)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)

            self.assertFalse(result.success)
            self.assertIn('special file', result.error.lower())

    def test_copy_unix_socket_fails_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            sock_path = Path(src_dir) / 's.sock'
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                srv.bind(str(sock_path))
            finally:
                srv.close()

            result = copy_files(['s.sock'], src_dir, dst_dir)

            self.assertFalse(result.success)
            self.assertIn('special file', result.error.lower())

    def test_copy_block_and_char_devices_fail_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            blk = Path(src_dir) / 'blkdev'
            chr_dev = Path(src_dir) / 'chrdev'
            blk.touch()
            chr_dev.touch()

            real_lstat = Path.lstat

            def fake_lstat(self_path: Path) -> os.stat_result:
                st = real_lstat(self_path)
                if self_path.name == 'blkdev':
                    fake = list(st)
                    fake[0] = stat.S_IFBLK | 0o600
                    return os.stat_result(fake)
                if self_path.name == 'chrdev':
                    fake = list(st)
                    fake[0] = stat.S_IFCHR | 0o600
                    return os.stat_result(fake)
                return st

            with mock.patch.object(Path, 'lstat', fake_lstat):
                result = copy_files(['blkdev', 'chrdev'], src_dir, dst_dir)

            self.assertFalse(result.success)
            self.assertEqual(len(result.errors), 2)
            self.assertTrue(all('special file' in e.lower() for e in result.errors))


class TestBrokenSymlinkSourceOverwrite(unittest.TestCase):
    """Issue #88: broken symlink at source must not crash overwrite prompt."""

    def test_copy_broken_symlink_over_valid_symlink_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            src_link = Path(src_dir) / 'link'
            src_link.symlink_to('/nonexistent/source/target')

            dst_target = Path(dst_dir) / 'real.txt'
            dst_target.write_text('hello')
            dst_link = Path(dst_dir) / 'link'
            dst_link.symlink_to(dst_target)

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = copy_files_with_overwrite(['link'], src_dir, dst_dir, handler)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(handler.prompt_count, 1)
            self.assertTrue(dst_link.is_symlink())
            self.assertEqual(os.readlink(dst_link), '/nonexistent/source/target')
            # Symlink metadata uses lstat: size 0 for symlinks
            self.assertEqual(handler.calls[0][1], 0)
            self.assertEqual(handler.calls[0][2], 0)

    def test_move_broken_symlink_over_valid_symlink_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            src_link = Path(src_dir) / 'link'
            src_link.symlink_to('/nonexistent/source/target')

            dst_target = Path(dst_dir) / 'real.txt'
            dst_target.write_text('hello')
            dst_link = Path(dst_dir) / 'link'
            dst_link.symlink_to(dst_target)

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = move_files_with_overwrite(['link'], src_dir, dst_dir, handler)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual(handler.prompt_count, 1)
            self.assertFalse(src_link.is_symlink())
            self.assertTrue(dst_link.is_symlink())
            self.assertEqual(os.readlink(dst_link), '/nonexistent/source/target')

    def test_overwrite_prompt_passes_correct_file_and_symlink_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            (Path(src_dir) / 'item').write_text('hello')  # 5 bytes
            dst_target = Path(dst_dir) / 'target.txt'
            dst_target.write_text('x' * 50)
            (Path(dst_dir) / 'item').symlink_to(dst_target)

            handler = RecordingOverwriteHandler([OverwriteChoice.NO])
            result = copy_files_with_overwrite(['item'], src_dir, dst_dir, handler)

            self.assertTrue(result.success)
            self.assertEqual(handler.prompt_count, 1)
            _, source_size, dest_size, *_ = handler.calls[0]
            self.assertEqual(source_size, 5)
            self.assertEqual(dest_size, 0)


class TestMoveAsideLongNamesAndCancelErrors(unittest.TestCase):
    """Issue #89: bounded sidecar names and cancel preserves prior errors."""

    def test_overwrite_250_byte_ascii_filename_succeeds(self) -> None:
        name = 'a' * 250
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            (Path(src_dir) / name).write_text('new')
            (Path(dst_dir) / name).write_text('old')

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = copy_files_with_overwrite([name], src_dir, dst_dir, handler)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual((Path(dst_dir) / name).read_text(), 'new')
            self.assertEqual(os.listdir(dst_dir), [name])

    def test_overwrite_250_byte_utf8_filename_succeeds(self) -> None:
        name = 'é' * 125  # 250 UTF-8 bytes
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            (Path(src_dir) / name).write_text('new-utf8')
            (Path(dst_dir) / name).write_text('old-utf8')

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            result = copy_files_with_overwrite([name], src_dir, dst_dir, handler)

            self.assertTrue(result.success, f'Unexpected error: {result.error!r}')
            self.assertEqual((Path(dst_dir) / name).read_text(), 'new-utf8')
            self.assertEqual(len(os.listdir(dst_dir)), 1)

    def test_overwrite_250_byte_filename_rollback_on_failure(self) -> None:
        name = 'b' * 250
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            (Path(src_dir) / name).write_text('new')
            dest_file = Path(dst_dir) / name
            dest_file.write_text('precious')

            handler = RecordingOverwriteHandler([OverwriteChoice.YES])
            with mock.patch.object(file_ops, '_copy_item', side_effect=OSError('disk full')) as mock_copy:
                result = copy_files_with_overwrite([name], src_dir, dst_dir, handler)

            mock_copy.assert_called_once()
            self.assertFalse(result.success)
            self.assertEqual(dest_file.read_text(), 'precious')
            self.assertEqual(os.listdir(dst_dir), [name])

    def test_move_aside_bounds_sidecar_to_255_utf8_bytes(self) -> None:
        for name in ('x' * 255, 'é' * 125):
            with tempfile.TemporaryDirectory() as tmpdir:
                dest_file = Path(tmpdir) / name
                dest_file.write_text('data')
                sidecar = file_ops._move_aside(dest_file)
                self.assertIsNotNone(sidecar)
                self.assertLessEqual(len(sidecar.name.encode('utf-8')), 255)
                self.assertTrue(sidecar.exists())
                self.assertFalse(dest_file.exists())

    def test_cancel_preserves_prior_errors(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            (Path(src_dir) / 'conflict.txt').write_text('src')
            (Path(dst_dir) / 'conflict.txt').write_text('dst')

            handler = RecordingOverwriteHandler([OverwriteChoice.CANCEL])
            result = copy_files_with_overwrite(
                ['missing.txt', 'conflict.txt'], src_dir, dst_dir, handler
            )

            self.assertTrue(result.cancelled)
            self.assertFalse(result.success)
            self.assertEqual(len(result.errors), 1)
            self.assertIn('missing.txt', result.errors[0])


class TestCalculateDirSizeAudit(unittest.TestCase):
    """Issue #118: iterative os.scandir and symlink handling in calculate_dir_size."""

    def test_symlink_to_directory_counted_by_lstat_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ext_dir = root / 'ext'
            ext_dir.mkdir()
            (ext_dir / 'big.bin').write_bytes(b'x' * 1000)

            measured = root / 'measured'
            measured.mkdir()
            (measured / 'small.txt').write_bytes(b'12345')  # 5 bytes
            dir_link = measured / 'dir_link'
            dir_link.symlink_to(ext_dir)

            expected = 5 + dir_link.lstat().st_size
            self.assertEqual(calculate_dir_size(measured), expected)

    def test_top_level_broken_symlink_returns_lstat_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            broken = Path(tmpdir) / 'broken'
            broken.symlink_to('/nonexistent/target/path')

            self.assertEqual(calculate_dir_size(broken), broken.lstat().st_size)

    def test_top_level_symlink_to_directory_returns_lstat_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ext_dir = root / 'ext'
            ext_dir.mkdir()
            (ext_dir / 'big.bin').write_bytes(b'x' * 500)
            dir_link = root / 'dir_link'
            dir_link.symlink_to(ext_dir)

            self.assertEqual(calculate_dir_size(dir_link), dir_link.lstat().st_size)

    def test_deep_tree_exceeding_recursion_limit(self) -> None:
        depth = 200
        original_limit = sys.getrecursionlimit()
        with tempfile.TemporaryDirectory() as tmpdir:
            top = Path(tmpdir) / 'r'
            cur = top
            cur.mkdir()
            for _ in range(depth):
                cur = cur / 'd'
                cur.mkdir()
            (cur / 'leaf').write_bytes(b'abcd')  # 4 bytes

            try:
                sys.setrecursionlimit(100)
                size = calculate_dir_size(top)
            finally:
                sys.setrecursionlimit(original_limit)

            self.assertEqual(size, 4)

    def test_top_level_unreadable_directory_returns_minus_one(self) -> None:
        if os.geteuid() == 0:
            self.skipTest('Root ignores chmod 0o000 permissions')
        with tempfile.TemporaryDirectory() as tmpdir:
            locked = Path(tmpdir) / 'locked'
            locked.mkdir()
            (locked / 'file.txt').write_text('hidden')
            os.chmod(locked, 0o000)
            try:
                self.assertEqual(calculate_dir_size(locked), -1)
            finally:
                os.chmod(locked, 0o755)


if __name__ == '__main__':
    unittest.main()
