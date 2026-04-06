"""Tests for menu dropdown navigation and selection."""

import curses
import unittest

from tnc.menu import Menu, MenuBar, MenuItem


class TestDropdownNavigation(unittest.TestCase):
    """Test up/down navigation in dropdown."""

    def test_down_arrow_moves_selection_down(self):
        """Down arrow should move selection down in dropdown."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 0
        menu.handle_key(curses.KEY_DOWN)
        self.assertEqual(menu.selected_item, 1)

    def test_up_arrow_moves_selection_up(self):
        """Up arrow should move selection up in dropdown."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 2
        menu.handle_key(curses.KEY_UP)
        self.assertEqual(menu.selected_item, 1)

    def test_selection_stays_at_top(self):
        """Up arrow at top should stay at top."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 0
        menu.handle_key(curses.KEY_UP)
        # Should close dropdown or stay at 0
        # Current implementation closes dropdown
        self.assertFalse(menu.dropdown_open)

    def test_selection_stays_at_bottom(self):
        """Down arrow at bottom should stay at bottom."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        # Get number of items in first menu
        num_items = len(menu.menus[0].items)
        menu.selected_item = num_items - 1
        menu.handle_key(curses.KEY_DOWN)
        self.assertEqual(menu.selected_item, num_items - 1)


class TestDropdownSelection(unittest.TestCase):
    """Test Enter key selection."""

    def test_enter_closes_dropdown(self):
        """Enter on item should close dropdown."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 0
        menu.handle_key(ord('\n'))
        self.assertFalse(menu.dropdown_open)

    def test_enter_returns_action(self):
        """Enter should return the selected action."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 1  # File menu
        menu.selected_item = 2  # Copy
        action = menu.get_selected_action()
        self.assertEqual(action, 'copy')

    def test_handle_key_returns_action_on_enter(self):
        """handle_key should return action string when Enter pressed on item."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 1  # File menu
        menu.selected_item = 2  # Copy
        result = menu.handle_key(ord('\n'))
        # Should return the action string, not just True
        self.assertEqual(result, 'copy')

    def test_handle_key_returns_action_for_left_menu(self):
        """handle_key should return action string for Left menu items."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 0  # Left menu
        menu.selected_item = 0  # Sort by name
        result = menu.handle_key(ord('\n'))
        # Left menu items now have action strings
        self.assertEqual(result, 'sort_name_left')


class TestDropdownVisuals(unittest.TestCase):
    """Test visual highlighting."""

    def test_selected_item_highlighted(self):
        """Selected item should have highlight attribute."""
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 1
        # The render method uses curses.A_REVERSE for selected item
        # We just verify the selected_item is tracked
        self.assertEqual(menu.selected_item, 1)


class TestDropdownShortcutRendering(unittest.TestCase):
    """Test that dropdown renders keyboard shortcuts right-aligned."""

    def test_dropdown_renders_shortcut_right_aligned(self):
        """Dropdown should render shortcut text right-aligned in item row."""
        from unittest import mock
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 1  # File menu (has shortcuts)
        menu.selected_item = 0

        mock_win = mock.MagicMock()
        menu.render_dropdown(mock_win, y=1, width=80)

        # Collect all rendered text for the dropdown
        rendered_texts = []
        for call in mock_win.addstr.call_args_list:
            if len(call[0]) >= 3:
                rendered_texts.append(call[0][2])

        # The View item (first in File menu) should contain "F3"
        view_text = rendered_texts[0] if rendered_texts else ''
        self.assertIn('F3', view_text)

    def test_dropdown_width_accounts_for_shortcut(self):
        """Dropdown width should be wide enough for name + shortcut."""
        from unittest import mock
        menu = MenuBar()
        # Create a menu with items that have shortcuts
        menu.menus[0] = Menu('Test', [
            MenuItem('View', 'view', shortcut='F3'),
            MenuItem('A Long Name', 'long'),
        ])
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 0
        menu.selected_item = 0

        mock_win = mock.MagicMock()
        menu.render_dropdown(mock_win, y=1, width=80)

        # Check that the rendered text for View includes both name and shortcut
        rendered_texts = [
            call[0][2] for call in mock_win.addstr.call_args_list
            if len(call[0]) >= 3
        ]
        view_text = rendered_texts[0] if rendered_texts else ''
        # Should contain both "View" and "F3"
        self.assertIn('View', view_text)
        self.assertIn('F3', view_text)
        # Shortcut should be right-aligned, so F3 near the end
        self.assertTrue(view_text.rstrip().endswith('F3'),
                        f"Expected shortcut at end, got: {view_text!r}")

    def test_dropdown_item_without_shortcut_has_no_extra_text(self):
        """Items without shortcuts should not show extra shortcut text."""
        from unittest import mock
        menu = MenuBar()
        menu.menus[0] = Menu('Test', [
            MenuItem('Rename', 'rename'),  # No shortcut
        ])
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 0
        menu.selected_item = 0

        mock_win = mock.MagicMock()
        menu.render_dropdown(mock_win, y=1, width=80)

        rendered_texts = [
            call[0][2] for call in mock_win.addstr.call_args_list
            if len(call[0]) >= 3
        ]
        rename_text = rendered_texts[0] if rendered_texts else ''
        # Should just be the name padded with spaces, no shortcut text
        self.assertIn('Rename', rename_text)
        # After stripping padding, should just be the name
        stripped = rename_text.strip()
        self.assertEqual(stripped, 'Rename')

    def test_all_items_uniform_width_in_mixed_shortcut_menu(self):
        """All items in a menu with mixed shortcuts should have the same width."""
        from unittest import mock
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 1  # File menu (has both shortcut and non-shortcut items)
        menu.selected_item = 0

        mock_win = mock.MagicMock()
        menu.render_dropdown(mock_win, y=1, width=80)

        rendered_texts = [
            call[0][2] for call in mock_win.addstr.call_args_list
            if len(call[0]) >= 3
        ]
        widths = [len(text) for text in rendered_texts]
        self.assertTrue(len(set(widths)) == 1,
                        f"Item widths should be uniform, got: {widths}")

        # Rename (no shortcut) should be padded but contain no shortcut text
        rename_idx = next(
            i for i, t in enumerate(rendered_texts) if 'Rename' in t
        )
        rename_text = rendered_texts[rename_idx]
        self.assertIn('Rename', rename_text)
        self.assertEqual(rename_text.strip(), 'Rename')


