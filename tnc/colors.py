"""Color pair definitions and initialization for Tiny Commander.

This module provides a centralized color management system with graceful
fallback for terminals without color support. Supports classic mc-style
blue backgrounds (default) or modern transparent backgrounds.
"""

import curses

# Color pair constants - these are pair IDs, not actual colors
# Note: Pair 0 is reserved by curses for the terminal's default colors
# and cannot be modified with init_pair(). We use it as-is for normal text.
PAIR_NORMAL = 0

# File type colors (1-6)
PAIR_DIRECTORY = 1      # Directories
PAIR_SELECTED = 2       # Selected/marked files
PAIR_EXECUTABLE = 3     # Executable files
PAIR_SYMLINK = 4        # Symbolic links
PAIR_BROKEN_LINK = 5    # Broken symbolic links
PAIR_HIDDEN = 6         # Hidden files (dotfiles)

# Cursor colors (7-8)
PAIR_CURSOR = 7         # Cursor highlight
PAIR_CURSOR_SELECTED = 8  # Cursor on selected file

# Menu colors (9-12)
PAIR_MENU_BAR = 9       # Menu bar background
PAIR_MENU_SELECTED = 10  # Selected menu item
PAIR_DROPDOWN = 11      # Dropdown menu
PAIR_DROPDOWN_SELECTED = 12  # Selected dropdown item

# UI element colors (13-18)
PAIR_FKEY = 13          # Function key number (e.g., "F3")
PAIR_FKEY_LABEL = 14    # Function key label (e.g., "View")
PAIR_STATUS = 15        # Status bar
PAIR_CMDLINE = 16       # Command line
PAIR_DIALOG = 17        # Dialog box background
PAIR_DIALOG_TITLE = 18  # Dialog title

# Panel background (19) - used for borders and empty space
PAIR_PANEL = 19

# Backwards compatibility alias for PR #82
PAIR_FKEY_NUMBER = PAIR_FKEY


