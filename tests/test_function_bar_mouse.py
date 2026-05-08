"""Tests for function bar mouse interactions (Issue #66)."""

import curses
import unittest
from unittest import mock

from tnc.app import Action, App
from tnc.function_bar import FunctionBar


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    mock_stdscr.getch.return_value = ord('q')
    return mock_stdscr


class TestFunctionBarPositionTracking(unittest.TestCase):
    """Test position tracking during render."""

    def test_has_button_positions_attribute(self):
        """FunctionBar should have button_positions attribute."""
        bar = FunctionBar()
        self.assertTrue(hasattr(bar, 'button_positions'))

    def test_has_render_y_attribute(self):
        """FunctionBar should have render_y attribute."""
        bar = FunctionBar()
        self.assertTrue(hasattr(bar, 'render_y'))

    def test_render_stores_y_position(self):
        """render() should store the y position."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()

        bar.render(mock_win, y=23, width=80)

        self.assertEqual(bar.render_y, 23)

    def test_render_populates_button_positions(self):
        """render() should populate button_positions list."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()

        bar.render(mock_win, y=23, width=80)

        # Should have positions for all 8 buttons (F3-F10 including F9)
        self.assertEqual(len(bar.button_positions), 8)

    def test_button_positions_have_correct_structure(self):
        """Each button position should be (start_x, end_x, action)."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()

        bar.render(mock_win, y=23, width=80)

        for pos in bar.button_positions:
            self.assertEqual(len(pos), 3)
            start_x, end_x, action = pos
            self.assertIsInstance(start_x, int)
            self.assertIsInstance(end_x, int)
            self.assertIsInstance(action, Action)
            self.assertLess(start_x, end_x)

    def test_button_positions_cover_expected_actions(self):
        """Button positions should include all expected actions."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()

        bar.render(mock_win, y=23, width=80)

        actions = [pos[2] for pos in bar.button_positions]
        self.assertIn(Action.VIEW, actions)
        self.assertIn(Action.EDIT, actions)
        self.assertIn(Action.COPY, actions)
        self.assertIn(Action.MOVE, actions)
        self.assertIn(Action.MKDIR, actions)
        self.assertIn(Action.DELETE, actions)
        self.assertIn(Action.MENU, actions)
        self.assertIn(Action.QUIT, actions)

    def test_render_clears_previous_positions(self):
        """render() should clear previous button_positions."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()

        # First render
        bar.render(mock_win, y=23, width=80)
        first_count = len(bar.button_positions)

        # Second render
        bar.render(mock_win, y=23, width=80)
        second_count = len(bar.button_positions)

        # Should have same count (cleared and repopulated)
        self.assertEqual(first_count, second_count)


class TestFunctionBarContainsPoint(unittest.TestCase):
    """Test contains_point() hit detection."""

    def test_contains_point_before_render_returns_false(self):
        """Point should return False before render is called."""
        bar = FunctionBar()
        # Before render, render_y is -1 (sentinel)
        self.assertFalse(bar.contains_point(40, 0))
        self.assertFalse(bar.contains_point(40, 23))

    def test_contains_point_in_function_bar_row(self):
        """Point in function bar row should return True."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        self.assertTrue(bar.contains_point(40, 23))

    def test_contains_point_outside_function_bar_row(self):
        """Point not in function bar row should return False."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        self.assertFalse(bar.contains_point(40, 22))
        self.assertFalse(bar.contains_point(40, 24))
        self.assertFalse(bar.contains_point(40, 0))

    def test_contains_point_respects_render_y(self):
        """contains_point should use stored render_y."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=10, width=80)

        self.assertTrue(bar.contains_point(40, 10))
        self.assertFalse(bar.contains_point(40, 23))


