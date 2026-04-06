"""Status bar displaying current file information."""

import curses
import stat
from pathlib import Path
from typing import Any

from tnc.colors import PAIR_STATUS, get_attr
from tnc.utils import format_mtime, format_permissions, format_size, safe_addstr


class StatusBar:
    """Status bar showing file info, position, and selection count."""

    def render(
        self,
        win: Any,
        y: int,
        width: int,
        panel: Any,
        is_left: bool = True,
        hint: str | None = None,
    ) -> None:
        """Render the status bar.

        Args:
            win: The curses window to render to.
            y: Y position (row) to render at.
            width: Available width in characters.
            panel: The active Panel to get information from.
            is_left: Whether this is the left panel (for indicator).
            hint: Optional hint text to display (e.g., escape hint).
        """
        # Build the status line
        parts = []

        # Panel indicator
        indicator = '[Left]' if is_left else '[Right]'
        parts.append(indicator)

        # Handle search mode
        if panel.search_mode:
            parts.append(f'/{panel.search_text}')
            content = ' '.join(parts)
            self._render_line(win, y, width, content)
            return

        # Get current entry info (wrap in try-except for graceful handling)
        try:
            if panel.entries and panel.cursor < len(panel.entries):
                entry = panel.entries[panel.cursor]
                name = entry.name

                # Get file info (handle '..' specially)
                if name != '..':
                    try:
                        file_path = panel.path / name
                        stat_info = file_path.lstat()
                        # Check for cached directory size first (use lstat mode, not is_dir)
                        is_directory = stat.S_ISDIR(stat_info.st_mode)
                        if is_directory:
                            cached_size = panel.get_cached_dir_size(name)
                            if cached_size is not None:
                                size_str = f'Dir: {format_size(cached_size)}'
                            else:
                                size_str = ''
                        else:
                            size_str = format_size(stat_info.st_size)
                        perms_str = format_permissions(stat_info.st_mode)
                        mtime_str = format_mtime(stat_info.st_mtime)
                    except OSError:
                        size_str = '?'
                        perms_str = '??????????'
                        mtime_str = '????????????'  # 12 chars to match format_mtime
                else:
                    size_str = ''
                    perms_str = ''
                    mtime_str = ''

                # Truncate name if needed (ensure minimum 10 chars on narrow terminals)
                max_name_len = max(10, width - 50)
                if len(name) > max_name_len:
                    name = name[:max_name_len - 3] + '...'

                parts.append(name)
                if size_str:
                    parts.append(size_str)
                if perms_str:
                    parts.append(perms_str)
                # Show mtime only on wide terminals (>= 70 chars)
                if mtime_str and width >= 70:
                    parts.append(mtime_str)

                # Position indicator
                position = self._format_position(panel.cursor, len(panel.entries))
                parts.append(position)
        except (IndexError, AttributeError):
            # Guard against race conditions: panel.entries or panel.cursor may change
            # between the bounds check and actual access if panel.refresh() is called
            # from another context (e.g., file operation completing)
            pass

        # Selection count (only if files are selected)
        if panel.selected:
            parts.append(f'| {len(panel.selected)} selected')

        # Show hint if provided (e.g., Escape hint)
        if hint:
            parts.append(f'| {hint}')

        content = '  '.join(parts)
        self._render_line(win, y, width, content)

    def _render_line(self, win: Any, y: int, width: int, content: str) -> None:
        """Render a line, padding or truncating to fit width.

        Uses mc-style black on cyan coloring.

        Args:
            win: The curses window.
            y: Y position.
            width: Available width.
            content: Content to render.
        """
        # Truncate if needed
        if len(content) > width:
            content = content[:width]

        # Pad to full width
        content = content.ljust(width)

        status_attr = get_attr(PAIR_STATUS)
        safe_addstr(win, y, 0, content, status_attr)

    def _format_position(self, cursor: int, total: int) -> str:
        """Format cursor position as 'X of Y'.

        Args:
            cursor: Current cursor position (0-indexed).
            total: Total number of entries.

        Returns:
            Formatted position string (1-indexed for display).
        """
        return f'{cursor + 1} of {total}'
