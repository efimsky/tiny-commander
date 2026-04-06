"""Tests for dialog module."""

import unittest
from unittest.mock import MagicMock, patch, call


class TestFormatSize(unittest.TestCase):
    """Tests for format_size function."""

    def test_format_size_bytes(self):
        """Sizes under 1KB should show bytes."""
        from tnc.dialog import format_size
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(1023), "1023 B")

    def test_format_size_kilobytes(self):
        """Sizes 1KB-1MB should show KB."""
        from tnc.dialog import format_size
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(2048), "2.0 KB")
        self.assertEqual(format_size(1536), "1.5 KB")

    def test_format_size_megabytes(self):
        """Sizes 1MB-1GB should show MB."""
        from tnc.dialog import format_size
        self.assertEqual(format_size(1024 * 1024), "1.0 MB")
        self.assertEqual(format_size(1024 * 1024 * 5), "5.0 MB")

    def test_format_size_gigabytes(self):
        """Sizes over 1GB should show GB."""
        from tnc.dialog import format_size
        self.assertEqual(format_size(1024 * 1024 * 1024), "1.0 GB")
        self.assertEqual(format_size(1024 * 1024 * 1024 * 2), "2.0 GB")


class TestFormatTime(unittest.TestCase):
    """Tests for format_time function."""

    def test_format_time_returns_datetime_string(self):
        """format_time should return YYYY-MM-DD HH:MM format."""
        from tnc.dialog import format_time
        # Use a known timestamp: 2024-01-15 14:30:00 UTC
        # Note: Result depends on local timezone
        result = format_time(1705329000)
        # Just check the format is correct (YYYY-MM-DD HH:MM)
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}')


class TestDrawModal(unittest.TestCase):
    """Tests for draw_modal function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_win = MagicMock()
        self.mock_win.getmaxyx.return_value = (24, 80)

    @patch('tnc.dialog.get_attr')
    def test_draw_modal_centers_horizontally(self, mock_get_attr):
        """Modal should be centered horizontally."""
        mock_get_attr.return_value = 0
        from tnc.dialog import draw_modal

        draw_modal(self.mock_win, 'Title', ['Line 1'], width=20)

        # Window is 80 wide, modal is 20 wide, so x should be (80-20)//2 = 30
        calls = self.mock_win.addstr.call_args_list
        # First call should be the top border at x=30
        self.assertEqual(calls[0][0][1], 30)

    @patch('tnc.dialog.get_attr')
    def test_draw_modal_centers_vertically(self, mock_get_attr):
        """Modal should be centered vertically."""
        mock_get_attr.return_value = 0
        from tnc.dialog import draw_modal

        # Modal with title + 2 lines + borders = 5 rows
        draw_modal(self.mock_win, 'Title', ['Line 1', 'Line 2'], width=20)

        # Window is 24 high, modal is 5 high (top border + title + 2 lines + bottom border)
        # y should be (24-5)//2 = 9
        calls = self.mock_win.addstr.call_args_list
        self.assertEqual(calls[0][0][0], 9)

    @patch('tnc.dialog.get_attr')
    def test_draw_modal_renders_title(self, mock_get_attr):
        """Modal should render the title."""
        mock_get_attr.return_value = 0
        from tnc.dialog import draw_modal

        draw_modal(self.mock_win, 'Test Title', ['Content'], width=30)

        # Find the call that contains the title
        title_found = False
        for call_item in self.mock_win.addstr.call_args_list:
            args = call_item[0]
            if len(args) >= 3 and 'Test Title' in str(args[2]):
                title_found = True
                break
        self.assertTrue(title_found, "Title should be rendered")

    @patch('tnc.dialog.get_attr')
    def test_draw_modal_renders_content_lines(self, mock_get_attr):
        """Modal should render all content lines."""
        mock_get_attr.return_value = 0
        from tnc.dialog import draw_modal

        draw_modal(self.mock_win, 'Title', ['Line 1', 'Line 2', 'Line 3'], width=30)

        # Check that each line is rendered
        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('Line 1', rendered_text)
        self.assertIn('Line 2', rendered_text)
        self.assertIn('Line 3', rendered_text)


class TestConfirmDialog(unittest.TestCase):
    """Tests for confirm_dialog function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_win = MagicMock()
        self.mock_win.getmaxyx.return_value = (24, 80)

    @patch('tnc.dialog.get_attr')
    def test_confirm_returns_true_on_y(self, mock_get_attr):
        """Confirm dialog returns True when user presses 'y'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('y')
        from tnc.dialog import confirm_dialog

        result = confirm_dialog(self.mock_win, 'Confirm?', 'Do this?')
        self.assertTrue(result)

    @patch('tnc.dialog.get_attr')
    def test_confirm_returns_true_on_Y(self, mock_get_attr):
        """Confirm dialog returns True when user presses 'Y'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('Y')
        from tnc.dialog import confirm_dialog

        result = confirm_dialog(self.mock_win, 'Confirm?', 'Do this?')
        self.assertTrue(result)

    @patch('tnc.dialog.get_attr')
    def test_confirm_returns_false_on_n(self, mock_get_attr):
        """Confirm dialog returns False when user presses 'n'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('n')
        from tnc.dialog import confirm_dialog

        result = confirm_dialog(self.mock_win, 'Confirm?', 'Do this?')
        self.assertFalse(result)

    @patch('tnc.dialog.get_attr')
    def test_confirm_returns_false_on_escape(self, mock_get_attr):
        """Confirm dialog returns False when user presses Escape."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = 27  # Escape
        from tnc.dialog import confirm_dialog

        result = confirm_dialog(self.mock_win, 'Confirm?', 'Do this?')
        self.assertFalse(result)

    @patch('tnc.dialog.get_attr')
    def test_confirm_ignores_other_keys(self, mock_get_attr):
        """Confirm dialog ignores keys other than y/n/Escape."""
        mock_get_attr.return_value = 0
        # Press 'x' first, then 'y'
        self.mock_win.getch.side_effect = [ord('x'), ord('y')]
        from tnc.dialog import confirm_dialog

        result = confirm_dialog(self.mock_win, 'Confirm?', 'Do this?')
        self.assertTrue(result)
        self.assertEqual(self.mock_win.getch.call_count, 2)


