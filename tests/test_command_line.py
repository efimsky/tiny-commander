"""Tests for command line input area."""

import curses
import unittest
from unittest import mock

from tnc.command_line import CommandLine


class TestCommandLinePrompt(unittest.TestCase):
    """Test command line prompt display."""

    def test_command_line_renders_prompt(self):
        """Command line should show current directory as prompt."""
        cmdline = CommandLine('/home/user/docs')
        rendered = cmdline.get_display_text(width=80)
        self.assertIn('/home/user/docs>', rendered)

    def test_long_prompt_truncated(self):
        """Long paths should be truncated."""
        cmdline = CommandLine('/very/long/path/that/exceeds/width')
        rendered = cmdline.get_display_text(width=30)
        self.assertLessEqual(len(rendered), 30)
        self.assertIn('>', rendered)


class TestTyping(unittest.TestCase):
    """Test character input."""

    def test_typing_adds_characters(self):
        """Characters should be added to input."""
        cmdline = CommandLine('/home/user')
        cmdline.handle_char('l')
        cmdline.handle_char('s')
        self.assertEqual(cmdline.input_text, 'ls')

    def test_insert_in_middle_of_text(self):
        """Characters inserted at cursor position."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'ls -la'
        cmdline.cursor_pos = 3
        cmdline.handle_char('x')
        self.assertEqual(cmdline.input_text, 'ls x-la')
        self.assertEqual(cmdline.cursor_pos, 4)


class TestBackspace(unittest.TestCase):
    """Test backspace key."""

    def test_backspace_removes_character(self):
        """Backspace should remove character before cursor."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'ls -la'
        cmdline.cursor_pos = 6
        cmdline.handle_key(curses.KEY_BACKSPACE)
        self.assertEqual(cmdline.input_text, 'ls -l')
        self.assertEqual(cmdline.cursor_pos, 5)

    def test_backspace_ascii_127(self):
        """ASCII 127 should also work as backspace."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'ab'
        cmdline.cursor_pos = 2
        cmdline.handle_key(127)
        self.assertEqual(cmdline.input_text, 'a')

    def test_backspace_ctrl_h(self):
        """Ctrl+H should also work as backspace."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'ab'
        cmdline.cursor_pos = 2
        cmdline.handle_key(8)  # Ctrl+H
        self.assertEqual(cmdline.input_text, 'a')

    def test_backspace_at_start_does_nothing(self):
        """Backspace at start should do nothing."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'test'
        cmdline.cursor_pos = 0
        cmdline.handle_key(curses.KEY_BACKSPACE)
        self.assertEqual(cmdline.input_text, 'test')

    def test_backspace_on_empty_does_nothing(self):
        """Backspace on empty input should do nothing."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = ''
        cmdline.handle_key(curses.KEY_BACKSPACE)
        self.assertEqual(cmdline.input_text, '')


class TestDelete(unittest.TestCase):
    """Test delete key."""

    def test_delete_removes_character_after_cursor(self):
        """Delete should remove character at cursor."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'hello'
        cmdline.cursor_pos = 2
        cmdline.handle_key(curses.KEY_DC)
        self.assertEqual(cmdline.input_text, 'helo')
        self.assertEqual(cmdline.cursor_pos, 2)

    def test_delete_at_end_does_nothing(self):
        """Delete at end should do nothing."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'test'
        cmdline.cursor_pos = 4
        cmdline.handle_key(curses.KEY_DC)
        self.assertEqual(cmdline.input_text, 'test')


class TestCursorMovement(unittest.TestCase):
    """Test cursor movement keys."""

    def test_left_arrow_moves_cursor(self):
        """Left arrow should move cursor left."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'hello'
        cmdline.cursor_pos = 5
        cmdline.handle_key(curses.KEY_LEFT)
        self.assertEqual(cmdline.cursor_pos, 4)

    def test_right_arrow_moves_cursor(self):
        """Right arrow should move cursor right."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'hello'
        cmdline.cursor_pos = 2
        cmdline.handle_key(curses.KEY_RIGHT)
        self.assertEqual(cmdline.cursor_pos, 3)

    def test_cursor_cannot_go_before_start(self):
        """Cursor should not go before start."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'hi'
        cmdline.cursor_pos = 0
        cmdline.handle_key(curses.KEY_LEFT)
        self.assertEqual(cmdline.cursor_pos, 0)

    def test_cursor_cannot_go_past_end(self):
        """Cursor should not go past end."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'hi'
        cmdline.cursor_pos = 2
        cmdline.handle_key(curses.KEY_RIGHT)
        self.assertEqual(cmdline.cursor_pos, 2)

    def test_home_moves_to_start(self):
        """Home should move cursor to start."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'hello'
        cmdline.cursor_pos = 3
        cmdline.handle_key(curses.KEY_HOME)
        self.assertEqual(cmdline.cursor_pos, 0)

    def test_end_moves_to_end(self):
        """End should move cursor to end."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'hello'
        cmdline.cursor_pos = 2
        cmdline.handle_key(curses.KEY_END)
        self.assertEqual(cmdline.cursor_pos, 5)


class TestEscape(unittest.TestCase):
    """Test escape key."""

    def test_escape_clears_input(self):
        """Escape should clear input."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'some command'
        cmdline.cursor_pos = 5
        cmdline.handle_key(27)  # Escape
        self.assertEqual(cmdline.input_text, '')
        self.assertEqual(cmdline.cursor_pos, 0)


class TestEnter(unittest.TestCase):
    """Test enter key."""

    def test_enter_returns_command(self):
        """Enter should return the input text."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'ls -la'
        result = cmdline.handle_key(curses.KEY_ENTER)
        self.assertEqual(result, 'ls -la')

    def test_enter_clears_input(self):
        """Enter should clear input after returning."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'ls -la'
        cmdline.handle_key(curses.KEY_ENTER)
        self.assertEqual(cmdline.input_text, '')

    def test_newline_also_works(self):
        """Newline character should also work."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'pwd'
        result = cmdline.handle_key(ord('\n'))
        self.assertEqual(result, 'pwd')


class TestSetPath(unittest.TestCase):
    """Test path updating."""

    def test_set_path_updates_prompt(self):
        """Setting path should update prompt."""
        cmdline = CommandLine('/old/path')
        cmdline.set_path('/new/path')
        rendered = cmdline.get_display_text(width=80)
        self.assertIn('/new/path>', rendered)


if __name__ == '__main__':
    unittest.main()
