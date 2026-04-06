"""Tests for chown file operations."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.file_ops import ChownResult, chown_files


class TestChownResult(unittest.TestCase):
    """Tests for ChownResult dataclass."""

    def test_chown_result_defaults(self):
        """ChownResult has correct default values."""
        result = ChownResult(success=True)
        self.assertTrue(result.success)
        self.assertEqual(result.error, '')
        self.assertEqual(result.changed_files, [])

    def test_chown_result_with_error(self):
        """ChownResult stores error message."""
        result = ChownResult(success=False, error='Operation not permitted')
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Operation not permitted')

    def test_chown_result_with_changed_files(self):
        """ChownResult stores list of changed files."""
        result = ChownResult(
            success=True,
            changed_files=['file1.txt', 'file2.txt']
        )
        self.assertEqual(result.changed_files, ['file1.txt', 'file2.txt'])


class TestChownFiles(unittest.TestCase):
    """Tests for chown_files function."""

    def test_chown_empty_list(self):
        """chown_files with empty list returns success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = chown_files([], tmpdir, uid=-1, gid=-1)
            self.assertTrue(result.success)
            self.assertEqual(result.changed_files, [])

    def test_chown_nonexistent_file(self):
        """chown_files handles non-existent files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = chown_files(['nonexistent.txt'], tmpdir, uid=-1, gid=-1)
            self.assertFalse(result.success)
            self.assertIn('nonexistent.txt', result.error)

    def test_chown_uid_only(self):
        """chown_files can change only uid (gid=-1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('content')
            current_uid = os.getuid()

            # Use -1 for gid to not change it
            result = chown_files(['test.txt'], tmpdir, uid=current_uid, gid=-1)

            # Should succeed (changing to same uid is allowed)
            self.assertTrue(result.success)
            self.assertEqual(result.changed_files, ['test.txt'])

    def test_chown_gid_only(self):
        """chown_files can change only gid (uid=-1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('content')
            current_gid = os.getgid()

            # Use -1 for uid to not change it
            result = chown_files(['test.txt'], tmpdir, uid=-1, gid=current_gid)

            # Should succeed (changing to same gid is allowed)
            self.assertTrue(result.success)
            self.assertEqual(result.changed_files, ['test.txt'])

    def test_chown_permission_denied(self):
        """chown_files handles permission denied gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('content')

            # Try to change to root (uid=0) - should fail without root
            if os.getuid() != 0:
                result = chown_files(['test.txt'], tmpdir, uid=0, gid=0)
                self.assertFalse(result.success)
                self.assertIn('test.txt', result.error)

    def test_chown_multiple_files(self):
        """chown_files handles multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'file1.txt'
            file2 = Path(tmpdir) / 'file2.txt'
            file1.write_text('content1')
            file2.write_text('content2')

            current_uid = os.getuid()
            current_gid = os.getgid()

            result = chown_files(
                ['file1.txt', 'file2.txt'],
                tmpdir,
                uid=current_uid,
                gid=current_gid
            )

            self.assertTrue(result.success)
            self.assertEqual(len(result.changed_files), 2)


if __name__ == '__main__':
    unittest.main()
