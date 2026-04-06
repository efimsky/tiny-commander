"""Panel class for displaying directory contents."""

import curses
import fnmatch
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from tnc.colors import (
    PAIR_BROKEN_LINK,
    PAIR_CURSOR,
    PAIR_CURSOR_SELECTED,
    PAIR_DIRECTORY,
    PAIR_EXECUTABLE,
    PAIR_HIDDEN,
    PAIR_NORMAL,
    PAIR_PANEL,
    PAIR_SELECTED,
    PAIR_SYMLINK,
    get_attr,
)
from tnc.file_ops import (
    CreateFileResult,
    DeleteResult,
    MkdirResult,
    calculate_dir_size,
    create_file,
    delete_files,
    mkdir,
)
from tnc.utils import format_mtime, format_size, safe_addstr

# Type variable for create operation results (MkdirResult, CreateFileResult)
_CreateResultT = TypeVar('_CreateResultT')


@dataclass(frozen=True)
class DisplayEntry:
    """Display-ready data for a single directory entry."""

    name: str  # Original entry name
    display_name: str  # Formatted name (*prefix for executable, /suffix for dir)
    size_str: str  # Formatted size (e.g., "4.2K", "12.0M")
    mtime_str: str  # Formatted mtime (e.g., "Jan 15 14:30")
    is_dir: bool  # Directory flag
    is_selected: bool  # Selection state
    has_cursor: bool  # Cursor is on this entry
    attr: int  # Color attribute for curses


def render_panel_entries(
    win: Any,
    entries: list[DisplayEntry],
    x: int,
    y: int,
    width: int,
    show_mtime: bool,
) -> None:
    """Render display entries to a curses window.

    Args:
        win: The curses window to render to.
        entries: List of DisplayEntry objects to render.
        x: X position (column) for the first entry.
        y: Y position (row) for the first entry.
        width: Available width for each entry line.
        show_mtime: Whether to display the mtime column.
    """
    # Calculate column widths
    size_width = 8  # Fixed width for size column
    mtime_space = (12 + 1) if show_mtime else 0  # mtime width + separator

    # Available width for name (size + mtime_space + padding)
    available_width = width - size_width - mtime_space - 2

    # Guard against panels too narrow to render meaningfully
    min_name_width = 4  # Need at least 1 char + "..."
    if available_width < min_name_width:
        return

    for i, entry in enumerate(entries):
        # Format display name (truncate if needed)
        display_name = entry.display_name
        if len(display_name) > available_width:
            display_name = display_name[:available_width - 3] + '...'

        # Format display string
        name_part = display_name.ljust(available_width)
        size_part = entry.size_str.rjust(size_width)

        if show_mtime:
            mtime_display = entry.mtime_str.ljust(12) if entry.mtime_str else ' ' * 12
            display = name_part + size_part + ' ' + mtime_display
        else:
            display = name_part + size_part

        safe_addstr(win, y + i, x, display[:width], entry.attr)


