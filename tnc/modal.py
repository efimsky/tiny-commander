"""Modal base class and ButtonBar widget.

Issue #16: every modal in the app needs mouse and arrow-key navigation. Rather
than wiring the same input loop into eight different dialogs, this module
hosts the shared shell. Each modal subclasses :class:`Modal`, overrides
``render`` and ``handle_key``, and (optionally) ``handle_click``. The base
owns the ``while True: getch()`` loop and the ``KEY_MOUSE`` → ``getmouse()``
→ ``handle_click(x, y, button_state)`` routing.

Simple button-style dialogs (Confirm, Overwrite, Error, Summary) compose a
:class:`ButtonBar` widget for their action buttons. The widget tracks where
each button was last rendered so click hit-testing is a list lookup.
"""

from __future__ import annotations

import curses
import inspect
from typing import Any, Callable, NamedTuple

from tnc.utils import safe_addstr


class Button(NamedTuple):
    """One actionable button inside a :class:`ButtonBar`.

    Attributes:
        label: Text shown on the button (e.g. ``'Yes'``).
        shortcut: Single character that activates this button when typed at
            the keyboard, or empty string for "no shortcut". Case-insensitive.
        value: Value returned by the button bar when this button is
            activated.
    """

    label: str
    shortcut: str
    value: Any


class ButtonBar:
    """A horizontal row of focusable buttons.

    Owns its focus state and the post-render hit-region cache. The cache is
    populated each time :meth:`render` runs so click hit-testing always
    matches the most recent paint.
    """

    def __init__(self, buttons: list[Button], focused: int = 0) -> None:
        if not buttons:
            raise ValueError('ButtonBar requires at least one button')
        self.buttons = buttons
        self.focused = focused
        # Each entry is (x_start, x_end, y, value); x range is half-open.
        self.button_positions: list[tuple[int, int, int, Any]] = []

    def render(
        self,
        win: Any,
        y: int,
        x_start: int,
        total_width: int,
        base_attr: int = 0,
    ) -> None:
        """Paint the bar and record hit regions.

        Buttons are evenly spaced across ``total_width`` starting at
        ``x_start``.

        Focus indication uses two redundant cues so it's obvious on every
        terminal regardless of palette or accessibility settings:

        - **Bracket markers** (mc-style): focused buttons render as
          ``[< Yes >]`` while unfocused render as ``[  Yes  ]``. Both
          variants are the same width, so the bar layout doesn't shift
          when focus moves. This works on monochrome terminals and is
          robust to colorblindness.
        - **Inverse video**: the focused button is also drawn with
          ``base_attr | curses.A_REVERSE``; unfocused gets ``base_attr``.
          Pass the surrounding dialog's color pair as ``base_attr`` so
          unfocused buttons blend with the dialog background and the
          focused one stands out via reverse video on the same palette.
        """
        self.button_positions.clear()
        if not self.buttons:
            return

        # Both variants are the same width: 6 surrounding chars plus the label,
        # so focus changes don't shift the bar layout.
        rendered_texts = [
            f'[< {btn.label} >]' if i == self.focused else f'[  {btn.label}  ]'
            for i, btn in enumerate(self.buttons)
        ]
        # Cumulative remaining width lets us shift left only when needed to fit
        # all buttons without overlapping, preserving centered layout otherwise.
        suffix_widths = [0] * len(rendered_texts)
        running = 0
        for i in range(len(rendered_texts) - 1, -1, -1):
            running += len(rendered_texts[i])
            suffix_widths[i] = running

        slot_width = max(total_width // len(self.buttons), 1)
        prev_end = x_start
        bar_end = x_start + max(total_width, 0)
        for i, (btn, text) in enumerate(zip(self.buttons, rendered_texts)):
            slot_x = x_start + i * slot_width
            offset = max(0, (slot_width - len(text)) // 2)
            max_start = bar_end - suffix_widths[i]
            text_x = max(prev_end, min(slot_x + offset, max_start))
            avail = bar_end - text_x
            if avail <= 0:
                continue
            visible = text[:avail]
            attr = base_attr | curses.A_REVERSE if i == self.focused else base_attr
            safe_addstr(win, y, text_x, visible, attr)

            # Record click region as the visible bracket span.
            end_x = text_x + len(visible)
            self.button_positions.append((text_x, end_x, y, btn.value))
            prev_end = end_x

    def hit_test(self, x: int, y: int) -> Any | None:
        """Return the value of the button at (x, y), or None if outside.

        ``None`` is reserved for "no hit"; callers must avoid using ``None``
        as a meaningful button value.
        """
        for x_start, x_end, btn_y, value in self.button_positions:
            if y == btn_y and x_start <= x < x_end:
                return value
        return None

    def move_focus(self, direction: int) -> None:
        """Shift focus by ``direction`` (positive = next, negative = prev), wrapping."""
        n = len(self.buttons)
        if n == 0:
            return
        self.focused = (self.focused + direction) % n

    def activate(self) -> Any:
        """Return the currently focused button's value."""
        return self.buttons[self.focused].value

    def activate_by_shortcut(self, ch: str) -> Any | None:
        """Return the value of the button whose shortcut matches ``ch``.

        Match is case-insensitive. Empty shortcuts never match. Returns
        ``None`` if no button matches.
        """
        if not ch:
            return None
        ch_low = ch.lower()
        for btn in self.buttons:
            if btn.shortcut and btn.shortcut.lower() == ch_low:
                return btn.value
        return None


# Sentinel: when ``Modal._result`` holds this object, the modal has not yet
# resolved a return value. Allows ``None`` and ``False`` to be valid results.
_UNSET: Any = object()


class Modal:
    """Base class for modal dialogs.

    Subclasses override:

    * ``render(win)`` — paint the modal each iteration of the loop.
    * ``handle_key(key)`` — react to an integer key code from ``getch``.
    * ``handle_click(x, y, button_state)`` — react to mouse clicks; default
      implementation ignores them.

    To finish the modal, the subclass calls :meth:`set_result` with the value
    that should be returned from :meth:`show`.
    """

    button_translator: Callable[[int], int] | None = None

    def __init__(self) -> None:
        self._done = False
        self._result: Any = _UNSET

    def set_result(self, value: Any) -> None:
        """Mark the modal as done and queue ``value`` for return."""
        self._result = value
        self._done = True

    def show(self, win: Any) -> Any:
        """Run the input loop until a subclass sets a result."""
        while not self._done:
            self.render(win)
            key = win.getch()
            if key == -1:
                continue
            if key == curses.KEY_RESIZE:
                try:
                    win.erase()
                except curses.error:
                    pass
                continue
            if key == curses.KEY_MOUSE:
                try:
                    _, x, y, _, button_state = curses.getmouse()
                except curses.error:
                    # Lost-mouse-event — drop and continue rather than crash.
                    continue
                translator = inspect.getattr_static(self, 'button_translator', None)
                if isinstance(translator, staticmethod):
                    translator = translator.__func__
                elif isinstance(translator, property):
                    translator = self.button_translator
                if translator is not None:
                    button_state = translator(button_state)
                self.handle_click(x, y, button_state)
            else:
                self.handle_key(key)
        return self._result

    def render(self, win: Any) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def handle_key(self, key: int) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def handle_click(self, x: int, y: int, button_state: int) -> None:
        """Default: ignore. Subclasses with clickable elements override."""
        return None
