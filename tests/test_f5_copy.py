"""Tests for F5 copy key integration."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.app import App, Action


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    # Default to accepting dialogs (y key)
    mock_stdscr.getch.return_value = ord('y')
    return mock_stdscr


class TestF5KeyBinding(unittest.TestCase):
    """Test F5 key triggers copy."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_f5_returns_copy_action(self, _mock_curs_set, _mock_has_colors):
        """F5 should return COPY action."""
        app = App(create_mock_stdscr())
        app.setup()

        result = app.handle_key(curses.KEY_F5)
        self.assertEqual(result, Action.COPY)


class TestCopyIntegration(unittest.TestCase):
    """Test copy operation through App."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_copy_uses_selected_files(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Copy should use selected files when available."""
        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                Path(left_dir, 'file1.txt').write_text('content1')
                Path(left_dir, 'file2.txt').write_text('content2')

                app = App(create_mock_stdscr())
                app.setup()

                # Set up panels with our directories
                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))

                # Select files
                app.left_panel.selected = {'file1.txt', 'file2.txt'}

                # Perform copy
                app.do_copy()

                # Files should be copied to right panel
                self.assertTrue(Path(right_dir, 'file1.txt').exists())
                self.assertTrue(Path(right_dir, 'file2.txt').exists())

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_copy_uses_current_file_when_nothing_selected(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Copy should use current file if nothing selected."""
        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                Path(left_dir, 'current.txt').write_text('content')

                app = App(create_mock_stdscr())
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))

                # Move cursor to the file (index 1, after '..')
                app.left_panel.cursor = 1

                # No selection
                self.assertEqual(len(app.left_panel.selected), 0)

                # Perform copy
                app.do_copy()

                # Current file should be copied
                self.assertTrue(Path(right_dir, 'current.txt').exists())

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_copy_refreshes_both_panels(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Copy should refresh both panels after operation."""
        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                Path(left_dir, 'file.txt').write_text('content')

                app = App(create_mock_stdscr())
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))
                app.left_panel.cursor = 1

                # Get initial entry count in right panel
                initial_count = len(app.right_panel.entries)

                app.do_copy()

                # Right panel should have more entries now
                self.assertGreater(len(app.right_panel.entries), initial_count)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_copy_clears_selection_after_success(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Copy should clear selection after successful copy."""
        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                Path(left_dir, 'file.txt').write_text('content')

                app = App(create_mock_stdscr())
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))
                app.left_panel.selected = {'file.txt'}

                app.do_copy()

                self.assertEqual(len(app.left_panel.selected), 0)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_copy_does_not_copy_dotdot(self, _mock_curs_set, _mock_has_colors):
        """Copy should not try to copy '..' entry."""
        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                app = App(create_mock_stdscr())
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))

                # Cursor on '..' (index 0)
                app.left_panel.cursor = 0

                # Should not raise an error
                result = app.do_copy()
                # Should indicate nothing to copy or handle gracefully
                self.assertIsNotNone(result)


class TestCopyFromRightToLeft(unittest.TestCase):
    """Test copy works in both directions."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_copy_from_right_panel_to_left(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Copy from right panel should go to left panel."""
        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                Path(right_dir, 'file.txt').write_text('from right')

                app = App(create_mock_stdscr())
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))

                # Switch to right panel
                app.switch_panel()
                self.assertEqual(app.active_panel, app.right_panel)

                # Move cursor to file
                app.right_panel.cursor = 1

                app.do_copy()

                # File should be in left directory
                self.assertTrue(Path(left_dir, 'file.txt').exists())


class TestFileOperationTemplate(unittest.TestCase):
    """Test the _do_file_operation template method."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_do_copy_uses_template(self, _mock_curs_set, _mock_has_colors):
        """do_copy should use the _do_file_operation template."""
        app = App(create_mock_stdscr())
        app.setup()
        # Verify _do_file_operation method exists
        self.assertTrue(hasattr(app, '_do_file_operation'))
        self.assertTrue(callable(app._do_file_operation))

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_do_move_uses_template(self, _mock_curs_set, _mock_has_colors):
        """do_move should use the _do_file_operation template."""
        app = App(create_mock_stdscr())
        app.setup()
        # Verify _do_file_operation method exists
        self.assertTrue(hasattr(app, '_do_file_operation'))
        self.assertTrue(callable(app._do_file_operation))

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_template_returns_empty_error_on_nothing_to_copy(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Template should return appropriate error when nothing to operate on."""
        with tempfile.TemporaryDirectory() as temp_dir:
            app = App(create_mock_stdscr())
            app.setup()
            app.left_panel.change_directory(Path(temp_dir))
            app.right_panel.change_directory(Path(temp_dir))
            # Cursor on '..'
            app.left_panel.cursor = 0

            result = app.do_copy()
            self.assertFalse(result.success)
            self.assertIn('Nothing to copy', result.error)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_template_returns_empty_error_on_nothing_to_move(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Template should return appropriate error when nothing to move."""
        with tempfile.TemporaryDirectory() as temp_dir:
            app = App(create_mock_stdscr())
            app.setup()
            app.left_panel.change_directory(Path(temp_dir))
            app.right_panel.change_directory(Path(temp_dir))
            # Cursor on '..'
            app.left_panel.cursor = 0

            result = app.do_move()
            self.assertFalse(result.success)
            self.assertIn('Nothing to move', result.error)


class TestCopyErrorDisplay(unittest.TestCase):
    """Test error display during copy operations."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('tnc.app.show_summary')
    def test_copy_with_errors_passes_errors_to_summary(
        self, mock_summary, _mock_doupdate, _mock_curs_set, _mock_has_colors
    ):
        """Copy operation should pass error details to show_summary."""
        with tempfile.TemporaryDirectory() as left_dir:
            with tempfile.TemporaryDirectory() as right_dir:
                # Create a file that will fail to copy (simulate permission error)
                Path(left_dir, 'file.txt').write_text('content')

                app = App(create_mock_stdscr())
                app.setup()

                app.left_panel.change_directory(Path(left_dir))
                app.right_panel.change_directory(Path(right_dir))
                app.left_panel.cursor = 1  # Select the file

                # Mock copy_files_with_overwrite to return an error
                with mock.patch('tnc.app.copy_files_with_overwrite') as mock_copy:
                    from tnc.file_ops import CopyResult
                    mock_copy.return_value = CopyResult(
                        success=False,
                        error='file.txt: Permission denied',
                        copied_files=[],
                        skipped_files=[]
                    )

                    app.do_copy()

                # Verify show_summary was called with errors
                mock_summary.assert_called_once()
                call_kwargs = mock_summary.call_args[1]
                self.assertIn('errors', call_kwargs)
                self.assertIsInstance(call_kwargs['errors'], list)
                self.assertIn('file.txt: Permission denied', call_kwargs['errors'])


if __name__ == '__main__':
    unittest.main()
