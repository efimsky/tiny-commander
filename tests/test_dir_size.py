"""Tests for directory size calculation functionality."""

import os
import tempfile
import unittest
from pathlib import Path

from tnc.file_ops import calculate_dir_size


class TestCalculateDirSize(unittest.TestCase):
    """Tests for calculate_dir_size function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_empty_directory(self) -> None:
        """Test size of empty directory is 0."""
        empty_dir = self.test_path / 'empty'
        empty_dir.mkdir()

        size = calculate_dir_size(empty_dir)

        self.assertEqual(size, 0)

    def test_single_file(self) -> None:
        """Test size with single file."""
        test_dir = self.test_path / 'single'
        test_dir.mkdir()
        file = test_dir / 'file.txt'
        file.write_text('hello')  # 5 bytes

        size = calculate_dir_size(test_dir)

        self.assertEqual(size, 5)

    def test_multiple_files(self) -> None:
        """Test size with multiple files."""
        test_dir = self.test_path / 'multi'
        test_dir.mkdir()
        (test_dir / 'a.txt').write_text('aaa')      # 3 bytes
        (test_dir / 'b.txt').write_text('bbbbbb')   # 6 bytes
        (test_dir / 'c.txt').write_text('c')        # 1 byte

        size = calculate_dir_size(test_dir)

        self.assertEqual(size, 10)

    def test_nested_directories(self) -> None:
        """Test size includes subdirectories."""
        test_dir = self.test_path / 'nested'
        test_dir.mkdir()
        sub_dir = test_dir / 'sub'
        sub_dir.mkdir()
        (test_dir / 'root.txt').write_text('root')  # 4 bytes
        (sub_dir / 'sub.txt').write_text('sub')     # 3 bytes

        size = calculate_dir_size(test_dir)

        self.assertEqual(size, 7)

    def test_deeply_nested(self) -> None:
        """Test size with deeply nested structure."""
        test_dir = self.test_path / 'deep'
        test_dir.mkdir()
        current = test_dir
        for i in range(5):
            current = current / f'level{i}'
            current.mkdir()
            (current / 'file.txt').write_text('x' * (i + 1))  # 1+2+3+4+5 = 15 bytes

        size = calculate_dir_size(test_dir)

        self.assertEqual(size, 15)

    def test_hidden_files_included(self) -> None:
        """Test that hidden files are included in size."""
        test_dir = self.test_path / 'hidden'
        test_dir.mkdir()
        (test_dir / '.hidden').write_text('hidden')    # 6 bytes
        (test_dir / 'visible').write_text('visible')   # 7 bytes

        size = calculate_dir_size(test_dir)

        self.assertEqual(size, 13)

    def test_symlink_not_followed(self) -> None:
        """Test that symlinks are not followed (uses lstat)."""
        test_dir = self.test_path / 'symlink'
        test_dir.mkdir()
        real_file = test_dir / 'real.txt'
        real_file.write_text('real content')  # 12 bytes
        link = test_dir / 'link.txt'
        link.symlink_to(real_file)

        size = calculate_dir_size(test_dir)

        # Should count real file (12) + symlink size (not the target content)
        # Symlink size is the length of the path it points to
        link_size = len(os.readlink(link))
        self.assertEqual(size, 12 + link_size)

    def test_broken_symlink(self) -> None:
        """Test handling of broken symlinks."""
        test_dir = self.test_path / 'broken_link'
        test_dir.mkdir()
        (test_dir / 'file.txt').write_text('data')  # 4 bytes
        link = test_dir / 'broken'
        link.symlink_to('/nonexistent/path')

        # Should not raise, should still count other files
        size = calculate_dir_size(test_dir)

        # Should count file + symlink size (even if broken)
        link_size = len(os.readlink(link))
        self.assertEqual(size, 4 + link_size)

    def test_permission_denied_partial(self) -> None:
        """Test that inaccessible files are skipped but others counted."""
        test_dir = self.test_path / 'partial_access'
        test_dir.mkdir()
        accessible = test_dir / 'accessible.txt'
        accessible.write_text('can read')  # 8 bytes

        no_read = test_dir / 'no_read'
        no_read.mkdir()
        no_read.chmod(0o000)

        try:
            size = calculate_dir_size(test_dir)
            # Should count accessible file at minimum
            self.assertGreaterEqual(size, 8)
        finally:
            no_read.chmod(0o755)

    def test_nonexistent_directory(self) -> None:
        """Test handling of non-existent directory."""
        nonexistent = self.test_path / 'does_not_exist'

        size = calculate_dir_size(nonexistent)

        self.assertEqual(size, -1)  # Error indicator

    def test_file_instead_of_directory(self) -> None:
        """Test that passing a file instead of directory returns file size."""
        file_path = self.test_path / 'just_a_file.txt'
        file_path.write_text('content')  # 7 bytes

        size = calculate_dir_size(file_path)

        # Should return the file's size if given a file
        self.assertEqual(size, 7)

    def test_returns_int(self) -> None:
        """Test that result is an integer."""
        test_dir = self.test_path / 'int_test'
        test_dir.mkdir()
        (test_dir / 'file.txt').write_text('test')

        size = calculate_dir_size(test_dir)

        self.assertIsInstance(size, int)


if __name__ == '__main__':
    unittest.main()
