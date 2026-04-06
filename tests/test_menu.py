"""Tests for F9 menu bar toggle and rendering."""

import curses
import unittest
from unittest import mock


class TestMenuBarStructure(unittest.TestCase):
    """Test menu bar structure."""

    def test_menu_bar_has_expected_items(self):
        """Menu bar should have Left, File, Command, Options, Right."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        names = [m.name for m in menu.menus]
        self.assertIn('Left', names)
        self.assertIn('File', names)
        self.assertIn('Command', names)
        self.assertIn('Options', names)
        self.assertIn('Right', names)

    def test_menu_bar_has_correct_order(self):
        """Menus should be in correct order."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        names = [m.name for m in menu.menus]
        self.assertEqual(names, ['Left', 'File', 'Command', 'Options', 'Right'])

    def test_menu_bar_initially_visible(self):
        """Menu bar should be visible by default (always visible like mc)."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        self.assertTrue(menu.visible)


class TestCommandMenuItems(unittest.TestCase):
    """Test Command menu has all expected items."""

    def test_command_menu_has_toggle_select(self):
        """Command menu should include Toggle select item."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        command_menu = next(m for m in menu.menus if m.name == 'Command')
        item_actions = [item.action for item in command_menu.items]
        self.assertIn('toggle_select', item_actions)


class TestF9Toggle(unittest.TestCase):
    """Test F9 toggling dropdown (menu bar is always visible)."""

    def test_f9_opens_dropdown(self):
        """F9 should open dropdown when menu bar is visible."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            self.assertTrue(app.menu.visible)
            self.assertFalse(app.menu.dropdown_open)
            app.handle_key(curses.KEY_F9)
            self.assertTrue(app.menu.dropdown_open)

    def test_f9_closes_dropdown(self):
        """F9 should close dropdown when already open."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            app.menu.dropdown_open = True
            app.handle_key(curses.KEY_F9)
            self.assertFalse(app.menu.dropdown_open)


class TestMenuNavigation(unittest.TestCase):
    """Test left/right arrow navigation when dropdown is open."""

    def test_left_arrow_changes_menu(self):
        """Left arrow should move to previous menu when dropdown open."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 1  # 'File'
        menu.handle_key(curses.KEY_LEFT)
        self.assertEqual(menu.selected_menu, 0)  # 'Left'

    def test_right_arrow_changes_menu(self):
        """Right arrow should move to next menu when dropdown open."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 0  # 'Left'
        menu.handle_key(curses.KEY_RIGHT)
        self.assertEqual(menu.selected_menu, 1)  # 'File'

    def test_left_arrow_wraps_around(self):
        """Left arrow at first menu should wrap to last."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 0  # 'Left'
        menu.handle_key(curses.KEY_LEFT)
        self.assertEqual(menu.selected_menu, 4)  # 'Right'

    def test_right_arrow_wraps_around(self):
        """Right arrow at last menu should wrap to first."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_menu = 4  # 'Right'
        menu.handle_key(curses.KEY_RIGHT)
        self.assertEqual(menu.selected_menu, 0)  # 'Left'

    def test_arrows_ignored_when_dropdown_closed(self):
        """Arrow keys should not navigate menus when dropdown is closed."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = False
        menu.selected_menu = 0
        result = menu.handle_key(curses.KEY_RIGHT)
        self.assertFalse(result)  # Key not handled
        self.assertEqual(menu.selected_menu, 0)  # No change


class TestDropdown(unittest.TestCase):
    """Test dropdown behavior."""

    def test_keys_ignored_when_dropdown_closed(self):
        """Keys should be ignored when dropdown is closed (menu just displays)."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = False

        # Down arrow should not be handled
        result = menu.handle_key(curses.KEY_DOWN)
        self.assertFalse(result)
        self.assertFalse(menu.dropdown_open)

        # Enter should not be handled
        result = menu.handle_key(ord('\n'))
        self.assertFalse(result)
        self.assertFalse(menu.dropdown_open)

    def test_down_navigates_in_dropdown(self):
        """Down arrow should navigate in open dropdown."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.selected_item = 0
        menu.handle_key(curses.KEY_DOWN)
        self.assertEqual(menu.selected_item, 1)


class TestEscapeKey(unittest.TestCase):
    """Test escape key behavior."""

    def test_escape_ignored_when_dropdown_closed(self):
        """Escape should be ignored when dropdown is closed (menu always visible)."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = False
        result = menu.handle_key(27)  # Escape
        self.assertFalse(result)  # Not handled
        self.assertTrue(menu.visible)  # Menu stays visible

    def test_escape_closes_dropdown(self):
        """Escape should close dropdown when open."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.handle_key(27)  # Escape
        self.assertFalse(menu.dropdown_open)
        self.assertTrue(menu.visible)  # Menu bar still visible

    def test_second_escape_does_nothing(self):
        """Second escape should do nothing (menu always visible)."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True
        menu.handle_key(27)  # Close dropdown
        result = menu.handle_key(27)  # Second escape
        self.assertFalse(result)  # Not handled (dropdown already closed)
        self.assertTrue(menu.visible)  # Menu still visible


