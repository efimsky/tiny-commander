"""Menu bar for Tiny Commander."""

import curses
import sys
from dataclasses import dataclass, field
from typing import Any

from tnc.colors import (
    PAIR_DROPDOWN,
    PAIR_DROPDOWN_SELECTED,
    PAIR_MENU_BAR,
    PAIR_MENU_SELECTED,
    get_attr,
)
from tnc.utils import safe_addstr


def _build_panel_sort_items(side: str) -> list['MenuItem']:
    """Build sort menu items for a panel.

    Args:
        side: Panel side ('left' or 'right').

    Returns:
        List of MenuItem instances for panel-specific sort options.
    """
    return [
        MenuItem('Sort by name', f'sort_name_{side}'),
        MenuItem('Sort by size', f'sort_size_{side}'),
        MenuItem('Sort by date', f'sort_date_{side}'),
        MenuItem('Sort by extension', f'sort_ext_{side}'),
        MenuItem('Reverse sort', f'reverse_sort_{side}'),
        MenuItem('Toggle hidden', 'toggle_hidden'),
    ]


@dataclass
class MenuItem:
    """A single menu item in a dropdown."""

    name: str
    action: str = ''  # Action identifier
    enabled: bool = True  # Whether item is selectable
    shortcut: str = ''  # Keyboard shortcut display text (e.g. 'F3')


@dataclass
class Menu:
    """A single menu in the menu bar."""

    name: str
    items: list[MenuItem] = field(default_factory=list)


