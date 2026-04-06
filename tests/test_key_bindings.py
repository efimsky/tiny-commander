"""Tests for key binding integration."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr
from tnc.app import Action, App


class TestHandleNavigationKey(unittest.TestCase):
    """Tests for _handle_navigation_key helper method."""

    def setUp(self):
        """Set up test fixtures."""
        self.patches = [
            mock.patch('curses.has_colors', return_value=False),
            mock.patch('curses.curs_set'),
        ]
        for p in self.patches:
            p.start()

        self.tmpdir = tempfile.TemporaryDirectory()
        self.cwd_patch = mock.patch('os.getcwd', return_value=self.tmpdir.name)
        self.cwd_patch.start()

        self.app = App(create_mock_stdscr())
        self.app.setup()

    def tearDown(self):
        """Clean up."""
        self.cwd_patch.stop()
        self.tmpdir.cleanup()
        for p in self.patches:
            p.stop()

    def test_down_key_returns_action(self):
        """Down key should be handled by navigation helper."""
        result = self.app._handle_navigation_key(curses.KEY_DOWN)
        self.assertEqual(result, Action.NONE)

    def test_up_key_returns_action(self):
        """Up key should be handled by navigation helper."""
        result = self.app._handle_navigation_key(curses.KEY_UP)
        self.assertEqual(result, Action.NONE)

    def test_home_key_returns_action(self):
        """Home key should be handled by navigation helper."""
        result = self.app._handle_navigation_key(curses.KEY_HOME)
        self.assertEqual(result, Action.NONE)

    def test_end_key_returns_action(self):
        """End key should be handled by navigation helper."""
        result = self.app._handle_navigation_key(curses.KEY_END)
        self.assertEqual(result, Action.NONE)

    def test_pageup_key_returns_action(self):
        """Page Up key should be handled by navigation helper."""
        result = self.app._handle_navigation_key(curses.KEY_PPAGE)
        self.assertEqual(result, Action.NONE)

    def test_pagedown_key_returns_action(self):
        """Page Down key should be handled by navigation helper."""
        result = self.app._handle_navigation_key(curses.KEY_NPAGE)
        self.assertEqual(result, Action.NONE)

    def test_tab_key_returns_action(self):
        """Tab key should be handled by navigation helper."""
        result = self.app._handle_navigation_key(ord('\t'))
        self.assertEqual(result, Action.NONE)

    def test_unhandled_key_returns_none(self):
        """Unhandled key should return None."""
        result = self.app._handle_navigation_key(ord('x'))
        self.assertIsNone(result)


class TestHandleSelectionKey(unittest.TestCase):
    """Tests for _handle_selection_key helper method."""

    def setUp(self):
        """Set up test fixtures."""
        self.patches = [
            mock.patch('curses.has_colors', return_value=False),
            mock.patch('curses.curs_set'),
        ]
        for p in self.patches:
            p.start()

        self.tmpdir = tempfile.TemporaryDirectory()
        self.cwd_patch = mock.patch('os.getcwd', return_value=self.tmpdir.name)
        self.cwd_patch.start()

        self.app = App(create_mock_stdscr())
        self.app.setup()

    def tearDown(self):
        """Clean up."""
        self.cwd_patch.stop()
        self.tmpdir.cleanup()
        for p in self.patches:
            p.stop()

    def test_insert_key_returns_action(self):
        """Insert key should be handled by selection helper."""
        result = self.app._handle_selection_key(curses.KEY_IC)
        self.assertEqual(result, Action.NONE)

    def test_star_key_returns_action(self):
        """* key should be handled by selection helper."""
        result = self.app._handle_selection_key(ord('*'))
        self.assertEqual(result, Action.NONE)

    def test_plus_key_returns_select_pattern(self):
        """+ key should return SELECT_PATTERN action."""
        result = self.app._handle_selection_key(ord('+'))
        self.assertEqual(result, Action.SELECT_PATTERN)

    def test_minus_key_returns_deselect_pattern(self):
        """- key should return DESELECT_PATTERN action."""
        result = self.app._handle_selection_key(ord('-'))
        self.assertEqual(result, Action.DESELECT_PATTERN)

    def test_slash_key_returns_action(self):
        """/ key should start search and return action."""
        result = self.app._handle_selection_key(ord('/'))
        self.assertEqual(result, Action.NONE)

    def test_unhandled_key_returns_none(self):
        """Unhandled key should return None."""
        result = self.app._handle_selection_key(ord('x'))
        self.assertIsNone(result)

    def test_space_key_returns_action(self):
        """Space key should be handled by selection helper."""
        result = self.app._handle_selection_key(ord(' '))
        self.assertEqual(result, Action.NONE)

    def test_space_key_ignored_when_command_line_has_text(self):
        """Space key should return None when command line has text."""
        self.app.command_line.handle_char('a')
        result = self.app._handle_selection_key(ord(' '))
        self.assertIsNone(result)

    def test_selection_keys_ignored_when_command_line_has_text(self):
        """Selection keys should return None when command line has text."""
        self.app.command_line.handle_char('a')  # Put text in command line
        result = self.app._handle_selection_key(ord('*'))
        self.assertIsNone(result)


class TestHandleOperationKey(unittest.TestCase):
    """Tests for _handle_operation_key helper method."""

    def setUp(self):
        """Set up test fixtures."""
        self.patches = [
            mock.patch('curses.has_colors', return_value=False),
            mock.patch('curses.curs_set'),
        ]
        for p in self.patches:
            p.start()

        self.tmpdir = tempfile.TemporaryDirectory()
        self.cwd_patch = mock.patch('os.getcwd', return_value=self.tmpdir.name)
        self.cwd_patch.start()

        self.app = App(create_mock_stdscr())
        self.app.setup()

    def tearDown(self):
        """Clean up."""
        self.cwd_patch.stop()
        self.tmpdir.cleanup()
        for p in self.patches:
            p.stop()

    def test_f3_returns_view(self):
        """F3 should return VIEW action."""
        result = self.app._handle_operation_key(curses.KEY_F3)
        self.assertEqual(result, Action.VIEW)

    def test_f4_returns_edit(self):
        """F4 should return EDIT action."""
        result = self.app._handle_operation_key(curses.KEY_F4)
        self.assertEqual(result, Action.EDIT)

    def test_f5_returns_copy(self):
        """F5 should return COPY action."""
        result = self.app._handle_operation_key(curses.KEY_F5)
        self.assertEqual(result, Action.COPY)

    def test_f6_returns_move(self):
        """F6 should return MOVE action."""
        result = self.app._handle_operation_key(curses.KEY_F6)
        self.assertEqual(result, Action.MOVE)

    def test_f7_returns_mkdir(self):
        """F7 should return MKDIR action."""
        result = self.app._handle_operation_key(curses.KEY_F7)
        self.assertEqual(result, Action.MKDIR)

    def test_f8_returns_delete(self):
        """F8 should return DELETE action."""
        result = self.app._handle_operation_key(curses.KEY_F8)
        self.assertEqual(result, Action.DELETE)

    def test_shift_f3_returns_cycle_sort(self):
        """Shift+F3 should return CYCLE_SORT action."""
        result = self.app._handle_operation_key(curses.KEY_F3 + 12)
        self.assertEqual(result, Action.CYCLE_SORT)

    def test_shift_f4_returns_create_file(self):
        """Shift+F4 should return CREATE_FILE action."""
        result = self.app._handle_operation_key(curses.KEY_F4 + 12)
        self.assertEqual(result, Action.CREATE_FILE)

    def test_alt_f3_returns_measure_dir_size(self):
        """Alt+F3 should return MEASURE_DIR_SIZE action."""
        result = self.app._handle_operation_key(curses.KEY_F3 + 48)
        self.assertEqual(result, Action.MEASURE_DIR_SIZE)

    def test_ctrl_f3_returns_toggle_sort_reverse(self):
        """Ctrl+F3 should return TOGGLE_SORT_REVERSE action."""
        result = self.app._handle_operation_key(curses.KEY_F3 + 24)
        self.assertEqual(result, Action.TOGGLE_SORT_REVERSE)

    def test_unhandled_key_returns_none(self):
        """Unhandled key should return None."""
        result = self.app._handle_operation_key(ord('x'))
        self.assertIsNone(result)


def _patch_curses(func):
    """Decorator to patch curses functions for tests."""
    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    return wrapper


class TestPlusMinusKeyBindings(unittest.TestCase):
    """Test + and - key bindings for pattern selection."""

    @_patch_curses
    def test_plus_returns_select_pattern_action(self, *_):
        """+ key should return SELECT_PATTERN action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                action = app.handle_key(ord('+'))

                self.assertEqual(action, Action.SELECT_PATTERN)

    @_patch_curses
    def test_minus_returns_deselect_pattern_action(self, *_):
        """- key should return DESELECT_PATTERN action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                action = app.handle_key(ord('-'))

                self.assertEqual(action, Action.DESELECT_PATTERN)


class TestAltEnterKeyBinding(unittest.TestCase):
    """Test Alt+Enter key binding for filename insertion."""

    @_patch_curses
    def test_alt_enter_inserts_filename(self, *_):
        """Alt+Enter should insert current filename into command line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test.txt').write_text('')

            with mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = create_mock_stdscr()
                app = App(stdscr)
                app.setup()

                # Find test.txt and move cursor to it
                for i, entry in enumerate(app.active_panel.entries):
                    if entry.name == 'test.txt':
                        app.active_panel.cursor = i
                        break

                # Alt+Enter sends Escape (27) followed by Enter
                # Simulate: getch returns Enter after Escape
                stdscr.getch.return_value = ord('\r')
                app.handle_key(27)  # Escape (start of Alt sequence)

                self.assertIn('test.txt', app.command_line.input_text)

    @_patch_curses
    def test_alt_enter_on_dotdot_does_nothing(self, *_):
        """Alt+Enter on '..' should not insert anything."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = create_mock_stdscr()
                app = App(stdscr)
                app.setup()

                app.active_panel.cursor = 0  # '..'
                # Alt+Enter sends Escape followed by Enter
                stdscr.getch.return_value = ord('\r')
                app.handle_key(27)  # Escape

                self.assertEqual(app.command_line.input_text, '')

    @_patch_curses
    def test_escape_alone_does_not_insert_filename(self, *_):
        """Escape alone (no following key) should not insert filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'test.txt').write_text('')

            with mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = create_mock_stdscr()
                app = App(stdscr)
                app.setup()

                # Find test.txt and move cursor to it
                for i, entry in enumerate(app.active_panel.entries):
                    if entry.name == 'test.txt':
                        app.active_panel.cursor = i
                        break

                # Simulate no key following Escape (returns -1 in nodelay mode)
                stdscr.getch.return_value = -1
                app.handle_key(27)  # Escape alone

                self.assertEqual(app.command_line.input_text, '')

    @_patch_curses
    def test_escape_followed_by_other_key_pushes_back(self, *_):
        """Escape followed by non-Enter key should push the key back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                with mock.patch('curses.ungetch') as mock_ungetch:
                    stdscr = create_mock_stdscr()
                    app = App(stdscr)
                    app.setup()

                    # Simulate Escape followed by 'j' key
                    stdscr.getch.return_value = ord('j')
                    app.handle_key(27)  # Escape

                    # 'j' should be pushed back for normal processing
                    mock_ungetch.assert_called_once_with(ord('j'))


class TestAsteriskKeyBinding(unittest.TestCase):
    """Test * key binding for invert selection."""

    @_patch_curses
    def test_asterisk_inverts_selection(self, *_):
        """* key should invert selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'file1.txt').write_text('')
            (Path(tmpdir) / 'file2.txt').write_text('')

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                # Initially nothing selected
                self.assertEqual(len(app.active_panel.selected), 0)

                # Invert should select all files
                app.handle_key(ord('*'))

                self.assertIn('file1.txt', app.active_panel.selected)
                self.assertIn('file2.txt', app.active_panel.selected)


