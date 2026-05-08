"""Tests for chown dialog."""

import curses
import os
import unittest
from unittest import mock

from tnc.dialog import ChownDialog, chown_dialog


class TestChownDialogInit(unittest.TestCase):
    """Tests for ChownDialog initialization."""

    def test_chown_dialog_init(self):
        """ChownDialog initializes with current owner/group."""
        dialog = ChownDialog(
            file_count=1,
            current_owner='alice',
            current_group='staff'
        )

        self.assertEqual(dialog.file_count, 1)
        self.assertEqual(dialog.owner_input, 'alice')
        self.assertEqual(dialog.group_input, 'staff')

    def test_chown_dialog_init_multiple_files(self):
        """ChownDialog for multiple files shows count."""
        dialog = ChownDialog(file_count=5, current_owner='bob', current_group='users')
        self.assertEqual(dialog.file_count, 5)


class TestChownDialogInput(unittest.TestCase):
    """Tests for ChownDialog text input."""

    def test_type_in_owner_field(self):
        """Can type in owner field."""
        dialog = ChownDialog(file_count=1, current_owner='', current_group='staff')

        # Type 'a', 'l', 'i', 'c', 'e'
        for char in 'alice':
            dialog.handle_key(ord(char))

        self.assertEqual(dialog.owner_input, 'alice')

    def test_backspace_in_owner_field(self):
        """Backspace removes character from owner field."""
        dialog = ChownDialog(file_count=1, current_owner='alice', current_group='staff')

        dialog.handle_key(curses.KEY_BACKSPACE)

        self.assertEqual(dialog.owner_input, 'alic')

    def test_tab_switches_to_group_field(self):
        """Tab switches focus to group field."""
        dialog = ChownDialog(file_count=1, current_owner='alice', current_group='staff')

        self.assertEqual(dialog.active_field, 'owner')

        dialog.handle_key(ord('\t'))

        self.assertEqual(dialog.active_field, 'group')

    def test_type_in_group_field(self):
        """Can type in group field after tabbing."""
        dialog = ChownDialog(file_count=1, current_owner='alice', current_group='')

        dialog.handle_key(ord('\t'))  # Switch to group
        for char in 'wheel':
            dialog.handle_key(ord(char))

        self.assertEqual(dialog.group_input, 'wheel')


class TestChownDialogAutocomplete(unittest.TestCase):
    """Tests for ChownDialog autocomplete."""

    def test_autocomplete_shows_matches(self):
        """Typing shows autocomplete suggestions."""
        dialog = ChownDialog(
            file_count=1,
            current_owner='',
            current_group='staff',
            users=['alice', 'adam', 'bob'],
            groups=['staff', 'wheel']
        )

        dialog.handle_key(ord('a'))

        self.assertIn('adam', dialog.get_autocomplete_suggestions())
        self.assertIn('alice', dialog.get_autocomplete_suggestions())
        self.assertNotIn('bob', dialog.get_autocomplete_suggestions())

    def test_down_arrow_navigates_autocomplete(self):
        """Down arrow navigates autocomplete list."""
        dialog = ChownDialog(
            file_count=1,
            current_owner='',
            current_group='staff',
            users=['adam', 'alice', 'anna'],
            groups=['staff']
        )

        dialog.handle_key(ord('a'))
        self.assertEqual(dialog.autocomplete_index, -1)  # No selection

        dialog.handle_key(curses.KEY_DOWN)
        self.assertEqual(dialog.autocomplete_index, 0)

        dialog.handle_key(curses.KEY_DOWN)
        self.assertEqual(dialog.autocomplete_index, 1)

    def test_enter_selects_autocomplete(self):
        """Enter selects autocomplete suggestion."""
        dialog = ChownDialog(
            file_count=1,
            current_owner='',
            current_group='staff',
            users=['adam', 'alice'],
            groups=['staff']
        )

        dialog.handle_key(ord('a'))
        dialog.handle_key(curses.KEY_DOWN)  # Select 'adam'
        dialog.handle_key(ord('\n'))

        self.assertEqual(dialog.owner_input, 'adam')


class TestChownDialogResult(unittest.TestCase):
    """Tests for ChownDialog result."""

    def test_escape_cancels(self):
        """Escape key returns None (cancel)."""
        dialog = ChownDialog(file_count=1, current_owner='alice', current_group='staff')

        result = dialog.handle_key(27)  # Escape

        self.assertTrue(dialog.cancelled)

    def test_get_result(self):
        """get_result returns owner and group strings."""
        dialog = ChownDialog(file_count=1, current_owner='alice', current_group='staff')

        result = dialog.get_result()

        self.assertEqual(result, ('alice', 'staff'))


class TestChownDialogMouse(unittest.TestCase):
    """Issue #16: ChownDialog gains click on owner field, group field, OK,
    and Cancel."""

    def _setup(self):
        d = ChownDialog(
            file_count=1,
            current_owner='alice',
            current_group='staff',
            users=['alice', 'bob', 'charlie'],
            groups=['staff', 'wheel'],
            filename='file.txt',
        )
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        return d, win

    def _hit(self, dialog, action_id):
        for x_start, x_end, y, target in dialog._click_targets:
            if target == action_id:
                return ((x_start + x_end) // 2, y)
        raise AssertionError(f'no click target for {action_id!r}')

    def test_click_on_owner_field_focuses_owner(self):
        d, win = self._setup()
        d.active_field = 'group'  # start somewhere else
        d.render(win)
        x, y = self._hit(d, 'owner_field')
        win.getch.side_effect = [curses.KEY_MOUSE, 27]  # click then Esc
        with mock.patch(
            'curses.getmouse',
            return_value=(0, x, y, 0, curses.BUTTON1_CLICKED),
        ):
            d.show(win)
        self.assertEqual(d.active_field, 'owner')

    def test_click_on_group_field_focuses_group(self):
        d, win = self._setup()
        d.active_field = 'owner'
        d.render(win)
        x, y = self._hit(d, 'group_field')
        win.getch.side_effect = [curses.KEY_MOUSE, 27]
        with mock.patch(
            'curses.getmouse',
            return_value=(0, x, y, 0, curses.BUTTON1_CLICKED),
        ):
            d.show(win)
        self.assertEqual(d.active_field, 'group')

    def test_click_on_ok_returns_tuple(self):
        d, win = self._setup()
        d.render(win)
        x, y = self._hit(d, 'ok')
        win.getch.side_effect = [curses.KEY_MOUSE]
        with mock.patch(
            'curses.getmouse',
            return_value=(0, x, y, 0, curses.BUTTON1_CLICKED),
        ):
            self.assertEqual(d.show(win), ('alice', 'staff'))

    def test_click_on_cancel_returns_none(self):
        d, win = self._setup()
        d.render(win)
        x, y = self._hit(d, 'cancel')
        win.getch.side_effect = [curses.KEY_MOUSE]
        with mock.patch(
            'curses.getmouse',
            return_value=(0, x, y, 0, curses.BUTTON1_CLICKED),
        ):
            self.assertIsNone(d.show(win))

    def test_existing_tab_navigation_preserved(self):
        """Regression: Tab still cycles owner → group → buttons."""
        d, _ = self._setup()
        self.assertEqual(d.active_field, 'owner')
        d.handle_key(ord('\t'))
        self.assertEqual(d.active_field, 'group')
        d.handle_key(ord('\t'))
        self.assertEqual(d.active_field, 'buttons')


if __name__ == '__main__':
    unittest.main()
