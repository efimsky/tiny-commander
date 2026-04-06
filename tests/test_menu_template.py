"""Tests for menu item template generation."""

import unittest

from tnc.menu import MenuBar, MenuItem, _build_panel_sort_items


class TestBuildPanelSortItems(unittest.TestCase):
    """Tests for _build_panel_sort_items helper function."""

    def test_build_left_panel_items_returns_list(self):
        """_build_panel_sort_items('left') returns a list."""
        items = _build_panel_sort_items('left')
        self.assertIsInstance(items, list)

    def test_build_left_panel_items_count(self):
        """_build_panel_sort_items('left') returns 6 items."""
        items = _build_panel_sort_items('left')
        self.assertEqual(len(items), 6)

    def test_build_left_panel_items_are_menu_items(self):
        """All items from _build_panel_sort_items are MenuItem instances."""
        items = _build_panel_sort_items('left')
        for item in items:
            self.assertIsInstance(item, MenuItem)

    def test_build_left_panel_sort_by_name(self):
        """First item is Sort by name with sort_name_left action."""
        items = _build_panel_sort_items('left')
        self.assertEqual(items[0].name, 'Sort by name')
        self.assertEqual(items[0].action, 'sort_name_left')

    def test_build_left_panel_sort_by_size(self):
        """Second item is Sort by size with sort_size_left action."""
        items = _build_panel_sort_items('left')
        self.assertEqual(items[1].name, 'Sort by size')
        self.assertEqual(items[1].action, 'sort_size_left')

    def test_build_left_panel_sort_by_date(self):
        """Third item is Sort by date with sort_date_left action."""
        items = _build_panel_sort_items('left')
        self.assertEqual(items[2].name, 'Sort by date')
        self.assertEqual(items[2].action, 'sort_date_left')

    def test_build_left_panel_sort_by_extension(self):
        """Fourth item is Sort by extension with sort_ext_left action."""
        items = _build_panel_sort_items('left')
        self.assertEqual(items[3].name, 'Sort by extension')
        self.assertEqual(items[3].action, 'sort_ext_left')

    def test_build_left_panel_reverse_sort(self):
        """Fifth item is Reverse sort with reverse_sort_left action."""
        items = _build_panel_sort_items('left')
        self.assertEqual(items[4].name, 'Reverse sort')
        self.assertEqual(items[4].action, 'reverse_sort_left')

    def test_build_left_panel_toggle_hidden(self):
        """Sixth item is Toggle hidden with toggle_hidden action (shared)."""
        items = _build_panel_sort_items('left')
        self.assertEqual(items[5].name, 'Toggle hidden')
        self.assertEqual(items[5].action, 'toggle_hidden')

    def test_build_right_panel_sort_by_name(self):
        """Right panel: Sort by name has sort_name_right action."""
        items = _build_panel_sort_items('right')
        self.assertEqual(items[0].name, 'Sort by name')
        self.assertEqual(items[0].action, 'sort_name_right')

    def test_build_right_panel_sort_by_size(self):
        """Right panel: Sort by size has sort_size_right action."""
        items = _build_panel_sort_items('right')
        self.assertEqual(items[1].name, 'Sort by size')
        self.assertEqual(items[1].action, 'sort_size_right')

    def test_build_right_panel_reverse_sort(self):
        """Right panel: Reverse sort has reverse_sort_right action."""
        items = _build_panel_sort_items('right')
        self.assertEqual(items[4].name, 'Reverse sort')
        self.assertEqual(items[4].action, 'reverse_sort_right')

    def test_build_right_panel_toggle_hidden_same(self):
        """Toggle hidden action is the same for both panels."""
        left_items = _build_panel_sort_items('left')
        right_items = _build_panel_sort_items('right')
        self.assertEqual(left_items[5].action, right_items[5].action)
        self.assertEqual(left_items[5].action, 'toggle_hidden')


class TestMenuBarUsesTemplate(unittest.TestCase):
    """Tests that MenuBar uses the template for Left/Right menus."""

    def test_left_menu_uses_template_items(self):
        """Left menu items match template-generated items."""
        menu_bar = MenuBar()
        left_menu = menu_bar.menus[0]  # First menu is 'Left'
        expected_items = _build_panel_sort_items('left')

        self.assertEqual(left_menu.name, 'Left')
        self.assertEqual(len(left_menu.items), len(expected_items))
        for actual, expected in zip(left_menu.items, expected_items):
            self.assertEqual(actual.name, expected.name)
            self.assertEqual(actual.action, expected.action)

    def test_right_menu_uses_template_items(self):
        """Right menu items match template-generated items."""
        menu_bar = MenuBar()
        right_menu = menu_bar.menus[4]  # Fifth menu is 'Right'
        expected_items = _build_panel_sort_items('right')

        self.assertEqual(right_menu.name, 'Right')
        self.assertEqual(len(right_menu.items), len(expected_items))
        for actual, expected in zip(right_menu.items, expected_items):
            self.assertEqual(actual.name, expected.name)
            self.assertEqual(actual.action, expected.action)


if __name__ == '__main__':
    unittest.main()
