"""Modal dialog system for Tiny Commander."""

import curses
from datetime import datetime
from typing import Any, Protocol

from tnc.colors import PAIR_DIALOG, PAIR_DIALOG_TITLE, get_attr
from tnc.file_ops import OverwriteChoice, OverwriteHandler
from tnc.utils import safe_addstr


class DialogProvider(Protocol):
    """Protocol for dialog operations.

    This protocol abstracts dialog operations to enable testing without
    actual curses dialogs. Implement this protocol to provide custom
    dialog behavior or mock dialogs in tests.
    """

    def confirm(self, title: str, message: str, default_yes: bool = True) -> bool:
        """Show a confirmation dialog.

        Args:
            title: Dialog title.
            message: Message to display.
            default_yes: If True, Enter selects Yes by default.

        Returns:
            True if user confirmed, False otherwise.
        """
        ...

    def select(
        self,
        title: str,
        options: list[str],
        allow_custom: bool = False
    ) -> str | None:
        """Show a selection dialog.

        Args:
            title: Dialog title.
            options: List of options to choose from.
            allow_custom: If True, allow custom text input.

        Returns:
            Selected option string, or None if cancelled.
        """
        ...

    def show_summary(
        self,
        operation: str,
        copied: int = 0,
        moved: int = 0,
        skipped: int = 0,
        cancelled: bool = False
    ) -> None:
        """Show operation summary.

        Args:
            operation: Type of operation ('copy' or 'move').
            copied: Number of files copied.
            moved: Number of files moved.
            skipped: Number of files skipped.
            cancelled: Whether operation was cancelled.
        """
        ...

    def prompt_input(
        self,
        title: str,
        prompt: str,
        default_value: str = ''
    ) -> str:
        """Show a text input dialog.

        Args:
            title: Dialog title.
            prompt: Prompt text above the input field.
            default_value: Initial text in the input field.

        Returns:
            Entered text, or empty string if cancelled.
        """
        ...


def _render_dialog_frame(width: int, title: str = '') -> dict:
    """Generate common dialog frame elements.

    Args:
        width: Total width of the dialog box.
        title: Optional title text to center.

    Returns:
        Dictionary with frame elements:
        - top: Top border string (┌───┐)
        - bottom: Bottom border string (└───┘)
        - separator: Separator string (├───┤)
        - empty: Empty line with side borders (│   │)
        - title_content: Centered title text (without borders)
        - content_line: Function to create padded content line
    """
    inner = width - 2

    def content_line(text: str) -> str:
        """Create a content line with side borders and padding."""
        return '│ ' + text.ljust(inner - 2) + ' │'

    return {
        'top': '┌' + '─' * inner + '┐',
        'bottom': '└' + '─' * inner + '┘',
        'separator': '├' + '─' * inner + '┤',
        'empty': '│' + ' ' * inner + '│',
        'title_content': title.center(inner),
        'content_line': content_line,
    }


def format_size(size: int) -> str:
    """Format file size in human-readable format.

    Args:
        size: Size in bytes.

    Returns:
        Formatted size string (e.g., "4.2 KB").
    """
    if size < 1024:
        return f'{size} B'
    elif size < 1024 * 1024:
        return f'{size / 1024:.1f} KB'
    elif size < 1024 * 1024 * 1024:
        return f'{size / (1024 * 1024):.1f} MB'
    else:
        return f'{size / (1024 * 1024 * 1024):.1f} GB'


def format_time(mtime: float) -> str:
    """Format modification time.

    Args:
        mtime: Unix timestamp.

    Returns:
        Formatted date string (e.g., "2024-01-15 14:32").
    """
    dt = datetime.fromtimestamp(mtime)
    return dt.strftime('%Y-%m-%d %H:%M')


def draw_modal(
    win: Any,
    title: str,
    lines: list[str],
    width: int = 50,
    footer: str = ''
) -> tuple[int, int]:
    """Draw a centered modal box on the screen.

    Args:
        win: Curses window to draw on.
        title: Title text for the modal.
        lines: Content lines to display.
        width: Width of the modal box.
        footer: Optional footer text (e.g., key hints).

    Returns:
        Tuple of (y, x) coordinates of the modal's top-left corner.
    """
    rows, cols = win.getmaxyx()

    # Calculate height: top border + title + separator + content lines + bottom border
    # Optional: footer separator + footer line
    height = 4 + len(lines)  # top + title + sep + lines + bottom
    if footer:
        height += 2  # footer separator + footer line

    # Ensure width fits with margin on narrow terminals
    max_width = cols - 2  # Leave 1 char margin on each side
    if width > max_width:
        width = max(max_width, 20)  # Minimum usable width

    # Center the modal
    y = (rows - height) // 2
    x = (cols - width) // 2

    # Ensure we stay within bounds
    if x < 1:
        x = 1
    if y < 0:
        y = 0

    dialog_attr = get_attr(PAIR_DIALOG)
    title_attr = get_attr(PAIR_DIALOG_TITLE)

    # Get frame elements
    frame = _render_dialog_frame(width, title)

    # Draw top border with title
    safe_addstr(win, y, x, frame['top'], dialog_attr)

    # Draw title line (centered)
    safe_addstr(win, y + 1, x, '│', dialog_attr)
    safe_addstr(win, y + 1, x + 1, frame['title_content'], title_attr)
    safe_addstr(win, y + 1, x + width - 1, '│', dialog_attr)

    # Draw separator after title
    safe_addstr(win, y + 2, x, frame['separator'], dialog_attr)

    # Draw content lines
    for i, line in enumerate(lines):
        safe_addstr(win, y + 3 + i, x, frame['content_line'](line), dialog_attr)

    # Draw footer if provided
    footer_y = y + 3 + len(lines)
    if footer:
        safe_addstr(win, footer_y, x, frame['separator'], dialog_attr)
        safe_addstr(win, footer_y + 1, x, frame['content_line'](footer), dialog_attr)
        footer_y += 2

    # Draw bottom border
    safe_addstr(win, footer_y, x, frame['bottom'], dialog_attr)

    win.refresh()
    return (y, x)


