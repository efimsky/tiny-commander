"""Tests for F6 move operation."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.file_ops import move_files, MoveResult


class TestMoveSingleFile(unittest.TestCase):
    """Test moving a single file."""

    def test_move_single_file(self):
        """Move single file to destination."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_file = Path(source_dir, 'file.txt')
                source_file.write_text('hello')

                result = move_files(['file.txt'], source_dir, dest_dir)

                self.assertTrue(result.success)
                dest_file = Path(dest_dir, 'file.txt')
                self.assertTrue(dest_file.exists())
                self.assertEqual(dest_file.read_text(), 'hello')
                # Original should be gone
                self.assertFalse(source_file.exists())


class TestMoveMultipleFiles(unittest.TestCase):
    """Test moving multiple files."""

    def test_move_multiple_files(self):
        """Move multiple files at once."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'a.txt').write_text('a')
                Path(source_dir, 'b.txt').write_text('b')

                result = move_files(['a.txt', 'b.txt'], source_dir, dest_dir)

                self.assertTrue(result.success)
                self.assertTrue(Path(dest_dir, 'a.txt').exists())
                self.assertTrue(Path(dest_dir, 'b.txt').exists())
                self.assertFalse(Path(source_dir, 'a.txt').exists())
                self.assertFalse(Path(source_dir, 'b.txt').exists())


class TestMoveDirectory(unittest.TestCase):
    """Test moving directories."""

    def test_move_directory_recursive(self):
        """Move directory with contents recursively."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                subdir = Path(source_dir, 'subdir')
                subdir.mkdir()
                Path(subdir, 'nested.txt').write_text('nested')

                result = move_files(['subdir'], source_dir, dest_dir)

                self.assertTrue(result.success)
                self.assertTrue(Path(dest_dir, 'subdir').is_dir())
                self.assertTrue(Path(dest_dir, 'subdir', 'nested.txt').exists())
                # Original should be gone
                self.assertFalse(Path(source_dir, 'subdir').exists())


class TestMovePreservesMetadata(unittest.TestCase):
    """Test that move preserves file metadata."""

    def test_move_preserves_permissions(self):
        """Move should preserve file permissions."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                script = Path(source_dir, 'script.sh')
                script.write_text('#!/bin/bash')
                os.chmod(script, 0o755)

                move_files(['script.sh'], source_dir, dest_dir)

                dest_mode = os.stat(Path(dest_dir, 'script.sh')).st_mode
                self.assertTrue(dest_mode & stat.S_IXUSR)


class TestMoveErrorHandling(unittest.TestCase):
    """Test error handling during move."""

    def test_move_to_same_directory_fails(self):
        """Move to same directory should fail gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').write_text('test')

            result = move_files(['file.txt'], tmpdir, tmpdir)

            self.assertFalse(result.success)
            self.assertIn('same', result.error.lower())

    def test_move_nonexistent_file_reports_error(self):
        """Move of nonexistent file should report error."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                result = move_files(['nonexistent.txt'], source_dir, dest_dir)

                self.assertFalse(result.success)

    def test_move_permission_denied_leaves_source_intact(self):
        """Move to read-only dir should fail and leave source intact."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_file = Path(source_dir, 'file.txt')
                source_file.write_text('test')
                os.chmod(dest_dir, 0o555)

                try:
                    result = move_files(['file.txt'], source_dir, dest_dir)
                    self.assertFalse(result.success)
                    # Source should still exist
                    self.assertTrue(source_file.exists())
                finally:
                    os.chmod(dest_dir, 0o755)

    def test_move_empty_list_does_nothing(self):
        """Move with empty file list should succeed but do nothing."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                result = move_files([], source_dir, dest_dir)
                self.assertTrue(result.success)


class TestMoveResult(unittest.TestCase):
    """Test MoveResult dataclass."""

    def test_move_result_success(self):
        """MoveResult should track success state."""
        result = MoveResult(success=True)
        self.assertTrue(result.success)
        self.assertEqual(result.error, '')

    def test_move_result_failure(self):
        """MoveResult should track error message."""
        result = MoveResult(success=False, error='Test error')
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Test error')


class TestF6KeyBinding(unittest.TestCase):
    """Test F6 key triggers move."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_f6_returns_move_action(self, _mock_curs_set, _mock_has_colors):
        """F6 should return MOVE action."""
        import curses
        from tnc.app import App, Action

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)
        mock_stdscr.getch.return_value = ord('y')

        app = App(mock_stdscr)
        app.setup()

        result = app.handle_key(curses.KEY_F6)
        self.assertEqual(result, Action.MOVE)


class TestMoveIntegration(unittest.TestCase):
    """Test move operation through App."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_move_removes_from_source(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Move should remove files from source panel."""
        from tnc.app import App

        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                Path(left_dir, 'file.txt').write_text('content')

                mock_stdscr = mock.MagicMock()
                mock_stdscr.getmaxyx.return_value = (24, 80)
                mock_stdscr.getch.return_value = ord('y')

                app = App(mock_stdscr)
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))
                app.left_panel.selected = {'file.txt'}

                app.do_move()

                # File should be in dest, not in source
                self.assertTrue(Path(right_dir, 'file.txt').exists())
                self.assertFalse(Path(left_dir, 'file.txt').exists())


class TestMoveErrorDisplay(unittest.TestCase):
    """Test error display during move operations."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('tnc.app.show_summary')
    def test_move_with_errors_passes_errors_to_summary(
        self, mock_summary, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ):
        """Move operation should pass error details to show_summary."""
        from tnc.app import App
        from tnc.file_ops import MoveResult

        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                Path(left_dir, 'file.txt').write_text('content')

                mock_stdscr = mock.MagicMock()
                mock_stdscr.getmaxyx.return_value = (24, 80)
                mock_stdscr.getch.return_value = ord('y')

                app = App(mock_stdscr)
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))
                app.left_panel.cursor = 1  # Select the file

                # Mock move_files_with_overwrite to return an error
                with mock.patch('tnc.app.move_files_with_overwrite') as mock_move:
                    mock_move.return_value = MoveResult(
                        success=False,
                        error='file.txt: Permission denied',
                        moved_files=[],
                        skipped_files=[]
                    )

                    app.do_move()

                # Verify show_summary was called with errors
                mock_summary.assert_called_once()
                call_kwargs = mock_summary.call_args[1]
                self.assertIn('errors', call_kwargs)
                self.assertIsInstance(call_kwargs['errors'], list)
                self.assertIn('file.txt: Permission denied', call_kwargs['errors'])


if __name__ == '__main__':
    unittest.main()
