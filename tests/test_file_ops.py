"""Tests for file operations (copy, move, delete)."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from tnc.file_ops import copy_files, CopyResult, validate_filename


class TestValidateFilename(unittest.TestCase):
    """Tests for validate_filename helper function."""

    def test_valid_filename_returns_none(self):
        """Valid filename should return None (no error)."""
        result = validate_filename('myfile.txt')
        self.assertIsNone(result)

    def test_valid_filename_with_spaces(self):
        """Filename with spaces should be valid."""
        result = validate_filename('my file.txt')
        self.assertIsNone(result)

    def test_valid_hidden_file(self):
        """Hidden files (starting with .) should be valid."""
        result = validate_filename('.hidden')
        self.assertIsNone(result)

    def test_empty_string_returns_error(self):
        """Empty string should return error."""
        result = validate_filename('')
        self.assertEqual(result, 'empty')

    def test_whitespace_only_returns_error(self):
        """Whitespace-only string should return error."""
        result = validate_filename('   ')
        self.assertEqual(result, 'empty')

    def test_none_returns_error(self):
        """None should return error."""
        result = validate_filename(None)
        self.assertEqual(result, 'empty')

    def test_dot_returns_error(self):
        """Single dot (.) should return error."""
        result = validate_filename('.')
        self.assertEqual(result, 'special')

    def test_dotdot_returns_error(self):
        """Double dot (..) should return error."""
        result = validate_filename('..')
        self.assertEqual(result, 'special')

    def test_slash_returns_error(self):
        """Filename containing slash should return error."""
        result = validate_filename('path/file')
        self.assertEqual(result, 'separator')

    def test_null_byte_returns_error(self):
        """Filename containing null byte should return error."""
        result = validate_filename('file\0name')
        self.assertEqual(result, 'null')


class TestCopySingleFile(unittest.TestCase):
    """Test copying a single file."""

    def test_copy_single_file(self):
        """Copy single file to destination."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_file = Path(source_dir, 'file.txt')
                source_file.write_text('hello')

                result = copy_files(['file.txt'], source_dir, dest_dir)

                self.assertTrue(result.success)
                dest_file = Path(dest_dir, 'file.txt')
                self.assertTrue(dest_file.exists())
                self.assertEqual(dest_file.read_text(), 'hello')
                # Original still exists
                self.assertTrue(source_file.exists())

    def test_copy_file_preserves_content(self):
        """Copied file should have identical content."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                content = 'test content\nwith newlines\n'
                Path(source_dir, 'test.txt').write_text(content)

                copy_files(['test.txt'], source_dir, dest_dir)

                self.assertEqual(
                    Path(dest_dir, 'test.txt').read_text(),
                    content
                )


class TestCopyMultipleFiles(unittest.TestCase):
    """Test copying multiple files."""

    def test_copy_multiple_files(self):
        """Copy multiple files at once."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'a.txt').write_text('a')
                Path(source_dir, 'b.txt').write_text('b')

                result = copy_files(['a.txt', 'b.txt'], source_dir, dest_dir)

                self.assertTrue(result.success)
                self.assertTrue(Path(dest_dir, 'a.txt').exists())
                self.assertTrue(Path(dest_dir, 'b.txt').exists())


class TestCopyDirectory(unittest.TestCase):
    """Test copying directories."""

    def test_copy_directory_recursive(self):
        """Copy directory with contents recursively."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                subdir = Path(source_dir, 'subdir')
                subdir.mkdir()
                Path(subdir, 'nested.txt').write_text('nested')

                result = copy_files(['subdir'], source_dir, dest_dir)

                self.assertTrue(result.success)
                self.assertTrue(Path(dest_dir, 'subdir').is_dir())
                self.assertTrue(Path(dest_dir, 'subdir', 'nested.txt').exists())
                self.assertEqual(
                    Path(dest_dir, 'subdir', 'nested.txt').read_text(),
                    'nested'
                )

    def test_copy_nested_directories(self):
        """Copy deeply nested directory structure."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                deep = Path(source_dir, 'a', 'b', 'c')
                deep.mkdir(parents=True)
                Path(deep, 'deep.txt').write_text('deep')

                result = copy_files(['a'], source_dir, dest_dir)

                self.assertTrue(result.success)
                self.assertTrue(Path(dest_dir, 'a', 'b', 'c', 'deep.txt').exists())


