"""Tests for utility functions."""

import curses
import stat
import unittest
from unittest import mock


class TestFormatPermissions(unittest.TestCase):
    """Test format_permissions function."""

    def test_regular_file_rw_r_r(self):
        """Regular file with 644 permissions."""
        from tnc.utils import format_permissions

        # -rw-r--r-- = 0o100644
        mode = stat.S_IFREG | 0o644
        result = format_permissions(mode)
        self.assertEqual(result, '-rw-r--r--')

    def test_regular_file_rwx_rx_rx(self):
        """Executable file with 755 permissions."""
        from tnc.utils import format_permissions

        # -rwxr-xr-x = 0o100755
        mode = stat.S_IFREG | 0o755
        result = format_permissions(mode)
        self.assertEqual(result, '-rwxr-xr-x')

    def test_directory_rwx_rx_rx(self):
        """Directory with 755 permissions."""
        from tnc.utils import format_permissions

        # drwxr-xr-x = 0o40755
        mode = stat.S_IFDIR | 0o755
        result = format_permissions(mode)
        self.assertEqual(result, 'drwxr-xr-x')

    def test_directory_rwx_rwx_rwx(self):
        """Directory with 777 permissions."""
        from tnc.utils import format_permissions

        # drwxrwxrwx = 0o40777
        mode = stat.S_IFDIR | 0o777
        result = format_permissions(mode)
        self.assertEqual(result, 'drwxrwxrwx')

    def test_symlink(self):
        """Symbolic link."""
        from tnc.utils import format_permissions

        # lrwxrwxrwx = 0o120777
        mode = stat.S_IFLNK | 0o777
        result = format_permissions(mode)
        self.assertEqual(result, 'lrwxrwxrwx')

    def test_no_permissions(self):
        """File with no permissions."""
        from tnc.utils import format_permissions

        # ---------- = 0o100000
        mode = stat.S_IFREG | 0o000
        result = format_permissions(mode)
        self.assertEqual(result, '----------')

    def test_write_only(self):
        """File with write-only permissions."""
        from tnc.utils import format_permissions

        # --w--w--w- = 0o100222
        mode = stat.S_IFREG | 0o222
        result = format_permissions(mode)
        self.assertEqual(result, '--w--w--w-')

    def test_execute_only(self):
        """File with execute-only permissions."""
        from tnc.utils import format_permissions

        # ---x--x--x = 0o100111
        mode = stat.S_IFREG | 0o111
        result = format_permissions(mode)
        self.assertEqual(result, '---x--x--x')

    def test_sticky_bit_with_execute(self):
        """Directory with sticky bit and execute permission (like /tmp)."""
        from tnc.utils import format_permissions

        # drwxrwxrwt = 0o41777
        mode = stat.S_IFDIR | 0o777 | stat.S_ISVTX
        result = format_permissions(mode)
        self.assertEqual(result, 'drwxrwxrwt')

    def test_sticky_bit_without_execute(self):
        """Directory with sticky bit but no other execute."""
        from tnc.utils import format_permissions

        # drwxrwxrwT = sticky without execute
        mode = stat.S_IFDIR | 0o776 | stat.S_ISVTX
        result = format_permissions(mode)
        self.assertEqual(result, 'drwxrwxrwT')

    def test_setuid_with_execute(self):
        """File with setuid and execute permission."""
        from tnc.utils import format_permissions

        # -rwsr-xr-x = setuid with execute
        mode = stat.S_IFREG | 0o755 | stat.S_ISUID
        result = format_permissions(mode)
        self.assertEqual(result, '-rwsr-xr-x')

    def test_setuid_without_execute(self):
        """File with setuid but no owner execute."""
        from tnc.utils import format_permissions

        # -rwSr-xr-x = setuid without execute
        mode = stat.S_IFREG | 0o655 | stat.S_ISUID
        result = format_permissions(mode)
        self.assertEqual(result, '-rwSr-xr-x')

    def test_setgid_with_execute(self):
        """File with setgid and group execute permission."""
        from tnc.utils import format_permissions

        # -rwxr-sr-x = setgid with execute
        mode = stat.S_IFREG | 0o755 | stat.S_ISGID
        result = format_permissions(mode)
        self.assertEqual(result, '-rwxr-sr-x')

    def test_setgid_without_execute(self):
        """File with setgid but no group execute."""
        from tnc.utils import format_permissions

        # -rwxr-Sr-x = setgid without execute
        mode = stat.S_IFREG | 0o745 | stat.S_ISGID
        result = format_permissions(mode)
        self.assertEqual(result, '-rwxr-Sr-x')

    def test_character_device(self):
        """Character device file."""
        from tnc.utils import format_permissions

        mode = stat.S_IFCHR | 0o666
        result = format_permissions(mode)
        self.assertEqual(result, 'crw-rw-rw-')

    def test_block_device(self):
        """Block device file."""
        from tnc.utils import format_permissions

        mode = stat.S_IFBLK | 0o660
        result = format_permissions(mode)
        self.assertEqual(result, 'brw-rw----')

    def test_fifo_pipe(self):
        """Named pipe (FIFO)."""
        from tnc.utils import format_permissions

        mode = stat.S_IFIFO | 0o644
        result = format_permissions(mode)
        self.assertEqual(result, 'prw-r--r--')

    def test_socket(self):
        """Unix socket."""
        from tnc.utils import format_permissions

        mode = stat.S_IFSOCK | 0o755
        result = format_permissions(mode)
        self.assertEqual(result, 'srwxr-xr-x')


