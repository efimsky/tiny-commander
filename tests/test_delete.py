"""Tests for F8 delete operation."""

import curses
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.file_ops import delete_files, DeleteResult


class TestDeleteSingleFile(unittest.TestCase):
    """Test deleting a single file."""

    def test_delete_single_file(self):
        """Delete single file."""
        with tempfile.TemporaryDirectory() as parent_dir:
            target = Path(parent_dir, 'file.txt')
            target.write_text('test')

            result = delete_files(['file.txt'], parent_dir)

            self.assertTrue(result.success)
            self.assertFalse(target.exists())

    def test_delete_preserves_other_files(self):
        """Delete should only remove specified files."""
        with tempfile.TemporaryDirectory() as parent_dir:
            Path(parent_dir, 'delete_me.txt').write_text('delete')
            keep = Path(parent_dir, 'keep_me.txt')
            keep.write_text('keep')

            delete_files(['delete_me.txt'], parent_dir)

            self.assertTrue(keep.exists())


class TestDeleteMultipleFiles(unittest.TestCase):
    """Test deleting multiple files."""

    def test_delete_multiple_files(self):
        """Delete multiple files at once."""
        with tempfile.TemporaryDirectory() as parent_dir:
            Path(parent_dir, 'a.txt').write_text('a')
            Path(parent_dir, 'b.txt').write_text('b')

            result = delete_files(['a.txt', 'b.txt'], parent_dir)

            self.assertTrue(result.success)
            self.assertFalse(Path(parent_dir, 'a.txt').exists())
            self.assertFalse(Path(parent_dir, 'b.txt').exists())


class TestDeleteDirectory(unittest.TestCase):
    """Test deleting directories."""

    def test_delete_directory_recursive(self):
        """Delete directory with contents."""
        with tempfile.TemporaryDirectory() as parent_dir:
            subdir = Path(parent_dir, 'subdir')
            subdir.mkdir()
            Path(subdir, 'nested.txt').write_text('nested')

            result = delete_files(['subdir'], parent_dir)

            self.assertTrue(result.success)
            self.assertFalse(subdir.exists())

    def test_delete_nonempty_directory(self):
        """Delete directory with many files."""
        with tempfile.TemporaryDirectory() as parent_dir:
            bigdir = Path(parent_dir, 'bigdir')
            bigdir.mkdir()
            for i in range(10):
                Path(bigdir, f'file{i}.txt').touch()

            result = delete_files(['bigdir'], parent_dir)

            self.assertTrue(result.success)
            self.assertFalse(bigdir.exists())


class TestDeleteSymlink(unittest.TestCase):
    """Test deleting symlinks."""

    def test_delete_symlink_not_target(self):
        """Deleting symlink should not delete target."""
        with tempfile.TemporaryDirectory() as parent_dir:
            target = Path(parent_dir, 'target.txt')
            target.write_text('target')
            link = Path(parent_dir, 'mylink')
            link.symlink_to('target.txt')

            delete_files(['mylink'], parent_dir)

            self.assertFalse(link.exists())
            self.assertTrue(target.exists())

    def test_delete_broken_symlink(self):
        """Broken symlinks should be deletable."""
        with tempfile.TemporaryDirectory() as parent_dir:
            link = Path(parent_dir, 'broken_link')
            link.symlink_to('nonexistent')

            result = delete_files(['broken_link'], parent_dir)

            self.assertTrue(result.success)
            self.assertFalse(link.is_symlink())


class TestDeleteValidation(unittest.TestCase):
    """Test delete input validation."""

    def test_delete_dotdot_rejected(self):
        """Cannot delete '..' entry."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = delete_files(['..'], parent_dir)

            self.assertFalse(result.success)
            self.assertIn('..', result.error)

    def test_delete_empty_list_succeeds(self):
        """Empty file list should succeed."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = delete_files([], parent_dir)
            self.assertTrue(result.success)


