"""Pure-stdlib VT100/ANSI screen emulator for real-PTY terminal tests."""

from __future__ import annotations

import codecs
from dataclasses import dataclass, replace
import unicodedata


_DEC_SPECIAL_GRAPHICS: dict[str, str] = {
    '`': '◆',
    'a': '▒',
    'f': '°',
    'g': '±',
    'j': '┘',
    'k': '┐',
    'l': '┌',
    'm': '└',
    'n': '┼',
    'o': '⎺',
    'p': '⎻',
    'q': '─',
    'r': '⎼',
    's': '⎽',
    't': '├',
    'u': '┤',
    'v': '┴',
    'w': '┬',
    'x': '│',
    'y': '≤',
    'z': '≥',
    '{': 'π',
    '|': '≠',
    '}': '£',
    '~': '·',
}


@dataclass(frozen=True, slots=True)
class Style:
    """Visual attributes for a single terminal cell."""

    fg: int | tuple[int, int, int] | None = None
    bg: int | tuple[int, int, int] | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False


DEFAULT_STYLE = Style()


@dataclass(frozen=True, slots=True)
class Cell:
    """A single character cell in a VirtualTerminal grid."""

    char: str = ' '
    style: Style = DEFAULT_STYLE
    is_continuation: bool = False


class _ScreenState:
    """Mutable grid and cursor state for one screen buffer (main or alternate)."""

    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self.grid: list[list[Cell]] = self._blank_grid(rows, cols, DEFAULT_STYLE)
        self.cursor_row = 0
        self.cursor_col = 0
        self.pending_wrap = False
        self.saved_cursor: tuple[int, int, Style, bool] | None = None
        self.scroll_top = 0
        self.scroll_bottom = max(0, rows - 1)

    @staticmethod
    def _blank_grid(rows: int, cols: int, style: Style) -> list[list[Cell]]:
        blank = Cell(char=' ', style=style)
        return [[blank for _ in range(cols)] for _ in range(rows)]

    def resize(self, rows: int, cols: int) -> None:
        new_grid = self._blank_grid(rows, cols, DEFAULT_STYLE)
        copy_rows = min(self.rows, rows)
        copy_cols = min(self.cols, cols)
        for r in range(copy_rows):
            row_cells = new_grid[r]
            src_cells = self.grid[r]
            for c in range(copy_cols):
                row_cells[c] = src_cells[c]
            # Avoid dangling half of a wide char at the right boundary
            if copy_cols > 0 and row_cells[copy_cols - 1].is_continuation:
                if copy_cols >= 2:
                    row_cells[copy_cols - 2] = Cell(' ', row_cells[copy_cols - 2].style)
                row_cells[copy_cols - 1] = Cell(' ', row_cells[copy_cols - 1].style)
            elif copy_cols > 0 and _char_width(row_cells[copy_cols - 1].char) == 2:
                # Truncated wide char whose continuation fell outside new_cols
                if cols == copy_cols:
                    row_cells[copy_cols - 1] = Cell(' ', row_cells[copy_cols - 1].style)
        self.grid = new_grid
        self.rows = rows
        self.cols = cols
        self.scroll_top = 0
        self.scroll_bottom = max(0, rows - 1)
        self.cursor_row = min(max(0, self.cursor_row), max(0, rows - 1))
        self.cursor_col = min(max(0, self.cursor_col), max(0, cols - 1))
        self.pending_wrap = False


def _char_width(ch: str) -> int:
    """Return display width (0, 1, or 2 columns) for a Unicode character."""
    if not ch:
        return 0
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1


