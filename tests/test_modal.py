"""Tests for the Modal base class and ButtonBar widget (issue #16)."""

import curses
import unittest
from unittest import mock


class TestButtonBar(unittest.TestCase):
    """ButtonBar widget: focus, hit-test, render-records-positions."""

    def _make_bar(self, focused: int = 0):
        from tnc.modal import Button, ButtonBar
        return ButtonBar(
            buttons=[
                Button(label='Yes', shortcut='y', value=True),
                Button(label='No', shortcut='n', value=False),
            ],
            focused=focused,
        )

    def test_render_records_hit_regions(self):
        bar = self._make_bar()
        win = mock.MagicMock()
        bar.render(win, y=10, x_start=20, total_width=40)

        # Two buttons → two entries.
        self.assertEqual(len(bar.button_positions), 2)
        for entry in bar.button_positions:
            x_start, x_end, y, value = entry
            self.assertIsInstance(x_start, int)
            self.assertIsInstance(x_end, int)
            self.assertEqual(y, 10)
            self.assertLess(x_start, x_end)

    def test_hit_test_returns_value_for_inside_x(self):
        bar = self._make_bar()
        win = mock.MagicMock()
        bar.render(win, y=10, x_start=20, total_width=40)

        first_x_start, first_x_end, _, first_value = bar.button_positions[0]
        # Click in the middle of the first button.
        midx = (first_x_start + first_x_end) // 2
        self.assertEqual(bar.hit_test(midx, 10), first_value)

    def test_hit_test_returns_none_for_wrong_y(self):
        bar = self._make_bar()
        win = mock.MagicMock()
        bar.render(win, y=10, x_start=20, total_width=40)

        midx = (bar.button_positions[0][0] + bar.button_positions[0][1]) // 2
        self.assertIsNone(bar.hit_test(midx, 9))
        self.assertIsNone(bar.hit_test(midx, 11))

    def test_hit_test_returns_none_for_outside_x(self):
        bar = self._make_bar()
        win = mock.MagicMock()
        bar.render(win, y=10, x_start=20, total_width=40)

        last_x_end = bar.button_positions[-1][1]
        self.assertIsNone(bar.hit_test(last_x_end + 5, 10))
        self.assertIsNone(bar.hit_test(0, 10))

    def test_move_focus_wraps(self):
        bar = self._make_bar(focused=0)
        bar.move_focus(-1)
        self.assertEqual(bar.focused, 1)  # wraps from 0 -> last
        bar.move_focus(1)
        self.assertEqual(bar.focused, 0)  # wraps from last -> 0
        bar.move_focus(1)
        self.assertEqual(bar.focused, 1)

    def test_activate_returns_focused_value(self):
        bar = self._make_bar(focused=1)
        self.assertEqual(bar.activate(), False)  # No
        bar.focused = 0
        self.assertEqual(bar.activate(), True)   # Yes

    def test_activate_by_shortcut_returns_value(self):
        bar = self._make_bar()
        self.assertEqual(bar.activate_by_shortcut('y'), True)
        self.assertEqual(bar.activate_by_shortcut('Y'), True)
        self.assertEqual(bar.activate_by_shortcut('n'), False)
        self.assertIsNone(bar.activate_by_shortcut('q'))

    def test_focused_button_rendered_with_reverse_attribute(self):
        bar = self._make_bar(focused=0)
        win = mock.MagicMock()
        bar.render(win, y=10, x_start=20, total_width=40)

        # Inspect the addstr calls; the first button should have included
        # curses.A_REVERSE in its attribute argument.
        attrs_used = []
        for call in win.addstr.call_args_list:
            args = call[0]
            if len(args) >= 4 and isinstance(args[2], str) and 'Yes' in args[2]:
                attrs_used.append(args[3])
        self.assertTrue(
            any(attr & curses.A_REVERSE for attr in attrs_used),
            f'Focused Yes button must include A_REVERSE; saw attrs={attrs_used!r}',
        )


class TestModalBase(unittest.TestCase):
    """Modal.show(): single loop drives render, getch, mouse routing."""

    def _make_modal_class(self):
        from tnc.modal import Modal

        class Spy(Modal):
            def __init__(self):
                super().__init__()
                self.render_calls = 0
                self.handle_key_calls = []
                self.handle_click_calls = []

            def render(self, win):
                self.render_calls += 1

            def handle_key(self, key):
                self.handle_key_calls.append(key)
                # Quit on Esc to terminate the loop deterministically.
                if key == 27:
                    self.set_result('cancelled')

            def handle_click(self, x, y, button_state):
                self.handle_click_calls.append((x, y, button_state))

        return Spy

    def test_show_loop_calls_render_before_each_getch(self):
        Spy = self._make_modal_class()
        m = Spy()
        win = mock.MagicMock()
        win.getch.side_effect = [ord('a'), ord('b'), 27]  # 27 = Esc

        m.show(win)

        self.assertEqual(m.render_calls, 3)
        self.assertEqual(m.handle_key_calls, [ord('a'), ord('b'), 27])

    def test_key_mouse_routes_to_handle_click(self):
        Spy = self._make_modal_class()
        m = Spy()
        win = mock.MagicMock()
        win.getch.side_effect = [curses.KEY_MOUSE, 27]

        with mock.patch('curses.getmouse', return_value=(0, 5, 7, 0, curses.BUTTON1_CLICKED)):
            m.show(win)

        self.assertEqual(m.handle_click_calls, [(5, 7, curses.BUTTON1_CLICKED)])
        # Mouse event was NOT also sent to handle_key.
        self.assertEqual(m.handle_key_calls, [27])

    def test_key_mouse_with_failed_getmouse_is_dropped(self):
        Spy = self._make_modal_class()
        m = Spy()
        win = mock.MagicMock()
        win.getch.side_effect = [curses.KEY_MOUSE, 27]

        with mock.patch('curses.getmouse', side_effect=curses.error('boom')):
            m.show(win)

        # No click dispatched, but the loop survived.
        self.assertEqual(m.handle_click_calls, [])
        self.assertEqual(m.handle_key_calls, [27])

    def test_set_result_terminates_loop_and_show_returns_value(self):
        from tnc.modal import Modal

        class Quick(Modal):
            def render(self, win):
                pass

            def handle_key(self, key):
                self.set_result(42)

            def handle_click(self, x, y, button_state):
                pass

        win = mock.MagicMock()
        win.getch.return_value = ord('x')

        result = Quick().show(win)
        self.assertEqual(result, 42)


if __name__ == '__main__':
    unittest.main()
