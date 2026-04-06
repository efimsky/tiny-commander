"""Tests for modal text input dialog."""

import curses
import unittest
from unittest import mock

from tnc.dialog import InputDialog


class TestInputDialogInit(unittest.TestCase):
    """Test InputDialog initialization."""

    def test_init_default_values(self):
        """InputDialog should initialize with empty text and cursor at 0."""
        dialog = InputDialog('Title', 'Enter name:')
        self.assertEqual(dialog.title, 'Title')
        self.assertEqual(dialog.prompt, 'Enter name:')
        self.assertEqual(dialog.text, '')
        self.assertEqual(dialog.cursor_pos, 0)

    def test_init_with_default_value(self):
        """InputDialog should initialize with default value and cursor at end."""
        dialog = InputDialog('Title', 'Enter name:', default_value='hello')
        self.assertEqual(dialog.text, 'hello')
        self.assertEqual(dialog.cursor_pos, 5)


class TestInputDialogTyping(unittest.TestCase):
    """Test basic character input."""

    def test_type_single_character(self):
        """Typing a character should add it to text."""
        dialog = InputDialog('Title', 'Prompt')
        result = dialog.handle_key(ord('a'))
        self.assertIsNone(result)
        self.assertEqual(dialog.text, 'a')
        self.assertEqual(dialog.cursor_pos, 1)

    def test_type_multiple_characters(self):
        """Typing multiple characters should build up text."""
        dialog = InputDialog('Title', 'Prompt')
        dialog.handle_key(ord('h'))
        dialog.handle_key(ord('i'))
        self.assertEqual(dialog.text, 'hi')
        self.assertEqual(dialog.cursor_pos, 2)

    def test_type_space(self):
        """Space should be accepted as input."""
        dialog = InputDialog('Title', 'Prompt')
        dialog.handle_key(ord(' '))
        self.assertEqual(dialog.text, ' ')

    def test_type_special_chars(self):
        """Special printable characters should be accepted."""
        dialog = InputDialog('Title', 'Prompt')
        for ch in '.-_~!@#$%':
            dialog.handle_key(ord(ch))
        self.assertEqual(dialog.text, '.-_~!@#$%')

    def test_insert_at_cursor_position(self):
        """Characters should be inserted at cursor position, not appended."""
        dialog = InputDialog('Title', 'Prompt', default_value='ac')
        dialog.cursor_pos = 1  # Between 'a' and 'c'
        dialog.handle_key(ord('b'))
        self.assertEqual(dialog.text, 'abc')
        self.assertEqual(dialog.cursor_pos, 2)


class TestInputDialogEnterEscape(unittest.TestCase):
    """Test Enter and Escape key handling."""

    def test_enter_returns_text(self):
        """Enter should return the current text."""
        dialog = InputDialog('Title', 'Prompt')
        dialog.handle_key(ord('h'))
        dialog.handle_key(ord('i'))
        result = dialog.handle_key(ord('\n'))
        self.assertEqual(result, 'hi')

    def test_carriage_return_returns_text(self):
        """Carriage return should also return the current text."""
        dialog = InputDialog('Title', 'Prompt', default_value='test')
        result = dialog.handle_key(ord('\r'))
        self.assertEqual(result, 'test')

    def test_curses_key_enter_returns_text(self):
        """curses.KEY_ENTER should return the current text."""
        dialog = InputDialog('Title', 'Prompt', default_value='test')
        result = dialog.handle_key(curses.KEY_ENTER)
        self.assertEqual(result, 'test')

    def test_enter_on_empty_returns_empty(self):
        """Enter on empty input should return empty string."""
        dialog = InputDialog('Title', 'Prompt')
        result = dialog.handle_key(ord('\n'))
        self.assertEqual(result, '')

    def test_escape_returns_none(self):
        """Escape should return None (cancelled)."""
        dialog = InputDialog('Title', 'Prompt', default_value='something')
        result = dialog.handle_key(27)  # Escape
        self.assertIsNone(result)