class ColorManager:
    """Manages color state for the application.

    Encapsulates color initialization and theme settings, enabling
    test isolation by creating separate instances with independent state.
    """

    def __init__(self, classic_theme: bool = True) -> None:
        """Initialize color manager.

        Args:
            classic_theme: True for classic mc-style blue backgrounds (default),
                          False for modern transparent backgrounds.
        """
        self._colors_enabled = False
        self._classic_theme = classic_theme

    @property
    def colors_enabled(self) -> bool:
        """Check if colors are currently enabled."""
        return self._colors_enabled

    @property
    def classic_theme(self) -> bool:
        """Check if classic theme is enabled."""
        return self._classic_theme

    def init_colors(self) -> bool:
        """Initialize color pairs for the application.

        Returns:
            True if colors were successfully initialized, False otherwise.
        """
        if not curses.has_colors():
            self._colors_enabled = False
            return False

        curses.start_color()
        curses.use_default_colors()

        self._apply_theme_colors()

        self._colors_enabled = True
        return True

    def set_classic_theme(self, enabled: bool) -> None:
        """Set the color theme.

        Args:
            enabled: True for classic mc-style blue backgrounds,
                     False for modern transparent backgrounds.
        """
        self._classic_theme = enabled
        if self._colors_enabled:
            self._apply_theme_colors()

    def _apply_theme_colors(self) -> None:
        """Apply color pairs based on current theme setting."""
        if self._classic_theme:
            self._apply_classic_theme()
        else:
            self._apply_modern_theme()

    def _apply_classic_theme(self) -> None:
        """Apply classic mc-style colors with blue panel backgrounds."""
        curses.init_pair(PAIR_PANEL, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(PAIR_DIRECTORY, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(PAIR_SELECTED, curses.COLOR_YELLOW, curses.COLOR_BLUE)
        curses.init_pair(PAIR_EXECUTABLE, curses.COLOR_GREEN, curses.COLOR_BLUE)
        curses.init_pair(PAIR_SYMLINK, curses.COLOR_MAGENTA, curses.COLOR_BLUE)
        curses.init_pair(PAIR_BROKEN_LINK, curses.COLOR_RED, curses.COLOR_BLUE)
        curses.init_pair(PAIR_HIDDEN, curses.COLOR_CYAN, curses.COLOR_BLUE)
        curses.init_pair(PAIR_CURSOR, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(PAIR_CURSOR_SELECTED, curses.COLOR_YELLOW, curses.COLOR_CYAN)
        curses.init_pair(PAIR_MENU_BAR, curses.COLOR_WHITE, curses.COLOR_CYAN)
        curses.init_pair(PAIR_MENU_SELECTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(PAIR_DROPDOWN, curses.COLOR_WHITE, curses.COLOR_CYAN)
        curses.init_pair(PAIR_DROPDOWN_SELECTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(PAIR_FKEY, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(PAIR_FKEY_LABEL, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(PAIR_STATUS, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(PAIR_CMDLINE, -1, -1)
        curses.init_pair(PAIR_DIALOG, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(PAIR_DIALOG_TITLE, curses.COLOR_WHITE, curses.COLOR_BLUE)

    def _apply_modern_theme(self) -> None:
        """Apply modern colors with transparent/default background."""
        curses.init_pair(PAIR_PANEL, -1, -1)
        curses.init_pair(PAIR_DIRECTORY, curses.COLOR_BLUE, -1)
        curses.init_pair(PAIR_SELECTED, curses.COLOR_YELLOW, -1)
        curses.init_pair(PAIR_EXECUTABLE, curses.COLOR_GREEN, -1)
        curses.init_pair(PAIR_SYMLINK, curses.COLOR_MAGENTA, -1)
        curses.init_pair(PAIR_BROKEN_LINK, curses.COLOR_RED, -1)
        curses.init_pair(PAIR_HIDDEN, curses.COLOR_CYAN, -1)
        curses.init_pair(PAIR_CURSOR, curses.COLOR_WHITE, curses.COLOR_CYAN)
        curses.init_pair(PAIR_CURSOR_SELECTED, curses.COLOR_YELLOW, curses.COLOR_CYAN)
        curses.init_pair(PAIR_MENU_BAR, curses.COLOR_WHITE, curses.COLOR_CYAN)
        curses.init_pair(PAIR_MENU_SELECTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(PAIR_DROPDOWN, curses.COLOR_WHITE, curses.COLOR_CYAN)
        curses.init_pair(PAIR_DROPDOWN_SELECTED, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(PAIR_FKEY, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(PAIR_FKEY_LABEL, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(PAIR_STATUS, -1, -1)
        curses.init_pair(PAIR_CMDLINE, -1, -1)
        curses.init_pair(PAIR_DIALOG, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(PAIR_DIALOG_TITLE, curses.COLOR_WHITE, curses.COLOR_BLUE)

    def get_attr(self, pair: int, bold: bool = False, reverse: bool = False) -> int:
        """Get curses attribute for a color pair with optional modifiers.

        Args:
            pair: Color pair constant (PAIR_*).
            bold: Whether to add bold attribute.
            reverse: Whether to add reverse video attribute.

        Returns:
            Combined curses attribute value.
        """
        if self._colors_enabled:
            attr = curses.color_pair(pair)
        else:
            attr = curses.A_NORMAL
            if pair in (PAIR_CURSOR, PAIR_CURSOR_SELECTED, PAIR_MENU_BAR,
                        PAIR_MENU_SELECTED, PAIR_DROPDOWN_SELECTED,
                        PAIR_FKEY, PAIR_FKEY_LABEL, PAIR_STATUS,
                        PAIR_DIALOG, PAIR_DIALOG_TITLE):
                attr |= curses.A_REVERSE

        if bold:
            attr |= curses.A_BOLD

        if reverse:
            attr |= curses.A_REVERSE

        return attr


# Default instance for backwards compatibility
_default_manager = ColorManager()


def init_colors() -> bool:
    """Initialize color pairs for the application.

    Delegates to default ColorManager instance.

    Returns:
        True if colors were successfully initialized, False otherwise.
    """
    return _default_manager.init_colors()


def set_classic_theme(enabled: bool) -> None:
    """Set the color theme.

    Delegates to default ColorManager instance.

    Args:
        enabled: True for classic mc-style blue backgrounds,
                 False for modern transparent backgrounds.
    """
    _default_manager.set_classic_theme(enabled)


def is_classic_theme() -> bool:
    """Check if classic theme is enabled.

    Delegates to default ColorManager instance.

    Returns:
        True if using classic mc-style colors, False for modern theme.
    """
    return _default_manager.classic_theme


def colors_enabled() -> bool:
    """Check if colors are currently enabled.

    Delegates to default ColorManager instance.

    Returns:
        True if colors are enabled, False otherwise.
    """
    return _default_manager.colors_enabled


def get_attr(pair: int, bold: bool = False, reverse: bool = False) -> int:
    """Get curses attribute for a color pair with optional modifiers.

    Delegates to default ColorManager instance.

    Args:
        pair: Color pair constant (PAIR_*).
        bold: Whether to add bold attribute.
        reverse: Whether to add reverse video attribute.

    Returns:
        Combined curses attribute value.
    """
    return _default_manager.get_attr(pair, bold, reverse)
