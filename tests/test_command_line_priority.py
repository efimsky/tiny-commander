"""Tests for command line input priority over selection modifiers.

When the command line has text, selection modifier keys (+, -, *, /)
should be treated as regular characters instead of triggering panel actions.

This addresses issue #90: Selection modifiers prevent from typing in shell row.
"""

import unittest
from unittest import mock

from tnc.app import Action, App


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    return mock_stdscr


class TestSelectionModifiersWithEmptyCommandLine(unittest.TestCase):
    """Test that selection modifiers work when command line is empty."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_plus_key_triggers_select_pattern_when_cmdline_empty(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'+' key should trigger SELECT_PATTERN when command line is empty."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = ''

        action = app.handle_key(ord('+'))

        self.assertEqual(action, Action.SELECT_PATTERN)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_minus_key_triggers_deselect_pattern_when_cmdline_empty(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'-' key should trigger DESELECT_PATTERN when command line is empty."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = ''

        action = app.handle_key(ord('-'))

        self.assertEqual(action, Action.DESELECT_PATTERN)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_asterisk_key_inverts_selection_when_cmdline_empty(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'*' key should invert selection when command line is empty."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = ''

        with mock.patch.object(app.active_panel, 'invert_selection') as mock_invert:
            app.handle_key(ord('*'))
            mock_invert.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_slash_key_starts_search_when_cmdline_empty(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'/' key should start search when command line is empty."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = ''

        with mock.patch.object(app.active_panel, 'start_search') as mock_search:
            app.handle_key(ord('/'))
            mock_search.assert_called_once()


class TestSelectionModifiersWithCommandLineText(unittest.TestCase):
    """Test that selection modifiers insert into command line when it has text."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_plus_key_inserts_when_cmdline_has_text(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'+' key should insert '+' into command line when it has text."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = 'echo 1'
        app.command_line.cursor_pos = 6

        action = app.handle_key(ord('+'))

        self.assertEqual(action, Action.NONE)
        self.assertEqual(app.command_line.input_text, 'echo 1+')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_minus_key_inserts_when_cmdline_has_text(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'-' key should insert '-' into command line when it has text."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = 'ls '
        app.command_line.cursor_pos = 3

        action = app.handle_key(ord('-'))

        self.assertEqual(action, Action.NONE)
        self.assertEqual(app.command_line.input_text, 'ls -')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_asterisk_key_inserts_when_cmdline_has_text(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'*' key should insert '*' into command line when it has text."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = 'ls '
        app.command_line.cursor_pos = 3

        with mock.patch.object(app.active_panel, 'invert_selection') as mock_invert:
            action = app.handle_key(ord('*'))
            mock_invert.assert_not_called()

        self.assertEqual(action, Action.NONE)
        self.assertEqual(app.command_line.input_text, 'ls *')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_slash_key_inserts_when_cmdline_has_text(
        self, _mock_curs_set, _mock_has_colors
    ):
        """'/' key should insert '/' into command line when it has text."""
        app = App(create_mock_stdscr())
        app.setup()
        app.command_line.input_text = 'cd /usr'
        app.command_line.cursor_pos = 7

        with mock.patch.object(app.active_panel, 'start_search') as mock_search:
            action = app.handle_key(ord('/'))
            mock_search.assert_not_called()

        self.assertEqual(action, Action.NONE)
        self.assertEqual(app.command_line.input_text, 'cd /usr/')


class TestTypingShellCommands(unittest.TestCase):
    """Integration tests for typing common shell commands."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_typing_ls_dash_la(self, _mock_curs_set, _mock_has_colors):
        """Should be able to type 'ls -la' without triggering deselect."""
        app = App(create_mock_stdscr())
        app.setup()

        # Type 'ls -la' character by character
        for char in 'ls -la':
            app.handle_key(ord(char))

        self.assertEqual(app.command_line.input_text, 'ls -la')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_typing_grep_with_wildcards(self, _mock_curs_set, _mock_has_colors):
        """Should be able to type 'grep *.txt' without triggering invert."""
        app = App(create_mock_stdscr())
        app.setup()

        # Type 'grep *.txt' character by character
        for char in 'grep *.txt':
            app.handle_key(ord(char))

        self.assertEqual(app.command_line.input_text, 'grep *.txt')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_typing_path_with_slashes(self, _mock_curs_set, _mock_has_colors):
        """Should be able to type paths with '/' without triggering search."""
        app = App(create_mock_stdscr())
        app.setup()

        # Type 'cd /usr/local/bin' character by character
        for char in 'cd /usr/local/bin':
            app.handle_key(ord(char))

        self.assertEqual(app.command_line.input_text, 'cd /usr/local/bin')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_typing_arithmetic_expression(self, _mock_curs_set, _mock_has_colors):
        """Should be able to type 'echo $((1+2-3*4))' without triggering actions."""
        app = App(create_mock_stdscr())
        app.setup()

        # Type arithmetic expression
        for char in 'echo $((1+2-3*4))':
            app.handle_key(ord(char))

        self.assertEqual(app.command_line.input_text, 'echo $((1+2-3*4))')


if __name__ == '__main__':
    unittest.main()