class TestOverwriteDialog(unittest.TestCase):
    """Tests for overwrite_dialog function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_win = MagicMock()
        self.mock_win.getmaxyx.return_value = (24, 80)

    @patch('tnc.dialog.get_attr')
    def test_overwrite_returns_yes_on_y(self, mock_get_attr):
        """Overwrite dialog returns YES when user presses 'y'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('y')
        from tnc.dialog import overwrite_dialog
        from tnc.file_ops import OverwriteChoice

        result = overwrite_dialog(
            self.mock_win, 'file.txt', 1024, 2048,
            source_mtime=1000, dest_mtime=900,
            current=1, total=5
        )
        self.assertEqual(result, OverwriteChoice.YES)

    @patch('tnc.dialog.get_attr')
    def test_overwrite_returns_no_on_n(self, mock_get_attr):
        """Overwrite dialog returns NO when user presses 'n'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('n')
        from tnc.dialog import overwrite_dialog
        from tnc.file_ops import OverwriteChoice

        result = overwrite_dialog(
            self.mock_win, 'file.txt', 1024, 2048,
            source_mtime=1000, dest_mtime=900,
            current=1, total=5
        )
        self.assertEqual(result, OverwriteChoice.NO)

    @patch('tnc.dialog.get_attr')
    def test_overwrite_returns_yes_all_on_a(self, mock_get_attr):
        """Overwrite dialog returns YES_ALL when user presses 'a'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('a')
        from tnc.dialog import overwrite_dialog
        from tnc.file_ops import OverwriteChoice

        result = overwrite_dialog(
            self.mock_win, 'file.txt', 1024, 2048,
            source_mtime=1000, dest_mtime=900,
            current=1, total=5
        )
        self.assertEqual(result, OverwriteChoice.YES_ALL)

    @patch('tnc.dialog.get_attr')
    def test_overwrite_returns_no_all_on_s(self, mock_get_attr):
        """Overwrite dialog returns NO_ALL when user presses 's'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('s')
        from tnc.dialog import overwrite_dialog
        from tnc.file_ops import OverwriteChoice

        result = overwrite_dialog(
            self.mock_win, 'file.txt', 1024, 2048,
            source_mtime=1000, dest_mtime=900,
            current=1, total=5
        )
        self.assertEqual(result, OverwriteChoice.NO_ALL)

    @patch('tnc.dialog.get_attr')
    def test_overwrite_returns_yes_older_on_o(self, mock_get_attr):
        """Overwrite dialog returns YES_OLDER when user presses 'o'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('o')
        from tnc.dialog import overwrite_dialog
        from tnc.file_ops import OverwriteChoice

        result = overwrite_dialog(
            self.mock_win, 'file.txt', 1024, 2048,
            source_mtime=1000, dest_mtime=900,
            current=1, total=5
        )
        self.assertEqual(result, OverwriteChoice.YES_OLDER)

    @patch('tnc.dialog.get_attr')
    def test_overwrite_returns_cancel_on_escape(self, mock_get_attr):
        """Overwrite dialog returns CANCEL when user presses Escape."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = 27  # Escape
        from tnc.dialog import overwrite_dialog
        from tnc.file_ops import OverwriteChoice

        result = overwrite_dialog(
            self.mock_win, 'file.txt', 1024, 2048,
            source_mtime=1000, dest_mtime=900,
            current=1, total=5
        )
        self.assertEqual(result, OverwriteChoice.CANCEL)

    @patch('tnc.dialog.get_attr')
    def test_overwrite_displays_progress(self, mock_get_attr):
        """Overwrite dialog should display progress counter."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('y')
        from tnc.dialog import overwrite_dialog

        overwrite_dialog(
            self.mock_win, 'file.txt', 1024, 2048,
            source_mtime=1000, dest_mtime=900,
            current=3, total=10
        )

        # Check that progress is rendered
        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('3', rendered_text)
        self.assertIn('10', rendered_text)


