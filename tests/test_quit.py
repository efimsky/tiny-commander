"""Tests for F10 to quit."""

import curses
import unittest
from unittest import mock

from tnc.app import App, Action


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    mock_stdscr.getch.return_value = ord('y')
    return mock_stdscr


class TestF10Quit(unittest.TestCase):
    """Test F10 key to quit."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_f10_triggers_quit(self, _mock_curs_set, _mock_has_colors):
        """F10 should return QUIT action."""
        app = App(create_mock_stdscr())
        app.setup()

        result = app.handle_key(curses.KEY_F10)
        self.assertEqual(result, Action.QUIT)


class TestCleanExit(unittest.TestCase):
    """Test that app quits cleanly."""

    def test_quit_returns_clean_exit_code(self):
        """Normal quit should return exit code 0."""
        from tnc.app import run_app

        with mock.patch('curses.wrapper') as mock_wrapper:
            mock_wrapper.return_value = 0
            exit_code = run_app()
            self.assertEqual(exit_code, 0)


if __name__ == '__main__':
    unittest.main()