class TestF7KeyBinding(unittest.TestCase):
    """Test F7 key binding for mkdir."""

    @_patch_curses
    def test_f7_returns_mkdir_action(self, *_):
        """F7 key should return MKDIR action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                action = app.handle_key(curses.KEY_F7)

                self.assertEqual(action, Action.MKDIR)


class TestF8KeyBinding(unittest.TestCase):
    """Test F8 key binding for delete."""

    @_patch_curses
    def test_f8_returns_delete_action(self, *_):
        """F8 key should return DELETE action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                action = app.handle_key(curses.KEY_F8)

                self.assertEqual(action, Action.DELETE)


class TestAltF3KeyBinding(unittest.TestCase):
    """Test Alt+F3 key binding for directory size calculation."""

    @_patch_curses
    def test_alt_f3_returns_measure_dir_size_action(self, *_):
        """Alt+F3 (KEY_F51) should return MEASURE_DIR_SIZE action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                # Alt+F3 is sent by terminals as KEY_F51 (KEY_F3 + 48)
                action = app.handle_key(curses.KEY_F3 + 48)

                self.assertEqual(action, Action.MEASURE_DIR_SIZE)


class TestCommandLineKeyboardRouting(unittest.TestCase):
    """Test keyboard input routing to command line."""

    @_patch_curses
    def test_printable_chars_go_to_command_line(self, *_):
        """Printable characters should be added to command line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                app.handle_key(ord('l'))
                app.handle_key(ord('s'))

                self.assertEqual(app.command_line.input_text, 'ls')

    @_patch_curses
    def test_left_right_arrows_control_command_line_cursor(self, *_):
        """Left/Right arrows should move command line cursor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                # Type some text
                app.handle_key(ord('t'))
                app.handle_key(ord('e'))
                app.handle_key(ord('s'))
                app.handle_key(ord('t'))

                self.assertEqual(app.command_line.cursor_pos, 4)

                # Move cursor left
                app.handle_key(curses.KEY_LEFT)
                self.assertEqual(app.command_line.cursor_pos, 3)

                # Move cursor right
                app.handle_key(curses.KEY_RIGHT)
                self.assertEqual(app.command_line.cursor_pos, 4)

    @_patch_curses
    def test_backspace_removes_from_command_line(self, *_):
        """Backspace should remove character from command line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                app.handle_key(ord('a'))
                app.handle_key(ord('b'))
                app.handle_key(127)  # Backspace

                self.assertEqual(app.command_line.input_text, 'a')

    @_patch_curses
    def test_delete_key_works_on_command_line(self, *_):
        """Delete key should remove character at cursor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                app.handle_key(ord('a'))
                app.handle_key(ord('b'))
                app.handle_key(curses.KEY_LEFT)  # Move to position 1
                app.handle_key(curses.KEY_DC)    # Delete 'b'

                self.assertEqual(app.command_line.input_text, 'a')

    @_patch_curses
    def test_special_chars_dont_go_to_command_line(self, *_):
        """Special chars (*, +, -, /) should not go to command line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                app.handle_key(ord('*'))
                app.handle_key(ord('+'))
                app.handle_key(ord('-'))
                app.handle_key(ord('/'))

                self.assertEqual(app.command_line.input_text, '')


