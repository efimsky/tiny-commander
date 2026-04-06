"""Function key bar component showing F-key actions at bottom of screen."""

from __future__ import annotations

import curses
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from tnc.colors import PAIR_FKEY, PAIR_FKEY_LABEL, get_attr
from tnc.utils import safe_addstr

if TYPE_CHECKING:
    from tnc.app import Action


class ModifierState(Enum):
    """Current modifier key state."""

    NONE = auto()
    SHIFT = auto()
    ALT = auto()


class FunctionBar:
    """Renders function key labels at bottom of screen.

    Labels change dynamically based on modifier key state:
    - Default: F3 View, F4 Edit, F5 Copy, F6 Move, F7 Mkdir, F8 Delete, F10 Quit
    - Shift: F3 Sort, F4 Create, ...
    - Alt: F3 DirSz, ...

    Uses mc-style two-tone rendering:
    - F-key number (e.g., "F3") in white on black
    - Label (e.g., "View") in black on cyan
    """

    # Keys to display in order (tuple since immutable)
    _DISPLAY_KEYS = ('F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10')

    # Default labels for each function key
    _DEFAULT_LABELS = {
        'F3': 'View',
        'F4': 'Edit',
        'F5': 'Copy',
        'F6': 'Move',
        'F7': 'Mkdir',
        'F8': 'Delete',
        'F9': 'Menu',
        'F10': 'Quit',
    }

    # Labels when Shift is held
    _SHIFT_LABELS = {
        'F3': 'Sort',
        'F4': 'Create',
    }

    # Labels when Alt is held
    _ALT_LABELS = {
        'F3': 'DirSz',
    }

    def __init__(self) -> None:
        """Initialize the function bar."""
        self._modifier = ModifierState.NONE
        # Position tracking for mouse click detection
        self.button_positions: list[tuple[int, int, Action]] = []
        self.render_y: int = -1  # Sentinel: no valid y coordinate until rendered
        # Visual feedback for clicks
        self.highlight_button: str | None = None

    def set_modifier(self, modifier: ModifierState) -> None:
        """Set the current modifier key state.

        Args:
            modifier: The modifier state to set.
        """
        self._modifier = modifier

    def get_labels(self) -> dict[str, str]:
        """Get current labels based on modifier state.

        Returns:
            Dictionary mapping F-key names to their labels.
        """
        labels = self._DEFAULT_LABELS.copy()

        if self._modifier == ModifierState.SHIFT:
            labels.update(self._SHIFT_LABELS)
        elif self._modifier == ModifierState.ALT:
            labels.update(self._ALT_LABELS)

        return labels

    def _get_key_number(self, key: str) -> str:
        """Extract the number from a function key name.

        Args:
            key: Function key name like 'F3' or 'F10'.

        Returns:
            The number portion, e.g., '3' or '10'.
        """
        return key[1:]  # Strip the 'F' prefix

    def render(self, win: Any, y: int, width: int) -> None:
        """Render the function key bar with mc-style two-tone colors.

        Keys are evenly distributed across the full width, similar to mc.

        Args:
            win: The curses window to render to.
            y: Y position (row) to render at.
            width: Available width in characters.
        """
        # Import here to avoid circular import
        from tnc.app import Action

        # Store position for mouse hit detection
        self.render_y = y
        self.button_positions.clear()

        labels = self.get_labels()
        fkey_attr = get_attr(PAIR_FKEY)
        label_attr = get_attr(PAIR_FKEY_LABEL)

        # Clear the line first with label background
        safe_addstr(win, y, 0, ' ' * width, label_attr)

        # Button definitions: (key, action)
        buttons = [
            ('F3', Action.VIEW),
            ('F4', Action.EDIT),
            ('F5', Action.COPY),
            ('F6', Action.MOVE),
            ('F7', Action.MKDIR),
            ('F8', Action.DELETE),
            ('F9', Action.MENU),
            ('F10', Action.QUIT),
        ]

        # Calculate cell width for even distribution
        cell_width = width // len(buttons)

        for i, (key, action) in enumerate(buttons):
            label = labels.get(key, '')

            # Position at start of this key's cell
            start_x = i * cell_width

            # Check if we have room for this key
            if start_x >= width:
                break

            # Track button position for mouse clicks
            end_x = start_x + cell_width
            self.button_positions.append((start_x, end_x, action))

            key_text = f' {key}'
            label_text = label

            # Check if this button should be highlighted (visual feedback)
            if self.highlight_button == key:
                # Invert colors for feedback
                safe_addstr(win, y, start_x, key_text, label_attr)
                safe_addstr(win, y, start_x + len(key_text), label_text, fkey_attr)
            else:
                # Normal rendering: F-key number (white on black), label (black on cyan)
                safe_addstr(win, y, start_x, key_text, fkey_attr)
                safe_addstr(win, y, start_x + len(key_text), label_text, label_attr)

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is within the function bar.

        Args:
            x: Screen x coordinate (column).
            y: Screen y coordinate (row).

        Returns:
            True if the point is in the function bar row.
        """
        if self.render_y < 0:
            return False  # Not rendered yet
        return y == self.render_y

    def action_at_point(self, x: int) -> Action | None:
        """Get the action for the button at an x coordinate.

        Args:
            x: Screen x coordinate (column).

        Returns:
            Action for the clicked button, or None if x is not over any button.
        """
        for start_x, end_x, action in self.button_positions:
            if start_x <= x < end_x:
                return action
        return None

    def get_key_at_point(self, x: int) -> str | None:
        """Get the F-key name at an x coordinate.

        Args:
            x: Screen x coordinate (column).

        Returns:
            F-key name (e.g., 'F3') or None if x is not over any button.
        """
        for i, (start_x, end_x, _) in enumerate(self.button_positions):
            if start_x <= x < end_x:
                return self._DISPLAY_KEYS[i]
        return None

    def show_click_feedback(self, key: str) -> None:
        """Set visual feedback for a clicked button.

        Args:
            key: The F-key name to highlight (e.g., 'F3').
        """
        self.highlight_button = key

    def clear_click_feedback(self) -> None:
        """Clear visual feedback (reset highlight)."""
        self.highlight_button = None