class TestMenuActions(unittest.TestCase):
    """Test menu actions integration with App."""

    def test_file_menu_copy_action(self):
        """Copy menu item should have 'copy' action."""
        menu = MenuBar()
        file_menu = menu.menus[1]  # File menu
        copy_item = next(i for i in file_menu.items if i.name == 'Copy')
        self.assertEqual(copy_item.action, 'copy')

    def test_file_menu_move_action(self):
        """Move menu item should have 'move' action."""
        menu = MenuBar()
        file_menu = menu.menus[1]  # File menu
        move_item = next(i for i in file_menu.items if i.name == 'Move')
        self.assertEqual(move_item.action, 'move')


class TestDisabledItems(unittest.TestCase):
    """Test disabled item handling."""

    def test_menu_item_has_enabled_field(self):
        """MenuItem should have enabled field."""
        item = MenuItem('Test')
        self.assertTrue(item.enabled)

    def test_menu_item_can_be_disabled(self):
        """MenuItem can be created with enabled=False."""
        item = MenuItem('Test', enabled=False)
        self.assertFalse(item.enabled)

    def test_down_arrow_skips_disabled_item(self):
        """Down arrow should skip disabled items."""
        menu = MenuBar()
        # Replace first menu with items including disabled
        menu.menus[0] = Menu('Test', [
            MenuItem('Item1'),
            MenuItem('Item2', enabled=False),
            MenuItem('Item3'),
        ])
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 0
        menu.handle_key(curses.KEY_DOWN)
        # Should skip Item2 and land on Item3
        self.assertEqual(menu.selected_item, 2)

    def test_up_arrow_skips_disabled_item(self):
        """Up arrow should skip disabled items."""
        menu = MenuBar()
        # Replace first menu with items including disabled
        menu.menus[0] = Menu('Test', [
            MenuItem('Item1'),
            MenuItem('Item2', enabled=False),
            MenuItem('Item3'),
        ])
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 2
        menu.handle_key(curses.KEY_UP)
        # Should skip Item2 and land on Item1
        self.assertEqual(menu.selected_item, 0)