class TestShowSummary(unittest.TestCase):
    """Tests for show_summary function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_win = MagicMock()
        self.mock_win.getmaxyx.return_value = (24, 80)

    def test_summary_shows_copied_count(self):
        """Summary should show number of copied files."""
        from tnc.dialog import show_summary

        show_summary(self.mock_win, 'copy', copied=5, skipped=0)

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('5', rendered_text)
        self.assertIn('Copied', rendered_text)

    def test_summary_shows_skipped_count(self):
        """Summary should show number of skipped files when non-zero."""
        from tnc.dialog import show_summary

        show_summary(self.mock_win, 'copy', copied=3, skipped=2)

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('skipped', rendered_text)
        self.assertIn('2', rendered_text)

    def test_summary_waits_for_keypress(self):
        """Summary should wait for a keypress before returning."""
        from tnc.dialog import show_summary

        show_summary(self.mock_win, 'copy', copied=5, skipped=0)

        self.mock_win.getch.assert_called_once()


class TestSelectionDialogStructure(unittest.TestCase):
    """Test SelectionDialog basic structure."""

    def test_selection_dialog_has_title(self):
        """SelectionDialog should accept and store a title."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Select Editor', options=['nano', 'vim'])
        self.assertEqual(dialog.title, 'Select Editor')

    def test_selection_dialog_has_options(self):
        """SelectionDialog should accept and store options."""
        from tnc.dialog import SelectionDialog
        options = ['nano', 'vim', 'emacs']
        dialog = SelectionDialog(title='Test', options=options)
        self.assertEqual(dialog.options, options)

    def test_selection_dialog_allows_custom(self):
        """SelectionDialog should support allow_custom flag."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano'], allow_custom=True)
        self.assertTrue(dialog.allow_custom)


class TestSelectionDialogInput(unittest.TestCase):
    """Test SelectionDialog input handling."""

    def test_number_key_returns_selection(self):
        """Pressing number key should return corresponding option."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano', 'vim', 'emacs'])
        result = dialog.handle_key(ord('1'))
        self.assertEqual(result, 'nano')

    def test_number_key_returns_second_option(self):
        """Pressing '2' should return second option."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano', 'vim', 'emacs'])
        result = dialog.handle_key(ord('2'))
        self.assertEqual(result, 'vim')

    def test_escape_returns_none(self):
        """Pressing Escape should return None (cancel)."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano', 'vim'])
        result = dialog.handle_key(27)  # Escape
        self.assertIsNone(result)

    def test_invalid_number_returns_none(self):
        """Pressing invalid number should return None (no action)."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano', 'vim'])
        result = dialog.handle_key(ord('9'))  # Out of range
        self.assertIsNone(result)

    def test_custom_option_triggers_input_mode(self):
        """Selecting Custom option should trigger input mode."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano', 'vim'], allow_custom=True)
        # Options are: 1=nano, 2=vim, 3=Custom
        result = dialog.handle_key(ord('3'))
        self.assertTrue(dialog.in_custom_input_mode)


