"""Tests for chmod file operations."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from tnc.file_ops import ChmodResult, chmod_files, chmod_recursive


class TestChmodResult(unittest.TestCase):
    """Tests for ChmodResult dataclass."""

    def test_chmod_result_defaults(self):
        """ChmodResult has correct default values."""
        result = ChmodResult(success=True)
        self.assertTrue(result.success)
        self.assertEqual(result.error, '')
        self.assertEqual(result.changed_files, [])

    def test_chmod_result_with_error(self):
        """ChmodResult stores error message."""
        result = ChmodResult(success=False, error='Permission denied')
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Permission denied')

    def test_chmod_result_with_changed_files(self):
        """ChmodResult stores list of changed files."""
        result = ChmodResult(
            success=True,
            changed_files=['file1.txt', 'file2.txt']
        )
        self.assertEqual(result.changed_files, ['file1.txt', 'file2.txt'])


class TestChmodFiles(unittest.TestCase):
    """Tests for chmod_files function."""

    def test_chmod_single_file_success(self):
        """chmod_files changes permissions on a single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('content')
            os.chmod(test_file, 0o644)

            result = chmod_files(['test.txt'], tmpdir, 0o755)

            self.assertTrue(result.success)
            self.assertEqual(result.error, '')
            self.assertEqual(result.changed_files, ['test.txt'])
            self.assertEqual(stat.S_IMODE(test_file.stat().st_mode), 0o755)

    def test_chmod_multiple_files(self):
        """chmod_files changes permissions on multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'file1.txt'
            file2 = Path(tmpdir) / 'file2.txt'
            file1.write_text('content1')
            file2.write_text('content2')
            os.chmod(file1, 0o644)
            os.chmod(file2, 0o644)

            result = chmod_files(['file1.txt', 'file2.txt'], tmpdir, 0o600)

            self.assertTrue(result.success)
            self.assertEqual(len(result.changed_files), 2)
            self.assertEqual(stat.S_IMODE(file1.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(file2.stat().st_mode), 0o600)

    def test_chmod_directory(self):
        """chmod_files changes permissions on a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / 'subdir'
            test_dir.mkdir()
            os.chmod(test_dir, 0o755)

            result = chmod_files(['subdir'], tmpdir, 0o700)

            self.assertTrue(result.success)
            self.assertEqual(result.changed_files, ['subdir'])
            self.assertEqual(stat.S_IMODE(test_dir.stat().st_mode), 0o700)

    def test_chmod_nonexistent_file(self):
        """chmod_files handles non-existent files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = chmod_files(['nonexistent.txt'], tmpdir, 0o755)

            self.assertFalse(result.success)
            self.assertIn('nonexistent.txt', result.error)

    def test_chmod_permission_denied(self):
        """chmod_files handles permission denied gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('content')

            # Make parent directory read-only (can't chmod files inside)
            os.chmod(tmpdir, 0o555)
            try:
                result = chmod_files(['test.txt'], tmpdir, 0o755)
                # On some systems this may succeed, on others fail
                # The important thing is it doesn't crash
            finally:
                os.chmod(tmpdir, 0o755)

    def test_chmod_empty_list(self):
        """chmod_files with empty list returns success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = chmod_files([], tmpdir, 0o755)
            self.assertTrue(result.success)
            self.assertEqual(result.changed_files, [])

    def test_chmod_symlink(self):
        """chmod_files handles symlinks (changes target permissions)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / 'target.txt'
            target.write_text('content')
            os.chmod(target, 0o644)

            link = Path(tmpdir) / 'link.txt'
            link.symlink_to(target)

            result = chmod_files(['link.txt'], tmpdir, 0o755)

            self.assertTrue(result.success)
            # Symlink chmod affects the target
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)


class TestChmodRecursive(unittest.TestCase):
    """Tests for chmod_recursive function."""

    def test_chmod_recursive_directory(self):
        """chmod_recursive changes permissions on directory and contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create structure: subdir/file1.txt, subdir/nested/file2.txt
            subdir = Path(tmpdir) / 'subdir'
            nested = subdir / 'nested'
            nested.mkdir(parents=True)

            file1 = subdir / 'file1.txt'
            file2 = nested / 'file2.txt'
            file1.write_text('content1')
            file2.write_text('content2')

            os.chmod(subdir, 0o755)
            os.chmod(nested, 0o755)
            os.chmod(file1, 0o644)
            os.chmod(file2, 0o644)

            result = chmod_recursive(subdir, 0o700, file_mode=0o600)

            self.assertTrue(result.success)
            # Directories get dir_mode
            self.assertEqual(stat.S_IMODE(subdir.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(nested.stat().st_mode), 0o700)
            # Files get file_mode
            self.assertEqual(stat.S_IMODE(file1.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(file2.stat().st_mode), 0o600)

    def test_chmod_recursive_same_mode(self):
        """chmod_recursive with same mode for files and dirs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()
            file1 = subdir / 'file1.txt'
            file1.write_text('content')

            # When file_mode is None, use dir_mode for all
            result = chmod_recursive(subdir, 0o755)

            self.assertTrue(result.success)
            self.assertEqual(stat.S_IMODE(subdir.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(file1.stat().st_mode), 0o755)

    def test_chmod_recursive_nonexistent(self):
        """chmod_recursive handles non-existent path."""
        result = chmod_recursive('/nonexistent/path', 0o755)

        self.assertFalse(result.success)
        self.assertIn('No such file', result.error)

    def test_chmod_recursive_on_file(self):
        """chmod_recursive on a file just changes that file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('content')
            os.chmod(test_file, 0o644)

            result = chmod_recursive(test_file, 0o755)

            self.assertTrue(result.success)
            self.assertEqual(stat.S_IMODE(test_file.stat().st_mode), 0o755)
            self.assertEqual(result.changed_files, [str(test_file)])

    def test_chmod_recursive_tracks_changed(self):
        """chmod_recursive returns list of changed files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()
            file1 = subdir / 'file1.txt'
            file2 = subdir / 'file2.txt'
            file1.write_text('content1')
            file2.write_text('content2')

            result = chmod_recursive(subdir, 0o755)

            self.assertTrue(result.success)
            # Should have 3 entries: subdir, file1, file2
            self.assertEqual(len(result.changed_files), 3)


if __name__ == '__main__':
    unittest.main()