class Panel:
    """A panel displaying directory contents."""

    # Maximum number of entries in navigation history
    _HISTORY_LIMIT = 50

    def __init__(self, path: str, width: int = 40, height: int = 20) -> None:
        """Initialize the panel.

        Args:
            path: The directory path to display.
            width: Panel width in characters.
            height: Panel height in characters.
        """
        self.path = Path(path).resolve()
        self.width = width
        self.height = height
        self.is_active = False
        self.cursor = 0
        self.scroll_offset = 0
        self.entries: list[Path] = []
        self.error_message: str | None = None
        self.selected: set[str] = set()
        # Search mode
        self.search_mode = False
        self.search_text = ''
        self._all_entries: list[Path] = []  # Full list before filtering
        # Sort order
        self.sort_order = 'name'  # Default sort by name
        self.sort_reversed = False  # Normal sort direction
        # Hidden files visibility
        self.show_hidden = True  # Show hidden files by default
        # Navigation history: maps parent path -> child directory name
        # Used to remember position when navigating up via '..'
        self._navigation_history: dict[Path, str] = {}
        # Cached directory sizes: maps full path -> size in bytes
        # Persists for the entire session (not cleared on directory change)
        self._dir_size_cache: dict[Path, int] = {}
        # Render position tracking for mouse hit detection
        self.render_x: int = 0
        self.render_y: int = 0
        self.render_width: int = width
        self.render_height: int = height
        self.refresh()

    def refresh(self) -> None:
        """Refresh the directory listing."""
        # Exit search mode on refresh to avoid stale state
        if self.search_mode:
            self.search_mode = False
            self.search_text = ''
            self._all_entries = []

        self.entries = []
        self.error_message = None
        try:
            # Always add '..' entry first (except at root)
            # path.parent == path is true only at filesystem root
            if self.path.parent != self.path:
                self.entries.append(Path('..'))

            # List directory contents
            items = list(self.path.iterdir())

            # Filter hidden files if needed
            if not self.show_hidden:
                items = [p for p in items if not p.name.startswith('.')]

            # Separate directories and files
            dirs = [p for p in items if p.is_dir()]
            files = [p for p in items if not p.is_dir()]

            # Sort both lists according to current sort order
            dirs = self._sort_entries(dirs)
            files = self._sort_entries(files)

            self.entries.extend(dirs)
            self.entries.extend(files)
        except PermissionError:
            self.error_message = 'Permission denied'
        except FileNotFoundError:
            self.error_message = 'Directory not found'
        except OSError as e:
            self.error_message = str(e)

    def render(self, win: Any, x: int, y: int) -> None:
        """Render the panel to a curses window.

        Args:
            win: The curses window to render to.
            x: X position (column).
            y: Y position (row).
        """
        # Store render position for mouse hit detection
        self.render_x = x
        self.render_y = y
        self.render_width = self.width
        self.render_height = self.height
        # Render border
        self._render_border(win, x, y)
        # Render header with path
        self._render_header(win, x, y)
        # Render file listing
        self._render_entries(win, x, y)

    def _render_border(self, win: Any, x: int, y: int) -> None:
        """Render the panel border with background color."""
        border_attr = get_attr(PAIR_PANEL)
        # Top border
        safe_addstr(win, y, x, '┌' + '─' * (self.width - 2) + '┐', border_attr)
        # Side borders and fill background
        for row in range(1, self.height - 1):
            safe_addstr(win, y + row, x, '│', border_attr)
            # Fill interior with panel background
            safe_addstr(win, y + row, x + 1, ' ' * (self.width - 2), border_attr)
            safe_addstr(win, y + row, x + self.width - 1, '│', border_attr)
        # Bottom border
        safe_addstr(win, y + self.height - 1, x, '└' + '─' * (self.width - 2) + '┘', border_attr)

    def _render_header(self, win: Any, x: int, y: int) -> None:
        """Render the panel header with path."""
        header = self.get_header_text(max_width=self.width - 4)
        # Center the header in the top border
        header_x = x + 2
        header_attr = get_attr(PAIR_PANEL)
        safe_addstr(win, y, header_x, f' {header} ', header_attr)

    def _render_entries(self, win: Any, x: int, y: int) -> None:
        """Render the directory entries."""
        if self.error_message:
            safe_addstr(win, y + 1, x + 1, self.error_message[:self.width - 2])
            return

        entries = self.get_display_entries()
        show_mtime = self.width >= 50
        render_panel_entries(
            win=win,
            entries=entries,
            x=x + 1,
            y=y + 1,
            width=self.width - 2,
            show_mtime=show_mtime,
        )

    def get_display_entries(self) -> list[DisplayEntry]:
        """Get display-ready data for all visible entries.

        Returns:
            List of DisplayEntry objects for rendering.
        """
        result: list[DisplayEntry] = []
        for i in range(self.visible_rows):
            entry_idx = self.scroll_offset + i
            if entry_idx >= len(self.entries):
                break
            entry = self.entries[entry_idx]
            has_cursor = entry_idx == self.cursor
            result.append(self._get_entry_data(entry, has_cursor))
        return result

    def _get_entry_data(self, entry: Path, has_cursor: bool) -> DisplayEntry:
        """Get display data for a single entry.

        Args:
            entry: The Path entry to get data for.
            has_cursor: Whether the cursor is on this entry.

        Returns:
            DisplayEntry with all display-ready data.
        """
        name = entry.name
        display_name = entry.name
        is_selected = entry.name in self.selected

        # File type detection flags
        is_directory = False
        is_symlink = False
        is_broken_link = False
        is_executable = False
        is_hidden = entry.name.startswith('.') and entry.name != '..'

        # Get file stats for size, mtime, and type detection
        size_str = ''
        mtime_str = ''
        if entry.name == '..':
            # Parent directory - special case
            is_directory = True
            try:
                mtime_str = format_mtime(self.path.parent.stat().st_mtime)
            except OSError:
                mtime_str = ''
        else:
            full_path = self.path / entry
            try:
                # Use lstat to detect symlinks
                lstat_info = full_path.lstat()
                is_symlink = stat.S_ISLNK(lstat_info.st_mode)

                if is_symlink:
                    # Check if symlink target exists
                    try:
                        full_path.stat()  # Follows symlink
                    except OSError:
                        is_broken_link = True

                # Get stat info (follows symlinks for size/mtime)
                try:
                    stat_info = full_path.stat()
                except OSError:
                    # Broken symlink - use lstat info
                    stat_info = lstat_info

                is_directory = stat.S_ISDIR(stat_info.st_mode)

                if is_directory:
                    # Check for cached directory size
                    cached_size = self.get_cached_dir_size(entry.name)
                    if cached_size is not None:
                        size_str = format_size(cached_size)
                else:
                    size_str = format_size(stat_info.st_size)
                    # Check if file is executable
                    if stat_info.st_mode & stat.S_IXUSR:
                        is_executable = True
                        display_name = '*' + display_name
                mtime_str = format_mtime(stat_info.st_mtime)
            except OSError:
                size_str = '?'
                mtime_str = ''

        if is_directory:
            display_name = display_name + '/'

        # Determine display attributes based on state
        # Priority: cursor > selected > file type
        if has_cursor and self.is_active:
            # Cursor is on this entry
            if is_selected:
                attr = get_attr(PAIR_CURSOR_SELECTED, bold=True)
            else:
                attr = get_attr(PAIR_CURSOR)
        elif is_selected:
            # Selected but no cursor
            attr = get_attr(PAIR_SELECTED, bold=True)
        elif is_broken_link:
            # Broken symlink - red warning color
            attr = get_attr(PAIR_BROKEN_LINK)
        elif is_symlink:
            # Valid symlink - magenta
            attr = get_attr(PAIR_SYMLINK)
        elif is_directory:
            # Directory - white/bold on classic, blue on modern
            attr = get_attr(PAIR_DIRECTORY, bold=True)
        elif is_executable:
            # Executable file - green
            attr = get_attr(PAIR_EXECUTABLE, bold=True)
        elif is_hidden:
            # Hidden file - dimmed
            attr = get_attr(PAIR_HIDDEN)
        else:
            # Normal file - use panel background color
            attr = get_attr(PAIR_PANEL)

        return DisplayEntry(
            name=name,
            display_name=display_name,
            size_str=size_str,
            mtime_str=mtime_str,
            is_dir=is_directory,
            is_selected=is_selected,
            has_cursor=has_cursor,
            attr=attr,
        )

    def get_sort_indicator(self) -> str:
        """Get the sort indicator string showing current sort type and direction.

        Returns:
            Sort indicator like 'vn' (name normal), '^s' (size reversed).
        """
        # Map sort order to single letter
        sort_letters = {
            'name': 'n',
            'size': 's',
            'date': 'd',
            'extension': 'e',
        }
        letter = sort_letters.get(self.sort_order, 'n')
        arrow = '^' if self.sort_reversed else 'v'
        return f'{arrow}{letter}'

    def get_header_text(self, max_width: int | None = None) -> str:
        """Get the header text with sort indicator and path, optionally truncated.

        Args:
            max_width: Maximum width for the header.

        Returns:
            Sort indicator and path string, possibly truncated.
        """
        indicator = self.get_sort_indicator()
        path_str = str(self.path)

        # indicator is 2 chars, plus space = 3 chars overhead
        if max_width:
            # Reserve space for indicator and space
            path_max = max_width - 3
            if len(path_str) > path_max:
                # Truncate path from the left, keeping the end
                path_str = '...' + path_str[-(path_max - 3):]

        return f'{indicator} {path_str}'

    def resize(self, width: int, height: int) -> None:
        """Resize the panel.

        Args:
            width: New width.
            height: New height.
        """
        self.width = width
        self.height = height
        # Adjust scroll if needed
        self._adjust_scroll()

    @property
    def visible_rows(self) -> int:
        """Number of file entry rows visible in the panel."""
        return self.height - 2

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a screen coordinate is within this panel's bounds.

        Args:
            x: Screen x coordinate (column).
            y: Screen y coordinate (row).

        Returns:
            True if the point is within the panel's rendered area.
        """
        return (
            self.render_x <= x < self.render_x + self.render_width and
            self.render_y <= y < self.render_y + self.render_height
        )

    def entry_at_point(self, x: int, y: int) -> int | None:
        """Get the entry index at a screen coordinate.

        Args:
            x: Screen x coordinate (column).
            y: Screen y coordinate (row).

        Returns:
            Entry index at the given coordinates, or None if the point
            is outside the entries area (header, border, or past entries).
        """
        if not self.contains_point(x, y):
            return None

        # Calculate row relative to panel (row 0 is header/border)
        relative_row = y - self.render_y

        # Row 0 is header, entries start at row 1
        if relative_row < 1:
            return None

        # Convert to entry index accounting for scroll
        entry_row = relative_row - 1  # 0-based row within entries area
        entry_index = entry_row + self.scroll_offset

        # Check if past the last entry
        if entry_index >= len(self.entries):
            return None

        return entry_index

    def _adjust_scroll(self) -> None:
        """Adjust scroll offset to keep cursor visible."""
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor
        elif self.cursor >= self.scroll_offset + self.visible_rows:
            self.scroll_offset = self.cursor - self.visible_rows + 1

    def _sort_entries(self, entries: list[Path]) -> list[Path]:
        """Sort entries according to current sort order and direction.

        Args:
            entries: List of Path objects to sort.

        Returns:
            Sorted list of Path objects.
        """
        # For size/date, "normal" is descending (largest/newest first)
        # For name/extension, "normal" is ascending (A-Z)
        match self.sort_order:
            case 'size':
                # Normal: largest first, reversed: smallest first
                return sorted(entries, key=self._get_size, reverse=not self.sort_reversed)
            case 'date':
                # Normal: newest first, reversed: oldest first
                return sorted(entries, key=self._get_mtime, reverse=not self.sort_reversed)
            case 'extension':
                return sorted(entries, key=self._get_extension_key, reverse=self.sort_reversed)
            case _:
                # Name sort (default)
                return sorted(entries, key=lambda p: p.name.lower(), reverse=self.sort_reversed)

    def _get_size(self, p: Path) -> int:
        """Get file size for sorting (largest first)."""
        try:
            return p.stat().st_size
        except OSError:
            return 0

    def _get_mtime(self, p: Path) -> float:
        """Get modification time for sorting (most recent first)."""
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    def _get_extension_key(self, p: Path) -> tuple[str, str]:
        """Get sort key for extension sorting (extension, then name)."""
        name = p.name.lower()
        if '.' in name:
            return (name.rsplit('.', 1)[1], name)
        return ('', name)

    def sort_by(self, order: str) -> None:
        """Change the sort order and refresh the panel.

        If selecting the same sort type, toggles the direction.
        If selecting a different sort type, resets direction to normal.

        Args:
            order: Sort order ('name', 'size', 'date', 'extension').
        """
        if self.sort_order == order:
            self.sort_reversed = not self.sort_reversed
        else:
            self.sort_order = order
            self.sort_reversed = False
        self.refresh()

    def toggle_sort_reverse(self) -> None:
        """Toggle the sort direction and refresh the panel."""
        self.sort_reversed = not self.sort_reversed
        self.refresh()

    def cycle_sort(self) -> None:
        """Cycle through sort orders: name -> size -> date -> extension -> name."""
        cycle = ['name', 'size', 'date', 'extension']
        try:
            current_index = cycle.index(self.sort_order)
            next_index = (current_index + 1) % len(cycle)
        except ValueError:
            # If current sort order is not in cycle, reset to name
            next_index = 0
        self.sort_by(cycle[next_index])

    def toggle_hidden(self) -> None:
        """Toggle visibility of hidden files (dotfiles)."""
        self.show_hidden = not self.show_hidden
        self.refresh()
        # Adjust cursor if it's now past the end
        if self.cursor >= len(self.entries):
            self.cursor = max(0, len(self.entries) - 1)
        self._adjust_scroll()

    def navigate_down(self) -> None:
        """Move cursor down one position."""
        if self.cursor < len(self.entries) - 1:
            self.cursor += 1
            self._adjust_scroll()

    def navigate_up(self) -> None:
        """Move cursor up one position."""
        if self.cursor > 0:
            self.cursor -= 1
            self._adjust_scroll()

    def navigate_to_top(self) -> None:
        """Move cursor to first entry (Home key)."""
        self.cursor = 0
        self._adjust_scroll()

    def navigate_to_bottom(self) -> None:
        """Move cursor to last entry (End key)."""
        if self.entries:
            self.cursor = len(self.entries) - 1
            self._adjust_scroll()

    def navigate_page_up(self) -> None:
        """Move cursor up by one page (Page Up key)."""
        self.cursor = max(0, self.cursor - self.visible_rows)
        self._adjust_scroll()

    def navigate_page_down(self) -> None:
        """Move cursor down by one page (Page Down key)."""
        if not self.entries:
            return
        self.cursor = min(len(self.entries) - 1, self.cursor + self.visible_rows)
        self._adjust_scroll()

    def enter(self) -> Path | None:
        """Handle Enter key on current entry.

        Returns:
            Path to file if a file was selected (for editing),
            None if a directory was entered.
        """
        if not self.entries:
            return None

        entry = self.entries[self.cursor]

        # Handle '..' entry
        if entry.name == '..':
            parent = self.path.parent
            if parent != self.path:  # Not at root
                # Remember current directory name for when we return
                self._push_history(parent, self.path.name)
                self.change_directory(parent)
            return None

        # Get the full path
        full_path = self.path / entry

        # Check if it's a directory
        if full_path.is_dir():
            self.change_directory(full_path)
            return None

        # It's a file - return path for editing
        return full_path

    def change_directory(self, new_path: Path, external: bool = False) -> None:
        """Change to a new directory.

        Args:
            new_path: The new directory path.
            external: If True, clear navigation history (for command-line nav).
        """
        if external:
            self._navigation_history.clear()

        self.path = new_path.resolve()
        self.scroll_offset = 0
        self.selected.clear()
        # Note: _dir_size_cache is NOT cleared - it persists for the session
        self.refresh()

        # Restore cursor position from history, or default to 0
        remembered_child = self._navigation_history.get(self.path)
        restored_index = self._find_entry_index(remembered_child) if remembered_child else None
        self.cursor = restored_index if restored_index is not None else 0
        self._adjust_scroll()

    def toggle_selection(self) -> None:
        """Toggle selection of the current entry and advance cursor."""
        if not self.entries:
            return

        entry = self.entries[self.cursor]

        # Toggle selection (skip '..' which cannot be selected)
        if entry.name != '..':
            self.selected ^= {entry.name}

        # Always advance cursor after toggle (if not at last entry)
        if self.cursor < len(self.entries) - 1:
            self.cursor += 1
            self._adjust_scroll()

    def _selectable_names(self) -> set[str]:
        """Return set of all selectable entry names (excludes '..')."""
        return {entry.name for entry in self.entries if entry.name != '..'}

    def _find_entry_index(self, name: str) -> int | None:
        """Find the index of an entry by name.

        Args:
            name: Name of the entry to find.

        Returns:
            Index of the entry, or None if not found.
        """
        for i, entry in enumerate(self.entries):
            if entry.name == name:
                return i
        return None

    def _push_history(self, parent_path: Path, child_name: str) -> None:
        """Add an entry to navigation history, enforcing size limit.

        Args:
            parent_path: The parent directory path (key).
            child_name: The child directory name to remember.
        """
        # If at limit, remove oldest entry (FIFO)
        if len(self._navigation_history) >= self._HISTORY_LIMIT:
            # Remove the first (oldest) entry
            oldest_key = next(iter(self._navigation_history))
            del self._navigation_history[oldest_key]

        self._navigation_history[parent_path] = child_name

    def select_by_pattern(self, pattern: str) -> None:
        """Select files matching the given pattern.

        Args:
            pattern: Shell-style wildcard pattern (supports *, ?).
        """
        if not pattern:
            return
        matches = {name for name in self._selectable_names() if fnmatch.fnmatch(name, pattern)}
        self.selected |= matches

    def deselect_by_pattern(self, pattern: str) -> None:
        """Deselect files matching the given pattern.

        Args:
            pattern: Shell-style wildcard pattern (supports *, ?).
        """
        if not pattern:
            return
        matches = {name for name in self.selected if fnmatch.fnmatch(name, pattern)}
        self.selected -= matches

    def invert_selection(self) -> None:
        """Invert the current selection."""
        self.selected = self._selectable_names() - self.selected

    def select_all(self) -> None:
        """Select all selectable entries."""
        self.selected = self._selectable_names()

    def get_files_for_operation(self) -> list[str]:
        """Get files for copy/move operations.

        Returns selected files, or the current file if nothing is selected.
        Returns empty list if cursor is on '..' or no valid entry exists.
        """
        if self.selected:
            return list(self.selected)

        if self.cursor >= len(self.entries):
            return []

        current_entry = self.entries[self.cursor]
        if current_entry.name == '..':
            return []

        return [current_entry.name]

    def _do_create_entry(
        self,
        name: str,
        create_func: Callable[[Path, str], _CreateResultT],
    ) -> _CreateResultT:
        """Template for create operations (directory or file).

        Args:
            name: Name of the entry to create.
            create_func: Function to call (mkdir or create_file).

        Returns:
            Result from the create function.
        """
        result = create_func(self.path, name)

        if result.success:
            self.refresh()
            # Move cursor to the new entry
            index = self._find_entry_index(name)
            if index is not None:
                self.cursor = index
                self._adjust_scroll()

        return result

    def create_directory(self, name: str) -> MkdirResult:
        """Create a new directory in the current path.

        Args:
            name: Name of the new directory.

        Returns:
            MkdirResult with success status.
        """
        return self._do_create_entry(name, mkdir)

    def create_file(self, name: str) -> CreateFileResult:
        """Create a new empty file in the current path.

        Args:
            name: Name of the new file.

        Returns:
            CreateFileResult with success status.
        """
        return self._do_create_entry(name, create_file)

    def measure_dir_size(self, name: str) -> int:
        """Calculate and cache the size of a directory.

        Args:
            name: Name of the directory to measure.

        Returns:
            Size in bytes, or -1 on error.
        """
        dir_path = (self.path / name).resolve()
        size = calculate_dir_size(dir_path)
        if size >= 0:
            self._dir_size_cache[dir_path] = size
        return size

    def get_cached_dir_size(self, name: str) -> int | None:
        """Get cached directory size if available.

        Args:
            name: Name of the directory.

        Returns:
            Size in bytes if cached, None otherwise.
        """
        dir_path = (self.path / name).resolve()
        return self._dir_size_cache.get(dir_path)

    def delete_selected(self) -> DeleteResult:
        """Delete selected files or current file if nothing selected.

        Returns:
            DeleteResult with success status.
        """
        files_to_delete = self.get_files_for_operation()
        if not files_to_delete:
            return DeleteResult(success=False, error='Nothing to delete')

        result = delete_files(files_to_delete, self.path)

        if result.success or result.deleted_files:
            self.selected.clear()
            self.refresh()
            # Adjust cursor if it's now past the end
            if self.cursor >= len(self.entries):
                self.cursor = max(0, len(self.entries) - 1)
            self._adjust_scroll()

        return result

    def start_search(self) -> None:
        """Activate search mode."""
        self.search_mode = True
        self.search_text = ''
        self._all_entries = self.entries.copy()

    def handle_search_char(self, char: str) -> None:
        """Add a character to the search text.

        Args:
            char: The character to add.
        """
        self.search_text += char
        self.apply_search_filter()

    def handle_search_backspace(self) -> None:
        """Remove the last character from search text."""
        if self.search_text:
            self.search_text = self.search_text[:-1]
            self.apply_search_filter()
        else:
            # Empty search text - exit search mode
            self.exit_search(confirm=False)

    def apply_search_filter(self) -> None:
        """Apply the current search filter to entries."""
        if not self.search_text:
            self.entries = self._all_entries.copy()
        else:
            search_lower = self.search_text.lower()
            self.entries = [
                e for e in self._all_entries
                if e.name == '..' or search_lower in e.name.lower()
            ]

        # Position cursor on first match after '..' (or 0 if only '..')
        self.cursor = 1 if len(self.entries) > 1 else 0
        self.scroll_offset = 0
        self._adjust_scroll()

    def exit_search(self, confirm: bool) -> None:
        """Exit search mode.

        Args:
            confirm: If True, position cursor on selected entry. If False, reset cursor.
        """
        self.search_mode = False

        # Remember selected entry before restoring full list
        selected_name = None
        if confirm and self.entries and self.cursor < len(self.entries):
            selected_name = self.entries[self.cursor].name

        # Restore full entry list
        self.entries = self._all_entries.copy()

        # Position cursor on previously selected entry, or reset to 0
        self.cursor = self._find_entry_index(selected_name) if selected_name else None
        if self.cursor is None:
            self.cursor = 0

        self.search_text = ''
        self._all_entries = []
        self._adjust_scroll()