class TestInputDialogBackspace(unittest.TestCase):
    """Test backspace key handling."""

    def test_backspace_deletes_last_char(self):
        """Backspace should delete character before cursor."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.handle_key(curses.KEY_BACKSPACE)
        self.assertEqual(dialog.text, 'ab')
        self.assertEqual(dialog.cursor_pos, 2)

    def test_backspace_127_deletes_char(self):
        """ASCII DEL (127) should work as backspace."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.handle_key(127)
        self.assertEqual(dialog.text, 'ab')

    def test_backspace_8_deletes_char(self):
        """ASCII BS (8) should work as backspace."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.handle_key(8)
        self.assertEqual(dialog.text, 'ab')

    def test_backspace_at_beginning_does_nothing(self):
        """Backspace at start of text should do nothing."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.cursor_pos = 0
        dialog.handle_key(curses.KEY_BACKSPACE)
        self.assertEqual(dialog.text, 'abc')
        self.assertEqual(dialog.cursor_pos, 0)

    def test_backspace_in_middle(self):
        """Backspace in middle should delete char before cursor."""
        dialog = InputDialog('Title', 'Prompt', default_value='abcd')
        dialog.cursor_pos = 2  # After 'ab'
        dialog.handle_key(curses.KEY_BACKSPACE)
        self.assertEqual(dialog.text, 'acd')
        self.assertEqual(dialog.cursor_pos, 1)


class TestInputDialogDelete(unittest.TestCase):
    """Test delete key handling."""

    def test_delete_removes_char_at_cursor(self):
        """Delete should remove character at cursor position."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.cursor_pos = 0
        dialog.handle_key(curses.KEY_DC)
        self.assertEqual(dialog.text, 'bc')
        self.assertEqual(dialog.cursor_pos, 0)

    def test_delete_in_middle(self):
        """Delete in middle should remove char at cursor."""
        dialog = InputDialog('Title', 'Prompt', default_value='abcd')
        dialog.cursor_pos = 1
        dialog.handle_key(curses.KEY_DC)
        self.assertEqual(dialog.text, 'acd')
        self.assertEqual(dialog.cursor_pos, 1)

    def test_delete_at_end_does_nothing(self):
        """Delete at end of text should do nothing."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.cursor_pos = 3
        dialog.handle_key(curses.KEY_DC)
        self.assertEqual(dialog.text, 'abc')
        self.assertEqual(dialog.cursor_pos, 3)


