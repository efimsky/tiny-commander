"""Tests for screen flicker reduction optimizations (Issue #100).

These tests verify that the curses flicker-reduction techniques are properly
implemented:
1. Using erase() instead of clear() to avoid forced terminal redraws
2. Using noutrefresh() + doupdate() for atomic screen updates
"""

import curses
import unittest
from unittest import mock


class TestFlickerReductionInDraw(unittest.TestCase):
    """Test that draw() uses flicker-reduction techniques."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_draw_uses_erase_not_clear(self, mock_doupdate, _mock_curs_set, _mock_has_colors):
        """draw() should use erase() instead of clear() to reduce flicker."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Reset mock to clear setup calls
        mock_stdscr.reset_mock()

        # Call draw
        app.draw()

        # Verify erase() was called
        mock_stdscr.erase.assert_called()

        # Verify clear() was NOT called
        mock_stdscr.clear.assert_not_called()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_draw_uses_noutrefresh_and_doupdate(self, mock_doupdate, _mock_curs_set, _mock_has_colors):
        """draw() should use noutrefresh() + doupdate() for atomic updates."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Reset mock to clear setup calls
        mock_stdscr.reset_mock()
        mock_doupdate.reset_mock()

        # Call draw
        app.draw()

        # Verify noutrefresh() was called on stdscr
        mock_stdscr.noutrefresh.assert_called()

        # Verify curses.doupdate() was called
        mock_doupdate.assert_called()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_draw_does_not_use_plain_refresh(self, mock_doupdate, _mock_curs_set, _mock_has_colors):
        """draw() should not use plain refresh() - use noutrefresh() + doupdate() instead."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Reset mock to clear setup calls
        mock_stdscr.reset_mock()

        # Call draw
        app.draw()

        # Verify refresh() was NOT called (we use noutrefresh + doupdate instead)
        mock_stdscr.refresh.assert_not_called()


class TestFlickerReductionRegressions(unittest.TestCase):
    """Regression tests to ensure flicker reduction doesn't break rendering."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_draw_still_renders_panels(self, mock_doupdate, _mock_curs_set, _mock_has_colors):
        """draw() should still render both panels after optimization."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Reset mock to clear setup calls
        mock_stdscr.reset_mock()

        # Call draw
        app.draw()

        # Verify addstr was called (panels render content)
        self.assertTrue(mock_stdscr.addstr.called)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_draw_positions_cursor_correctly(self, mock_doupdate, _mock_curs_set, _mock_has_colors):
        """draw() should still position cursor on command line."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        # Reset mock to clear setup calls
        mock_stdscr.reset_mock()

        # Call draw
        app.draw()

        # Verify cursor is positioned (move was called)
        mock_stdscr.move.assert_called()

        # Cursor should be on command line row (row 22 for 24-row terminal without menu)
        # Command line is at rows - 2 = 22
        call_args = mock_stdscr.move.call_args
        row = call_args[0][0]
        self.assertEqual(row, 22)


if __name__ == '__main__':
    unittest.main()