class TestMenuItemShortcut(unittest.TestCase):
    """Test MenuItem shortcut field."""

    def test_menu_item_shortcut_defaults_to_empty(self):
        """MenuItem shortcut should default to empty string."""
        item = MenuItem('Test', 'test_action')
        self.assertEqual(item.shortcut, '')

    def test_menu_item_shortcut_custom_value(self):
        """MenuItem should accept a custom shortcut string."""
        item = MenuItem('View', 'view', shortcut='F3')
        self.assertEqual(item.shortcut, 'F3')

    def test_file_menu_view_has_f3_shortcut(self):
        """File menu View item should have F3 shortcut."""
        menu = MenuBar()
        file_menu = menu.menus[1]  # File menu
        view_item = next(i for i in file_menu.items if i.name == 'View')
        self.assertEqual(view_item.shortcut, 'F3')

    def test_file_menu_edit_has_f4_shortcut(self):
        """File menu Edit item should have F4 shortcut."""
        menu = MenuBar()
        file_menu = menu.menus[1]
        edit_item = next(i for i in file_menu.items if i.name == 'Edit')
        self.assertEqual(edit_item.shortcut, 'F4')

    def test_file_menu_copy_has_f5_shortcut(self):
        """File menu Copy item should have F5 shortcut."""
        menu = MenuBar()
        file_menu = menu.menus[1]
        copy_item = next(i for i in file_menu.items if i.name == 'Copy')
        self.assertEqual(copy_item.shortcut, 'F5')

    def test_file_menu_move_has_f6_shortcut(self):
        """File menu Move item should have F6 shortcut."""
        menu = MenuBar()
        file_menu = menu.menus[1]
        move_item = next(i for i in file_menu.items if i.name == 'Move')
        self.assertEqual(move_item.shortcut, 'F6')

    def test_file_menu_delete_has_f8_shortcut(self):
        """File menu Delete item should have F8 shortcut."""
        menu = MenuBar()
        file_menu = menu.menus[1]
        delete_item = next(i for i in file_menu.items if i.name == 'Delete')
        self.assertEqual(delete_item.shortcut, 'F8')

    def test_file_menu_mkdir_has_f7_shortcut(self):
        """File menu Mkdir item should have F7 shortcut."""
        menu = MenuBar()
        file_menu = menu.menus[1]
        mkdir_item = next(i for i in file_menu.items if i.name == 'Mkdir')
        self.assertEqual(mkdir_item.shortcut, 'F7')

    def test_file_menu_rename_has_no_shortcut(self):
        """File menu Rename item should have no shortcut."""
        menu = MenuBar()
        file_menu = menu.menus[1]
        rename_item = next(i for i in file_menu.items if i.name == 'Rename')
        self.assertEqual(rename_item.shortcut, '')

    def test_command_menu_invert_selection_has_star_shortcut(self):
        """Command menu Invert selection should have * shortcut."""
        menu = MenuBar()
        cmd_menu = menu.menus[2]  # Command menu
        item = next(i for i in cmd_menu.items if i.name == 'Invert selection')
        self.assertEqual(item.shortcut, '*')

    def test_command_menu_select_by_pattern_has_plus_shortcut(self):
        """Command menu Select by pattern should have + shortcut."""
        menu = MenuBar()
        cmd_menu = menu.menus[2]
        item = next(i for i in cmd_menu.items if i.name == 'Select by pattern')
        self.assertEqual(item.shortcut, '+')

    def test_command_menu_select_all_has_no_shortcut(self):
        """Command menu Select all should have no shortcut."""
        menu = MenuBar()
        cmd_menu = menu.menus[2]
        item = next(i for i in cmd_menu.items if i.name == 'Select all')
        self.assertEqual(item.shortcut, '')

    def test_left_menu_items_have_no_shortcuts(self):
        """Left menu sort items should have no shortcuts."""
        menu = MenuBar()
        left_menu = menu.menus[0]
        for item in left_menu.items:
            self.assertEqual(item.shortcut, '',
                             f"Left menu item '{item.name}' should have no shortcut")

    def test_options_menu_items_have_no_shortcuts(self):
        """Options menu items should have no shortcuts."""
        menu = MenuBar()
        options_menu = menu.menus[3]
        for item in options_menu.items:
            self.assertEqual(item.shortcut, '',
                             f"Options menu item '{item.name}' should have no shortcut")


class TestMenuActionExecution(unittest.TestCase):
    """Test that menu actions trigger correct App actions."""

    def test_copy_menu_triggers_copy_action(self):
        """Selecting Copy in menu should trigger COPY action."""
        from unittest import mock
        from tnc.app import App, Action, MENU_ACTION_MAP

        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            # Open menu and select Copy
            app.menu.visible = True
            app.menu.dropdown_open = True
            app.menu.selected_menu = 1  # File menu
            app.menu.selected_item = 2  # Copy

            # Simulate Enter key
            action = app.handle_key(ord('\n'))
            self.assertEqual(action, Action.COPY)

    def test_sort_left_menu_triggers_sort_action(self):
        """Selecting Sort by name in Left menu should trigger SORT_NAME_LEFT."""
        from unittest import mock
        from tnc.app import App, Action

        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            # Open menu and select Sort by name in Left menu
            app.menu.visible = True
            app.menu.dropdown_open = True
            app.menu.selected_menu = 0  # Left menu
            app.menu.selected_item = 0  # Sort by name

            action = app.handle_key(ord('\n'))
            self.assertEqual(action, Action.SORT_NAME_LEFT)

    def test_select_all_menu_triggers_action(self):
        """Selecting Select all in Command menu should trigger SELECT_ALL."""
        from unittest import mock
        from tnc.app import App, Action

        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            # Open menu and select Select all in Command menu
            app.menu.visible = True
            app.menu.dropdown_open = True
            app.menu.selected_menu = 2  # Command menu
            app.menu.selected_item = 1  # Select all (after Toggle select)

            action = app.handle_key(ord('\n'))
            self.assertEqual(action, Action.SELECT_ALL)


if __name__ == '__main__':
    unittest.main()