class TestCopyPreservesMetadata(unittest.TestCase):
    """Test that copy preserves file metadata."""

    def test_copy_preserves_permissions(self):
        """Copy should preserve file permissions."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                script = Path(source_dir, 'script.sh')
                script.write_text('#!/bin/bash')
                os.chmod(script, 0o755)

                copy_files(['script.sh'], source_dir, dest_dir)

                dest_mode = os.stat(Path(dest_dir, 'script.sh')).st_mode
                # Check executable bits are preserved
                self.assertTrue(dest_mode & stat.S_IXUSR)

    def test_copy_preserves_mtime(self):
        """Copy should preserve modification time."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_path = Path(source_dir, 'old.txt')
                source_path.write_text('old')
                # Set a specific mtime
                os.utime(source_path, (1000000, 1000000))
                old_mtime = os.path.getmtime(source_path)

                copy_files(['old.txt'], source_dir, dest_dir)

                new_mtime = os.path.getmtime(Path(dest_dir, 'old.txt'))
                self.assertAlmostEqual(old_mtime, new_mtime, delta=1)


class TestCopySymlink(unittest.TestCase):
    """Test copying symlinks."""

    def test_copy_symlink_as_symlink(self):
        """Symlinks should be copied as symlinks."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                target = Path(source_dir, 'target.txt')
                target.write_text('target')
                link = Path(source_dir, 'mylink')
                link.symlink_to('target.txt')

                copy_files(['mylink'], source_dir, dest_dir)

                dest_link = Path(dest_dir, 'mylink')
                self.assertTrue(dest_link.is_symlink())
                # Link points to same relative target
                self.assertEqual(os.readlink(dest_link), 'target.txt')


class TestCopyErrorHandling(unittest.TestCase):
    """Test error handling during copy."""

    def test_copy_to_same_directory_fails(self):
        """Copy to same directory should fail gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').write_text('test')

            result = copy_files(['file.txt'], tmpdir, tmpdir)

            self.assertFalse(result.success)
            self.assertIn('same', result.error.lower())

    def test_copy_nonexistent_file_reports_error(self):
        """Copy of nonexistent file should report error."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                result = copy_files(['nonexistent.txt'], source_dir, dest_dir)

                self.assertFalse(result.success)

    def test_copy_permission_denied_reports_error(self):
        """Copy to read-only directory should report error."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'file.txt').write_text('test')
                os.chmod(dest_dir, 0o555)

                try:
                    result = copy_files(['file.txt'], source_dir, dest_dir)
                    self.assertFalse(result.success)
                    self.assertIn('permission', result.error.lower())
                finally:
                    os.chmod(dest_dir, 0o755)

    def test_copy_empty_list_does_nothing(self):
        """Copy with empty file list should succeed but do nothing."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                result = copy_files([], source_dir, dest_dir)
                self.assertTrue(result.success)


class TestCopyResult(unittest.TestCase):
    """Test CopyResult dataclass."""

    def test_copy_result_success(self):
        """CopyResult should track success state."""
        result = CopyResult(success=True)
        self.assertTrue(result.success)
        self.assertEqual(result.error, '')

    def test_copy_result_failure(self):
        """CopyResult should track error message."""
        result = CopyResult(success=False, error='Test error')
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Test error')


class TestRenameFile(unittest.TestCase):
    """Test renaming files and directories."""

    def test_rename_file(self):
        """Rename a file successfully."""
        from tnc.file_ops import rename_file

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'old.txt').write_text('content')

            result = rename_file(tmpdir, 'old.txt', 'new.txt')

            self.assertTrue(result.success)
            self.assertEqual(result.new_name, 'new.txt')
            self.assertFalse(Path(tmpdir, 'old.txt').exists())
            self.assertTrue(Path(tmpdir, 'new.txt').exists())
            self.assertEqual(Path(tmpdir, 'new.txt').read_text(), 'content')

    def test_rename_directory(self):
        """Rename a directory successfully."""
        from tnc.file_ops import rename_file

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'olddir').mkdir()
            Path(tmpdir, 'olddir', 'file.txt').touch()

            result = rename_file(tmpdir, 'olddir', 'newdir')

            self.assertTrue(result.success)
            self.assertFalse(Path(tmpdir, 'olddir').exists())
            self.assertTrue(Path(tmpdir, 'newdir').is_dir())
            self.assertTrue(Path(tmpdir, 'newdir', 'file.txt').exists())

    def test_rename_empty_name_fails(self):
        """Rename with empty name should fail."""
        from tnc.file_ops import rename_file

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            result = rename_file(tmpdir, 'file.txt', '')

            self.assertFalse(result.success)
            self.assertIn('empty', result.error.lower())

    def test_rename_to_existing_fails(self):
        """Rename to existing name should fail."""
        from tnc.file_ops import rename_file

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            result = rename_file(tmpdir, 'file1.txt', 'file2.txt')

            self.assertFalse(result.success)
            self.assertIn('exists', result.error.lower())

    def test_rename_invalid_name_with_slash(self):
        """Rename with slash in name should fail."""
        from tnc.file_ops import rename_file

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            result = rename_file(tmpdir, 'file.txt', 'bad/name.txt')

            self.assertFalse(result.success)
            self.assertIn('separator', result.error.lower())


if __name__ == '__main__':
    unittest.main()