class TestFunctionBarActionAtPoint(unittest.TestCase):
    """Test action_at_point() method."""

    def test_action_at_point_returns_action_for_button(self):
        """action_at_point should return Action for valid button region."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # With 8 buttons and width=80, cell_width = 10
        # First button (F3 View) should be at x=0-9
        result = bar.action_at_point(5)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Action)

    def test_action_at_point_first_button_is_view(self):
        """First button (F3) should return Action.VIEW."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # First button starts at x=0
        result = bar.action_at_point(0)
        self.assertEqual(result, Action.VIEW)

    def test_action_at_point_last_button_is_quit(self):
        """Last button (F10) should return Action.QUIT."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # With 8 buttons and width=80, cell_width = 10
        # Last button (F10 Quit) at position 7, starts at x=70
        result = bar.action_at_point(70)
        self.assertEqual(result, Action.QUIT)

    def test_action_at_point_returns_none_past_buttons(self):
        """action_at_point should return None for x past all buttons."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # Way past all buttons
        result = bar.action_at_point(85)
        self.assertIsNone(result)

    def test_action_at_point_f9_returns_menu(self):
        """F9 button should return Action.MENU."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # F9 is 7th button (index 6), at x = 6 * 10 = 60
        result = bar.action_at_point(60)
        self.assertEqual(result, Action.MENU)


class TestAppHandleMouseFunctionBar(unittest.TestCase):
    """Test App.handle_mouse() routing to function bar."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    def test_click_function_bar_returns_action(self, _mousemask, _doupdate, _curs_set, _has_colors):
        """Clicking on function bar button should return corresponding action."""
        app = App(create_mock_stdscr(rows=24, cols=80))
        app.setup()
        app.draw()

        # Function bar is at last row (y=23)
        # F3 (View) is first button
        result = app.handle_mouse(5, 23, curses.BUTTON1_CLICKED)

        self.assertEqual(result, Action.VIEW)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    def test_click_f5_returns_copy(self, _mousemask, _doupdate, _curs_set, _has_colors):
        """Clicking F5 button should return Action.COPY."""
        app = App(create_mock_stdscr(rows=24, cols=80))
        app.setup()
        app.draw()

        # F5 is 3rd button (index 2), at x = 2 * 10 = 20
        result = app.handle_mouse(25, 23, curses.BUTTON1_CLICKED)

        self.assertEqual(result, Action.COPY)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    def test_click_f10_returns_quit(self, _mousemask, _doupdate, _curs_set, _has_colors):
        """Clicking F10 button should return Action.QUIT."""
        app = App(create_mock_stdscr(rows=24, cols=80))
        app.setup()
        app.draw()

        # F10 is last button (index 7), at x = 7 * 10 = 70
        result = app.handle_mouse(75, 23, curses.BUTTON1_CLICKED)

        self.assertEqual(result, Action.QUIT)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    def test_click_f9_returns_menu(self, _mousemask, _doupdate, _curs_set, _has_colors):
        """Clicking F9 button should return Action.MENU."""
        app = App(create_mock_stdscr(rows=24, cols=80))
        app.setup()
        app.draw()

        # F9 is 7th button (index 6), at x = 6 * 10 = 60
        result = app.handle_mouse(65, 23, curses.BUTTON1_CLICKED)

        self.assertEqual(result, Action.MENU)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    def test_function_bar_click_closes_dropdown_first(self, _mousemask, _doupdate, _curs_set, _has_colors):
        """Clicking function bar with dropdown open should close dropdown first."""
        app = App(create_mock_stdscr(rows=24, cols=80))
        app.setup()
        app.draw()

        # Open dropdown
        app.menu.dropdown_open = True

        # Click on function bar
        result = app.handle_mouse(5, 23, curses.BUTTON1_CLICKED)

        # Dropdown should be closed
        self.assertFalse(app.menu.dropdown_open)
        # Should return NONE (not trigger action)
        self.assertEqual(result, Action.NONE)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    def test_function_bar_only_responds_to_left_click(self, _mousemask, _doupdate, _curs_set, _has_colors):
        """Function bar should only respond to left clicks, not scroll."""
        app = App(create_mock_stdscr(rows=24, cols=80))
        app.setup()
        app.draw()

        # Scroll wheel on function bar should not trigger action
        result = app.handle_mouse(5, 23, curses.BUTTON4_PRESSED)

        self.assertEqual(result, Action.NONE)


class TestFunctionBarVisualFeedback(unittest.TestCase):
    """Test visual feedback on click."""

    def test_has_highlight_button_attribute(self):
        """FunctionBar should have highlight_button attribute."""
        bar = FunctionBar()
        self.assertTrue(hasattr(bar, 'highlight_button'))

    def test_highlight_button_initially_none(self):
        """highlight_button should be None initially."""
        bar = FunctionBar()
        self.assertIsNone(bar.highlight_button)

    def test_show_click_feedback_sets_highlight(self):
        """show_click_feedback should set highlight_button."""
        bar = FunctionBar()

        bar.show_click_feedback('F3')

        self.assertEqual(bar.highlight_button, 'F3')

    def test_clear_click_feedback(self):
        """clear_click_feedback should reset highlight_button to None."""
        bar = FunctionBar()
        bar.highlight_button = 'F3'

        bar.clear_click_feedback()

        self.assertIsNone(bar.highlight_button)