def confirm_dialog(
    win: Any,
    title: str,
    message: str,
    default_yes: bool = True
) -> bool:
    """Show a simple y/n confirmation dialog.

    Args:
        win: Curses window to draw on.
        title: Dialog title.
        message: Message to display.
        default_yes: If True, Enter selects Yes (default). If False, Enter selects No.

    Returns:
        True if user confirmed, False otherwise.
    """
    # Show [Y/n] or [y/N] based on default
    if default_yes:
        hint = '[Y/n]'
    else:
        hint = '[y/N]'

    lines = [message, '', f'(y)es  (n)o  {hint}']
    draw_modal(win, title, lines, width=max(len(message) + 6, len(title) + 6, 30))

    while True:
        key = win.getch()
        if key in (ord('y'), ord('Y')):
            return True
        elif key in (ord('n'), ord('N'), 27):  # 27 = Escape
            return False
        elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
            return default_yes


def overwrite_dialog(
    win: Any,
    filename: str,
    source_size: int,
    dest_size: int,
    source_mtime: float,
    dest_mtime: float,
    current: int,
    total: int
) -> OverwriteChoice:
    """Show overwrite confirmation dialog with file details.

    Args:
        win: Curses window to draw on.
        filename: Name of the conflicting file.
        source_size: Size of source file in bytes.
        dest_size: Size of destination file in bytes.
        source_mtime: Modification time of source file.
        dest_mtime: Modification time of destination file.
        current: Current file number in operation.
        total: Total files in operation.

    Returns:
        User's choice as OverwriteChoice enum.
    """
    title = f'File already exists - {current} of {total}'

    # Format file info
    source_info = f'Source:  {format_size(source_size):>10}   {format_time(source_mtime)}'
    dest_info = f'Dest:    {format_size(dest_size):>10}   {format_time(dest_mtime)}'

    lines = [
        filename,
        '',
        source_info,
        dest_info,
    ]

    footer = '(y)es (n)o (a)ll (s)kip-all (o)nly-newer Esc'

    # Calculate width to fit content
    width = max(
        len(title) + 6,
        len(filename) + 6,
        len(source_info) + 6,
        len(footer) + 6,
        50
    )

    draw_modal(win, title, lines, width=width, footer=footer)

    while True:
        key = win.getch()
        if key in (ord('y'), ord('Y')):
            return OverwriteChoice.YES
        elif key in (ord('n'), ord('N')):
            return OverwriteChoice.NO
        elif key in (ord('a'), ord('A')):
            return OverwriteChoice.YES_ALL
        elif key in (ord('s'), ord('S')):
            return OverwriteChoice.NO_ALL
        elif key in (ord('o'), ord('O')):
            return OverwriteChoice.YES_OLDER
        elif key == 27:  # Escape
            return OverwriteChoice.CANCEL


def show_summary(
    win: Any,
    operation: str,
    copied: int = 0,
    moved: int = 0,
    skipped: int = 0,
    cancelled: bool = False,
    errors: list[str] | None = None,
    max_errors: int = 3
) -> None:
    """Show operation summary, optionally with error details.

    Args:
        win: Curses window to draw on.
        operation: Type of operation ('copy' or 'move').
        copied: Number of files copied (for copy operation).
        moved: Number of files moved (for move operation).
        skipped: Number of files skipped.
        cancelled: Whether operation was cancelled.
        errors: Optional list of error messages to display.
        max_errors: Maximum number of errors to show before truncating.
    """
    # If there are errors, show a modal dialog instead of a simple message
    if errors:
        if cancelled:
            title = 'Operation cancelled'
        elif operation == 'copy':
            title = 'Copy completed with errors'
        else:
            title = 'Move completed with errors'

        # Build the main message
        if operation == 'copy':
            if skipped > 0:
                message = f'Copied {copied} file(s), skipped {skipped}, {len(errors)} failed'
            else:
                message = f'Copied {copied} file(s), {len(errors)} failed'
        else:
            if skipped > 0:
                message = f'Moved {moved} file(s), skipped {skipped}, {len(errors)} failed'
            else:
                message = f'Moved {moved} file(s), {len(errors)} failed'

        show_error_dialog(win, title, message, details=errors, max_details=max_errors)
        return

    # No errors - show simple message at bottom
    rows, cols = win.getmaxyx()
    last_row = rows - 1

    if cancelled:
        message = 'Operation cancelled'
    elif operation == 'copy':
        if skipped > 0:
            message = f'Copied {copied} file(s), skipped {skipped}'
        else:
            message = f'Copied {copied} file(s)'
    else:  # move
        if skipped > 0:
            message = f'Moved {moved} file(s), skipped {skipped}'
        else:
            message = f'Moved {moved} file(s)'

    message += ' [Press any key]'

    safe_addstr(win, last_row, 0, message[:cols - 1])
    try:
        win.clrtoeol()
        win.refresh()
    except curses.error:
        pass

    win.getch()


def show_error_dialog(
    win: Any,
    title: str,
    message: str,
    details: list[str] | None = None,
    max_details: int = 5
) -> None:
    """Display a modal error dialog.

    Shows an error message in a centered modal dialog, optionally with
    additional detail lines (e.g., per-file errors). Waits for user to
    press any key before returning.

    Args:
        win: Curses window to draw on.
        title: Dialog title (e.g., "Error", "Copy Failed").
        message: Main error message.
        details: Optional list of detailed error messages (e.g., per-file errors).
        max_details: Maximum number of detail lines to show before truncating.
    """
    lines = [message, '']

    if details:
        # Show up to max_details errors
        for error in details[:max_details]:
            lines.append(f'  {error}')

        # Show truncation message if there are more
        remaining = len(details) - max_details
        if remaining > 0:
            lines.append(f'  ...and {remaining} more error(s)')

    lines.append('')
    lines.append('[Press any key]')

    # Calculate width to fit content
    max_line_len = max(len(line) for line in lines)
    width = max(len(title) + 6, max_line_len + 6, 40)

    draw_modal(win, title, lines, width=width)
    win.getch()


class CursesOverwriteHandler(OverwriteHandler):
    """Curses-based overwrite handler that shows modal dialogs."""

    def __init__(self, win: Any):
        """Initialize the handler.

        Args:
            win: Curses window to draw dialogs on.
        """
        self.win = win

    def prompt(
        self,
        filename: str,
        source_size: int,
        dest_size: int,
        source_mtime: float,
        dest_mtime: float,
        current: int,
        total: int
    ) -> OverwriteChoice:
        """Show overwrite dialog and return user's choice.

        Args:
            filename: Name of the conflicting file.
            source_size: Size of source file in bytes.
            dest_size: Size of destination file in bytes.
            source_mtime: Modification time of source file.
            dest_mtime: Modification time of destination file.
            current: Current file number in operation.
            total: Total files in operation.

        Returns:
            User's choice as OverwriteChoice enum.
        """
        return overwrite_dialog(
            self.win, filename, source_size, dest_size,
            source_mtime, dest_mtime, current, total
        )