class TestSelectionDialogCustomInput(unittest.TestCase):
    """Test SelectionDialog custom text input."""

    def test_custom_mode_accepts_text(self):
        """Custom input mode should accept text characters."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano'], allow_custom=True)
        dialog.handle_key(ord('2'))  # Select Custom
        self.assertTrue(dialog.in_custom_input_mode)

        # Type characters
        dialog.handle_key(ord('c'))
        dialog.handle_key(ord('o'))
        dialog.handle_key(ord('d'))
        dialog.handle_key(ord('e'))

        self.assertEqual(dialog.custom_text, 'code')

    def test_custom_mode_enter_returns_text(self):
        """Enter in custom mode should return the typed text."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano'], allow_custom=True)
        dialog.handle_key(ord('2'))  # Select Custom
        dialog.handle_key(ord('v'))
        dialog.handle_key(ord('i'))
        dialog.handle_key(ord('m'))
        result = dialog.handle_key(ord('\n'))  # Enter

        self.assertEqual(result, 'vim')

    def test_custom_mode_escape_cancels(self):
        """Escape in custom mode should return to selection mode."""
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano'], allow_custom=True)
        dialog.handle_key(ord('2'))  # Select Custom
        dialog.handle_key(ord('t'))
        dialog.handle_key(ord('e'))
        dialog.handle_key(27)  # Escape

        self.assertFalse(dialog.in_custom_input_mode)
        self.assertEqual(dialog.custom_text, '')

    def test_custom_mode_backspace_deletes(self):
        """Backspace in custom mode should delete last character."""
        import curses
        from tnc.dialog import SelectionDialog
        dialog = SelectionDialog(title='Test', options=['nano'], allow_custom=True)
        dialog.handle_key(ord('2'))  # Select Custom
        dialog.handle_key(ord('a'))
        dialog.handle_key(ord('b'))
        dialog.handle_key(ord('c'))
        dialog.handle_key(curses.KEY_BACKSPACE)

        self.assertEqual(dialog.custom_text, 'ab')


class TestConfirmDialogEnterDefault(unittest.TestCase):
    """Test confirm_dialog Enter key behavior."""

    def test_confirm_dialog_enter_returns_default_yes(self):
        """Enter should return True when default_yes=True."""
        from tnc.dialog import confirm_dialog
        mock_win = MagicMock()
        mock_win.getmaxyx.return_value = (24, 80)
        mock_win.getch.return_value = ord('\n')  # Enter

        with patch('tnc.dialog.get_attr', return_value=0):
            result = confirm_dialog(mock_win, 'Test', 'Message?', default_yes=True)

        self.assertTrue(result)

    def test_confirm_dialog_enter_returns_default_no(self):
        """Enter should return False when default_yes=False."""
        from tnc.dialog import confirm_dialog
        mock_win = MagicMock()
        mock_win.getmaxyx.return_value = (24, 80)
        mock_win.getch.return_value = ord('\n')  # Enter

        with patch('tnc.dialog.get_attr', return_value=0):
            result = confirm_dialog(mock_win, 'Test', 'Message?', default_yes=False)

        self.assertFalse(result)


