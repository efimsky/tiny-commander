"""Tests for UI rendering - two-panel layout with borders."""

import unittest
from unittest import mock


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    mock_stdscr.getch.return_value = ord('y')
    return mock_stdscr


class TestTwoPanelLayout(unittest.TestCase):
    """Test that two panels are rendered side-by-side."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_two_panels_drawn_side_by_side(self, _mock_curs_set, _mock_has_colors):
        """Two panels should be drawn side-by-side."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Verify app has two panels
        self.assertIsNotNone(app.left_panel)
        self.assertIsNotNone(app.right_panel)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_panel_widths_split_screen(self, _mock_curs_set, _mock_has_colors):
        """Panels should each take half the screen width."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Each panel should be roughly half width (accounting for border)
        self.assertEqual(app.left_panel.width, 40)
        self.assertEqual(app.right_panel.width, 40)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_panels_resize_with_terminal(self, _mock_curs_set, _mock_has_colors):
        """Panels should resize when terminal size changes."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Simulate terminal resize
        mock_stdscr.getmaxyx.return_value = (30, 160)
        app.handle_resize()

        self.assertEqual(app.left_panel.width, 80)
        self.assertEqual(app.right_panel.width, 80)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_active_panel_tracked(self, _mock_curs_set, _mock_has_colors):
        """Active panel should be tracked."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Left panel is active by default
        self.assertEqual(app.active_panel, app.left_panel)


class TestPanelBorders(unittest.TestCase):
    """Test that panels have borders."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_panel_has_border_attribute(self, _mock_curs_set, _mock_has_colors):
        """Panel should have a border."""
        from tnc.panel import Panel

        panel = Panel('/tmp', width=40, height=20)
        # Panel should be able to render borders
        self.assertTrue(hasattr(panel, 'render'))


class TestActivePanel(unittest.TestCase):
    """Test active panel visual distinction."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_active_panel_is_highlighted(self, _mock_curs_set, _mock_has_colors):
        """Active panel should be visually distinguished."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Active panel should have is_active = True
        self.assertTrue(app.active_panel.is_active)
        # Inactive panel should have is_active = False
        inactive = app.right_panel if app.active_panel == app.left_panel else app.left_panel
        self.assertFalse(inactive.is_active)


class TestStatusBar(unittest.TestCase):
    """Test status bar integration."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_status_bar_initialized(self, _mock_curs_set, _mock_has_colors):
        """App should have a status bar after setup."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        self.assertIsNotNone(app.status_bar)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_panel_height_leaves_room_for_bottom_bars(self, _mock_curs_set, _mock_has_colors):
        """Panel height should be rows - 4 (menu bar + 3 bottom rows).

        Layout: menu bar, status bar, command line, function bar (4 rows total).
        """
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Height should be 24 - 4 = 20 (menu + status bar + command line + function bar)
        self.assertEqual(app.left_panel.height, 20)
        self.assertEqual(app.right_panel.height, 20)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_panel_height_after_resize(self, _mock_curs_set, _mock_has_colors):
        """Panel height should be rows - 4 after resize (menu always visible)."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Resize to 30 rows
        mock_stdscr.getmaxyx.return_value = (30, 80)
        app.handle_resize()

        # Height should be 30 - 4 = 26 (menu + status bar + command line + function bar)
        self.assertEqual(app.left_panel.height, 26)
        self.assertEqual(app.right_panel.height, 26)


class TestCommandLine(unittest.TestCase):
    """Test command line rendering integration."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_command_line_initialized(self, _mock_curs_set, _mock_has_colors):
        """App should have a command line after setup."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        self.assertIsNotNone(app.command_line)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_command_line_rendered_at_correct_row(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
        """Command line should be rendered at rows - 2 (between status bar and function bar)."""
        from tnc.app import App

        mock_stdscr = create_mock_stdscr(24, 80)
        app = App(mock_stdscr)
        app.setup()

        # Call draw to render the UI
        app.draw()

        # Command line should render at row 22 (24 - 2)
        # Check that addstr was called with y=22 for command line content
        calls = mock_stdscr.addstr.call_args_list
        command_line_row_calls = [c for c in calls if c[0][0] == 22]
        self.assertTrue(
            len(command_line_row_calls) > 0,
            f"Expected command line to be rendered at row 22, but no addstr calls found at that row. "
            f"Calls were at rows: {sorted(set(c[0][0] for c in calls if len(c[0]) >= 2))}"
        )


if __name__ == '__main__':
    unittest.main()
