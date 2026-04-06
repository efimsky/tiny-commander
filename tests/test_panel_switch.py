"""Tests for Tab key - switch active panel."""

import curses
import unittest
from unittest import mock


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    mock_stdscr.getch.return_value = ord('y')
    return mock_stdscr


class TestTabSwitchesPanel(unittest.TestCase):
    """Test Tab key switches between panels."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_tab_switches_from_left_to_right(self, _mock_curs_set, _mock_has_colors):
        """Tab should switch from left to right panel."""
        from tnc.app import App

        app = App(create_mock_stdscr())
        app.setup()

        # Left panel is active by default
        self.assertEqual(app.active_panel, app.left_panel)
        self.assertTrue(app.left_panel.is_active)
        self.assertFalse(app.right_panel.is_active)

        # Press Tab
        app.handle_key(ord('\t'))

        # Right panel should now be active
        self.assertEqual(app.active_panel, app.right_panel)
        self.assertFalse(app.left_panel.is_active)
        self.assertTrue(app.right_panel.is_active)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_tab_switches_from_right_to_left(self, _mock_curs_set, _mock_has_colors):
        """Tab should switch from right to left panel."""
        from tnc.app import App

        app = App(create_mock_stdscr())
        app.setup()

        # Set right panel as active
        app.active_panel = app.right_panel
        app.left_panel.is_active = False
        app.right_panel.is_active = True

        # Press Tab
        app.handle_key(ord('\t'))

        # Left panel should now be active
        self.assertEqual(app.active_panel, app.left_panel)
        self.assertTrue(app.left_panel.is_active)
        self.assertFalse(app.right_panel.is_active)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_active_panel_is_highlighted(self, _mock_curs_set, _mock_has_colors):
        """Active panel should have is_active=True."""
        from tnc.app import App

        app = App(create_mock_stdscr())
        app.setup()

        # Verify only active panel is highlighted
        self.assertTrue(app.active_panel.is_active)

        other_panel = (
            app.right_panel if app.active_panel == app.left_panel
            else app.left_panel
        )
        self.assertFalse(other_panel.is_active)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_tab_toggles_continuously(self, _mock_curs_set, _mock_has_colors):
        """Multiple Tab presses should toggle between panels."""
        from tnc.app import App

        app = App(create_mock_stdscr())
        app.setup()

        # Start at left
        self.assertEqual(app.active_panel, app.left_panel)

        # Tab -> right
        app.handle_key(ord('\t'))
        self.assertEqual(app.active_panel, app.right_panel)

        # Tab -> left
        app.handle_key(ord('\t'))
        self.assertEqual(app.active_panel, app.left_panel)

        # Tab -> right
        app.handle_key(ord('\t'))
        self.assertEqual(app.active_panel, app.right_panel)


if __name__ == '__main__':
    unittest.main()