class TestRenderDialogFrame(unittest.TestCase):
    """Tests for _render_dialog_frame helper function."""

    def test_top_border_format(self):
        """Top border should be ┌───┐ format."""
        from tnc.dialog import _render_dialog_frame
        frame = _render_dialog_frame(width=20)
        self.assertEqual(frame['top'], "┌" + "─" * 18 + "┐")

    def test_bottom_border_format(self):
        """Bottom border should be └───┘ format."""
        from tnc.dialog import _render_dialog_frame
        frame = _render_dialog_frame(width=20)
        self.assertEqual(frame['bottom'], "└" + "─" * 18 + "┘")

    def test_separator_format(self):
        """Separator should be ├───┤ format."""
        from tnc.dialog import _render_dialog_frame
        frame = _render_dialog_frame(width=20)
        self.assertEqual(frame['separator'], "├" + "─" * 18 + "┤")

    def test_title_line_centered(self):
        """Title should be centered within side borders."""
        from tnc.dialog import _render_dialog_frame
        frame = _render_dialog_frame(width=20, title='Test')
        # Title centered in 18 chars (width - 2 for borders)
        expected = 'Test'.center(18)
        self.assertEqual(frame['title_content'], expected)

    def test_content_line_padded(self):
        """Content line should be padded and have side borders."""
        from tnc.dialog import _render_dialog_frame
        frame = _render_dialog_frame(width=20)
        content = frame['content_line']('Hello')
        # │ Hello          │ (with padding)
        self.assertEqual(content[0], '│')
        self.assertEqual(content[-1], '│')
        self.assertIn('Hello', content)
        self.assertEqual(len(content), 20)

    def test_empty_line_format(self):
        """Empty line should be │ spaces │."""
        from tnc.dialog import _render_dialog_frame
        frame = _render_dialog_frame(width=20)
        empty = frame['empty']
        self.assertEqual(empty, "│" + " " * 18 + "│")

    def test_different_widths(self):
        """Frame elements should adapt to different widths."""
        from tnc.dialog import _render_dialog_frame
        frame_30 = _render_dialog_frame(width=30)
        frame_50 = _render_dialog_frame(width=50)

        self.assertEqual(len(frame_30['top']), 30)
        self.assertEqual(len(frame_50['top']), 50)
        self.assertEqual(len(frame_30['bottom']), 30)
        self.assertEqual(len(frame_50['bottom']), 50)


class TestShowErrorDialog(unittest.TestCase):
    """Tests for show_error_dialog function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_win = MagicMock()
        self.mock_win.getmaxyx.return_value = (24, 80)

    @patch('tnc.dialog.get_attr')
    def test_show_error_dialog_displays_title(self, mock_get_attr):
        """Error dialog should display the title."""
        mock_get_attr.return_value = 0
        from tnc.dialog import show_error_dialog

        show_error_dialog(self.mock_win, 'Error', 'Something went wrong')

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('Error', rendered_text)

    @patch('tnc.dialog.get_attr')
    def test_show_error_dialog_displays_message(self, mock_get_attr):
        """Error dialog should display the message."""
        mock_get_attr.return_value = 0
        from tnc.dialog import show_error_dialog

        show_error_dialog(self.mock_win, 'Error', 'Something went wrong')

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('Something went wrong', rendered_text)

    @patch('tnc.dialog.get_attr')
    def test_show_error_dialog_waits_for_keypress(self, mock_get_attr):
        """Error dialog should wait for a keypress before returning."""
        mock_get_attr.return_value = 0
        from tnc.dialog import show_error_dialog

        show_error_dialog(self.mock_win, 'Error', 'Something went wrong')

        self.mock_win.getch.assert_called_once()

    @patch('tnc.dialog.get_attr')
    def test_show_error_dialog_displays_details(self, mock_get_attr):
        """Error dialog should display detail lines when provided."""
        mock_get_attr.return_value = 0
        from tnc.dialog import show_error_dialog

        details = ['file1.txt: Permission denied', 'file2.txt: Permission denied']
        show_error_dialog(self.mock_win, 'Error', 'Copy failed', details=details)

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('file1.txt: Permission denied', rendered_text)
        self.assertIn('file2.txt: Permission denied', rendered_text)

    @patch('tnc.dialog.get_attr')
    def test_show_error_dialog_truncates_long_details(self, mock_get_attr):
        """Error dialog should truncate details when there are too many."""
        mock_get_attr.return_value = 0
        from tnc.dialog import show_error_dialog

        details = [f'file{i}.txt: Permission denied' for i in range(10)]
        show_error_dialog(self.mock_win, 'Error', 'Copy failed', details=details, max_details=3)

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        # Should show first 3 details plus truncation message
        self.assertIn('file0.txt: Permission denied', rendered_text)
        self.assertIn('file1.txt: Permission denied', rendered_text)
        self.assertIn('file2.txt: Permission denied', rendered_text)
        self.assertIn('7 more', rendered_text)  # 10 - 3 = 7 more
        # Should NOT show file3 through file9
        self.assertNotIn('file3.txt', rendered_text)


class TestShowSummaryWithErrors(unittest.TestCase):
    """Tests for show_summary function with error display."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_win = MagicMock()
        self.mock_win.getmaxyx.return_value = (24, 80)

    @patch('tnc.dialog.get_attr')
    def test_summary_with_errors_displays_error_details(self, mock_get_attr):
        """Summary should display error details when provided."""
        mock_get_attr.return_value = 0
        from tnc.dialog import show_summary

        errors = ['file1.txt: Permission denied']
        show_summary(self.mock_win, 'copy', copied=2, errors=errors)

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('file1.txt: Permission denied', rendered_text)

    @patch('tnc.dialog.get_attr')
    def test_summary_truncates_many_errors(self, mock_get_attr):
        """Summary should truncate error list when there are many errors."""
        mock_get_attr.return_value = 0
        from tnc.dialog import show_summary

        errors = [f'file{i}.txt: Permission denied' for i in range(10)]
        show_summary(self.mock_win, 'copy', copied=2, errors=errors, max_errors=3)

        rendered_text = ' '.join(str(c) for c in self.mock_win.addstr.call_args_list)
        self.assertIn('7 more', rendered_text)  # 10 - 3 = 7 more


