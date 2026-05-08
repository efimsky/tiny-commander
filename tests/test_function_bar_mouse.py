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

        # Issue #78 added F1 Help and F2 Menu, so the bar now shows 10 buttons.
        self.assertEqual(len(bar.button_positions), 10)

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
        self.assertIn(Action.HELP, actions)  # F1, issue #78
        self.assertIn(Action.MENU, actions)  # F2 / F9, issue #78
        self.assertIn(Action.VIEW, actions)
        self.assertIn(Action.EDIT, actions)
        self.assertIn(Action.COPY, actions)
        self.assertIn(Action.MOVE, actions)
        self.assertIn(Action.MKDIR, actions)
        self.assertIn(Action.DELETE, actions)
        self.assertIn(Action.QUIT, actions)

    def test_button_positions_first_two_cells_are_f1_help_and_f2_menu(self):
        """Issue #78: F1 (Help) is at cell 0, F2 (Menu) is at cell 1."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        self.assertEqual(bar.button_positions[0][2], Action.HELP)
        self.assertEqual(bar.button_positions[1][2], Action.MENU)

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

        # Issue #78: 10 buttons at width=80, cell_width = 8.
        # First button (F1 Help) covers x=0-7.
        result = bar.action_at_point(5)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Action)

    def test_action_at_point_first_button_is_help(self):
        """First button (F1) should return Action.HELP after issue #78."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        result = bar.action_at_point(0)
        self.assertEqual(result, Action.HELP)

    def test_action_at_point_last_button_is_quit(self):
        """Last button (F10) should return Action.QUIT."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # Issue #78: F10 is 10th button (index 9), at x = 9 * 8 = 72.
        result = bar.action_at_point(72)
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

        # Issue #78: F9 is 9th button (index 8), at x = 8 * 8 = 64.
        result = bar.action_at_point(64)
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

        # Function bar is at last row (y=23). Issue #78: F1 (Help) is the
        # first button at cell [0, 8).
        result = app.handle_mouse(5, 23, curses.BUTTON1_CLICKED)

        self.assertEqual(result, Action.HELP)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    def test_click_f5_returns_copy(self, _mousemask, _doupdate, _curs_set, _has_colors):
        """Clicking F5 button should return Action.COPY."""
        app = App(create_mock_stdscr(rows=24, cols=80))
        app.setup()
        app.draw()

        # Issue #78: F5 is 5th button (index 4), at x = 4 * 8 = 32.
        result = app.handle_mouse(33, 23, curses.BUTTON1_CLICKED)

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

        # Issue #78: F10 is last button (index 9), at x = 9 * 8 = 72.
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

        # Issue #78: F9 is 9th button (index 8), at x = 8 * 8 = 64.
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

    def test_label_rendered_centered_within_cell_at_width_145(self):
        """At width=145 (10 buttons after #78, cell_width=14), F7's
        ' F7Mkdir' (8 chars) should render centered at x = 6*14 + (14-8)//2
        = 84 + 3 = 87, not at the cell start x=84."""
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=145)

        f7_calls = [(x, t) for (x, t) in calls if t == ' F7']
        self.assertEqual(len(f7_calls), 1)
        x, _ = f7_calls[0]
        # F7 is index 6 in the 10-button bar. Cell [84, 98). Label is 8 chars.
        self.assertEqual(x, 87, f'F7 key should render at x=87 (centered), got x={x}')

    def test_narrow_cell_clamps_label_to_cell_start(self):
        """When the label is wider than the cell, the centering offset
        would go negative. The clamp `max(0, ...)` must keep the label
        starting at start_x, never to the left of it."""
        bar = FunctionBar()
        # 10 buttons at width=30 → cell_width=3. Every label is wider than 3.
        calls = self._capture_addstr_calls(bar, width=30)
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
        the same boundaries. Issue #78 made the bar 10 buttons wide."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        # Width=80 → cell_width=8. 10 buttons.
        expected = [
            (0, 8, Action.HELP),
            (8, 16, Action.MENU),
            (16, 24, Action.VIEW),
            (24, 32, Action.EDIT),
            (32, 40, Action.COPY),
            (40, 48, Action.MOVE),
            (48, 56, Action.MKDIR),
            (56, 64, Action.DELETE),
            (64, 72, Action.MENU),
            (72, 80, Action.QUIT),
        ]
        self.assertEqual(bar.button_positions, expected)

    def test_click_in_f8_cell_returns_delete(self):
        """Issue #18 / #78: at width=80, F8 cell is [56, 64). Click in
        the middle of the cell (x=60) returns Action.DELETE."""
        bar = FunctionBar()
        mock_win = mock.MagicMock()
        bar.render(mock_win, y=23, width=80)

        self.assertEqual(bar.action_at_point(56), Action.DELETE)
        self.assertEqual(bar.action_at_point(60), Action.DELETE)
        self.assertEqual(bar.action_at_point(63), Action.DELETE)


class TestFunctionBarEdgeAnchoring(unittest.TestCase):
    """Issue #80: the first button anchors to col 0 (no left padding)
    and the last button anchors to its cell's right edge (no trailing
    pad inside the cell). Middle buttons keep #18's centering."""

    def _capture_addstr_calls(self, bar: FunctionBar, width: int):
        calls: list[tuple[int, str]] = []
        win = mock.MagicMock()

        def fake_addstr(_y, x, text, *_args, **_kwargs):
            calls.append((x, text))

        win.addstr.side_effect = fake_addstr
        bar.render(win, y=0, width=width)
        return [(x, t) for (x, t) in calls if not (x == 0 and len(t) == width)]

    def test_first_button_renders_at_col_zero_at_width_145(self):
        """At width=145 (cell_width=14), F1 (' F1Help', 7 chars) used to
        render centered at col 3 with cols 0-2 cyan-padding. Now it
        anchors to col 0 — no leading cyan strip before F1."""
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=145)
        f1_calls = [(x, t) for (x, t) in calls if t == ' F1']
        self.assertEqual(len(f1_calls), 1, f1_calls)
        x, _ = f1_calls[0]
        self.assertEqual(x, 0, f'F1 should anchor to col 0, got x={x}')

    def test_first_button_renders_at_col_zero_at_width_80(self):
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=80)
        f1_calls = [(x, t) for (x, t) in calls if t == ' F1']
        self.assertEqual(len(f1_calls), 1)
        self.assertEqual(f1_calls[0][0], 0)

    def test_last_button_anchors_to_cell_right_edge_at_width_145(self):
        """At width=145, cell_width=14, F10 cell [126, 140). Label
        ' F10Quit' (8 chars). Right-anchored: text_start = 140 - 8 = 132."""
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=145)
        f10_calls = [(x, t) for (x, t) in calls if t == ' F10']
        self.assertEqual(len(f10_calls), 1, f10_calls)
        x, _ = f10_calls[0]
        self.assertEqual(x, 132, f'F10 should right-anchor at col 132, got x={x}')

    def test_middle_buttons_remain_centered_at_width_145(self):
        """F2..F9 keep issue #18's centering; this regression-locks that
        the edge-anchor change doesn't accidentally affect middle buttons."""
        bar = FunctionBar()
        calls = self._capture_addstr_calls(bar, width=145)
        # cell_width = 14. F5 (' F5Copy', 7 chars) at index 4:
        # cell [56, 70). Centered: 56 + (14-7)//2 = 56 + 3 = 59.
        f5_calls = [(x, t) for (x, t) in calls if t == ' F5']
        self.assertEqual(len(f5_calls), 1)
        self.assertEqual(f5_calls[0][0], 59)

    def test_button_positions_unchanged_by_edge_anchoring(self):
        """Edge anchoring is a render-only change — the click hit-region
        table (button_positions) is the same as before."""
        bar = FunctionBar()
        win = mock.MagicMock()
        bar.render(win, y=0, width=80)
        expected_starts = [i * 8 for i in range(10)]
        actual_starts = [s for s, _, _ in bar.button_positions]
        self.assertEqual(actual_starts, expected_starts)


if __name__ == '__main__':
    unittest.main()
