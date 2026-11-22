"""Tests for Ctrl+X chord key bindings."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.app import Action, App


class TestCtrlXChord(unittest.TestCase):
    """Tests for Ctrl+X chord handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.mkdtemp()
        self.test_file = Path(self.tmpdir) / 'test.txt'
        self.test_file.write_text('content')

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_sets_pending_and_returns_none(self, _mock_colors, _mock_curs_set):
        """First keypress Ctrl+X sets ctrl_x_pending and returns NONE without polling."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()

        with mock.patch.object(app, '_get_next_key_if_available') as mock_next:
            action = app.handle_key(24)

        self.assertEqual(action, Action.NONE)
        self.assertTrue(app.ctrl_x_pending)
        mock_next.assert_not_called()

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_c_triggers_chmod(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by 'c' triggers CHMOD action via two-keypress state."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()
        app.left_panel._path = Path(self.tmpdir)
        app.right_panel._path = Path(self.tmpdir)
        app.left_panel.refresh()

        self.assertEqual(app.handle_key(24), Action.NONE)
        self.assertTrue(app.ctrl_x_pending)

        action = app.handle_key(ord('c'))
        self.assertEqual(action, Action.CHMOD)
        self.assertFalse(app.ctrl_x_pending)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_o_triggers_chown(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by 'o' triggers CHOWN action via two-keypress state."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()
        app.left_panel._path = Path(self.tmpdir)
        app.right_panel._path = Path(self.tmpdir)

        self.assertEqual(app.handle_key(24), Action.NONE)
        self.assertTrue(app.ctrl_x_pending)

        action = app.handle_key(ord('o'))
        self.assertEqual(action, Action.CHOWN)
        self.assertFalse(app.ctrl_x_pending)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_uppercase_c_triggers_chmod(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by 'C' (uppercase) triggers CHMOD action."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()

        self.assertEqual(app.handle_key(24), Action.NONE)
        action = app.handle_key(ord('C'))
        self.assertEqual(action, Action.CHMOD)
        self.assertFalse(app.ctrl_x_pending)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_uppercase_o_triggers_chown(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by 'O' (uppercase) triggers CHOWN action."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()

        self.assertEqual(app.handle_key(24), Action.NONE)
        action = app.handle_key(ord('O'))
        self.assertEqual(action, Action.CHOWN)
        self.assertFalse(app.ctrl_x_pending)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_other_key_ignored_and_not_typed(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by invalid key returns NONE without typing to command line."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()

        self.assertEqual(app.handle_key(24), Action.NONE)
        action = app.handle_key(ord('x'))

        self.assertEqual(action, Action.NONE)
        self.assertFalse(app.ctrl_x_pending)
        self.assertEqual(app.command_line.input_text, '')

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_escape_cancels_chord_without_escape_pending(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by Escape cancels chord cleanly without setting escape_pending."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()
        app.command_line.input_text = 'ls'

        self.assertEqual(app.handle_key(24), Action.NONE)
        action = app.handle_key(27)

        self.assertEqual(action, Action.NONE)
        self.assertFalse(app.ctrl_x_pending)
        self.assertFalse(app.escape_pending)
        self.assertEqual(app.command_line.input_text, 'ls')


class TestChmodChownActions(unittest.TestCase):
    """Tests for CHMOD and CHOWN action enum values."""

    def test_chmod_action_exists(self):
        """Action enum has CHMOD value."""
        self.assertIsNotNone(Action.CHMOD)

    def test_chown_action_exists(self):
        """Action enum has CHOWN value."""
        self.assertIsNotNone(Action.CHOWN)


if __name__ == '__main__':
    unittest.main()