class TestDialogProviderProtocol(unittest.TestCase):
    """Tests for DialogProvider Protocol."""

    def test_protocol_defines_confirm(self):
        """DialogProvider Protocol should define confirm method."""
        from tnc.dialog import DialogProvider
        from typing import get_type_hints
        # Protocol should have confirm method
        self.assertTrue(hasattr(DialogProvider, 'confirm'))

    def test_protocol_defines_select(self):
        """DialogProvider Protocol should define select method."""
        from tnc.dialog import DialogProvider
        self.assertTrue(hasattr(DialogProvider, 'select'))

    def test_protocol_defines_show_summary(self):
        """DialogProvider Protocol should define show_summary method."""
        from tnc.dialog import DialogProvider
        self.assertTrue(hasattr(DialogProvider, 'show_summary'))


class TestCursesDialogProvider(unittest.TestCase):
    """Tests for CursesDialogProvider implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_win = MagicMock()
        self.mock_win.getmaxyx.return_value = (24, 80)

    @patch('tnc.dialog.get_attr')
    def test_confirm_returns_true_on_y(self, mock_get_attr):
        """CursesDialogProvider.confirm should return True on 'y'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('y')
        from tnc.dialog import CursesDialogProvider

        provider = CursesDialogProvider(self.mock_win)
        result = provider.confirm('Title', 'Message?')

        self.assertTrue(result)

    @patch('tnc.dialog.get_attr')
    def test_confirm_returns_false_on_n(self, mock_get_attr):
        """CursesDialogProvider.confirm should return False on 'n'."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('n')
        from tnc.dialog import CursesDialogProvider

        provider = CursesDialogProvider(self.mock_win)
        result = provider.confirm('Title', 'Message?')

        self.assertFalse(result)

    @patch('tnc.dialog.get_attr')
    def test_select_returns_selected_option(self, mock_get_attr):
        """CursesDialogProvider.select should return selected option."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = ord('1')
        from tnc.dialog import CursesDialogProvider

        provider = CursesDialogProvider(self.mock_win)
        result = provider.select('Title', ['option1', 'option2'])

        self.assertEqual(result, 'option1')

    @patch('tnc.dialog.get_attr')
    def test_select_returns_none_on_escape(self, mock_get_attr):
        """CursesDialogProvider.select should return None on Escape."""
        mock_get_attr.return_value = 0
        self.mock_win.getch.return_value = 27  # Escape
        from tnc.dialog import CursesDialogProvider

        provider = CursesDialogProvider(self.mock_win)
        result = provider.select('Title', ['option1', 'option2'])

        self.assertIsNone(result)


class TestMockDialogProvider(unittest.TestCase):
    """Tests for using mock DialogProvider in tests."""

    def test_can_create_mock_provider(self):
        """Should be able to create a mock that implements DialogProvider."""
        from tnc.dialog import DialogProvider
        mock_provider = MagicMock(spec=DialogProvider)
        mock_provider.confirm.return_value = True

        result = mock_provider.confirm('Title', 'Message?')

        self.assertTrue(result)
        mock_provider.confirm.assert_called_once_with('Title', 'Message?')

    def test_mock_provider_select(self):
        """Mock provider should support select method."""
        from tnc.dialog import DialogProvider
        mock_provider = MagicMock(spec=DialogProvider)
        mock_provider.select.return_value = 'nano'

        result = mock_provider.select('Select editor', ['nano', 'vim'])

        self.assertEqual(result, 'nano')


if __name__ == '__main__':
    unittest.main()