class CursesDialogProvider:
    """Curses-based implementation of DialogProvider.

    Uses curses dialogs for user interaction. This is the default
    implementation used by the application.
    """

    def __init__(self, win: Any) -> None:
        """Initialize the dialog provider.

        Args:
            win: Curses window to draw dialogs on.
        """
        self.win = win

    def confirm(self, title: str, message: str, default_yes: bool = True) -> bool:
        """Show a confirmation dialog.

        Args:
            title: Dialog title.
            message: Message to display.
            default_yes: If True, Enter selects Yes by default.

        Returns:
            True if user confirmed, False otherwise.
        """
        return confirm_dialog(self.win, title, message, default_yes)

    def select(
        self,
        title: str,
        options: list[str],
        allow_custom: bool = False
    ) -> str | None:
        """Show a selection dialog.

        Args:
            title: Dialog title.
            options: List of options to choose from.
            allow_custom: If True, allow custom text input.

        Returns:
            Selected option string, or None if cancelled.
        """
        dialog = SelectionDialog(title, options, allow_custom)
        return dialog.show(self.win)

    def show_summary(
        self,
        operation: str,
        copied: int = 0,
        moved: int = 0,
        skipped: int = 0,
        cancelled: bool = False
    ) -> None:
        """Show operation summary.

        Args:
            operation: Type of operation ('copy' or 'move').
            copied: Number of files copied.
            moved: Number of files moved.
            skipped: Number of files skipped.
            cancelled: Whether operation was cancelled.
        """
        show_summary(self.win, operation, copied, moved, skipped, cancelled)

    def prompt_input(
        self,
        title: str,
        prompt: str,
        default_value: str = ''
    ) -> str:
        """Show a text input dialog.

        Args:
            title: Dialog title.
            prompt: Prompt text above the input field.
            default_value: Initial text in the input field.

        Returns:
            Entered text, or empty string if cancelled.
        """
        return input_dialog(self.win, title, prompt, default_value)


class SelectionDialog:
    """A modal selection dialog with numbered options.

    Displays a centered, bordered dialog box with a title and
    numbered options. Optionally includes a Custom option for text input.

    Attributes:
        title: Dialog title displayed in top border.
        options: List of option strings.
        allow_custom: Whether to show Custom option.
        in_custom_input_mode: Whether currently in text input mode.
        custom_text: Text entered in custom mode.
    """

    MIN_WIDTH = 30

    def __init__(
        self,
        title: str,
        options: list[str],
        allow_custom: bool = False
    ) -> None:
        """Initialize a selection dialog.

        Args:
            title: Dialog title.
            options: List of options to display.
            allow_custom: If True, add Custom option for text input.
        """
        self.title = title
        self.options = options
        self.allow_custom = allow_custom
        self.in_custom_input_mode = False
        self.custom_text = ''

    def get_dimensions(self) -> tuple[int, int]:
        """Calculate dialog dimensions based on content.

        Returns:
            Tuple of (width, height).
        """
        # Calculate number of items
        num_items = len(self.options)
        if self.allow_custom:
            num_items += 1

        # Width: max of title or longest option, plus numbering and padding
        max_option_len = max(len(opt) for opt in self.options) if self.options else 0
        if self.allow_custom:
            max_option_len = max(max_option_len, len('Custom...'))

        content_width = max(len(self.title), max_option_len + 4)  # +4 for "N. "
        width = max(content_width + 6, self.MIN_WIDTH)

        # Height: border + blank + options + blank + hint + border
        # In custom mode: border + blank + prompt + input + blank + hint + border = 7
        if self.in_custom_input_mode:
            height = 7
        else:
            height = num_items + 5  # borders(2) + blank(1) + hint(1) + blank(1)

        return width, height

    def handle_key(self, key: int) -> str | None:
        """Handle a keypress and return result.

        Args:
            key: Key code from curses.

        Returns:
            Selected option string, or None if not handled/cancelled.
        """
        if self.in_custom_input_mode:
            return self._handle_custom_input_key(key)

        # Escape cancels
        if key == 27:
            return None

        # Check for number key (supports 1-9 only)
        try:
            char = chr(key)
            if char.isdigit():
                num = int(char)
                if 1 <= num <= len(self.options):
                    return self.options[num - 1]
                elif self.allow_custom and num == len(self.options) + 1:
                    # Enter custom input mode
                    self.in_custom_input_mode = True
                    self.custom_text = ''
                    return None
        except (ValueError, TypeError):
            pass

        return None

    def _handle_custom_input_key(self, key: int) -> str | None:
        """Handle key in custom input mode.

        Args:
            key: Key code.

        Returns:
            Custom text if Enter pressed with text, None otherwise.
        """
        # Escape exits custom mode
        if key == 27:
            self.in_custom_input_mode = False
            self.custom_text = ''
            return None

        # Enter submits if text is non-empty
        if key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
            if self.custom_text:
                result = self.custom_text
                self.in_custom_input_mode = False
                self.custom_text = ''
                return result
            return None

        # Backspace
        if key in (curses.KEY_BACKSPACE, 127, 8):
            if self.custom_text:
                self.custom_text = self.custom_text[:-1]
            return None

        # Printable character
        if 32 <= key <= 126:
            self.custom_text += chr(key)
            return None

        return None

    def render(self, stdscr: Any) -> None:
        """Render the dialog to the screen.

        Args:
            stdscr: Curses window to render to.
        """
        rows, cols = stdscr.getmaxyx()
        width, height = self.get_dimensions()

        # Calculate centered position
        start_y = (rows - height) // 2
        start_x = (cols - width) // 2

        dialog_attr = get_attr(PAIR_DIALOG)
        title_attr = get_attr(PAIR_DIALOG_TITLE)

        if self.in_custom_input_mode:
            self._render_custom_input(stdscr, start_y, start_x, width, height, dialog_attr, title_attr)
        else:
            self._render_selection(stdscr, start_y, start_x, width, height, dialog_attr, title_attr)

    def _render_selection(
        self,
        stdscr: Any,
        start_y: int,
        start_x: int,
        width: int,
        height: int,
        dialog_attr: int,
        title_attr: int
    ) -> None:
        """Render the selection list mode."""
        frame = _render_dialog_frame(width, self.title)

        # Top border
        safe_addstr(stdscr, start_y, start_x, frame['top'], dialog_attr)

        # Title line
        safe_addstr(stdscr, start_y + 1, start_x, '│', dialog_attr)
        safe_addstr(stdscr, start_y + 1, start_x + 1, frame['title_content'], title_attr)
        safe_addstr(stdscr, start_y + 1, start_x + width - 1, '│', dialog_attr)

        # Separator
        safe_addstr(stdscr, start_y + 2, start_x, frame['separator'], dialog_attr)

        # Options
        line_y = start_y + 3
        for i, opt in enumerate(self.options, 1):
            content = f'│  {i}. {opt}'.ljust(width - 1) + '│'
            safe_addstr(stdscr, line_y, start_x, content, dialog_attr)
            line_y += 1

        # Custom option
        if self.allow_custom:
            num = len(self.options) + 1
            content = f'│  {num}. Custom...'.ljust(width - 1) + '│'
            safe_addstr(stdscr, line_y, start_x, content, dialog_attr)
            line_y += 1

        # Empty line
        safe_addstr(stdscr, line_y, start_x, frame['empty'], dialog_attr)
        line_y += 1

        # Hint line
        max_num = len(self.options) + (1 if self.allow_custom else 0)
        hint = f'Press 1-{max_num} or [Esc] to cancel'
        safe_addstr(stdscr, line_y, start_x, frame['content_line'](hint), dialog_attr)
        line_y += 1

        # Bottom border
        safe_addstr(stdscr, line_y, start_x, frame['bottom'], dialog_attr)

        stdscr.refresh()

    def _render_custom_input(
        self,
        stdscr: Any,
        start_y: int,
        start_x: int,
        width: int,
        height: int,
        dialog_attr: int,
        title_attr: int
    ) -> None:
        """Render the custom text input mode."""
        frame = _render_dialog_frame(width, self.title)

        # Top border
        safe_addstr(stdscr, start_y, start_x, frame['top'], dialog_attr)

        # Title line
        safe_addstr(stdscr, start_y + 1, start_x, '│', dialog_attr)
        safe_addstr(stdscr, start_y + 1, start_x + 1, frame['title_content'], title_attr)
        safe_addstr(stdscr, start_y + 1, start_x + width - 1, '│', dialog_attr)

        # Separator
        safe_addstr(stdscr, start_y + 2, start_x, frame['separator'], dialog_attr)

        # Prompt line
        prompt = '│  Enter custom command:'.ljust(width - 1) + '│'
        safe_addstr(stdscr, start_y + 3, start_x, prompt, dialog_attr)

        # Input line with cursor
        input_display = f'> {self.custom_text}_'
        input_content = f'│  {input_display}'.ljust(width - 1) + '│'
        safe_addstr(stdscr, start_y + 4, start_x, input_content, dialog_attr)

        # Empty line
        safe_addstr(stdscr, start_y + 5, start_x, frame['empty'], dialog_attr)

        # Hint line
        hint = '[Enter] to confirm, [Esc] to cancel'
        safe_addstr(stdscr, start_y + 6, start_x, frame['content_line'](hint), dialog_attr)

        # Bottom border
        safe_addstr(stdscr, start_y + 7, start_x, frame['bottom'], dialog_attr)

        stdscr.refresh()

    def show(self, stdscr: Any) -> str | None:
        """Show the dialog and handle input until a choice is made.

        Args:
            stdscr: Curses window.

        Returns:
            Selected option string, or None if cancelled.
        """
        while True:
            self.render(stdscr)
            key = stdscr.getch()
            result = self.handle_key(key)

            # In selection mode, None from number keys means continue
            # But None from Escape means cancel
            if result is not None:
                return result

            # Check if we got Escape (key 27) outside custom mode
            if not self.in_custom_input_mode and key == 27:
                return None