class TestDeleteErrorHandling(unittest.TestCase):
    """Test delete error handling."""

    def test_delete_nonexistent_file(self):
        """Delete of nonexistent file should report error."""
        with tempfile.TemporaryDirectory() as parent_dir:
            result = delete_files(['nonexistent.txt'], parent_dir)

            self.assertFalse(result.success)

    def test_delete_permission_denied(self):
        """Delete in protected directory should fail gracefully."""
        with tempfile.TemporaryDirectory() as parent_dir:
            target = Path(parent_dir, 'file.txt')
            target.write_text('test')
            os.chmod(parent_dir, 0o555)

            try:
                result = delete_files(['file.txt'], parent_dir)
                self.assertFalse(result.success)
            finally:
                os.chmod(parent_dir, 0o755)


class TestDeleteResult(unittest.TestCase):
    """Test DeleteResult dataclass."""

    def test_delete_result_success(self):
        """DeleteResult should track success state."""
        result = DeleteResult(success=True)
        self.assertTrue(result.success)

    def test_delete_result_failure(self):
        """DeleteResult should track error message."""
        result = DeleteResult(success=False, error='Test error')
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Test error')


class TestF8KeyBinding(unittest.TestCase):
    """Test F8 key triggers delete."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_f8_returns_delete_action(self, _mock_curs_set, _mock_has_colors):
        """F8 should return DELETE action."""
        from tnc.app import App, Action

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        result = app.handle_key(curses.KEY_F8)
        self.assertEqual(result, Action.DELETE)


class TestPanelDelete(unittest.TestCase):
    """Test delete through Panel."""

    def test_panel_delete_selected(self):
        """Panel should delete selected files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from tnc.panel import Panel

            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.selected = {'file1.txt'}

            result = panel.delete_selected()

            self.assertTrue(result.success)
            self.assertFalse(Path(tmpdir, 'file1.txt').exists())
            self.assertTrue(Path(tmpdir, 'file2.txt').exists())

    def test_panel_delete_current_if_nothing_selected(self):
        """Panel should delete current file if nothing selected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from tnc.panel import Panel

            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.cursor = 1  # file.txt (after ..)

            result = panel.delete_selected()

            self.assertTrue(result.success)
            self.assertFalse(Path(tmpdir, 'file.txt').exists())

    def test_cursor_adjusts_after_delete(self):
        """Cursor should stay valid after delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from tnc.panel import Panel

            Path(tmpdir, 'a.txt').touch()
            Path(tmpdir, 'b.txt').touch()
            Path(tmpdir, 'c.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            # Cursor on last file
            panel.cursor = len(panel.entries) - 1
            original_count = len(panel.entries)
            filename = panel.entries[panel.cursor].name
            panel.selected = {filename}

            panel.delete_selected()

            self.assertLessEqual(panel.cursor, len(panel.entries) - 1)
            self.assertEqual(len(panel.entries), original_count - 1)


class TestDeleteErrorDisplay(unittest.TestCase):
    """Test error display during delete operations."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('tnc.app.show_error_dialog')
    def test_delete_with_errors_shows_error_dialog(
        self, mock_error_dialog, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ):
        """Delete operation should show error dialog when files fail to delete."""
        from tnc.app import App
        from tnc.file_ops import DeleteResult

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').write_text('content')

            mock_stdscr = mock.MagicMock()
            mock_stdscr.getmaxyx.return_value = (24, 80)
            mock_stdscr.getch.return_value = ord('y')  # Confirm delete

            app = App(mock_stdscr)
            app.setup()

            app.active_panel.change_directory(Path(tmpdir))
            app.active_panel.cursor = 1  # Select the file

            # Mock delete_selected to return an error
            with mock.patch.object(app.active_panel, 'delete_selected') as mock_delete:
                mock_delete.return_value = DeleteResult(
                    success=False,
                    error='file.txt: Permission denied',
                    deleted_files=[]
                )

                app._prompt_delete()

            # Verify show_error_dialog was called
            mock_error_dialog.assert_called_once()
            call_args = mock_error_dialog.call_args[0]
            self.assertIn('Delete', call_args[1])  # title
            self.assertIn('Permission denied', call_args[2])  # message


if __name__ == '__main__':
    unittest.main()