class TestMenuRendering(unittest.TestCase):
    """Test menu bar rendering."""

    def test_menu_renders_to_width(self):
        """Menu bar should render to specified width."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        text = menu.get_display_text(width=80)
        self.assertLessEqual(len(text), 80)

    def test_menu_shows_all_names(self):
        """Rendered menu should show all menu names."""
        from tnc.menu import MenuBar
        menu = MenuBar()
        menu.visible = True
        text = menu.get_display_text(width=80)
        self.assertIn('Left', text)
        self.assertIn('File', text)
        self.assertIn('Command', text)
        self.assertIn('Options', text)
        self.assertIn('Right', text)


class TestMenuKeyDelegation(unittest.TestCase):
    """Test that App delegates keys to menu when visible."""

    def test_arrows_go_to_menu_when_dropdown_open(self):
        """Arrow keys should go to menu when dropdown is open."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            app.menu.visible = True
            app.menu.dropdown_open = True  # Dropdown must be open
            app.menu.selected_menu = 0
            # Right arrow should move menu selection
            app.handle_key(curses.KEY_RIGHT)
            self.assertEqual(app.menu.selected_menu, 1)

    def test_escape_closes_dropdown(self):
        """Escape should close dropdown (menu stays visible)."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            app.menu.visible = True
            app.menu.dropdown_open = True
            app.handle_key(27)  # Escape
            self.assertFalse(app.menu.dropdown_open)
            self.assertTrue(app.menu.visible)  # Menu still visible


class TestMenuBarPanelOffset(unittest.TestCase):
    """Test that panels render below menu bar (always visible)."""

    def test_panels_always_render_at_y1(self):
        """Panels should always render at y=1 (below always-visible menu bar)."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False), \
             mock.patch('curses.doupdate'):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            # Menu is always visible
            self.assertTrue(app.menu.visible)

            # Mock panel render methods to capture y position
            app.left_panel.render = mock.MagicMock()
            app.right_panel.render = mock.MagicMock()

            app.draw()

            # Panels should render at y=1 (below menu bar)
            left_call = app.left_panel.render.call_args
            right_call = app.right_panel.render.call_args
            # render(win, x, y) - y is the third positional arg
            self.assertEqual(left_call[0][2], 1, "Left panel should render at y=1")
            self.assertEqual(right_call[0][2], 1, "Right panel should render at y=1")

    def test_panel_height_is_rows_minus_4(self):
        """Panel height should be rows - 4 (menu + status + cmdline + funcbar)."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False), \
             mock.patch('curses.doupdate'):
            stdscr = mock.MagicMock()
            rows, cols = 24, 80
            stdscr.getmaxyx.return_value = (rows, cols)
            app = App(stdscr)
            app.setup()

            # Height is always rows - 4 (menu always visible)
            self.assertEqual(app.left_panel.height, rows - 4)
            self.assertEqual(app.right_panel.height, rows - 4)

    def test_handle_resize_maintains_bottom_bar_space(self):
        """handle_resize should use rows-4 (menu + 3 bottom rows)."""
        from tnc.app import App
        with mock.patch('curses.curs_set'), \
             mock.patch('curses.has_colors', return_value=False):
            stdscr = mock.MagicMock()
            stdscr.getmaxyx.return_value = (24, 80)
            app = App(stdscr)
            app.setup()

            # Simulate resize to new dimensions
            new_rows, new_cols = 30, 100
            stdscr.getmaxyx.return_value = (new_rows, new_cols)
            app.handle_resize()

            # Height should be rows - 4 (menu + status bar + command line + function bar)
            expected_height = new_rows - 4
            self.assertEqual(app.left_panel.height, expected_height)
            self.assertEqual(app.right_panel.height, expected_height)


class TestMenuBarHighlighting(unittest.TestCase):
    """Test menu bar highlighting behavior."""

    def test_no_menu_highlighted_when_dropdown_closed(self):
        """No menu should be highlighted when dropdown is closed (issue #130)."""
        from tnc.menu import MenuBar
        from tnc.colors import PAIR_MENU_SELECTED, get_attr

        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = False  # Dropdown closed - no highlight expected
        mock_win = mock.MagicMock()

        menu.render(mock_win, y=0, width=80)

        # Check that no addstr call used PAIR_MENU_SELECTED
        selected_attr = get_attr(PAIR_MENU_SELECTED, bold=True)
        for call in mock_win.addstr.call_args_list:
            # addstr(y, x, text, attr) - attr is the 4th argument
            if len(call[0]) >= 4:
                attr_used = call[0][3]
                self.assertNotEqual(
                    attr_used, selected_attr,
                    f"Menu should not be highlighted when dropdown is closed, "
                    f"but got highlighted text: {call[0][2]!r}"
                )

    def test_menu_highlighted_when_dropdown_open(self):
        """Selected menu should be highlighted when dropdown is open."""
        from tnc.menu import MenuBar
        from tnc.colors import PAIR_MENU_SELECTED, get_attr

        menu = MenuBar()
        menu.visible = True
        menu.dropdown_open = True  # Dropdown open - highlight expected
        menu.selected_menu = 0  # "Left" menu selected
        mock_win = mock.MagicMock()

        menu.render(mock_win, y=0, width=80)

        # Check that at least one addstr call used PAIR_MENU_SELECTED
        selected_attr = get_attr(PAIR_MENU_SELECTED, bold=True)
        highlighted_calls = [
            call for call in mock_win.addstr.call_args_list
            if len(call[0]) >= 4 and call[0][3] == selected_attr
        ]
        self.assertGreater(
            len(highlighted_calls), 0,
            "Selected menu should be highlighted when dropdown is open"
        )


if __name__ == '__main__':
    unittest.main()