# Permission bit names in grid order (3 rows x 3 cols)
_GRID_BITS = [
    ['owner_read', 'owner_write', 'owner_exec'],
    ['group_read', 'group_write', 'group_exec'],
    ['other_read', 'other_write', 'other_exec'],
]

# Special bits row
_SPECIAL_BITS = ['setuid', 'setgid', 'sticky']


class ChmodDialog:
    """Dialog for changing file permissions.

    Displays a checkbox grid for rwx permissions and special bits,
    with live octal mode preview.
    """

    def __init__(
        self,
        file_count: int,
        initial_mode: int | None = None,
        initial_states: dict[str, 'TriState'] | None = None,
        has_directory: bool = False,
        filename: str | None = None
    ) -> None:
        """Initialize chmod dialog.

        Args:
            file_count: Number of files being modified.
            initial_mode: Initial mode for single file (ignored if initial_states provided).
            initial_states: Pre-computed tri-states for multiple files.
            has_directory: True if any selected item is a directory.
            filename: Name of single file (for display).
        """
        from tnc.permissions import TriState, get_permission_bits

        self.file_count = file_count
        self.has_directory = has_directory
        self.filename = filename
        self.recursive = False

        # Navigation state
        self.cursor_row = 0  # 0-2 for rwx rows, 3 for special bits, 4 for recursive
        self.cursor_col = 0  # 0-2 for columns
        self.focus_section = 'grid'  # 'grid', 'special', 'recursive', 'buttons'
        self.button_focus = 0  # 0=OK, 1=Cancel
        self.cancelled = False

        # Initialize bit states
        self._bit_states: dict[str, TriState] = {}

        if initial_states is not None:
            self._bit_states = initial_states.copy()
        elif initial_mode is not None:
            bits = get_permission_bits(initial_mode)
            for name, is_set in bits.items():
                self._bit_states[name] = TriState.CHECKED if is_set else TriState.UNCHECKED
        else:
            # Default to 0o644
            bits = get_permission_bits(0o644)
            for name, is_set in bits.items():
                self._bit_states[name] = TriState.CHECKED if is_set else TriState.UNCHECKED

    def get_bit_state(self, bit_name: str) -> 'TriState':
        """Get current state of a permission bit."""
        from tnc.permissions import TriState
        return self._bit_states.get(bit_name, TriState.UNCHECKED)

    def set_bit_state(self, bit_name: str, state: 'TriState') -> None:
        """Set state of a permission bit."""
        self._bit_states[bit_name] = state

    def _get_current_bit_name(self) -> str | None:
        """Get bit name at current cursor position."""
        if self.focus_section == 'grid' and self.cursor_row < 3:
            return _GRID_BITS[self.cursor_row][self.cursor_col]
        elif self.focus_section == 'special':
            if self.cursor_col < len(_SPECIAL_BITS):
                return _SPECIAL_BITS[self.cursor_col]
        return None

    def toggle_current(self) -> None:
        """Toggle the checkbox at current cursor position."""
        from tnc.permissions import TriState

        bit_name = self._get_current_bit_name()
        if bit_name:
            current = self.get_bit_state(bit_name)
            if current == TriState.CHECKED:
                self.set_bit_state(bit_name, TriState.UNCHECKED)
            else:
                # UNCHECKED or MIXED -> CHECKED
                self.set_bit_state(bit_name, TriState.CHECKED)

    def toggle_recursive(self) -> None:
        """Toggle recursive option."""
        self.recursive = not self.recursive

    def handle_key(self, key: int) -> int | None:
        """Handle a keypress.

        Args:
            key: Key code from curses.

        Returns:
            Mode (int) if OK pressed, None if cancelled or continuing.
        """
        import curses

        # Escape cancels
        if key == 27:
            self.cancelled = True
            return None

        # Navigation
        if key == curses.KEY_RIGHT:
            if self.focus_section in ('grid', 'special'):
                self.cursor_col = min(self.cursor_col + 1, 2)
            elif self.focus_section == 'buttons':
                self.button_focus = 1
        elif key == curses.KEY_LEFT:
            if self.focus_section in ('grid', 'special'):
                self.cursor_col = max(self.cursor_col - 1, 0)
            elif self.focus_section == 'buttons':
                self.button_focus = 0
        elif key == curses.KEY_DOWN:
            if self.focus_section == 'grid':
                if self.cursor_row < 2:
                    self.cursor_row += 1
                else:
                    self.focus_section = 'special'
                    self.cursor_col = min(self.cursor_col, 2)
            elif self.focus_section == 'special':
                if self.has_directory:
                    self.focus_section = 'recursive'
                else:
                    self.focus_section = 'buttons'
            elif self.focus_section == 'recursive':
                self.focus_section = 'buttons'
        elif key == curses.KEY_UP:
            if self.focus_section == 'grid' and self.cursor_row > 0:
                self.cursor_row -= 1
            elif self.focus_section == 'special':
                self.focus_section = 'grid'
                self.cursor_row = 2
            elif self.focus_section == 'recursive':
                self.focus_section = 'special'
            elif self.focus_section == 'buttons':
                if self.has_directory:
                    self.focus_section = 'recursive'
                else:
                    self.focus_section = 'special'

        # Toggle with space
        elif key == ord(' '):
            if self.focus_section in ('grid', 'special'):
                self.toggle_current()
            elif self.focus_section == 'recursive':
                self.toggle_recursive()

        # Enter confirms or activates button
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            if self.focus_section == 'buttons':
                if self.button_focus == 0:  # OK
                    return self.get_result_mode()
                else:  # Cancel
                    self.cancelled = True
                    return None
            else:
                # Enter on checkbox toggles it
                if self.focus_section in ('grid', 'special'):
                    self.toggle_current()
                elif self.focus_section == 'recursive':
                    self.toggle_recursive()

        # Tab moves between sections
        elif key == ord('\t'):
            sections = ['grid', 'special']
            if self.has_directory:
                sections.append('recursive')
            sections.append('buttons')

            try:
                idx = sections.index(self.focus_section)
                self.focus_section = sections[(idx + 1) % len(sections)]
                if self.focus_section == 'grid':
                    self.cursor_row = 0
                    self.cursor_col = 0
            except ValueError:
                self.focus_section = 'grid'

        return None  # Continue dialog

    def get_result_mode(self) -> int:
        """Calculate mode from current bit states.

        Returns a mode with only CHECKED bits set. MIXED bits contribute 0.

        Note: When applying to multiple files with mixed permissions, this mode
        is applied uniformly. For bits that remain MIXED (user didn't change),
        those bits will become 0 on all files. This is a known limitation -
        proper per-file preservation would require tracking which bits the user
        explicitly changed and applying only those changes per file.
        """
        from tnc.permissions import TriState, set_permission_bit

        mode = 0
        for bit_name, state in self._bit_states.items():
            if state == TriState.CHECKED:
                mode = set_permission_bit(mode, bit_name, True)

        return mode

    def get_octal_preview(self) -> str:
        """Get octal string for current mode."""
        from tnc.permissions import mode_to_octal_string
        return mode_to_octal_string(self.get_result_mode())

    def get_dimensions(self) -> tuple[int, int]:
        """Calculate dialog dimensions.

        Returns:
            Tuple of (width, height).
        """
        width = 60
        height = 14  # Base height
        if self.has_directory:
            height += 1  # Recursive checkbox
        return width, height

    def render(self, win: Any) -> None:
        """Render the dialog.

        Args:
            win: Curses window to render to.
        """
        from tnc.permissions import TriState

        rows, cols = win.getmaxyx()
        width, height = self.get_dimensions()

        start_y = (rows - height) // 2
        start_x = (cols - width) // 2

        dialog_attr = get_attr(PAIR_DIALOG)
        title_attr = get_attr(PAIR_DIALOG_TITLE)

        # Draw border and title
        title = 'Change Permissions'
        top_border = '┌─ ' + title + ' ' + '─' * (width - len(title) - 5) + '┐'
        try:
            win.addstr(start_y, start_x, top_border, dialog_attr)
        except curses.error:
            pass

        line_y = start_y + 1

        # File info line
        if self.file_count == 1 and self.filename:
            info = f'File: {self.filename}'
        else:
            info = f'Changing permissions for {self.file_count} files'
        self._draw_line(win, line_y, start_x, width, info, dialog_attr)
        line_y += 1

        # Empty line
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Header row
        header = '         Read    Write   Execute'
        self._draw_line(win, line_y, start_x, width, header, dialog_attr)
        line_y += 1

        # Permission grid
        row_labels = ['Owner', 'Group', 'Other']
        for row_idx, label in enumerate(row_labels):
            row_text = f'  {label:6}'
            for col_idx in range(3):
                bit_name = _GRID_BITS[row_idx][col_idx]
                state = self.get_bit_state(bit_name)
                checkbox = self._format_checkbox(state)

                # Highlight if focused
                if (self.focus_section == 'grid' and
                    self.cursor_row == row_idx and
                    self.cursor_col == col_idx):
                    checkbox = f'>{checkbox}<'
                else:
                    checkbox = f' {checkbox} '

                row_text += f'  {checkbox}  '

            self._draw_line(win, line_y, start_x, width, row_text, dialog_attr)
            line_y += 1

        # Empty line
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Special bits row
        special_text = '  Special:'
        special_labels = ['Set UID', 'Set GID', 'Sticky']
        for col_idx, (bit_name, label) in enumerate(zip(_SPECIAL_BITS, special_labels)):
            state = self.get_bit_state(bit_name)
            checkbox = self._format_checkbox(state)

            if self.focus_section == 'special' and self.cursor_col == col_idx:
                special_text += f'  >{checkbox}< {label}'
            else:
                special_text += f'   {checkbox}  {label}'

        self._draw_line(win, line_y, start_x, width, special_text, dialog_attr)
        line_y += 1

        # Empty line
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Octal preview
        octal = self.get_octal_preview()
        self._draw_line(win, line_y, start_x, width, f'  Mode: {octal}', dialog_attr)
        line_y += 1

        # Recursive option (only for directories)
        if self.has_directory:
            self._draw_line(win, line_y, start_x, width, '', dialog_attr)
            line_y += 1

            checkbox = '[x]' if self.recursive else '[ ]'
            if self.focus_section == 'recursive':
                recursive_text = f'  >{checkbox}< Apply recursively'
            else:
                recursive_text = f'   {checkbox}  Apply recursively'
            self._draw_line(win, line_y, start_x, width, recursive_text, dialog_attr)
            line_y += 1

        # Empty line before buttons
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Buttons
        ok_btn = '[  OK  ]' if self.focus_section != 'buttons' or self.button_focus != 0 else '[ >OK< ]'
        cancel_btn = '[Cancel]' if self.focus_section != 'buttons' or self.button_focus != 1 else '[>Cancel<]'
        buttons = f'{ok_btn}  {cancel_btn}'.center(width - 4)
        self._draw_line(win, line_y, start_x, width, buttons, dialog_attr)
        line_y += 1

        # Bottom border
        bottom_border = '└' + '─' * (width - 2) + '┘'
        try:
            win.addstr(line_y, start_x, bottom_border, dialog_attr)
        except curses.error:
            pass

        win.refresh()

    def _draw_line(self, win: Any, y: int, x: int, width: int, content: str, attr: int) -> None:
        """Draw a line with borders."""
        line = '│ ' + content.ljust(width - 4) + ' │'
        try:
            win.addstr(y, x, line, attr)
        except curses.error:
            pass

    def _format_checkbox(self, state: 'TriState') -> str:
        """Format checkbox based on state."""
        from tnc.permissions import TriState
        if state == TriState.CHECKED:
            return '[x]'
        elif state == TriState.MIXED:
            return '[~]'
        else:
            return '[ ]'

    def show(self, win: Any) -> int | None:
        """Show dialog and handle input until done.

        Args:
            win: Curses window.

        Returns:
            New mode (int) or None if cancelled.
        """
        while True:
            self.render(win)
            key = win.getch()
            result = self.handle_key(key)

            if result is not None:
                return result

            # Check if cancelled (Escape or Cancel button)
            if self.cancelled:
                return None