class TestDoubleEscapeBehavior(unittest.TestCase):
    """Test double-Escape to clear command line."""

    @_patch_curses
    def test_first_escape_sets_pending_flag(self, *_):
        """First Escape with text should set escape_pending flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = create_mock_stdscr()
                stdscr.getch.return_value = -1  # No key follows Escape
                app = App(stdscr)
                app.setup()

                # Type some text
                app.handle_key(ord('l'))
                app.handle_key(ord('s'))

                # First Escape
                app.handle_key(27)

                self.assertTrue(app.escape_pending)
                self.assertEqual(app.command_line.input_text, 'ls')

    @_patch_curses
    def test_second_escape_clears_command_line(self, *_):
        """Second Escape should clear command line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = create_mock_stdscr()
                stdscr.getch.return_value = -1  # No key follows Escape
                app = App(stdscr)
                app.setup()

                # Type some text
                app.handle_key(ord('l'))
                app.handle_key(ord('s'))

                # First Escape - sets pending
                app.handle_key(27)
                # Second Escape - clears
                app.handle_key(27)

                self.assertFalse(app.escape_pending)
                self.assertEqual(app.command_line.input_text, '')

    @_patch_curses
    def test_other_key_clears_escape_pending(self, *_):
        """Any other key should clear escape_pending flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = create_mock_stdscr()
                stdscr.getch.return_value = -1  # No key follows Escape
                app = App(stdscr)
                app.setup()

                # Type some text and press Escape
                app.handle_key(ord('l'))
                app.handle_key(27)

                self.assertTrue(app.escape_pending)

                # Any other key should clear the flag
                app.handle_key(ord('s'))

                self.assertFalse(app.escape_pending)
                self.assertEqual(app.command_line.input_text, 'ls')

    @_patch_curses
    def test_escape_on_empty_command_line_does_nothing(self, *_):
        """Escape on empty command line should not set pending flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                stdscr = create_mock_stdscr()
                stdscr.getch.return_value = -1  # No key follows Escape
                app = App(stdscr)
                app.setup()

                # Escape on empty command line
                app.handle_key(27)

                self.assertFalse(app.escape_pending)


class TestEnterKeyBehavior(unittest.TestCase):
    """Test Enter key behavior with command line."""

    @_patch_curses
    def test_enter_with_empty_command_line_enters_directory(self, *_):
        """Enter with empty command line should enter directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()

            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()

                # Find subdir and move cursor to it
                for i, entry in enumerate(app.active_panel.entries):
                    if entry.name == 'subdir':
                        app.active_panel.cursor = i
                        break

                original_path = app.active_panel.path

                # Press Enter with empty command line
                app.handle_key(ord('\r'))

                # Should have entered the directory
                self.assertNotEqual(app.active_panel.path, original_path)
                self.assertEqual(app.active_panel.path.name, 'subdir')


if __name__ == '__main__':
    unittest.main()