class VirtualTerminal:
    """In-memory VT100/ANSI screen buffer tracking text, styles, cursor, and modes."""

    _GROUND = 0
    _ESC = 1
    _ESC_INTERMEDIATE = 2
    _CSI = 3
    _OSC = 4
    _OSC_ESC = 5
    _DCS = 6
    _DCS_ESC = 7

    def __init__(self, rows: int = 24, cols: int = 80) -> None:
        if rows < 1 or cols < 1:
            raise ValueError(f'Terminal dimensions must be >= 1, got {rows}x{cols}')
        self._main = _ScreenState(rows, cols)
        self._alt = _ScreenState(rows, cols)
        self._active = self._main
        self.in_alt_screen = False
        self.cursor_visible = True
        self.mouse_tracking = False
        self.sgr_mouse = False
        self.app_cursor_keys = False
        self.auto_wrap = True
        self.current_style = DEFAULT_STYLE
        self._g0_charset = 'B'
        self._g1_charset = 'B'
        self._gl_is_g1 = False
        self._last_printed = ''

        self._decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self._state = self._GROUND
        self._esc_buf: list[str] = []
        self._csi_buf: list[str] = []

    @property
    def rows(self) -> int:
        return self._active.rows

    @property
    def cols(self) -> int:
        return self._active.cols

    @property
    def cursor_row(self) -> int:
        return self._active.cursor_row

    @property
    def cursor_col(self) -> int:
        return self._active.cursor_col

    def cell(self, row: int, col: int) -> Cell:
        """Return the Cell at (row, col)."""
        return self._active.grid[row][col]

    def resize(self, rows: int, cols: int) -> None:
        """Resize both main and alternate screen buffers."""
        if rows < 1 or cols < 1:
            raise ValueError(f'Terminal dimensions must be >= 1, got {rows}x{cols}')
        self._main.resize(rows, cols)
        self._alt.resize(rows, cols)

    def feed(self, data: bytes | str) -> None:
        """Feed raw terminal output bytes (or text) incrementally."""
        if isinstance(data, bytes):
            text = self._decoder.decode(data, final=False)
        else:
            text = data
        for ch in text:
            self._process_char(ch)

    def row_text(self, row: int, *, strip_trailing: bool = True) -> str:
        """Return rendered text for a single row."""
        chars = [c.char for c in self._active.grid[row] if not c.is_continuation]
        line = ''.join(chars)
        return line.rstrip(' ') if strip_trailing else line

    def lines(self, *, strip_trailing: bool = True) -> list[str]:
        """Return all rows as a list of strings."""
        return [self.row_text(r, strip_trailing=strip_trailing) for r in range(self.rows)]

    def text(self, *, strip_trailing: bool = True) -> str:
        """Return full screen content joined with newlines."""
        return '\n'.join(self.lines(strip_trailing=strip_trailing))

    def region(self, row: int, col: int, height: int, width: int) -> list[str]:
        """Extract a rectangular slice of screen text."""
        out: list[str] = []
        end_r = min(self.rows, row + height)
        end_c = min(self.cols, col + width)
        for r in range(max(0, row), end_r):
            chars = [
                c.char
                for c in self._active.grid[r][max(0, col):end_c]
                if not c.is_continuation
            ]
            out.append(''.join(chars))
        return out

    def find_all(self, needle: str, *, row: int | None = None) -> list[tuple[int, int]]:
        """Find all occurrences of ``needle`` as ``(col, row)`` pairs."""
        if not needle:
            return []
        row_range = [row] if row is not None else range(self.rows)
        matches: list[tuple[int, int]] = []
        for r in row_range:
            if r < 0 or r >= self.rows:
                continue
            chars: list[str] = []
            col_map: list[int] = []
            for c_idx, cell in enumerate(self._active.grid[r]):
                if not cell.is_continuation:
                    chars.append(cell.char)
                    col_map.append(c_idx)
            line = ''.join(chars)
            start = 0
            while True:
                idx = line.find(needle, start)
                if idx == -1:
                    break
                matches.append((col_map[idx], r))
                start = idx + 1
        return matches

    def find_text(
        self,
        needle: str,
        *,
        row: int | None = None,
        occurrence: int = 0,
    ) -> tuple[int, int] | None:
        """Find the Nth occurrence of ``needle`` as ``(col, row)`` or None."""
        matches = self.find_all(needle, row=row)
        if 0 <= occurrence < len(matches):
            return matches[occurrence]
        return None

    def contains(self, needle: str) -> bool:
        """Return True if ``needle`` appears anywhere on screen."""
        return self.find_text(needle) is not None

    def screenshot(self, *, with_ruler: bool = True) -> str:
        """Format a readable ASCII screenshot with cursor and mode metadata."""
        header = (
            f'VirtualTerminal({self.rows}x{self.cols} '
            f'cursor=({self.cursor_col},{self.cursor_row}) '
            f'alt={self.in_alt_screen} mouse={self.mouse_tracking} '
            f'sgr={self.sgr_mouse} vis={self.cursor_visible})'
        )
        out = [header]
        if with_ruler:
            tens = ''.join(str((c // 10) % 10) if c % 10 == 0 else ' ' for c in range(self.cols))
            ones = ''.join(str(c % 10) for c in range(self.cols))
            out.append(f'     {tens}')
            out.append(f'     {ones}')
        border = '+' + '-' * self.cols + '+'
        out.append(('    ' if with_ruler else '') + border)
        for r in range(self.rows):
            row_str = self.row_text(r, strip_trailing=False)
            # Pad with spaces if wide chars shortened string length below cols
            if len(row_str) < self.cols:
                row_str = row_str.ljust(self.cols)
            if with_ruler:
                out.append(f'{r:3d}:|{row_str}|')
            else:
                out.append(f'|{row_str}|')
        out.append(('    ' if with_ruler else '') + border)
        return '\n'.join(out)

    # ------------------------------------------------------------------
    # State machine internals
    # ------------------------------------------------------------------

    def _process_char(self, ch: str) -> None:
        if self._state == self._GROUND:
            self._handle_ground(ch)
        elif self._state == self._ESC:
            self._handle_esc(ch)
        elif self._state == self._ESC_INTERMEDIATE:
            self._handle_esc_intermediate(ch)
        elif self._state == self._CSI:
            self._handle_csi(ch)
        elif self._state == self._OSC:
            if ch == '\x07':
                self._state = self._GROUND
            elif ch == '\x1b':
                self._state = self._OSC_ESC
        elif self._state == self._OSC_ESC:
            self._state = self._GROUND if ch == '\\' else self._OSC
        elif self._state == self._DCS:
            if ch == '\x1b':
                self._state = self._DCS_ESC
        elif self._state == self._DCS_ESC:
            self._state = self._GROUND if ch == '\\' else self._DCS

    def _handle_ground(self, ch: str) -> None:
        code = ord(ch)
        if code == 0x1B:  # ESC
            self._state = self._ESC
            self._esc_buf.clear()
        elif ch == '\r':
            self._active.cursor_col = 0
            self._active.pending_wrap = False
        elif ch in ('\n', '\x0b', '\x0c'):
            self._active.pending_wrap = False
            self._linefeed()
        elif ch == '\b':
            self._active.pending_wrap = False
            if self._active.cursor_col > 0:
                self._active.cursor_col -= 1
        elif ch == '\t':
            self._active.pending_wrap = False
            next_stop = min(self.cols - 1, ((self.cursor_col // 8) + 1) * 8)
            self._active.cursor_col = next_stop
        elif ch == '\x0e':  # SO - invoke G1
            self._gl_is_g1 = True
        elif ch == '\x0f':  # SI - invoke G0
            self._gl_is_g1 = False
        elif code < 0x20 or code == 0x7F:
            # Ignore NUL, BEL, etc.
            return
        else:
            charset = self._g1_charset if self._gl_is_g1 else self._g0_charset
            if charset == '0' and ch in _DEC_SPECIAL_GRAPHICS:
                ch = _DEC_SPECIAL_GRAPHICS[ch]
            self._put_char(ch)

    def _handle_esc(self, ch: str) -> None:
        if ch == '[':
            self._csi_buf.clear()
            self._state = self._CSI
        elif ch == ']':
            self._state = self._OSC
        elif ch == 'P':
            self._state = self._DCS
        elif ch in ('(', ')', '*', '+', '#', '%', ' '):
            self._esc_buf = [ch]
            self._state = self._ESC_INTERMEDIATE
        elif ch == 'M':  # Reverse Index
            self._active.pending_wrap = False
            self._reverse_index()
            self._state = self._GROUND
        elif ch == 'D':  # Index
            self._active.pending_wrap = False
            self._linefeed()
            self._state = self._GROUND
        elif ch == 'E':  # Next line
            self._active.cursor_col = 0
            self._active.pending_wrap = False
            self._linefeed()
            self._state = self._GROUND
        elif ch == '7':  # DECSC
            self._active.saved_cursor = (
                self._active.cursor_row,
                self._active.cursor_col,
                self.current_style,
                self.auto_wrap,
            )
            self._state = self._GROUND
        elif ch == '8':  # DECRC
            if self._active.saved_cursor is not None:
                r, c, st, aw = self._active.saved_cursor
                self._active.cursor_row = min(r, self.rows - 1)
                self._active.cursor_col = min(c, self.cols - 1)
                self.current_style = st
                self.auto_wrap = aw
                self._active.pending_wrap = False
            self._state = self._GROUND
        elif ch == 'c':  # RIS full reset
            self.__init__(self.rows, self.cols)
        else:
            # Includes ESC = and ESC > (keypad modes)
            self._state = self._GROUND

    def _handle_esc_intermediate(self, ch: str) -> None:
        prefix = self._esc_buf[0] if self._esc_buf else ''
        if prefix == '(':
            self._g0_charset = ch
        elif prefix == ')':
            self._g1_charset = ch
        self._state = self._GROUND

    def _handle_csi(self, ch: str) -> None:
        code = ord(ch)
        if 0x40 <= code <= 0x7E:
            seq = ''.join(self._csi_buf)
            self._state = self._GROUND
            self._dispatch_csi(seq, ch)
        elif ch == '\x1b':
            self._esc_buf.clear()
            self._state = self._ESC
        else:
            self._csi_buf.append(ch)

    # ------------------------------------------------------------------
    # Grid & CSI operations
    # ------------------------------------------------------------------

    def _clear_wide_overlap(self, row: int, col: int) -> None:
        """Clear any wide char cell overlapping (row, col) to preserve grid consistency."""
        grid_row = self._active.grid[row]
        cell = grid_row[col]
        if cell.is_continuation and col > 0:
            grid_row[col - 1] = Cell(' ', grid_row[col - 1].style)
            grid_row[col] = Cell(' ', cell.style)
        elif _char_width(cell.char) == 2 and col + 1 < self.cols:
            grid_row[col] = Cell(' ', cell.style)
            grid_row[col + 1] = Cell(' ', grid_row[col + 1].style)

    def _put_char(self, ch: str) -> None:
        w = _char_width(ch)
        if w == 0:
            return
        if w == 2 and self.cols < 2:
            return

        scr = self._active
        if scr.pending_wrap:
            if self.auto_wrap:
                self._linefeed()
                scr.cursor_col = 0
            scr.pending_wrap = False

        if w == 2 and scr.cursor_col == self.cols - 1:
            if self.auto_wrap:
                self._clear_wide_overlap(scr.cursor_row, scr.cursor_col)
                scr.grid[scr.cursor_row][scr.cursor_col] = Cell(' ', self.current_style)
                self._linefeed()
                scr.cursor_col = 0
            else:
                scr.cursor_col = max(0, self.cols - 2)

        r, c = scr.cursor_row, scr.cursor_col
        self._clear_wide_overlap(r, c)
        scr.grid[r][c] = Cell(char=ch, style=self.current_style)
        if w == 2 and c + 1 < self.cols:
            self._clear_wide_overlap(r, c + 1)
            scr.grid[r][c + 1] = Cell(char='', style=self.current_style, is_continuation=True)

        self._last_printed = ch
        if c + w >= self.cols:
            scr.cursor_col = self.cols - w if w == 2 and not self.auto_wrap else self.cols - 1
            scr.pending_wrap = self.auto_wrap
        else:
            scr.cursor_col = c + w

    def _blank_row(self) -> list[Cell]:
        blank = Cell(' ', self.current_style)
        return [blank for _ in range(self.cols)]

    def _scroll_up(self, top: int, bottom: int, count: int = 1) -> None:
        grid = self._active.grid
        region_len = bottom - top + 1
        n = min(count, region_len)
        if n <= 0:
            return
        del grid[top:top + n]
        for _ in range(n):
            grid.insert(bottom, self._blank_row())

    def _scroll_down(self, top: int, bottom: int, count: int = 1) -> None:
        grid = self._active.grid
        region_len = bottom - top + 1
        n = min(count, region_len)
        if n <= 0:
            return
        del grid[bottom - n + 1:bottom + 1]
        for _ in range(n):
            grid.insert(top, self._blank_row())

    def _linefeed(self) -> None:
        scr = self._active
        if scr.cursor_row == scr.scroll_bottom:
            self._scroll_up(scr.scroll_top, scr.scroll_bottom, 1)
        elif scr.cursor_row < self.rows - 1:
            scr.cursor_row += 1

    def _reverse_index(self) -> None:
        scr = self._active
        if scr.cursor_row == scr.scroll_top:
            self._scroll_down(scr.scroll_top, scr.scroll_bottom, 1)
        elif scr.cursor_row > 0:
            scr.cursor_row -= 1

    @staticmethod
    def _parse_params(raw: str, default: int = 0) -> list[int]:
        if not raw:
            return [default]
        out: list[int] = []
        for part in raw.split(';'):
            out.append(int(part) if part.isdigit() else default)
        return out

    def _dispatch_csi(self, raw: str, final: str) -> None:
        if raw.startswith('?'):
            self._handle_dec_private(raw[1:], final)
            return
        if raw.startswith('>'):
            return

        scr = self._active
        p = self._parse_params(raw, default=0)
        p1 = max(1, p[0]) if p[0] == 0 and final in (
            'A', 'B', 'C', 'D', 'E', 'F', 'G', 'd', 'L', 'M', 'P', '@', 'S', 'T', 'X', 'b',
        ) else p[0]

        if final in ('H', 'f'):
            parts = self._parse_params(raw, default=1)
            row = (parts[0] if parts[0] > 0 else 1) - 1
            col = (parts[1] if len(parts) > 1 and parts[1] > 0 else 1) - 1
            scr.cursor_row = min(max(0, row), self.rows - 1)
            scr.cursor_col = min(max(0, col), self.cols - 1)
            scr.pending_wrap = False
        elif final == 'A':
            scr.cursor_row = max(scr.scroll_top if scr.cursor_row >= scr.scroll_top else 0, scr.cursor_row - p1)
            scr.pending_wrap = False
        elif final == 'B':
            limit = scr.scroll_bottom if scr.cursor_row <= scr.scroll_bottom else self.rows - 1
            scr.cursor_row = min(limit, scr.cursor_row + p1)
            scr.pending_wrap = False
        elif final == 'C':
            scr.cursor_col = min(self.cols - 1, scr.cursor_col + p1)
            scr.pending_wrap = False
        elif final == 'D':
            scr.cursor_col = max(0, scr.cursor_col - p1)
            scr.pending_wrap = False
        elif final == 'E':
            scr.cursor_row = min(self.rows - 1, scr.cursor_row + p1)
            scr.cursor_col = 0
            scr.pending_wrap = False
        elif final == 'F':
            scr.cursor_row = max(0, scr.cursor_row - p1)
            scr.cursor_col = 0
            scr.pending_wrap = False
        elif final == 'G':
            scr.cursor_col = min(max(0, p1 - 1), self.cols - 1)
            scr.pending_wrap = False
        elif final == 'd':
            scr.cursor_row = min(max(0, p1 - 1), self.rows - 1)
            scr.pending_wrap = False
        elif final == 'J':
            self._erase_display(p[0])
        elif final == 'K':
            self._erase_line(p[0])
        elif final == 'X':
            blank = Cell(' ', self.current_style)
            end = min(self.cols, scr.cursor_col + p1)
            for c in range(scr.cursor_col, end):
                self._clear_wide_overlap(scr.cursor_row, c)
                scr.grid[scr.cursor_row][c] = blank
        elif final == 'L':
            if scr.scroll_top <= scr.cursor_row <= scr.scroll_bottom:
                self._scroll_down(scr.cursor_row, scr.scroll_bottom, p1)
                scr.cursor_col = 0
                scr.pending_wrap = False
        elif final == 'M':
            if scr.scroll_top <= scr.cursor_row <= scr.scroll_bottom:
                self._scroll_up(scr.cursor_row, scr.scroll_bottom, p1)
                scr.cursor_col = 0
                scr.pending_wrap = False
        elif final == '@':
            self._insert_chars(p1)
        elif final == 'P':
            self._delete_chars(p1)
        elif final == 'S':
            self._scroll_up(scr.scroll_top, scr.scroll_bottom, p1)
        elif final == 'T':
            self._scroll_down(scr.scroll_top, scr.scroll_bottom, p1)
        elif final == 'b':
            if self._last_printed:
                for _ in range(p1):
                    self._put_char(self._last_printed)
        elif final == 'r':
            parts = self._parse_params(raw, default=0)
            top = (parts[0] - 1) if parts[0] > 0 else 0
            bot = (parts[1] - 1) if len(parts) > 1 and parts[1] > 0 else self.rows - 1
            if 0 <= top < bot < self.rows:
                scr.scroll_top = top
                scr.scroll_bottom = bot
            else:
                scr.scroll_top = 0
                scr.scroll_bottom = self.rows - 1
            scr.cursor_row = 0
            scr.cursor_col = 0
            scr.pending_wrap = False
        elif final == 'm':
            self._apply_sgr(self._parse_params(raw, default=0))
        elif final == 's':
            scr.saved_cursor = (scr.cursor_row, scr.cursor_col, self.current_style, self.auto_wrap)
        elif final == 'u':
            if scr.saved_cursor is not None:
                r, c, st, aw = scr.saved_cursor
                scr.cursor_row = min(r, self.rows - 1)
                scr.cursor_col = min(c, self.cols - 1)
                self.current_style = st
                self.auto_wrap = aw
                scr.pending_wrap = False

    def _erase_display(self, mode: int) -> None:
        scr = self._active
        blank = Cell(' ', self.current_style)
        if mode == 0:
            self._erase_line(0)
            for r in range(scr.cursor_row + 1, self.rows):
                scr.grid[r] = [blank for _ in range(self.cols)]
        elif mode == 1:
            for r in range(0, scr.cursor_row):
                scr.grid[r] = [blank for _ in range(self.cols)]
            self._erase_line(1)
        elif mode in (2, 3):
            for r in range(self.rows):
                scr.grid[r] = [blank for _ in range(self.cols)]

    def _erase_line(self, mode: int) -> None:
        scr = self._active
        r = scr.cursor_row
        blank = Cell(' ', self.current_style)
        if mode == 0:
            start, end = scr.cursor_col, self.cols
        elif mode == 1:
            start, end = 0, scr.cursor_col + 1
        elif mode == 2:
            start, end = 0, self.cols
        else:
            return
        for c in range(start, end):
            self._clear_wide_overlap(r, c)
            scr.grid[r][c] = blank

    def _insert_chars(self, count: int) -> None:
        scr = self._active
        r, c = scr.cursor_row, scr.cursor_col
        n = min(count, self.cols - c)
        if n <= 0:
            return
        self._clear_wide_overlap(r, c)
        blank = Cell(' ', self.current_style)
        row = scr.grid[r]
        scr.grid[r] = row[:c] + [blank] * n + row[c:self.cols - n]
        if scr.grid[r][-1].is_continuation is False and _char_width(scr.grid[r][-1].char) == 2:
            scr.grid[r][-1] = blank

    def _delete_chars(self, count: int) -> None:
        scr = self._active
        r, c = scr.cursor_row, scr.cursor_col
        n = min(count, self.cols - c)
        if n <= 0:
            return
        self._clear_wide_overlap(r, c)
        if c + n - 1 < self.cols:
            self._clear_wide_overlap(r, c + n - 1)
        blank = Cell(' ', self.current_style)
        row = scr.grid[r]
        scr.grid[r] = row[:c] + row[c + n:] + [blank] * n

    def _handle_dec_private(self, raw: str, final: str) -> None:
        if final not in ('h', 'l'):
            return
        enable = final == 'h'
        for mode in self._parse_params(raw, default=0):
            if mode == 1:
                self.app_cursor_keys = enable
            elif mode == 7:
                self.auto_wrap = enable
            elif mode == 25:
                self.cursor_visible = enable
            elif mode in (1000, 1002, 1003):
                self.mouse_tracking = enable
            elif mode == 1006:
                self.sgr_mouse = enable
            elif mode in (47, 1047, 1049):
                self._switch_alt_screen(enable, clear_and_save=(mode == 1049))

    def _switch_alt_screen(self, enable: bool, *, clear_and_save: bool) -> None:
        if enable and not self.in_alt_screen:
            if clear_and_save:
                self._main.saved_cursor = (
                    self._main.cursor_row,
                    self._main.cursor_col,
                    self.current_style,
                    self.auto_wrap,
                )
            self._alt = _ScreenState(self._main.rows, self._main.cols)
            self._active = self._alt
            self.in_alt_screen = True
        elif not enable and self.in_alt_screen:
            self._active = self._main
            self.in_alt_screen = False
            if clear_and_save and self._main.saved_cursor is not None:
                r, c, st, aw = self._main.saved_cursor
                self._main.cursor_row = min(r, self._main.rows - 1)
                self._main.cursor_col = min(c, self._main.cols - 1)
                self.current_style = st
                self.auto_wrap = aw
                self._main.pending_wrap = False

    def _apply_sgr(self, params: list[int]) -> None:
        s = self.current_style
        i = 0
        while i < len(params):
            code = params[i]
            if code == 0:
                s = DEFAULT_STYLE
            elif code == 1:
                s = replace(s, bold=True)
            elif code == 2:
                s = replace(s, dim=True)
            elif code == 3:
                s = replace(s, italic=True)
            elif code == 4:
                s = replace(s, underline=True)
            elif code == 7:
                s = replace(s, reverse=True)
            elif code == 22:
                s = replace(s, bold=False, dim=False)
            elif code == 23:
                s = replace(s, italic=False)
            elif code == 24:
                s = replace(s, underline=False)
            elif code == 27:
                s = replace(s, reverse=False)
            elif 30 <= code <= 37:
                s = replace(s, fg=code - 30)
            elif code == 39:
                s = replace(s, fg=None)
            elif 40 <= code <= 47:
                s = replace(s, bg=code - 40)
            elif code == 49:
                s = replace(s, bg=None)
            elif 90 <= code <= 97:
                s = replace(s, fg=code - 90 + 8)
            elif 100 <= code <= 107:
                s = replace(s, bg=code - 100 + 8)
            elif code in (38, 48):
                is_fg = code == 38
                if i + 2 < len(params) and params[i + 1] == 5:
                    color = params[i + 2]
                    s = replace(s, fg=color) if is_fg else replace(s, bg=color)
                    i += 2
                elif i + 4 < len(params) and params[i + 1] == 2:
                    rgb = (params[i + 2], params[i + 3], params[i + 4])
                    s = replace(s, fg=rgb) if is_fg else replace(s, bg=rgb)
                    i += 4
            i += 1
        self.current_style = s