def chmod_dialog(
    win: Any,
    file_count: int,
    initial_mode: int | None = None,
    initial_states: dict[str, Any] | None = None,
    has_directory: bool = False,
    filename: str | None = None
) -> tuple[int, bool] | None:
    """Show chmod dialog and return result.

    Args:
        win: Curses window.
        file_count: Number of files being modified.
        initial_mode: Initial mode for single file.
        initial_states: Pre-computed tri-states for multiple files.
        has_directory: True if any selected item is a directory.
        filename: Name of single file (for display).

    Returns:
        Tuple of (mode, recursive) or None if cancelled.
    """
    dialog = ChmodDialog(
        file_count=file_count,
        initial_mode=initial_mode,
        initial_states=initial_states,
        has_directory=has_directory,
        filename=filename
    )

    result = dialog.show(win)
    if result is not None:
        return (result, dialog.recursive)
    return None


class ChownDialog:
    """Dialog for changing file ownership.

    Displays text input fields for owner and group with autocomplete.
    """

    def __init__(
        self,
        file_count: int,
        current_owner: str,
        current_group: str,
        users: list[str] | None = None,
        groups: list[str] | None = None,
        filename: str | None = None
    ) -> None:
        """Initialize chown dialog.

        Args:
            file_count: Number of files being modified.
            current_owner: Current owner name.
            current_group: Current group name.
            users: List of available usernames (fetched if None).
            groups: List of available group names (fetched if None).
            filename: Name of single file (for display).
        """
        from tnc.permissions import get_system_users, get_system_groups

        self.file_count = file_count
        self.filename = filename
        self.owner_input = current_owner
        self.group_input = current_group
        self.cancelled = False

        # Get system users/groups if not provided
        self.users = users if users is not None else get_system_users()
        self.groups = groups if groups is not None else get_system_groups()

        # Input state
        self.active_field = 'owner'  # 'owner', 'group', 'buttons'
        self.cursor_pos = len(current_owner)
        self.autocomplete_index = -1  # -1 means no selection
        self.button_focus = 0  # 0=OK, 1=Cancel

    def get_autocomplete_suggestions(self) -> list[str]:
        """Get autocomplete suggestions for current field."""
        from tnc.permissions import filter_by_prefix

        if self.active_field == 'owner':
            return filter_by_prefix(self.users, self.owner_input)
        elif self.active_field == 'group':
            return filter_by_prefix(self.groups, self.group_input)
        return []

    def handle_key(self, key: int) -> bool:
        """Handle a keypress.

        Args:
            key: Key code from curses.

        Returns:
            True if dialog should close.
        """
        import curses

        # Escape cancels
        if key == 27:
            self.cancelled = True
            return True

        # Tab switches fields
        if key == ord('\t'):
            if self.active_field == 'owner':
                self.active_field = 'group'
                self.cursor_pos = len(self.group_input)
            elif self.active_field == 'group':
                self.active_field = 'buttons'
            else:
                self.active_field = 'owner'
                self.cursor_pos = len(self.owner_input)
            self.autocomplete_index = -1
            return False

        # Arrow keys for autocomplete navigation
        if key == curses.KEY_DOWN:
            suggestions = self.get_autocomplete_suggestions()
            if suggestions and self.active_field in ('owner', 'group'):
                self.autocomplete_index = min(
                    self.autocomplete_index + 1,
                    len(suggestions) - 1
                )
            elif self.active_field == 'buttons':
                pass  # No down from buttons
            return False

        if key == curses.KEY_UP:
            if self.autocomplete_index >= 0:
                self.autocomplete_index -= 1
            return False

        if key == curses.KEY_LEFT:
            if self.active_field == 'buttons':
                self.button_focus = 0
            return False

        if key == curses.KEY_RIGHT:
            if self.active_field == 'buttons':
                self.button_focus = 1
            return False

        # Enter - select autocomplete or confirm
        if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            suggestions = self.get_autocomplete_suggestions()
            if self.autocomplete_index >= 0 and self.autocomplete_index < len(suggestions):
                # Select from autocomplete
                selected = suggestions[self.autocomplete_index]
                if self.active_field == 'owner':
                    self.owner_input = selected
                    self.cursor_pos = len(selected)
                elif self.active_field == 'group':
                    self.group_input = selected
                    self.cursor_pos = len(selected)
                self.autocomplete_index = -1
                return False
            elif self.active_field == 'buttons':
                if self.button_focus == 1:  # Cancel
                    self.cancelled = True
                return True  # Close dialog
            else:
                # Move to next field
                if self.active_field == 'owner':
                    self.active_field = 'group'
                    self.cursor_pos = len(self.group_input)
                elif self.active_field == 'group':
                    self.active_field = 'buttons'
                self.autocomplete_index = -1
            return False

        # Backspace
        if key in (curses.KEY_BACKSPACE, 127, ord('\b')):
            if self.active_field == 'owner' and self.owner_input:
                self.owner_input = self.owner_input[:-1]
                self.cursor_pos = len(self.owner_input)
            elif self.active_field == 'group' and self.group_input:
                self.group_input = self.group_input[:-1]
                self.cursor_pos = len(self.group_input)
            self.autocomplete_index = -1
            return False

        # Printable characters
        if 32 <= key <= 126:
            char = chr(key)
            if self.active_field == 'owner':
                self.owner_input += char
                self.cursor_pos = len(self.owner_input)
            elif self.active_field == 'group':
                self.group_input += char
                self.cursor_pos = len(self.group_input)
            self.autocomplete_index = -1
            return False

        return False

    def get_result(self) -> tuple[str, str]:
        """Get current owner and group values."""
        return (self.owner_input, self.group_input)

    def get_dimensions(self) -> tuple[int, int]:
        """Calculate dialog dimensions."""
        width = 60
        height = 12
        # Add height for autocomplete dropdown
        suggestions = self.get_autocomplete_suggestions()
        if suggestions:
            height += min(len(suggestions), 5) + 1
        return width, height

    def render(self, win: Any) -> None:
        """Render the dialog."""
        rows, cols = win.getmaxyx()
        width, height = self.get_dimensions()

        start_y = (rows - height) // 2
        start_x = (cols - width) // 2

        dialog_attr = get_attr(PAIR_DIALOG)
        title_attr = get_attr(PAIR_DIALOG_TITLE)

        # Draw border and title
        title = 'Change Ownership'
        top_border = '┌─ ' + title + ' ' + '─' * (width - len(title) - 5) + '┐'
        try:
            win.addstr(start_y, start_x, top_border, dialog_attr)
        except curses.error:
            pass

        line_y = start_y + 1

        # File info line
        if self.file_count == 1 and self.filename:
            info = f'File: {self.filename}'
        else:
            info = f'Changing ownership for {self.file_count} files'
        self._draw_line(win, line_y, start_x, width, info, dialog_attr)
        line_y += 1

        # Empty line
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Owner field
        owner_label = 'Owner: '
        owner_field = self.owner_input + ('_' if self.active_field == 'owner' else '')
        owner_line = f'  {owner_label}[{owner_field.ljust(20)}]'
        self._draw_line(win, line_y, start_x, width, owner_line, dialog_attr)
        line_y += 1

        # Autocomplete for owner
        if self.active_field == 'owner':
            suggestions = self.get_autocomplete_suggestions()[:5]
            for i, suggestion in enumerate(suggestions):
                prefix = '> ' if i == self.autocomplete_index else '  '
                self._draw_line(win, line_y, start_x, width, f'         {prefix}{suggestion}', dialog_attr)
                line_y += 1

        # Empty line
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Group field
        group_label = 'Group: '
        group_field = self.group_input + ('_' if self.active_field == 'group' else '')
        group_line = f'  {group_label}[{group_field.ljust(20)}]'
        self._draw_line(win, line_y, start_x, width, group_line, dialog_attr)
        line_y += 1

        # Autocomplete for group
        if self.active_field == 'group':
            suggestions = self.get_autocomplete_suggestions()[:5]
            for i, suggestion in enumerate(suggestions):
                prefix = '> ' if i == self.autocomplete_index else '  '
                self._draw_line(win, line_y, start_x, width, f'         {prefix}{suggestion}', dialog_attr)
                line_y += 1

        # Empty line
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Note about privileges
        note = 'Note: Changing owner typically requires root'
        self._draw_line(win, line_y, start_x, width, f'  {note}', dialog_attr)
        line_y += 1

        # Empty line before buttons
        self._draw_line(win, line_y, start_x, width, '', dialog_attr)
        line_y += 1

        # Buttons
        ok_btn = '[  OK  ]' if self.active_field != 'buttons' or self.button_focus != 0 else '[ >OK< ]'
        cancel_btn = '[Cancel]' if self.active_field != 'buttons' or self.button_focus != 1 else '[>Cancel<]'
        buttons = f'{ok_btn}  {cancel_btn}'.center(width - 4)
        self._draw_line(win, line_y, start_x, width, buttons, dialog_attr)
        line_y += 1

        # Bottom border
        bottom_border = '└' + '─' * (width - 2) + '┘'
        try:
            win.addstr(line_y, start_x, bottom_border, dialog_attr)
        except curses.error:
            pass

        win.refresh()

    def _draw_line(self, win: Any, y: int, x: int, width: int, content: str, attr: int) -> None:
        """Draw a line with borders."""
        line = '│ ' + content.ljust(width - 4) + ' │'
        try:
            win.addstr(y, x, line, attr)
        except curses.error:
            pass

    def show(self, win: Any) -> tuple[str, str] | None:
        """Show dialog and handle input until done.

        Returns:
            Tuple of (owner, group) or None if cancelled.
        """
        while True:
            self.render(win)
            key = win.getch()
            if self.handle_key(key):
                if self.cancelled:
                    return None
                return self.get_result()


