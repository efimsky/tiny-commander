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
    def test_ctrl_x_c_triggers_chmod(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by 'c' triggers CHMOD action."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()
        app.left_panel._path = Path(self.tmpdir)
        app.right_panel._path = Path(self.tmpdir)
        app.left_panel.refresh()

        # Ctrl+X is ASCII 24
        # Simulate Ctrl+X then 'c' via _get_next_key_if_available
        with mock.patch.object(app, '_get_next_key_if_available', return_value=ord('c')):
            action = app.handle_key(24)

        self.assertEqual(action, Action.CHMOD)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_o_triggers_chown(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by 'o' triggers CHOWN action."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()
        app.left_panel._path = Path(self.tmpdir)
        app.right_panel._path = Path(self.tmpdir)

        # Simulate Ctrl+X then 'o'
        with mock.patch.object(app, '_get_next_key_if_available', return_value=ord('o')):
            action = app.handle_key(24)

        self.assertEqual(action, Action.CHOWN)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_uppercase_c_triggers_chmod(self, _mock_colors, _mock_curs_set):
        """Ctrl+X followed by 'C' (uppercase) triggers CHMOD action."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()

        with mock.patch.object(app, '_get_next_key_if_available', return_value=ord('C')):
            action = app.handle_key(24)

        self.assertEqual(action, Action.CHMOD)

    @mock.patch('curses.ungetch')
    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_other_key_ignored(self, _mock_colors, _mock_curs_set, _mock_ungetch):
        """Ctrl+X followed by other keys returns NONE."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()

        # Simulate Ctrl+X then 'x' (not a valid chord)
        with mock.patch.object(app, '_get_next_key_if_available', return_value=ord('x')):
            action = app.handle_key(24)

        self.assertEqual(action, Action.NONE)

    @mock.patch('curses.curs_set')
    @mock.patch('curses.has_colors', return_value=False)
    def test_ctrl_x_timeout(self, _mock_colors, _mock_curs_set):
        """Ctrl+X without follow-up key returns NONE."""
        stdscr = mock.MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        app = App(stdscr)
        app.setup()

        # Simulate timeout (no follow-up key)
        with mock.patch.object(app, '_get_next_key_if_available', return_value=-1):
            action = app.handle_key(24)

        self.assertEqual(action, Action.NONE)


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