class TestFormatSize(unittest.TestCase):
    """Test format_size function."""

    def test_negative_size(self):
        """Negative sizes should return placeholder."""
        from tnc.utils import format_size

        self.assertEqual(format_size(-1), '?')
        self.assertEqual(format_size(-1024), '?')

    def test_bytes(self):
        """Sizes under 1K should show bytes."""
        from tnc.utils import format_size

        self.assertEqual(format_size(0), '0')
        self.assertEqual(format_size(512), '512')
        self.assertEqual(format_size(1023), '1023')

    def test_kilobytes(self):
        """Sizes in KB range."""
        from tnc.utils import format_size

        self.assertEqual(format_size(1024), '1.0K')
        self.assertEqual(format_size(1536), '1.5K')

    def test_megabytes(self):
        """Sizes in MB range."""
        from tnc.utils import format_size

        self.assertEqual(format_size(1024 * 1024), '1.0M')
        self.assertEqual(format_size(2 * 1024 * 1024), '2.0M')

    def test_gigabytes(self):
        """Sizes in GB range."""
        from tnc.utils import format_size

        self.assertEqual(format_size(1024 * 1024 * 1024), '1.0G')


class TestSafeAddstr(unittest.TestCase):
    """Test safe_addstr function."""

    def test_safe_addstr_success(self):
        """safe_addstr should call win.addstr with provided arguments."""
        from tnc.utils import safe_addstr

        win = mock.MagicMock()
        safe_addstr(win, 5, 10, 'hello', curses.A_BOLD)

        win.addstr.assert_called_once_with(5, 10, 'hello', curses.A_BOLD)

    def test_safe_addstr_default_attr(self):
        """safe_addstr should use 0 as default attribute."""
        from tnc.utils import safe_addstr

        win = mock.MagicMock()
        safe_addstr(win, 0, 0, 'text')

        win.addstr.assert_called_once_with(0, 0, 'text', 0)

    def test_safe_addstr_curses_error_ignored(self):
        """safe_addstr should silently ignore curses.error exceptions."""
        from tnc.utils import safe_addstr

        win = mock.MagicMock()
        win.addstr.side_effect = curses.error('addstr() returned ERR')

        # Should not raise
        safe_addstr(win, 100, 200, 'out of bounds')

    def test_safe_addstr_other_exceptions_propagate(self):
        """safe_addstr should not catch non-curses exceptions."""
        from tnc.utils import safe_addstr

        win = mock.MagicMock()
        win.addstr.side_effect = TypeError('unexpected error')

        with self.assertRaises(TypeError):
            safe_addstr(win, 0, 0, 'text')

    def test_safe_addstr_empty_string(self):
        """safe_addstr should handle empty strings."""
        from tnc.utils import safe_addstr

        win = mock.MagicMock()
        safe_addstr(win, 0, 0, '')

        win.addstr.assert_called_once_with(0, 0, '', 0)

    def test_safe_addstr_unicode(self):
        """safe_addstr should handle unicode strings."""
        from tnc.utils import safe_addstr

        win = mock.MagicMock()
        safe_addstr(win, 0, 0, '日本語テスト')

        win.addstr.assert_called_once_with(0, 0, '日本語テスト', 0)


if __name__ == '__main__':
    unittest.main()
