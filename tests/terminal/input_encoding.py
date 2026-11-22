"""Keyboard and mouse wire-protocol encoders for real-PTY testing."""

from __future__ import annotations

import curses
from enum import IntEnum
import os


_STATIC_KEY_FALLBACK: dict[str, bytes] = {
    'up': b'\x1bOA',
    'down': b'\x1bOB',
    'right': b'\x1bOC',
    'left': b'\x1bOD',
    'home': b'\x1bOH',
    'end': b'\x1bOF',
    'pgup': b'\x1b[5~',
    'pgdn': b'\x1b[6~',
    'insert': b'\x1b[2~',
    'delete': b'\x1b[3~',
    'backspace': b'\x7f',
    'shift+tab': b'\x1b[Z',
    'f1': b'\x1bOP',
    'f2': b'\x1bOQ',
    'f3': b'\x1bOR',
    'f4': b'\x1bOS',
    'f5': b'\x1b[15~',
    'f6': b'\x1b[17~',
    'f7': b'\x1b[18~',
    'f8': b'\x1b[19~',
    'f9': b'\x1b[20~',
    'f10': b'\x1b[21~',
    'f11': b'\x1b[23~',
    'f12': b'\x1b[24~',
    'shift+f1': b'\x1b[1;2P',
    'shift+f2': b'\x1b[1;2Q',
    'shift+f3': b'\x1b[1;2R',
    'shift+f4': b'\x1b[1;2S',
    'shift+f5': b'\x1b[15;2~',
    'shift+f6': b'\x1b[17;2~',
    'shift+f7': b'\x1b[18;2~',
    'shift+f8': b'\x1b[19;2~',
    'shift+f9': b'\x1b[20;2~',
    'shift+f10': b'\x1b[21;2~',
    'shift+f11': b'\x1b[23;2~',
    'shift+f12': b'\x1b[24;2~',
    'ctrl+f1': b'\x1b[1;5P',
    'ctrl+f2': b'\x1b[1;5Q',
    'ctrl+f3': b'\x1b[1;5R',
    'ctrl+f4': b'\x1b[1;5S',
    'ctrl+f5': b'\x1b[15;5~',
    'ctrl+f6': b'\x1b[17;5~',
    'ctrl+f7': b'\x1b[18;5~',
    'ctrl+f8': b'\x1b[19;5~',
    'ctrl+f9': b'\x1b[20;5~',
    'ctrl+f10': b'\x1b[21;5~',
    'ctrl+f11': b'\x1b[23;5~',
    'ctrl+f12': b'\x1b[24;5~',
    'alt+f1': b'\x1b[1;3P',
    'alt+f2': b'\x1b[1;3Q',
    'alt+f3': b'\x1b[1;3R',
    'alt+f4': b'\x1b[1;3S',
    'alt+f5': b'\x1b[15;3~',
    'alt+f6': b'\x1b[17;3~',
    'alt+f7': b'\x1b[18;3~',
    'alt+f8': b'\x1b[19;3~',
    'alt+f9': b'\x1b[20;3~',
    'alt+f10': b'\x1b[21;3~',
    'alt+f11': b'\x1b[23;3~',
    'alt+f12': b'\x1b[24;3~',
}

_TERMINFO_KEY_TO_CAP: dict[str, str] = {
    'up': 'kcuu1',
    'down': 'kcud1',
    'left': 'kcub1',
    'right': 'kcuf1',
    'home': 'khome',
    'end': 'kend',
    'pgup': 'kpp',
    'pgdn': 'knp',
    'insert': 'kich1',
    'delete': 'kdch1',
    'shift+tab': 'kcbt',
    **{f'f{n}': f'kf{n}' for n in range(1, 13)},
    **{f'shift+f{n}': f'kf{n + 12}' for n in range(1, 13)},
    **{f'ctrl+f{n}': f'kf{n + 24}' for n in range(1, 13)},
    **{f'alt+f{n}': f'kf{n + 48}' for n in range(1, 13)},
}

_ALIASES: dict[str, str] = {
    'return': 'enter',
    'cr': 'enter',
    'escape': 'esc',
    'page_up': 'pgup',
    'pageup': 'pgup',
    'ppage': 'pgup',
    'page_down': 'pgdn',
    'pagedown': 'pgdn',
    'npage': 'pgdn',
    'ins': 'insert',
    'ic': 'insert',
    'del': 'delete',
    'dc': 'delete',
    'bs': 'backspace',
    'btab': 'shift+tab',
}

_FIXED_KEYS: dict[str, bytes] = {
    'enter': b'\r',
    'lf': b'\n',
    'tab': b'\t',
    'esc': b'\x1b',
    'space': b' ',
}

_TERMINFO_CACHE: dict[str, dict[str, bytes]] = {}