def chown_dialog(
    win: Any,
    file_count: int,
    current_owner: str,
    current_group: str,
    filename: str | None = None
) -> tuple[str, str] | None:
    """Show chown dialog and return result.

    Args:
        win: Curses window.
        file_count: Number of files being modified.
        current_owner: Current owner name.
        current_group: Current group name.
        filename: Name of single file (for display).

    Returns:
        Tuple of (owner, group) or None if cancelled.
    """
    dialog = ChownDialog(
        file_count=file_count,
        current_owner=current_owner,
        current_group=current_group,
        filename=filename
    )

    return dialog.show(win)


class InputDialog:
    """A modal text input dialog with full editing support.

    Displays a centered dialog box with a title, prompt text, and an
    editable text field. Supports cursor movement (arrows, Home/End),
    character deletion (Backspace, Delete), and text insertion at cursor.

    Attributes:
        title: Dialog title displayed in the title bar.
        prompt: Prompt text displayed above the input field.
        text: Current text in the input field.
        cursor_pos: Current cursor position within text.
    """

    MIN_WIDTH = 40

    def __init__(
        self,
        title: str,
        prompt: str,
        default_value: str = ''
    ) -> None:
        """Initialize the input dialog.

        Args:
            title: Dialog title.
            prompt: Prompt text shown above input field.
            default_value: Initial text in the input field.
        """
        self.title = title
        self.prompt = prompt
        self.text = default_value
        self.cursor_pos = len(default_value)

    def handle_key(self, key: int) -> str | None:
        """Handle a keypress and return result if dialog should close.

        Args:
            key: Key code from curses.

        Returns:
            - str: The input text (Enter pressed). May be empty.
            - None: Dialog should continue (character typed, cursor moved)
              or dialog was cancelled (Escape). Callers should check the
              key value to distinguish; see show() for the pattern.
        """
        # Enter confirms
        if key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
            return self.text

        # Escape cancels
        if key == 27:
            return None

        # Backspace
        if key in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.text = (self.text[:self.cursor_pos - 1]
                             + self.text[self.cursor_pos:])
                self.cursor_pos -= 1
            return None

        # Delete
        if key == curses.KEY_DC:
            if self.cursor_pos < len(self.text):
                self.text = (self.text[:self.cursor_pos]
                             + self.text[self.cursor_pos + 1:])
            return None

        # Left arrow
        if key == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            return None

        # Right arrow
        if key == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.text):
                self.cursor_pos += 1
            return None

        # Home
        if key == curses.KEY_HOME:
            self.cursor_pos = 0
            return None

        # End
        if key == curses.KEY_END:
            self.cursor_pos = len(self.text)
            return None

        # Printable character
        if 32 <= key <= 126:
            ch = chr(key)
            self.text = (self.text[:self.cursor_pos]
                         + ch
                         + self.text[self.cursor_pos:])
            self.cursor_pos += 1
            return None

        return None

    def render(self, stdscr: Any) -> None:
        """Render the dialog to the screen.

        Args:
            stdscr: Curses window to render to.
        """
        rows, cols = stdscr.getmaxyx()

        # Calculate width
        content_width = max(len(self.title), len(self.prompt), len(self.text) + 4)
        width = max(content_width + 6, self.MIN_WIDTH)
        # Clamp to terminal width
        if width > cols - 2:
            width = max(cols - 2, 20)

        inner = width - 2
        # Max visible text length (account for "> " prefix and borders)
        max_text_len = max(inner - 4, 1)  # At least 1 char visible

        # Build the visible text with cursor
        # Scroll text if it's longer than visible area
        visible_start = 0
        if self.cursor_pos > max_text_len:
            visible_start = self.cursor_pos - max_text_len
        visible_text = self.text[visible_start:visible_start + max_text_len]
        cursor_visual = self.cursor_pos - visible_start

        input_display = '> ' + visible_text

        # Content lines
        lines = [
            self.prompt,
            input_display,
            '',
        ]

        footer = '[Enter] OK  [Esc] Cancel'

        # Height: top + title + sep + empty + lines + footer_sep + footer + bottom
        height = 5 + len(lines) + 2

        # Center
        y = (rows - height) // 2
        x = (cols - width) // 2
        if x < 1:
            x = 1
        if y < 0:
            y = 0

        dialog_attr = get_attr(PAIR_DIALOG)
        title_attr = get_attr(PAIR_DIALOG_TITLE)
        frame = _render_dialog_frame(width, self.title)

        # Top border
        safe_addstr(stdscr, y, x, frame['top'], dialog_attr)

        # Title line
        safe_addstr(stdscr, y + 1, x, '│', dialog_attr)
        safe_addstr(stdscr, y + 1, x + 1, frame['title_content'], title_attr)
        safe_addstr(stdscr, y + 1, x + width - 1, '│', dialog_attr)

        # Separator
        safe_addstr(stdscr, y + 2, x, frame['separator'], dialog_attr)

        # Empty line before prompt
        safe_addstr(stdscr, y + 3, x, frame['empty'], dialog_attr)

        # Content lines
        for i, line in enumerate(lines):
            safe_addstr(stdscr, y + 4 + i, x,
                        frame['content_line'](line), dialog_attr)

        # Footer separator
        footer_y = y + 4 + len(lines)
        safe_addstr(stdscr, footer_y, x, frame['separator'], dialog_attr)

        # Footer
        safe_addstr(stdscr, footer_y + 1, x,
                    frame['content_line'](footer), dialog_attr)

        # Bottom border
        safe_addstr(stdscr, footer_y + 2, x, frame['bottom'], dialog_attr)

        # Position cursor on the input field for visual feedback
        cursor_y = y + 5  # Input line (prompt is y+4, input is y+5)
        cursor_x = x + 4 + cursor_visual  # "│ > " = 4 chars offset
        try:
            stdscr.move(cursor_y, cursor_x)
        except curses.error:
            pass

        stdscr.refresh()

    def show(self, stdscr: Any) -> str | None:
        """Show the dialog and handle input until confirmed or cancelled.

        Args:
            stdscr: Curses window.

        Returns:
            The entered text string on Enter, or None if cancelled (Escape).
        """
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        try:
            while True:
                self.render(stdscr)
                key = stdscr.getch()
                result = self.handle_key(key)

                if result is not None:
                    return result

                if key == 27:
                    return None
        finally:
            try:
                curses.curs_set(0)
            except curses.error:
                pass


def input_dialog(
    win: Any,
    title: str,
    prompt: str,
    default_value: str = ''
) -> str:
    """Show a modal text input dialog.

    Args:
        win: Curses window to draw on.
        title: Dialog title.
        prompt: Prompt text shown above input field.
        default_value: Initial text in the input field.

    Returns:
        The entered text, or empty string if cancelled.
    """
    dialog = InputDialog(title, prompt, default_value)
    result = dialog.show(win)
    return result if result is not None else ''
