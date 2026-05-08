"""Tests for the F1 help dialog and F1/F2 keyboard routing (issue #78)."""

import curses
import os
import tempfile
import unittest
from unittest import mock


class TestKeybindings(unittest.TestCase):
    """F1 / F2 must dispatch to Action.HELP / Action.MENU."""

    def _make_app(self):
        from tnc.app import App
        with mock.patch('curses.has_colors', return_value=False), \
             mock.patch('curses.curs_set'), \
             mock.patch('curses.mousemask'):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            stdscr.getch.return_value = ord('q')
            with tempfile.TemporaryDirectory() as td, \
                 mock.patch('os.getcwd', return_value=td):
                app = App(stdscr)
                app.setup()
                return app

    def test_action_help_exists_in_enum(self):
        from tnc.app import Action
        self.assertTrue(hasattr(Action, 'HELP'))

    def test_f1_routes_to_help_action(self):
        from tnc.app import Action
        app = self._make_app()
        self.assertEqual(app.handle_key(curses.KEY_F1), Action.HELP)

    def test_f2_routes_to_menu_action(self):
        from tnc.app import Action
        app = self._make_app()
        self.assertEqual(app.handle_key(curses.KEY_F2), Action.MENU)


class TestHelpModal(unittest.TestCase):
    """HelpModal renders structured keybinding help and dismisses cleanly."""

    def test_help_modal_renders_known_keybindings(self):
        from tnc.dialog import HelpModal
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (40, 100)
        modal.render(win)
        all_text = ' '.join(
            str(call) for call in win.addstr.call_args_list
        )
        # Spot-check a few known keys/labels.
        self.assertIn('F3', all_text)
        self.assertIn('View', all_text)
        self.assertIn('Tab', all_text)
        self.assertIn('Esc', all_text)

    def test_help_modal_renders_section_headers(self):
        from tnc.dialog import HelpModal
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (40, 100)
        modal.render(win)
        all_text = ' '.join(
            str(call) for call in win.addstr.call_args_list
        )
        for header in ('Navigation', 'File operations', 'Selection'):
            self.assertIn(header, all_text)

    def test_help_modal_dismisses_on_esc(self):
        from tnc.dialog import HelpModal
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (40, 100)
        win.getch.side_effect = [27]  # Esc
        modal.show(win)
        # Modal exited the loop, so getch was called exactly once.
        self.assertEqual(win.getch.call_count, 1)

    def test_help_modal_dismisses_on_enter(self):
        from tnc.dialog import HelpModal
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (40, 100)
        win.getch.side_effect = [ord('\n')]
        modal.show(win)
        self.assertEqual(win.getch.call_count, 1)

    def test_help_modal_dismisses_on_click_in_ok_button(self):
        from tnc.dialog import HelpModal
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (40, 100)
        modal.render(win)
        x_start, x_end, btn_y, _ = modal.button_bar.button_positions[0]
        midx = (x_start + x_end) // 2

        win.getch.side_effect = [curses.KEY_MOUSE]
        with mock.patch(
            'curses.getmouse',
            return_value=(0, midx, btn_y, 0, curses.BUTTON1_CLICKED),
        ):
            modal.show(win)
        self.assertEqual(win.getch.call_count, 1)

    def test_help_modal_ignores_outside_click(self):
        """Click outside any button keeps the loop alive; a follow-up key terminates."""
        from tnc.dialog import HelpModal
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (40, 100)
        # Outside click at (0, 0), then Esc.
        win.getch.side_effect = [curses.KEY_MOUSE, 27]
        with mock.patch(
            'curses.getmouse',
            return_value=(0, 0, 0, 0, curses.BUTTON1_CLICKED),
        ):
            modal.show(win)
        # 2 getch calls — outside click ignored, then Esc terminates.
        self.assertEqual(win.getch.call_count, 2)


if __name__ == '__main__':
    unittest.main()
