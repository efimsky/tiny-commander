"""Tests for permissions module."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from tnc.permissions import (
    mode_to_octal_string,
    get_permission_bits,
    set_permission_bit,
    get_common_mode,
    get_system_users,
    get_system_groups,
    filter_by_prefix,
    TriState,
)


class TestModeFormatting(unittest.TestCase):
    """Tests for mode formatting functions."""

    def test_mode_to_octal_string(self):
        """mode_to_octal_string formats mode as octal string."""
        self.assertEqual(mode_to_octal_string(0o755), '0755')
        self.assertEqual(mode_to_octal_string(0o644), '0644')
        self.assertEqual(mode_to_octal_string(0o777), '0777')
        self.assertEqual(mode_to_octal_string(0o000), '0000')

    def test_mode_to_octal_string_with_special_bits(self):
        """mode_to_octal_string includes special bits."""
        self.assertEqual(mode_to_octal_string(0o4755), '4755')  # setuid
        self.assertEqual(mode_to_octal_string(0o2755), '2755')  # setgid
        self.assertEqual(mode_to_octal_string(0o1755), '1755')  # sticky


class TestPermissionBits(unittest.TestCase):
    """Tests for permission bit manipulation."""

    def test_get_permission_bits_basic(self):
        """get_permission_bits returns correct bits for basic mode."""
        bits = get_permission_bits(0o755)

        # Owner: rwx
        self.assertTrue(bits['owner_read'])
        self.assertTrue(bits['owner_write'])
        self.assertTrue(bits['owner_exec'])

        # Group: r-x
        self.assertTrue(bits['group_read'])
        self.assertFalse(bits['group_write'])
        self.assertTrue(bits['group_exec'])

        # Other: r-x
        self.assertTrue(bits['other_read'])
        self.assertFalse(bits['other_write'])
        self.assertTrue(bits['other_exec'])

        # No special bits
        self.assertFalse(bits['setuid'])
        self.assertFalse(bits['setgid'])
        self.assertFalse(bits['sticky'])

    def test_get_permission_bits_special(self):
        """get_permission_bits returns correct special bits."""
        # setuid
        bits = get_permission_bits(0o4755)
        self.assertTrue(bits['setuid'])
        self.assertFalse(bits['setgid'])
        self.assertFalse(bits['sticky'])

        # setgid
        bits = get_permission_bits(0o2755)
        self.assertFalse(bits['setuid'])
        self.assertTrue(bits['setgid'])
        self.assertFalse(bits['sticky'])

        # sticky
        bits = get_permission_bits(0o1755)
        self.assertFalse(bits['setuid'])
        self.assertFalse(bits['setgid'])
        self.assertTrue(bits['sticky'])

    def test_set_permission_bit_basic(self):
        """set_permission_bit modifies mode correctly."""
        mode = 0o644

        # Add execute for owner
        mode = set_permission_bit(mode, 'owner_exec', True)
        self.assertEqual(mode, 0o744)

        # Remove read for other
        mode = set_permission_bit(mode, 'other_read', False)
        self.assertEqual(mode, 0o740)

    def test_set_permission_bit_special(self):
        """set_permission_bit handles special bits."""
        mode = 0o755

        # Add setuid
        mode = set_permission_bit(mode, 'setuid', True)
        self.assertEqual(mode, 0o4755)

        # Add setgid
        mode = set_permission_bit(mode, 'setgid', True)
        self.assertEqual(mode, 0o6755)

        # Remove setuid
        mode = set_permission_bit(mode, 'setuid', False)
        self.assertEqual(mode, 0o2755)


class TestTriState(unittest.TestCase):
    """Tests for TriState enum."""

    def test_tristate_values(self):
        """TriState has expected values."""
        self.assertIsNotNone(TriState.UNCHECKED)
        self.assertIsNotNone(TriState.CHECKED)
        self.assertIsNotNone(TriState.MIXED)


class TestCommonMode(unittest.TestCase):
    """Tests for get_common_mode function."""

    def test_get_common_mode_all_same(self):
        """get_common_mode returns CHECKED/UNCHECKED when all bits match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'file1.txt'
            file2 = Path(tmpdir) / 'file2.txt'
            file1.write_text('content1')
            file2.write_text('content2')
            os.chmod(file1, 0o644)
            os.chmod(file2, 0o644)

            result, failed_count = get_common_mode([file1, file2])

            self.assertEqual(failed_count, 0)
            self.assertEqual(result['owner_read'], TriState.CHECKED)
            self.assertEqual(result['owner_write'], TriState.CHECKED)
            self.assertEqual(result['owner_exec'], TriState.UNCHECKED)
            self.assertEqual(result['group_read'], TriState.CHECKED)
            self.assertEqual(result['other_read'], TriState.CHECKED)

    def test_get_common_mode_mixed(self):
        """get_common_mode returns MIXED when bits differ."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'file1.txt'
            file2 = Path(tmpdir) / 'file2.txt'
            file1.write_text('content1')
            file2.write_text('content2')
            os.chmod(file1, 0o755)  # rwxr-xr-x
            os.chmod(file2, 0o644)  # rw-r--r--

            result, failed_count = get_common_mode([file1, file2])

            self.assertEqual(failed_count, 0)
            # owner_write is same (both have it)
            self.assertEqual(result['owner_write'], TriState.CHECKED)
            # owner_exec differs
            self.assertEqual(result['owner_exec'], TriState.MIXED)
            # group_exec differs
            self.assertEqual(result['group_exec'], TriState.MIXED)

    def test_get_common_mode_single_file(self):
        """get_common_mode works with single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'file1.txt'
            file1.write_text('content')
            os.chmod(file1, 0o755)

            result, failed_count = get_common_mode([file1])

            self.assertEqual(failed_count, 0)
            self.assertEqual(result['owner_exec'], TriState.CHECKED)
            self.assertEqual(result['group_write'], TriState.UNCHECKED)

    def test_get_common_mode_with_stat_failures(self):
        """get_common_mode returns failed_count for files that can't be stat'd."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'file1.txt'
            file1.write_text('content')
            os.chmod(file1, 0o755)
            nonexistent = Path(tmpdir) / 'nonexistent.txt'

            result, failed_count = get_common_mode([file1, nonexistent])

            self.assertEqual(failed_count, 1)
            # Should still return valid results for the file that worked
            self.assertEqual(result['owner_exec'], TriState.CHECKED)

    def test_get_common_mode_all_fail(self):
        """get_common_mode returns all UNCHECKED when all files fail stat."""
        nonexistent1 = Path('/nonexistent/file1.txt')
        nonexistent2 = Path('/nonexistent/file2.txt')

        result, failed_count = get_common_mode([nonexistent1, nonexistent2])

        self.assertEqual(failed_count, 2)
        self.assertEqual(result['owner_read'], TriState.UNCHECKED)
        self.assertEqual(result['owner_write'], TriState.UNCHECKED)

    def test_get_common_mode_empty_list(self):
        """get_common_mode returns all UNCHECKED for empty list."""
        result, failed_count = get_common_mode([])

        self.assertEqual(failed_count, 0)
        self.assertEqual(result['owner_read'], TriState.UNCHECKED)


class TestSystemUsers(unittest.TestCase):
    """Tests for get_system_users function."""

    def test_get_system_users_returns_list(self):
        """get_system_users returns a list of usernames."""
        users = get_system_users()
        self.assertIsInstance(users, list)
        self.assertGreater(len(users), 0)
        # Current user should be in the list
        import pwd
        current_user = pwd.getpwuid(os.getuid()).pw_name
        self.assertIn(current_user, users)


class TestSystemGroups(unittest.TestCase):
    """Tests for get_system_groups function."""

    def test_get_system_groups_returns_list(self):
        """get_system_groups returns a list of group names."""
        groups = get_system_groups()
        self.assertIsInstance(groups, list)
        self.assertGreater(len(groups), 0)


class TestFilterByPrefix(unittest.TestCase):
    """Tests for filter_by_prefix function."""

    def test_filter_by_prefix_basic(self):
        """filter_by_prefix returns matching items."""
        items = ['alice', 'bob', 'adam', 'anna']
        result = filter_by_prefix(items, 'a')
        self.assertEqual(result, ['adam', 'alice', 'anna'])

    def test_filter_by_prefix_case_insensitive(self):
        """filter_by_prefix is case insensitive."""
        items = ['Alice', 'Bob', 'Adam']
        result = filter_by_prefix(items, 'a')
        self.assertEqual(result, ['Adam', 'Alice'])

    def test_filter_by_prefix_empty(self):
        """filter_by_prefix with empty prefix returns all sorted."""
        items = ['bob', 'alice']
        result = filter_by_prefix(items, '')
        self.assertEqual(result, ['alice', 'bob'])

    def test_filter_by_prefix_no_matches(self):
        """filter_by_prefix returns empty list when no matches."""
        items = ['alice', 'bob']
        result = filter_by_prefix(items, 'x')
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