class MenuBar:
    """Menu bar at the top of the screen."""

    def __init__(self) -> None:
        """Initialize menu bar with default menus."""
        self.visible = True  # Always visible (like classic mc)
        self.dropdown_open = False
        self.selected_menu = 0
        self.selected_item = 0

        # Position tracking for mouse hit detection
        self.menu_positions: list[tuple[int, int, int]] = []  # (start_x, end_x, menu_idx)
        self.dropdown_positions: list[tuple[int, int, int, int]] = []  # (y, start_x, end_x, item_idx)
        self.render_y: int = 0

        # Initialize menus
        self.menus = [
            Menu('Left', _build_panel_sort_items('left')),
            Menu('File', self._build_file_menu_items()),
            Menu('Command', [
                MenuItem('Toggle select', 'toggle_select'),
                MenuItem('Select all', 'select_all'),
                MenuItem('Deselect all', 'deselect_all'),
                MenuItem('Invert selection', 'invert_selection', shortcut='*'),
                MenuItem('Select by pattern', 'select_pattern', shortcut='+'),
            ]),
            Menu('Options', [
                MenuItem('Editor settings', 'editor_settings'),
                MenuItem('Pager settings', 'pager_settings'),
                MenuItem('Classic colors', 'toggle_classic_colors'),
                MenuItem('Mouse support', 'toggle_mouse'),
                MenuItem('Swap mouse buttons', 'toggle_mouse_swap'),
            ]),
            Menu('Right', _build_panel_sort_items('right')),
        ]

    def _build_file_menu_items(self) -> list[MenuItem]:
        """Build File menu items, with platform-specific items."""
        items = [
            MenuItem('View', 'view', shortcut='F3'),
            MenuItem('Edit', 'edit', shortcut='F4'),
            MenuItem('Copy', 'copy', shortcut='F5'),
            MenuItem('Move', 'move', shortcut='F6'),
            MenuItem('Delete', 'delete', shortcut='F8'),
            MenuItem('Rename', 'rename'),
            MenuItem('Mkdir', 'mkdir', shortcut='F7'),
            MenuItem('Permissions...', 'chmod'),
            MenuItem('Ownership...', 'chown'),
        ]
        if sys.platform == 'darwin':
            items.append(MenuItem('Open in Finder', 'open_in_finder',
                                  shortcut='Alt+O'))
        return items

    def handle_key(self, key: int) -> str | bool:
        """Handle a key press.

        Only handles keys when dropdown is open (menu navigation mode).
        When dropdown is closed, returns False to let other components handle keys.

        Args:
            key: The key code.

        Returns:
            False if the key was not handled.
            True if the key was handled but no action triggered.
            Action string if an item was selected (may be empty string).
        """
        if not self.visible:
            return False

        # Only handle keys when dropdown is open (menu navigation active)
        if not self.dropdown_open:
            return False

        # Escape key - close dropdown
        if key == 27:
            self.dropdown_open = False
            return True

        # Left arrow - previous menu (wraps around)
        if key == curses.KEY_LEFT:
            self.selected_menu = (self.selected_menu - 1) % len(self.menus)
            self.selected_item = 0  # Reset item selection when switching menus
            return True

        # Right arrow - next menu (wraps around)
        if key == curses.KEY_RIGHT:
            self.selected_menu = (self.selected_menu + 1) % len(self.menus)
            self.selected_item = 0  # Reset item selection when switching menus
            return True

        # Enter - select item
        if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            action = self.get_selected_action()
            self.dropdown_open = False
            return action  # Return action string (may be empty)

        # Down arrow - navigate down in dropdown
        if key == curses.KEY_DOWN:
            next_item = self._find_next_enabled(self.selected_item + 1, 1)
            if next_item is not None:
                self.selected_item = next_item
            return True

        # Up arrow - navigate up in dropdown
        if key == curses.KEY_UP:
            prev_item = self._find_next_enabled(self.selected_item - 1, -1)
            if prev_item is not None:
                self.selected_item = prev_item
            else:
                # Close dropdown when going up from first item
                self.dropdown_open = False
            return True

        return False

    def _find_next_enabled(self, start: int, direction: int) -> int | None:
        """Find next enabled item in the current menu.

        Args:
            start: Starting index to search from.
            direction: 1 for down, -1 for up.

        Returns:
            Index of next enabled item, or None if not found.
        """
        menu = self.menus[self.selected_menu]
        index = start
        while 0 <= index < len(menu.items):
            if menu.items[index].enabled:
                return index
            index += direction
        return None

    def get_selected_action(self) -> str:
        """Get the action string for the currently selected item.

        Returns:
            The action string, or empty string if no action.
        """
        menu = self.menus[self.selected_menu]
        if 0 <= self.selected_item < len(menu.items):
            return menu.items[self.selected_item].action
        return ''

    def get_display_text(self, width: int) -> str:
        """Get the display text for the menu bar.

        Args:
            width: Available width.

        Returns:
            The formatted menu bar text.
        """
        text = ''.join(f' {menu.name} ' for menu in self.menus)
        return text.ljust(width)[:width]

    def render(self, win: Any, y: int, width: int) -> None:
        """Render the menu bar to a curses window.

        Args:
            win: The curses window.
            y: Y position to render at.
            width: Available width.
        """
        if not self.visible:
            return

        # Store render position for mouse hit detection
        self.render_y = y
        self.menu_positions.clear()

        # Render menu bar background
        bar_attr = get_attr(PAIR_MENU_BAR)
        safe_addstr(win, y, 0, ' ' * width, bar_attr)

        # Render each menu item and track positions
        x = 0
        for i, menu in enumerate(self.menus):
            name = f' {menu.name} '
            start_x = x
            end_x = x + len(name)
            self.menu_positions.append((start_x, end_x, i))

            if self.dropdown_open and i == self.selected_menu:
                attr = get_attr(PAIR_MENU_SELECTED, bold=True)
            else:
                attr = bar_attr
            safe_addstr(win, y, x, name, attr)
            x = end_x

    def render_dropdown(self, win: Any, y: int, width: int) -> None:
        """Render the dropdown menu if open.

        Args:
            win: The curses window.
            y: Y position to start dropdown (below menu bar).
            width: Available width.
        """
        # Clear dropdown positions
        self.dropdown_positions.clear()

        if not self.visible or not self.dropdown_open:
            return

        menu = self.menus[self.selected_menu]

        if not menu.items:
            return

        # Calculate dropdown position
        x = 0
        for i in range(self.selected_menu):
            x += len(f' {self.menus[i].name} ')

        # Calculate uniform width for all items, accounting for shortcuts
        max_name = max(len(item.name) for item in menu.items)
        max_shortcut = max(
            (len(item.shortcut) for item in menu.items), default=0
        )
        # Width: space + name + gap + shortcut + space
        # If no shortcuts, keep original: space + name + space
        if max_shortcut:
            item_width = max_name + max_shortcut + 4  # ' name  shortcut '
        else:
            item_width = max_name + 2  # ' name '

        # Render dropdown items and track positions
        for i, item in enumerate(menu.items):
            item_y = y + i
            start_x = x
            end_x = x + item_width
            self.dropdown_positions.append((item_y, start_x, end_x, i))

            if i == self.selected_item:
                attr = get_attr(PAIR_DROPDOWN_SELECTED)
            else:
                attr = get_attr(PAIR_DROPDOWN)

            if item.shortcut:
                # Right-align shortcut: ' name     shortcut '
                gap = item_width - len(item.name) - len(item.shortcut) - 2
                item_text = f' {item.name}{" " * gap}{item.shortcut} '
            else:
                item_text = f' {item.name} '.ljust(item_width)
            safe_addstr(win, item_y, start_x, item_text, attr)

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is within the menu bar.

        Args:
            x: Screen x coordinate (column).
            y: Screen y coordinate (row).

        Returns:
            True if the point is in the menu bar row.
        """
        if not self.visible:
            return False
        return y == self.render_y

    def menu_at_point(self, x: int) -> int | None:
        """Get the menu index at an x coordinate.

        Args:
            x: Screen x coordinate (column).

        Returns:
            Menu index, or None if x is not over any menu.
        """
        for start_x, end_x, menu_idx in self.menu_positions:
            if start_x <= x < end_x:
                return menu_idx
        return None

    def dropdown_item_at_point(self, x: int, y: int) -> int | None:
        """Get the dropdown item index at a point.

        Args:
            x: Screen x coordinate (column).
            y: Screen y coordinate (row).

        Returns:
            Item index, or None if point is not over any dropdown item.
        """
        if not self.dropdown_open:
            return None

        for item_y, start_x, end_x, item_idx in self.dropdown_positions:
            if y == item_y and start_x <= x < end_x:
                return item_idx
        return None