def _load_terminfo_map(term: str) -> dict[str, bytes]:
    if term in _TERMINFO_CACHE:
        return _TERMINFO_CACHE[term]
    loaded = dict(_STATIC_KEY_FALLBACK)
    try:
        fd = os.open(os.devnull, os.O_WRONLY)
        try:
            curses.setupterm(term, fd)
        finally:
            os.close(fd)
        for key_name, cap in _TERMINFO_KEY_TO_CAP.items():
            val = curses.tigetstr(cap)
            if val:
                loaded[key_name] = val
    except (curses.error, OSError):
        pass
    _TERMINFO_CACHE[term] = loaded
    return loaded


class KeyMap:
    """Translates symbolic key names (and Alt/Ctrl/Shift combos) into terminal bytes."""

    def __init__(self, term: str = 'xterm-256color') -> None:
        self.term = term
        self._table = _load_terminfo_map(term)

    def encode(self, key: str) -> bytes:
        """Encode a single symbolic key or character into wire bytes."""
        if not key:
            raise KeyError('Empty key name')
        if len(key) == 1:
            return key.encode('utf-8')

        norm = key.lower().strip()
        norm = _ALIASES.get(norm, norm)
        if norm in _FIXED_KEYS:
            return _FIXED_KEYS[norm]
        if norm in self._table:
            return self._table[norm]

        if '+' in norm:
            mod, rest = norm.split('+', 1)
            rest = _ALIASES.get(rest, rest)
            if mod == 'alt' and f'alt+{rest}' not in self._table:
                return b'\x1b' + self.encode(rest)
            if mod == 'ctrl' and len(rest) == 1 and 'a' <= rest <= 'z':
                return bytes([ord(rest) - ord('a') + 1])

        raise KeyError(f'Unknown key specification: {key!r}')

    def encode_sequence(self, *keys: str) -> bytes:
        """Concatenate encoded byte sequences for multiple keys."""
        return b''.join(self.encode(k) for k in keys)


class MouseButton(IntEnum):
    """Mouse button codes matching X10/SGR terminal wire protocol."""

    LEFT = 0
    MIDDLE = 1
    RIGHT = 2
    RELEASE = 3
    WHEEL_UP = 64
    WHEEL_DOWN = 65


def _wheel_code(direction: str | int) -> int:
    if isinstance(direction, int):
        return direction
    d = direction.lower().strip()
    if d == 'up':
        return int(MouseButton.WHEEL_UP)
    if d == 'down':
        return int(MouseButton.WHEEL_DOWN)
    raise ValueError(f'Invalid wheel direction: {direction!r} (expected "up" or "down")')


class MouseEncoder:
    """Encodes X10 and SGR (1006) mouse events using 0-based (x, y) coordinates."""

    @staticmethod
    def _validate_nonneg(x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise ValueError(f'Coordinates must be >= 0, got ({x}, {y})')

    @classmethod
    def x10_press(cls, button: MouseButton | int, x: int, y: int) -> bytes:
        cls._validate_nonneg(x, y)
        if x > 222 or y > 222:
            raise ValueError(f'X10 mouse coordinates must be <= 222, got ({x}, {y})')
        return bytes([0x1B, ord('['), ord('M'), 32 + int(button), 32 + x + 1, 32 + y + 1])

    @classmethod
    def x10_release(cls, x: int, y: int) -> bytes:
        return cls.x10_press(MouseButton.RELEASE, x, y)

    @classmethod
    def x10_click(cls, button: MouseButton | int, x: int, y: int) -> bytes:
        return cls.x10_press(button, x, y) + cls.x10_release(x, y)

    @classmethod
    def x10_wheel(cls, direction: str | int, x: int, y: int) -> bytes:
        return cls.x10_press(_wheel_code(direction), x, y)

    @classmethod
    def sgr_press(cls, button: MouseButton | int, x: int, y: int) -> bytes:
        cls._validate_nonneg(x, y)
        return f'\x1b[<{int(button)};{x + 1};{y + 1}M'.encode('ascii')

    @classmethod
    def sgr_release(cls, button: MouseButton | int, x: int, y: int) -> bytes:
        cls._validate_nonneg(x, y)
        return f'\x1b[<{int(button)};{x + 1};{y + 1}m'.encode('ascii')

    @classmethod
    def sgr_click(cls, button: MouseButton | int, x: int, y: int) -> bytes:
        return cls.sgr_press(button, x, y) + cls.sgr_release(button, x, y)

    @classmethod
    def sgr_wheel(cls, direction: str | int, x: int, y: int) -> bytes:
        return cls.sgr_press(_wheel_code(direction), x, y)

    @classmethod
    def encode_click(
        cls,
        button: MouseButton | int,
        x: int,
        y: int,
        *,
        sgr: bool = False,
    ) -> bytes:
        return cls.sgr_click(button, x, y) if sgr else cls.x10_click(button, x, y)

    @classmethod
    def encode_wheel(
        cls,
        direction: str | int,
        x: int,
        y: int,
        *,
        sgr: bool = False,
    ) -> bytes:
        return cls.sgr_wheel(direction, x, y) if sgr else cls.x10_wheel(direction, x, y)