class TestInputDialogArrowKeys(unittest.TestCase):
    """Test left/right arrow key navigation."""

    def test_left_arrow_moves_cursor_left(self):
        """Left arrow should move cursor one position left."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.handle_key(curses.KEY_LEFT)
        self.assertEqual(dialog.cursor_pos, 2)

    def test_left_arrow_at_start_does_nothing(self):
        """Left arrow at start should not move cursor."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.cursor_pos = 0
        dialog.handle_key(curses.KEY_LEFT)
        self.assertEqual(dialog.cursor_pos, 0)

    def test_right_arrow_moves_cursor_right(self):
        """Right arrow should move cursor one position right."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.cursor_pos = 0
        dialog.handle_key(curses.KEY_RIGHT)
        self.assertEqual(dialog.cursor_pos, 1)

    def test_right_arrow_at_end_does_nothing(self):
        """Right arrow at end should not move cursor."""
        dialog = InputDialog('Title', 'Prompt', default_value='abc')
        dialog.handle_key(curses.KEY_RIGHT)
        self.assertEqual(dialog.cursor_pos, 3)  # Already at end


class TestInputDialogHomeEnd(unittest.TestCase):
    """Test Home and End key navigation."""

    def test_home_moves_cursor_to_start(self):
        """Home key should move cursor to position 0."""
        dialog = InputDialog('Title', 'Prompt', default_value='hello')
        self.assertEqual(dialog.cursor_pos, 5)
        dialog.handle_key(curses.KEY_HOME)
        self.assertEqual(dialog.cursor_pos, 0)

    def test_end_moves_cursor_to_end(self):
        """End key should move cursor to end of text."""
        dialog = InputDialog('Title', 'Prompt', default_value='hello')
        dialog.cursor_pos = 0
        dialog.handle_key(curses.KEY_END)
        self.assertEqual(dialog.cursor_pos, 5)

    def test_home_at_start_does_nothing(self):
        """Home at start should remain at 0."""
        dialog = InputDialog('Title', 'Prompt', default_value='hello')
        dialog.cursor_pos = 0
        dialog.handle_key(curses.KEY_HOME)
        self.assertEqual(dialog.cursor_pos, 0)

    def test_end_at_end_does_nothing(self):
        """End at end should remain at end."""
        dialog = InputDialog('Title', 'Prompt', default_value='hello')
        dialog.handle_key(curses.KEY_END)
        self.assertEqual(dialog.cursor_pos, 5)


class TestInputDialogShow(unittest.TestCase):
    """Test the show() method with mocked curses."""

    def test_show_returns_text_on_enter(self):
        """show() should return typed text when Enter is pressed."""
        dialog = InputDialog('Title', 'Prompt')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.side_effect = [ord('h'), ord('i'), ord('\n')]

        result = dialog.show(stdscr)
        self.assertEqual(result, 'hi')

    def test_show_returns_none_on_escape(self):
        """show() should return None when Escape is pressed."""
        dialog = InputDialog('Title', 'Prompt')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.side_effect = [ord('h'), ord('i'), 27]

        result = dialog.show(stdscr)
        self.assertIsNone(result)

    def test_show_with_default_value(self):
        """show() should start with default value and return it on Enter."""
        dialog = InputDialog('Title', 'Prompt', default_value='default')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.return_value = ord('\n')

        result = dialog.show(stdscr)
        self.assertEqual(result, 'default')

    def test_show_renders_dialog(self):
        """show() should call render before each getch."""
        dialog = InputDialog('Title', 'Prompt')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.return_value = ord('\n')

        with mock.patch.object(dialog, 'render') as mock_render:
            dialog.show(stdscr)
            mock_render.assert_called()

    @mock.patch('curses.curs_set')
    def test_show_enables_cursor(self, mock_curs_set):
        """show() should enable cursor during input and restore after."""
        dialog = InputDialog('Title', 'Prompt')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.return_value = ord('\n')

        dialog.show(stdscr)

        # curs_set(1) at start, curs_set(0) at end
        calls = [c[0][0] for c in mock_curs_set.call_args_list]
        self.assertIn(1, calls)
        self.assertIn(0, calls)
        # curs_set(0) should be the last call (restore)
        self.assertEqual(calls[-1], 0)

    @mock.patch('curses.curs_set')
    def test_show_restores_cursor_on_escape(self, mock_curs_set):
        """show() should restore cursor even when cancelled."""
        dialog = InputDialog('Title', 'Prompt')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.return_value = 27  # Escape

        dialog.show(stdscr)

        # Last call should be curs_set(0) regardless of how dialog exits
        calls = [c[0][0] for c in mock_curs_set.call_args_list]
        self.assertEqual(calls[-1], 0)


class TestInputDialogRender(unittest.TestCase):
    """Test rendering of the dialog."""

    def test_render_draws_title(self):
        """render() should draw the title in the dialog."""
        dialog = InputDialog('My Title', 'Enter name:')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        dialog.render(stdscr)

        # Check that addstr was called (dialog was rendered)
        self.assertTrue(stdscr.addstr.called or
                        any('My Title' in str(c) for c in stdscr.addstr.call_args_list))

    def test_render_on_small_terminal(self):
        """render() should handle small terminals without crashing."""
        dialog = InputDialog('Title', 'Prompt')
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (10, 30)

        # Should not raise
        dialog.render(stdscr)


class TestInputDialogConvenienceFunction(unittest.TestCase):
    """Test the input_dialog() convenience function."""

    def test_input_dialog_returns_text(self):
        """input_dialog() should return typed text."""
        from tnc.dialog import input_dialog

        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.side_effect = [ord('t'), ord('e'), ord('s'), ord('t'), ord('\n')]

        result = input_dialog(stdscr, 'Title', 'Prompt')
        self.assertEqual(result, 'test')

    def test_input_dialog_returns_empty_on_escape(self):
        """input_dialog() should return empty string on escape."""
        from tnc.dialog import input_dialog

        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.return_value = 27

        result = input_dialog(stdscr, 'Title', 'Prompt')
        self.assertEqual(result, '')

    def test_input_dialog_with_default_value(self):
        """input_dialog() should pass default_value to InputDialog."""
        from tnc.dialog import input_dialog

        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.return_value = ord('\n')

        result = input_dialog(stdscr, 'Title', 'Prompt', default_value='hello')
        self.assertEqual(result, 'hello')


if __name__ == '__main__':
    unittest.main()