class TestActionMenuExists(unittest.TestCase):
    """Test Action.MENU exists in Action enum."""

    def test_action_menu_exists(self):
        """Action.MENU should exist."""
        self.assertTrue(hasattr(Action, 'MENU'))


class TestFunctionBarLabelCentering(unittest.TestCase):
    """Issue #18: labels must be centered within their cells so a click
    just before the visible label still resolves to that button (the
    user's perceived F-key) rather than to the previous cell's
    trailing padding."""

    def _capture_addstr_calls(self, bar: FunctionBar, width: int):
        """Render bar and return a list of (x, text) tuples for label
        rendering. Filters out the full-line background clear at x=0.
        """
        calls: list[tuple[int, str]] = []
        win = mock.MagicMock()

        def fake_addstr(_y, x, text, *_args, **_kwargs):
            calls.append((x, text))

        win.addstr.side_effect = fake_addstr
        bar.render(win, y=0, width=width)
        # Discard the initial full-row background clear (text is all spaces and
        # spans the full width). Keep only key/label render calls.
        return [(x, t) for (x, t) in calls if not (x == 0 and len(t) == width)]

    def test_label_rendered_centered_within_cell_at_width_80(self):
        """At width=80 (cell_width=10), F7's ' F7Mkdir' (8 chars) should
        render centered at x = 40 + (10-8)//2 = 41, not at x = 40."""
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=80)

        # Find the call that wrote ' F7' (the F7 key portion).
        f7_calls = [(x, t) for (x, t) in calls if t == ' F7']
        self.assertEqual(len(f7_calls), 1, f'expected 1 ` F7` render, got {f7_calls}')
        x, _ = f7_calls[0]
        # Cell is [40, 50). Label ' F7Mkdir' is 8 chars. Centered: 40 + 1 = 41.
        self.assertEqual(x, 41, f'F7 key should render at x=41 (centered), got x={x}')

    def test_label_rendered_centered_within_cell_at_width_145(self):
        """At width=145 (cell_width=18), F8's ' F8Delete' (9 chars) should
        render centered at x = 90 + (18-9)//2 = 94, not at x = 90."""
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=145)

        f8_calls = [(x, t) for (x, t) in calls if t == ' F8']
        self.assertEqual(len(f8_calls), 1)
        x, _ = f8_calls[0]
        # Cell is [90, 108). Label ' F8Delete' is 9 chars. Centered: 90 + 4 = 94.
        self.assertEqual(x, 94, f'F8 key should render at x=94 (centered), got x={x}')

    def test_narrow_cell_clamps_label_to_cell_start(self):
        """When the label is wider than the cell, the centering offset
        would go negative. The clamp `max(0, ...)` must keep the label
        starting at start_x, never to the left of it."""
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=24)
        # cell_width = 24 // 8 = 3. Every label is wider than 3.
        # Each ' F<N>' key render must land at i*3 (no negative shift).
        key_calls = [(x, t) for (x, t) in calls if t.startswith(' F')]
        for i, (x, t) in enumerate(key_calls):
            expected_start = i * 3
            self.assertEqual(
                x, expected_start,
                f'narrow-cell render of {t!r} should clamp to x={expected_start}, got x={x}',
            )

    def test_button_positions_unchanged_by_centering(self):
        """The centering change must NOT alter the click-region table
        (button_positions). Existing keybinding/click logic depends on
        the same boundaries."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        expected = [
            (0, 10, Action.VIEW),
            (10, 20, Action.EDIT),
            (20, 30, Action.COPY),
            (30, 40, Action.MOVE),
            (40, 50, Action.MKDIR),
            (50, 60, Action.DELETE),
            (60, 70, Action.MENU),
            (70, 80, Action.QUIT),
        ]
        self.assertEqual(bar.button_positions, expected)

    def test_padding_click_visually_adjacent_to_next_label_resolves_to_next(self):
        """Issue #18 user-facing assertion: at width=80, after centering
        the F8 label sits at chars 51-59 with one char of left padding
        at 50. A click at x=50 (visible left edge of F8 region, in F8
        cell) returns DELETE. Clicks at 49 still return MKDIR (in F7
        cell), which is correct because x=49 is now visually closer to
        F7's centered label than to F8's."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # Click on F8's left padding (still inside F8 cell [50, 60)):
        self.assertEqual(bar.action_at_point(50), Action.DELETE)
        # Click on visible F8 label center:
        self.assertEqual(bar.action_at_point(55), Action.DELETE)


if __name__ == '__main__':
    unittest.main()
