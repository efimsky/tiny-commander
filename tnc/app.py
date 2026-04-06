"""Main application class for Tiny Commander."""

import curses
import os
import shlex
import stat
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable

from tnc.colors import init_colors, is_classic_theme, set_classic_theme
from tnc.command_line import CommandLine
from tnc.config import Config
from tnc.dialog import (
    CursesOverwriteHandler,
    SelectionDialog,
    confirm_dialog,
    input_dialog,
    show_error_dialog,
    show_summary,
)
from tnc.file_ops import (
    CopyResult,
    MoveResult,
    RenameResult,
    copy_files_with_overwrite,
    move_files_with_overwrite,
    rename_file,
)
from tnc.function_bar import FunctionBar
from tnc.menu import MenuBar
from tnc.panel import Panel
from tnc.status_bar import StatusBar


class Action(Enum):
    """Actions that can be triggered by key presses."""

    NONE = auto()
    QUIT = auto()
    COPY = auto()
    MOVE = auto()
    MKDIR = auto()
    DELETE = auto()
    VIEW = auto()
    EDIT = auto()
    SELECT_PATTERN = auto()
    DESELECT_PATTERN = auto()
    CREATE_FILE = auto()
    MEASURE_DIR_SIZE = auto()
    CYCLE_SORT = auto()
    TOGGLE_SORT_REVERSE = auto()
    OPEN_IN_FINDER = auto()  # macOS only
    # Menu-triggered actions
    RENAME = auto()
    TOGGLE_SELECT = auto()
    SELECT_ALL = auto()
    DESELECT_ALL = auto()
    INVERT_SELECTION = auto()
    TOGGLE_HIDDEN = auto()
    EDITOR_SETTINGS = auto()
    PAGER_SETTINGS = auto()
    TOGGLE_CLASSIC_COLORS = auto()
    TOGGLE_MOUSE = auto()
    TOGGLE_MOUSE_SWAP = auto()
    MENU = auto()  # Toggle menu dropdown
    CHMOD = auto()  # Change permissions
    CHOWN = auto()  # Change ownership
    # Panel-specific sort actions
    SORT_NAME_LEFT = auto()
    SORT_SIZE_LEFT = auto()
    SORT_DATE_LEFT = auto()
    SORT_EXT_LEFT = auto()
    SORT_NAME_RIGHT = auto()
    SORT_SIZE_RIGHT = auto()
    SORT_DATE_RIGHT = auto()
    SORT_EXT_RIGHT = auto()
    REVERSE_SORT_LEFT = auto()
    REVERSE_SORT_RIGHT = auto()


# Map menu action strings to Action enum values
MENU_ACTION_MAP: dict[str, Action] = {
    'view': Action.VIEW,
    'edit': Action.EDIT,
    'copy': Action.COPY,
    'move': Action.MOVE,
    'delete': Action.DELETE,
    'rename': Action.RENAME,
    'mkdir': Action.MKDIR,
    'open_in_finder': Action.OPEN_IN_FINDER,
    'toggle_select': Action.TOGGLE_SELECT,
    'select_all': Action.SELECT_ALL,
    'deselect_all': Action.DESELECT_ALL,
    'invert_selection': Action.INVERT_SELECTION,
    'select_pattern': Action.SELECT_PATTERN,
    'toggle_hidden': Action.TOGGLE_HIDDEN,
    'editor_settings': Action.EDITOR_SETTINGS,
    'pager_settings': Action.PAGER_SETTINGS,
    'toggle_classic_colors': Action.TOGGLE_CLASSIC_COLORS,
    'toggle_mouse': Action.TOGGLE_MOUSE,
    'toggle_mouse_swap': Action.TOGGLE_MOUSE_SWAP,
    'sort_name_left': Action.SORT_NAME_LEFT,
    'sort_size_left': Action.SORT_SIZE_LEFT,
    'sort_date_left': Action.SORT_DATE_LEFT,
    'sort_ext_left': Action.SORT_EXT_LEFT,
    'sort_name_right': Action.SORT_NAME_RIGHT,
    'sort_size_right': Action.SORT_SIZE_RIGHT,
    'sort_date_right': Action.SORT_DATE_RIGHT,
    'sort_ext_right': Action.SORT_EXT_RIGHT,
    'reverse_sort_left': Action.REVERSE_SORT_LEFT,
    'reverse_sort_right': Action.REVERSE_SORT_RIGHT,
    'chmod': Action.CHMOD,
    'chown': Action.CHOWN,
}

# Data-driven mapping for panel-specific sort actions
# Maps Action -> (panel_attr, sort_type) where sort_type is None for reverse
_SORT_ACTIONS: dict[Action, tuple[str, str | None]] = {
    Action.SORT_NAME_LEFT: ('left_panel', 'name'),
    Action.SORT_SIZE_LEFT: ('left_panel', 'size'),
    Action.SORT_DATE_LEFT: ('left_panel', 'date'),
    Action.SORT_EXT_LEFT: ('left_panel', 'extension'),
    Action.REVERSE_SORT_LEFT: ('left_panel', None),
    Action.SORT_NAME_RIGHT: ('right_panel', 'name'),
    Action.SORT_SIZE_RIGHT: ('right_panel', 'size'),
    Action.SORT_DATE_RIGHT: ('right_panel', 'date'),
    Action.SORT_EXT_RIGHT: ('right_panel', 'extension'),
    Action.REVERSE_SORT_RIGHT: ('right_panel', None),
}


@dataclass
class ViewResult:
    """Result of a view/edit operation."""

    success: bool
    error: str = ''


class App:
    """Main application class managing the curses interface."""

    def __init__(self, stdscr: Any) -> None:
        """Initialize the application with a curses screen."""
        self.stdscr = stdscr
        self.running = False
        self.left_panel: Panel | None = None
        self.right_panel: Panel | None = None
        self.active_panel: Panel | None = None
        self.command_line: CommandLine | None = None
        self.menu: MenuBar | None = None
        self.status_bar: StatusBar | None = None
        self.function_bar: FunctionBar | None = None
        self.config: Config = Config()
        self.escape_pending: bool = False  # For double-Escape to clear command line
        self._mouse_active: bool = False  # Whether mouse events are currently enabled

    @property
    def menu_visible(self) -> bool:
        """Return True if menu bar is visible."""
        return self.menu is not None and self.menu.visible

    @property
    def mouse_enabled(self) -> bool:
        """Return True if mouse support is currently active."""
        return self._mouse_active

    def setup(self) -> None:
        """Configure curses environment for the application."""
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.nodelay(False)

        # Load config and apply color theme before initializing colors
        self.config = Config.load(Config.default_path())
        set_classic_theme(self.config.classic_colors)
        init_colors()

        # Enable mouse support if configured
        if self.config.mouse_enabled:
            self._enable_mouse()

        # Initialize panels
        self._init_panels()

        # Initialize action handler dispatch dictionary
        self._action_handlers = self._init_action_handlers()

    def _init_action_handlers(self) -> dict[Action, Callable[[], None]]:
        """Initialize the action handler dispatch dictionary.

        Returns a dictionary mapping Action enum values to handler functions.
        QUIT and NONE are handled separately in the run loop.
        """
        return {
            # File operations
            Action.COPY: self.do_copy,
            Action.MOVE: self.do_move,
            Action.VIEW: self._handle_view,
            Action.EDIT: self._handle_edit,
            Action.DELETE: self._prompt_delete,
            Action.MKDIR: self._prompt_mkdir,
            Action.CREATE_FILE: self._prompt_create_file,
            Action.RENAME: self._prompt_rename,
            # Selection operations
            Action.TOGGLE_SELECT: lambda: self.active_panel.toggle_selection(),
            Action.SELECT_PATTERN: self._prompt_select_pattern,
            Action.DESELECT_PATTERN: self._prompt_deselect_pattern,
            Action.SELECT_ALL: lambda: self.active_panel.select_all(),
            Action.DESELECT_ALL: lambda: self.active_panel.selected.clear(),
            Action.INVERT_SELECTION: lambda: self.active_panel.invert_selection(),
            # Sort operations (active panel)
            Action.CYCLE_SORT: lambda: self.active_panel.cycle_sort(),
            Action.TOGGLE_SORT_REVERSE: lambda: self.active_panel.toggle_sort_reverse(),
            Action.TOGGLE_HIDDEN: lambda: self.active_panel.toggle_hidden(),
            # Directory operations
            Action.MEASURE_DIR_SIZE: self._measure_dir_size,
            Action.OPEN_IN_FINDER: self.open_in_finder,
            # Settings
            Action.EDITOR_SETTINGS: self._prompt_editor_setup,
            Action.PAGER_SETTINGS: self._prompt_pager_setup,
            Action.TOGGLE_CLASSIC_COLORS: self._toggle_classic_colors,
            Action.TOGGLE_MOUSE: self._toggle_mouse,
            Action.TOGGLE_MOUSE_SWAP: self._toggle_mouse_swap,
            Action.MENU: self._toggle_menu_dropdown,
            # Permission operations
            Action.CHMOD: self._prompt_chmod,
            Action.CHOWN: self._prompt_chown,
            # Panel-specific sort operations (data-driven)
            **{action: (lambda a=action: self._handle_sort_action(a))
               for action in _SORT_ACTIONS},
        }

    def _handle_view(self) -> None:
        """Handle VIEW action with error display."""
        result = self.view_current_file()
        if not result.success:
            self._show_error(result.error)

    def _handle_edit(self) -> None:
        """Handle EDIT action with error display."""
        result = self.edit_current_file()
        if not result.success:
            self._show_error(result.error)

    def _handle_sort_action(self, action: Action) -> None:
        """Handle panel-specific sort actions using data-driven mapping.

        Args:
            action: The sort action to handle.
        """
        panel_attr, sort_type = _SORT_ACTIONS[action]
        panel = getattr(self, panel_attr)
        if sort_type is None:
            panel.toggle_sort_reverse()
        else:
            panel.sort_by(sort_type)

    def _init_panels(self) -> None:
        """Initialize the two panels."""
        rows, cols = self.stdscr.getmaxyx()
        panel_width = cols // 2
        # Leave room for menu bar, status bar, command line, and function bar
        panel_height = rows - 4

        cwd = os.getcwd()
        self.left_panel = Panel(cwd, width=panel_width, height=panel_height)
        self.right_panel = Panel(cwd, width=panel_width, height=panel_height)

        # Left panel is active by default
        self.left_panel.is_active = True
        self.right_panel.is_active = False
        self.active_panel = self.left_panel

        # Initialize command line with active panel's path
        self.command_line = CommandLine(str(self.active_panel.path))

        # Initialize menu bar
        self.menu = MenuBar()

        # Initialize status bar
        self.status_bar = StatusBar()

        # Initialize function key bar
        self.function_bar = FunctionBar()

    def handle_resize(self) -> None:
        """Handle terminal resize event."""
        rows, cols = self.stdscr.getmaxyx()
        panel_width = cols // 2
        # Panel height: rows - 4 (menu bar + status bar + command line + function bar)
        panel_height = rows - 4

        if self.left_panel:
            self.left_panel.resize(panel_width, panel_height)
        if self.right_panel:
            self.right_panel.resize(panel_width, panel_height)

    def cleanup(self) -> None:
        """Restore terminal state."""
        try:
            curses.curs_set(1)
        except curses.error:
            pass

    def run(self) -> int:
        """Run the main application loop. Returns exit code."""
        self.running = True
        while self.running:
            self.draw()
            key = self.stdscr.getch()

            # Get action from input event
            action = Action.NONE
            if key == curses.KEY_RESIZE:
                self.handle_resize()
            elif key == curses.KEY_MOUSE and self._mouse_active:
                try:
                    _, x, y, _, button_state = curses.getmouse()
                except curses.error:
                    pass  # Mouse event parsing failed, ignore
                else:
                    button_state = self._translate_button_state(button_state)
                    action = self.handle_mouse(x, y, button_state)
            else:
                action = self.handle_key(key)

            # Process action (from both keyboard and mouse)
            if action == Action.QUIT:
                self.running = False
            elif handler := self._action_handlers.get(action):
                handler()
        return 0

    def draw(self) -> None:
        """Draw the interface."""
        # Clear function bar click feedback from previous frame
        self.function_bar.clear_click_feedback()

        # Use erase() instead of clear() to reduce flicker.
        # clear() forces a full terminal redraw; erase() only clears the buffer.
        self.stdscr.erase()
        rows, cols = self.stdscr.getmaxyx()

        # Layout: menu | panels | status bar | command line | function bar
        # Menu bar is always visible (row 0), panels start at row 1
        panel_y = 1
        panel_height = rows - 4  # menu(1) + status(1) + cmdline(1) + funcbar(1)

        # Resize panels if needed
        panel_width = cols // 2
        if self.left_panel.height != panel_height:
            self.left_panel.resize(panel_width, panel_height)
            self.right_panel.resize(panel_width, panel_height)

        # Draw panels (always exist after setup)
        self.left_panel.render(self.stdscr, 0, panel_y)
        self.right_panel.render(self.stdscr, self.left_panel.width, panel_y)

        # Draw menu bar on top (always visible)
        self.menu.render(self.stdscr, 0, cols)
        self.menu.render_dropdown(self.stdscr, 1, cols)

        # Draw status bar (row before command line)
        is_left = self.active_panel == self.left_panel
        hint = '[Esc] again to clear' if self.escape_pending else None
        self.status_bar.render(self.stdscr, rows - 3, cols, self.active_panel, is_left, hint)

        # Draw command line (row before function bar)
        cursor_x = self.command_line.render(self.stdscr, rows - 2, cols)

        # Draw function key bar at bottom
        self.function_bar.render(self.stdscr, rows - 1, cols)

        # Show cursor on command line (like mc)
        curses.curs_set(1)
        self.stdscr.move(rows - 2, min(cursor_x, cols - 1))

        # Use noutrefresh() + doupdate() for atomic screen update to reduce flicker.
        # This batches all changes before sending to the terminal.
        self.stdscr.noutrefresh()
        curses.doupdate()

    def handle_key(self, key: int) -> Action:
        """Handle a key press and return the resulting action."""
        # Clear escape_pending on any key that's not Escape
        if key != 27:
            self.escape_pending = False

        if key == curses.KEY_F10:
            return Action.QUIT

        # Handle search mode input first
        if self.active_panel.search_mode:
            if key == 27:  # Escape
                self.active_panel.exit_search(confirm=False)
                return Action.NONE
            elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                self.active_panel.exit_search(confirm=True)
                return Action.NONE
            elif key in (curses.KEY_BACKSPACE, 127, ord('\b')):
                self.active_panel.handle_search_backspace()
                return Action.NONE
            elif 32 <= key <= 126:  # Printable ASCII
                self.active_panel.handle_search_char(chr(key))
                return Action.NONE
            # Allow navigation keys (down/up) to still work in search mode

        # Handle menu keys when menu is visible
        if self.menu and self.menu.visible:
            result = self.menu.handle_key(key)
            if result is False:
                pass  # Key not handled by menu, continue
            elif result is True:
                return Action.NONE  # Key handled, no action
            elif isinstance(result, str):
                # Menu item selected - convert action string to Action enum
                if result and result in MENU_ACTION_MAP:
                    return MENU_ACTION_MAP[result]
                return Action.NONE  # Empty action or unknown action

        # Handle Escape key - check for Alt+key sequences or double-escape
        # Note: Alt+Enter is handled here as Escape+Enter because many terminals
        # send it this way, unlike Alt+Fn which uses KEY_F(n+48) directly.
        if key == 27:
            next_key = self._get_next_key_if_available()
            if next_key in (curses.KEY_ENTER, ord('\r'), ord('\n')):
                # Alt+Enter - insert filename into command line
                self._insert_filename_to_command_line()
            elif next_key in (ord('o'), ord('O')):
                # Alt+O - open in Finder (macOS only)
                if sys.platform == 'darwin':
                    return Action.OPEN_IN_FINDER
                return Action.NONE
            elif next_key != -1:
                # Got a different key after Escape - push it back for processing
                curses.ungetch(next_key)
            else:
                # Plain Escape - handle double-escape for command line
                if self.command_line.input_text:
                    if self.escape_pending:
                        # Second Escape - clear command line
                        self.command_line.handle_key(27)
                        self.escape_pending = False
                    else:
                        # First Escape - show hint
                        self.escape_pending = True
            return Action.NONE

        # Handle Ctrl+X chord (ASCII 24) for chmod/chown
        if key == 24:  # Ctrl+X
            next_key = self._get_next_key_if_available()
            if next_key in (ord('c'), ord('C')):
                return Action.CHMOD
            elif next_key in (ord('o'), ord('O')):
                return Action.CHOWN
            elif next_key != -1:
                # Got a different key after Ctrl+X - push it back for processing
                curses.ungetch(next_key)
            return Action.NONE

        # Command line editing keys: arrows, backspace, delete
        command_line_keys = (
            curses.KEY_LEFT,
            curses.KEY_RIGHT,
            curses.KEY_BACKSPACE,
            curses.KEY_DC,
            127,        # Backspace (alternate)
            ord('\b'),  # Backspace (ctrl+h)
        )
        if key in command_line_keys:
            self.command_line.handle_key(key)
            return Action.NONE

        # Try navigation keys
        if (result := self._handle_navigation_key(key)) is not None:
            return result

        # Try selection keys
        if (result := self._handle_selection_key(key)) is not None:
            return result

        # Try operation keys
        if (result := self._handle_operation_key(key)) is not None:
            return result

        # Printable ASCII characters go to command line
        if 32 <= key <= 126:
            self.command_line.handle_char(chr(key))

        return Action.NONE

    def _handle_navigation_key(self, key: int) -> Action | None:
        """Handle navigation keys (arrows, home, end, page up/down, tab).

        Args:
            key: Key code from curses.

        Returns:
            Action.NONE if key was handled, None if not a navigation key.
        """
        if key == curses.KEY_DOWN:
            self.active_panel.navigate_down()
            return Action.NONE
        elif key == curses.KEY_UP:
            self.active_panel.navigate_up()
            return Action.NONE
        elif key == curses.KEY_HOME:
            self.active_panel.navigate_to_top()
            return Action.NONE
        elif key == curses.KEY_END:
            self.active_panel.navigate_to_bottom()
            return Action.NONE
        elif key == curses.KEY_PPAGE:
            self.active_panel.navigate_page_up()
            return Action.NONE
        elif key == curses.KEY_NPAGE:
            self.active_panel.navigate_page_down()
            return Action.NONE
        elif key in (curses.KEY_ENTER, ord('\r'), ord('\n')):
            # Enter key - execute command if command line has text, else enter directory
            if self.command_line.input_text:
                self._execute_command()
            else:
                file_path = self.active_panel.enter()
                self.command_line.set_path(str(self.active_panel.path))
                # If enter() returned a file path, check if it's executable
                if file_path and self._is_executable(file_path):
                    self._execute_file(file_path)
            return Action.NONE
        elif key == ord('\t'):
            self.switch_panel()
            return Action.NONE
        return None

    def _handle_selection_key(self, key: int) -> Action | None:
        """Handle selection keys (insert, space, *, +, -, /).

        Args:
            key: Key code from curses.

        Returns:
            Action if key was handled, None if not a selection key.
        """
        if key == curses.KEY_IC:  # Insert key
            self.active_panel.toggle_selection()
            return Action.NONE
        # Selection modifiers only work when command line is empty
        # Otherwise, these keys should be typed into the command line
        if self.command_line.input_text:
            return None
        if key == ord(' '):
            self.active_panel.toggle_selection()
            return Action.NONE
        if key == ord('*'):
            self.active_panel.invert_selection()
            return Action.NONE
        elif key == ord('+'):
            return Action.SELECT_PATTERN
        elif key == ord('-'):
            return Action.DESELECT_PATTERN
        elif key == ord('/'):
            self.active_panel.start_search()
            return Action.NONE
        return None

    def _handle_operation_key(self, key: int) -> Action | None:
        """Handle operation keys (F3-F9, Shift+F, Alt+F, Ctrl+F keys).

        Args:
            key: Key code from curses.

        Returns:
            Action if key was handled, None if not an operation key.
        """
        if key == curses.KEY_F3:
            return Action.VIEW
        elif key == curses.KEY_F4:
            return Action.EDIT
        elif key == curses.KEY_F5:
            return Action.COPY
        elif key == curses.KEY_F6:
            return Action.MOVE
        elif key == curses.KEY_F7:
            return Action.MKDIR
        elif key == curses.KEY_F8:
            return Action.DELETE
        elif key == curses.KEY_F9:
            # Toggle dropdown (menu bar is always visible)
            self.menu.dropdown_open = not self.menu.dropdown_open
            if self.menu.dropdown_open:
                self.menu.selected_item = 0
            return Action.NONE
        # Shift+F keys (KEY_F13-KEY_F24 are Shift+F1-F12)
        elif key == curses.KEY_F3 + 12:  # Shift+F3 = KEY_F15
            return Action.CYCLE_SORT
        elif key == curses.KEY_F4 + 12:  # Shift+F4 = KEY_F16
            return Action.CREATE_FILE
        # Alt+F keys (KEY_F49-KEY_F60 are Alt+F1-F12)
        elif key == curses.KEY_F3 + 48:  # Alt+F3 = KEY_F51
            return Action.MEASURE_DIR_SIZE
        # Ctrl+F keys (KEY_F25-KEY_F36 are Ctrl+F1-F12, terminal-dependent)
        elif key == curses.KEY_F3 + 24:  # Ctrl+F3 = KEY_F27
            return Action.TOGGLE_SORT_REVERSE
        return None

    def switch_panel(self) -> None:
        """Switch active panel between left and right."""
        if self.active_panel == self.left_panel:
            self.active_panel = self.right_panel
        else:
            self.active_panel = self.left_panel

        # Update is_active flags
        self.left_panel.is_active = (self.active_panel == self.left_panel)
        self.right_panel.is_active = (self.active_panel == self.right_panel)

        # Update command line path to active panel's directory
        self.command_line.set_path(str(self.active_panel.path))

    def get_other_panel(self) -> Panel:
        """Get the panel that is not currently active."""
        if self.active_panel == self.left_panel:
            return self.right_panel
        return self.left_panel

    def _do_file_operation(
        self,
        operation_name: str,
        operation_func: Callable,
        result_class: type,
        result_field: str,
        summary_kwarg: str,
    ) -> CopyResult | MoveResult:
        """Template method for copy/move file operations.

        Handles the common workflow:
        1. Get files to operate on
        2. Show confirmation dialog
        3. Execute operation with overwrite handling
        4. Refresh panels
        5. Show summary

        Args:
            operation_name: Display name ('Copy' or 'Move').
            operation_func: The file operation function to call.
            result_class: The result class (CopyResult or MoveResult).
            result_field: Name of the success list field ('copied_files' or 'moved_files').
            summary_kwarg: Keyword arg for show_summary ('copied' or 'moved').

        Returns:
            CopyResult or MoveResult with operation status.
        """
        source_panel = self.active_panel
        dest_panel = self.get_other_panel()

        files_to_operate = source_panel.get_files_for_operation()
        if not files_to_operate:
            return result_class(success=False, error=f'Nothing to {operation_name.lower()}')

        # Show pre-confirmation dialog
        count = len(files_to_operate)
        dest_path = str(dest_panel.path)
        if count == 1:
            message = f'{operation_name} "{files_to_operate[0]}" to {dest_path}?'
        else:
            message = f'{operation_name} {count} files to {dest_path}?'

        if not confirm_dialog(self.stdscr, operation_name, message):
            return result_class(success=False, error='', cancelled=True)

        # Perform operation with overwrite handling
        handler = CursesOverwriteHandler(self.stdscr)
        result = operation_func(
            files_to_operate, source_panel.path, dest_panel.path, handler
        )

        # Refresh panels if any files were processed
        processed_files = getattr(result, result_field)
        if result.success or processed_files:
            source_panel.selected.clear()
            source_panel.refresh()
            dest_panel.refresh()

        # Show summary (with errors if any)
        self.draw()
        # Split error string back into list for display
        error_list = result.error.split('; ') if result.error else None
        show_summary(
            self.stdscr, operation_name.lower(),
            **{summary_kwarg: len(processed_files)},
            skipped=len(result.skipped_files),
            cancelled=result.cancelled,
            errors=error_list
        )

        return result

    def do_copy(self) -> CopyResult:
        """Copy selected files from active panel to other panel.

        Shows confirmation dialog before copying, handles overwrites with
        a modal dialog, and displays a summary after completion.

        Returns:
            CopyResult with success status.
        """
        return self._do_file_operation(
            operation_name='Copy',
            operation_func=copy_files_with_overwrite,
            result_class=CopyResult,
            result_field='copied_files',
            summary_kwarg='copied',
        )

    def do_move(self) -> MoveResult:
        """Move selected files from active panel to other panel.

        Shows confirmation dialog before moving, handles overwrites with
        a modal dialog, and displays a summary after completion.

        Returns:
            MoveResult with success status.
        """
        return self._do_file_operation(
            operation_name='Move',
            operation_func=move_files_with_overwrite,
            result_class=MoveResult,
            result_field='moved_files',
            summary_kwarg='moved',
        )

    def _open_with_external(self, tool: str | None, tool_name: str, refresh_panel: bool = False) -> ViewResult:
        """Open current file with an external tool (editor or pager).

        Args:
            tool: The command to run (e.g., 'nano', 'less -R').
            tool_name: Human-readable name for error messages ('editor' or 'pager').
            refresh_panel: Whether to refresh the panel after (for edit, not view).

        Returns:
            ViewResult with success status.
        """
        if self.active_panel.cursor >= len(self.active_panel.entries):
            return ViewResult(success=False, error='No file selected')

        entry = self.active_panel.entries[self.active_panel.cursor]

        if entry.name == '..':
            return ViewResult(success=False, error=f'Cannot {tool_name[0:4]} parent directory')

        file_path = self.active_panel.path / entry.name

        if file_path.is_dir():
            return ViewResult(success=False, error=f'Cannot {tool_name[0:4]} directory')

        if not tool:
            return ViewResult(success=False, error=f'No {tool_name} configured')

        curses.endwin()
        try:
            subprocess.run(shlex.split(tool) + [str(file_path)])
            return ViewResult(success=True)
        except FileNotFoundError:
            return ViewResult(success=False, error=f'{tool_name.capitalize()} not found: {tool}')
        except OSError as e:
            return ViewResult(success=False, error=str(e))
        finally:
            self.stdscr.refresh()
            if refresh_panel:
                self.active_panel.refresh()

    def view_current_file(self) -> ViewResult:
        """View current file with pager."""
        pager = self.config.get_pager()
        if not pager:
            # Prompt user to select a pager
            self._prompt_pager_setup()
            pager = self.config.pager
            if not pager:
                return ViewResult(success=False, error='Pager setup cancelled')
        return self._open_with_external(pager, 'pager')

    def edit_current_file(self) -> ViewResult:
        """Edit current file with editor."""
        editor = self.config.get_editor()
        if not editor:
            # Prompt user to select an editor
            self._prompt_editor_setup()
            editor = self.config.editor
            if not editor:
                return ViewResult(success=False, error='Editor setup cancelled')
        # Map display name to actual command (e.g., TextEdit -> open -e)
        editor_cmd = Config.get_editor_command(editor)
        return self._open_with_external(editor_cmd, 'editor', refresh_panel=True)

    def open_in_finder(self) -> None:
        """Open current selection in Finder (macOS only).

        Reveals the selected file or folder in Finder. If '..' is selected,
        reveals the current directory instead.
        """
        if sys.platform != 'darwin':
            return

        # Determine what to reveal
        if self.active_panel.cursor >= len(self.active_panel.entries):
            return

        entry = self.active_panel.entries[self.active_panel.cursor]

        if entry.name == '..':
            # Reveal current directory
            path_to_reveal = str(self.active_panel.path)
        else:
            # Reveal the selected item
            path_to_reveal = str(self.active_panel.path / entry.name)

        curses.endwin()
        try:
            subprocess.run(['open', '-R', path_to_reveal])
        except (FileNotFoundError, OSError) as e:
            self.stdscr.refresh()
            self._show_error(f'Failed to open Finder: {e}')
            return
        self.stdscr.refresh()

    def _prompt_tool_setup(self, tool_type: str, options: list[str]) -> str | None:
        """Prompt user to select a tool from available options.

        Args:
            tool_type: Type of tool ('pager' or 'editor').
            options: List of available tool commands.

        Returns:
            Selected tool command, or None if cancelled.
        """
        # Show error dialog if no tools available
        if not options:
            confirm_dialog(
                self.stdscr,
                'Error',
                f'No {tool_type}s found on system.',
                default_yes=True
            )
            return None

        # Show selection dialog with custom option
        title = f'Select {tool_type.title()}'
        dialog = SelectionDialog(
            title=title,
            options=options,
            allow_custom=True
        )

        return dialog.show(self.stdscr)

    def _prompt_pager_setup(self) -> None:
        """Prompt user to select a pager."""
        options = Config.get_available_pagers()
        selected = self._prompt_tool_setup('pager', options)
        if selected:
            self.config.pager = selected
            self.config.save()

    def _prompt_editor_setup(self) -> None:
        """Prompt user to select an editor."""
        options = Config.get_available_editors()
        selected = self._prompt_tool_setup('editor', options)
        if selected:
            self.config.editor = selected
            self.config.save()

    def _toggle_classic_colors(self) -> None:
        """Toggle between classic mc-style blue and modern transparent theme."""
        # Toggle the setting
        new_value = not is_classic_theme()
        set_classic_theme(new_value)
        # Save to config
        self.config.classic_colors = new_value
        self.config.save()

    def _enable_mouse(self) -> bool:
        """Enable mouse event capture.

        Returns:
            True if mouse was successfully enabled, False if unavailable.
        """
        try:
            # Only capture click and scroll events, not motion
            # Note: BUTTON5 not available on all platforms (macOS ncurses)
            mouse_events = (
                curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED |
                curses.BUTTON2_CLICKED |  # Middle click (scroll wheel click)
                curses.BUTTON3_CLICKED |  # Right click
                getattr(curses, 'BUTTON3_DOUBLE_CLICKED', 0) |  # Right double-click (for swap)
                curses.BUTTON4_PRESSED |  # Scroll up
                getattr(curses, 'BUTTON5_PRESSED', 0)  # Scroll down (if available)
            )
            result = curses.mousemask(mouse_events)
            self._mouse_active = result != 0
        except curses.error:
            # Curses not properly initialized (e.g., in tests)
            self._mouse_active = False
        return self._mouse_active

    def _disable_mouse(self) -> None:
        """Disable mouse event capture."""
        try:
            curses.mousemask(0)
        except curses.error:
            pass
        self._mouse_active = False

    def _toggle_mouse(self) -> None:
        """Toggle mouse support on/off and save to config."""
        if self._mouse_active:
            self._disable_mouse()
            self.config.mouse_enabled = False
        else:
            self._enable_mouse()
            self.config.mouse_enabled = True
        self.config.save()

    def _toggle_menu_dropdown(self) -> None:
        """Toggle menu dropdown open/closed."""
        self.menu.dropdown_open = not self.menu.dropdown_open
        if self.menu.dropdown_open:
            self.menu.selected_item = 0

    def _toggle_mouse_swap(self) -> None:
        """Toggle mouse button swap (for left-handed users) and save to config."""
        self.config.mouse_swap = not self.config.mouse_swap
        self.config.save()

    def _translate_button_state(self, button_state: int) -> int:
        """Translate mouse button state based on swap setting.

        When mouse_swap is True, swaps left-click (BUTTON1) with right-click
        (BUTTON3). Scroll wheel buttons (BUTTON4/5) are unchanged.
        """
        if not self.config.mouse_swap:
            return button_state

        # Cache constant (may not exist on all platforms)
        b3_double = getattr(curses, 'BUTTON3_DOUBLE_CLICKED', 0)

        # Check original button states before modifying
        has_b1_click = button_state & curses.BUTTON1_CLICKED
        has_b1_double = button_state & curses.BUTTON1_DOUBLE_CLICKED
        has_b3_click = button_state & curses.BUTTON3_CLICKED
        has_b3_double = button_state & b3_double

        result = button_state

        # Swap BUTTON1 -> BUTTON3
        if has_b1_click:
            result = (result & ~curses.BUTTON1_CLICKED) | curses.BUTTON3_CLICKED
        if has_b1_double:
            result = (result & ~curses.BUTTON1_DOUBLE_CLICKED) | (b3_double or curses.BUTTON3_CLICKED)

        # Swap BUTTON3 -> BUTTON1
        if has_b3_click:
            result = (result & ~curses.BUTTON3_CLICKED) | curses.BUTTON1_CLICKED
        if has_b3_double:
            result = (result & ~b3_double) | curses.BUTTON1_DOUBLE_CLICKED

        return result

    def handle_mouse(self, x: int, y: int, button_state: int) -> Action:
        """Route mouse events to appropriate UI component.

        Args:
            x: Mouse x coordinate.
            y: Mouse y coordinate.
            button_state: Bitmask of button states.

        Returns:
            Action to perform, or Action.NONE if no action.
        """
        # Handle middle-click (scroll wheel click) as Enter on active panel
        # Works anywhere on screen, always acts on active panel
        if button_state & curses.BUTTON2_CLICKED:
            file_path = self.active_panel.enter()
            self.command_line.set_path(str(self.active_panel.path))
            if self.active_panel.error_message:
                self._show_error(self.active_panel.error_message)
            # If enter() returned a file path, check if it's executable
            if file_path and self._is_executable(file_path):
                self._execute_file(file_path)
            return Action.NONE

        # Handle left-click only for menu interactions
        if button_state & curses.BUTTON1_CLICKED:
            # Check if dropdown is open and click is on a dropdown item
            if self.menu.dropdown_open:
                item_idx = self.menu.dropdown_item_at_point(x, y)
                if item_idx is not None:
                    # Check if item is enabled before executing
                    menu = self.menu.menus[self.menu.selected_menu]
                    if not menu.items[item_idx].enabled:
                        return Action.NONE  # Disabled item - do nothing

                    # Execute the item action
                    self.menu.selected_item = item_idx
                    action_str = self.menu.get_selected_action()
                    self.menu.dropdown_open = False
                    if action_str and action_str in MENU_ACTION_MAP:
                        return MENU_ACTION_MAP[action_str]
                    return Action.NONE

            # Check if click is in menu bar
            if self.menu.contains_point(x, y):
                menu_idx = self.menu.menu_at_point(x)
                if menu_idx is not None:
                    if self.menu.dropdown_open and self.menu.selected_menu == menu_idx:
                        # Click same menu - toggle dropdown closed
                        self.menu.dropdown_open = False
                    else:
                        # Click different menu or dropdown closed - open/switch
                        self.menu.selected_menu = menu_idx
                        self.menu.dropdown_open = True
                        self.menu.selected_item = 0
                return Action.NONE

            # Click outside menu area while dropdown open - close dropdown
            if self.menu.dropdown_open:
                self.menu.dropdown_open = False
                # Check if click was on function bar - close dropdown only
                if self.function_bar.contains_point(x, y):
                    return Action.NONE
                # Don't return - also handle panel click below

            # Check if click is in function bar
            if self.function_bar.contains_point(x, y):
                action = self.function_bar.action_at_point(x)
                if not action:
                    return Action.NONE
                # Show visual feedback
                key = self.function_bar.get_key_at_point(x)
                if key:
                    self.function_bar.show_click_feedback(key)
                return action

        # Check if click is in left panel
        if self.left_panel.contains_point(x, y):
            # Switch to left panel if not already active
            if self.active_panel != self.left_panel:
                self.active_panel = self.left_panel
                self.left_panel.is_active = True
                self.right_panel.is_active = False
                self.command_line.set_path(str(self.active_panel.path))
            return self._handle_panel_click(self.left_panel, x, y, button_state)

        # Check if click is in right panel
        if self.right_panel.contains_point(x, y):
            # Switch to right panel if not already active
            if self.active_panel != self.right_panel:
                self.active_panel = self.right_panel
                self.right_panel.is_active = True
                self.left_panel.is_active = False
                self.command_line.set_path(str(self.active_panel.path))
            return self._handle_panel_click(self.right_panel, x, y, button_state)

        return Action.NONE

    def _handle_panel_click(self, panel: Panel, x: int, y: int, button_state: int) -> Action:
        """Handle mouse click on a file panel.

        Args:
            panel: The panel that was clicked.
            x: Mouse x coordinate.
            y: Mouse y coordinate.
            button_state: Bitmask of button states.

        Returns:
            Action to perform, or Action.NONE if no action.
        """
        # Handle scroll wheel (doesn't need entry position)
        if button_state & curses.BUTTON4_PRESSED:
            panel.navigate_up()
            return Action.NONE

        # BUTTON5_PRESSED may not exist on all platforms (e.g., macOS ncurses)
        button5 = getattr(curses, 'BUTTON5_PRESSED', 0x200000)
        if button_state & button5:
            panel.navigate_down()
            return Action.NONE

        # Get entry at click position
        entry_idx = panel.entry_at_point(x, y)
        if entry_idx is None:
            return Action.NONE

        # Move cursor to clicked entry
        panel.cursor = entry_idx
        panel._adjust_scroll()

        # Handle double-click - enter directory or open file
        if button_state & curses.BUTTON1_DOUBLE_CLICKED:
            file_path = panel.enter()
            self.command_line.set_path(str(panel.path))
            # Show error if directory couldn't be entered (e.g., permission denied)
            if panel.error_message:
                self._show_error(panel.error_message)
            if file_path and self._is_executable(file_path):
                self._execute_file(file_path)
            return Action.NONE

        # Handle right-click - insert filename into command line
        if button_state & curses.BUTTON3_CLICKED:
            self._insert_filename_to_command_line()
            return Action.NONE

        return Action.NONE

    def _show_error(self, message: str) -> None:
        """Display an error message to the user.

        Args:
            message: Error message to display.
        """
        show_error_dialog(self.stdscr, 'Error', message)

    def _get_next_key_if_available(self) -> int:
        """Check for next key in input buffer without blocking.

        Used to detect Alt+key sequences (Escape followed by another key).
        Returns the next key code, or -1 if no key is available.
        """
        self.stdscr.nodelay(True)
        try:
            return self.stdscr.getch()
        finally:
            self.stdscr.nodelay(False)

    def _insert_filename_to_command_line(self) -> None:
        """Insert current filename into command line."""
        if self.active_panel.cursor >= len(self.active_panel.entries):
            return

        entry = self.active_panel.entries[self.active_panel.cursor]
        if entry.name != '..':
            self.command_line.insert_filename(entry.name)

    def _execute_command(self) -> None:
        """Execute the command line input in full terminal mode.

        Uses full terminal mode (suspends curses) rather than capturing output
        because users need interactive programs (vim, less, ssh, etc.) to work.
        This is the same approach used by mc and other file managers.

        Note: CommandLine.execute() exists for captured output scenarios but
        is not used here because file manager commands need full terminal access.
        """
        command = self.command_line.input_text.strip()
        if not command:
            return

        # Clear the command line
        self.command_line.handle_key(curses.KEY_ENTER)

        # Suspend curses and run command in terminal
        curses.endwin()
        try:
            # Run command in active panel's directory (shell=True for pipes, redirects, etc.)
            subprocess.run(command, shell=True, cwd=str(self.active_panel.path))
        except (OSError, subprocess.SubprocessError) as e:
            print(f'\nError: {e}')
        # Wait for user to press a key
        print('\n[Press any key to continue]', end='', flush=True)
        # Read a single character
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            # Restore curses
            self.stdscr.refresh()

        # Refresh both panels to show any file changes
        self.left_panel.refresh()
        self.right_panel.refresh()

    def _is_executable(self, file_path: 'Path') -> bool:
        """Check if a file is executable by the owner.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file has the executable bit set for owner.
        """
        try:
            return bool(file_path.stat().st_mode & stat.S_IXUSR)
        except OSError:
            return False

    def _execute_file(self, file_path: 'Path') -> None:
        """Execute a file in the terminal.

        Suspends curses, runs the executable, then waits for a key press
        before restoring the curses display.

        Args:
            file_path: Path to the executable file.
        """
        curses.endwin()
        try:
            subprocess.run([str(file_path)], cwd=str(file_path.parent))
        except (OSError, subprocess.SubprocessError) as e:
            print(f'\nError: {e}')
        print('\n[Press any key to continue]', end='', flush=True)
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            self.stdscr.refresh()
        self.left_panel.refresh()
        self.right_panel.refresh()

    def _prompt_pattern(
        self, title: str, prompt_text: str, action: Callable[[str], None]
    ) -> None:
        """Prompt for pattern and apply action to matching files.

        Args:
            title: Dialog title.
            prompt_text: Text to display as the prompt.
            action: Function to call with the entered pattern.
        """
        pattern = input_dialog(self.stdscr, title, prompt_text)
        if pattern:
            action(pattern)

    def _prompt_select_pattern(self) -> None:
        """Prompt for pattern and select matching files."""
        self._prompt_pattern(
            'Select by pattern', 'Enter pattern (e.g. *.txt):',
            self.active_panel.select_by_pattern
        )

    def _prompt_deselect_pattern(self) -> None:
        """Prompt for pattern and deselect matching files."""
        self._prompt_pattern(
            'Deselect by pattern', 'Enter pattern (e.g. *.txt):',
            self.active_panel.deselect_by_pattern
        )

    def _prompt_mkdir(self) -> None:
        """Prompt for directory name and create it."""
        name = input_dialog(
            self.stdscr, 'Create directory', 'Enter directory name:'
        )
        if name:
            result = self.active_panel.create_directory(name)
            if not result.success:
                show_error_dialog(
                    self.stdscr, 'Mkdir Failed',
                    result.error or 'Unknown error'
                )

    def _prompt_delete(self) -> None:
        """Prompt for confirmation and delete selected files."""
        files = self.active_panel.get_files_for_operation()
        if not files:
            return

        # Build message based on file count
        if len(files) == 1:
            message = f'Delete "{files[0]}"?'
        else:
            message = f'Delete {len(files)} files?'

        # Show confirmation modal dialog (Enter = Yes, consistent with PR #95)
        if confirm_dialog(self.stdscr, 'Delete Confirmation', message, default_yes=True):
            result = self.active_panel.delete_selected()
            if not result.success:
                show_error_dialog(
                    self.stdscr, 'Delete Failed',
                    result.error or 'Unknown error'
                )

    def _prompt_rename(self) -> None:
        """Prompt for new name and rename the current file/directory."""
        if self.active_panel.cursor >= len(self.active_panel.entries):
            return

        entry = self.active_panel.entries[self.active_panel.cursor]
        if entry.name == '..':
            self._show_error('Cannot rename parent directory')
            return

        old_name = entry.name
        new_name = input_dialog(
            self.stdscr, 'Rename',
            f'Rename "{old_name}" to:',
            default_value=old_name
        )

        if new_name and new_name != old_name:
            result = rename_file(self.active_panel.path, old_name, new_name)
            if result.success:
                # Refresh panel and position cursor on renamed item
                self.active_panel.refresh()
                # Find and select the renamed item
                for i, e in enumerate(self.active_panel.entries):
                    if e.name == new_name:
                        self.active_panel.cursor = i
                        break
            else:
                self._show_error(result.error)

    def _prompt_chmod(self) -> None:
        """Prompt for permissions and change them on selected files."""
        import grp
        import pwd
        from pathlib import Path

        from tnc.dialog import chmod_dialog
        from tnc.file_ops import chmod_files, chmod_recursive
        from tnc.permissions import TriState, get_common_mode

        files = self.active_panel.get_files_for_operation()
        if not files:
            return

        # Get current permissions and check if any are directories
        paths = [self.active_panel.path / f for f in files]
        has_directory = any(p.is_dir() and not p.is_symlink() for p in paths)

        # Get common mode state
        if len(files) == 1:
            try:
                mode = paths[0].stat().st_mode
                result = chmod_dialog(
                    self.stdscr,
                    file_count=1,
                    initial_mode=mode,
                    has_directory=has_directory,
                    filename=files[0]
                )
            except OSError as e:
                self._show_error(str(e))
                return
        else:
            common_states, failed_count = get_common_mode(paths)
            if failed_count == len(paths):
                self._show_error("Cannot stat any of the selected files")
                return
            result = chmod_dialog(
                self.stdscr,
                file_count=len(files),
                initial_states=common_states,
                has_directory=has_directory
            )

        if result is None:
            return

        new_mode, recursive = result

        # Apply changes
        if recursive and has_directory:
            # Apply recursively to directories
            errors = []
            for path in paths:
                if path.is_dir() and not path.is_symlink():
                    res = chmod_recursive(path, new_mode, file_mode=new_mode)
                    if not res.success:
                        errors.append(res.error)
                else:
                    res = chmod_files([path.name], self.active_panel.path, new_mode)
                    if not res.success:
                        errors.append(res.error)
            if errors:
                self._show_error('; '.join(errors))
        else:
            res = chmod_files(files, self.active_panel.path, new_mode)
            if not res.success:
                self._show_error(res.error)

        self.active_panel.refresh()

    def _prompt_chown(self) -> None:
        """Prompt for owner/group and change them on selected files."""
        import grp
        import pwd
        from pathlib import Path

        from tnc.dialog import chown_dialog
        from tnc.file_ops import chown_files

        files = self.active_panel.get_files_for_operation()
        if not files:
            return

        # Get current owner/group
        paths = [self.active_panel.path / f for f in files]
        try:
            stat_info = paths[0].stat()
            try:
                current_owner = pwd.getpwuid(stat_info.st_uid).pw_name
            except KeyError:
                current_owner = str(stat_info.st_uid)
            try:
                current_group = grp.getgrgid(stat_info.st_gid).gr_name
            except KeyError:
                current_group = str(stat_info.st_gid)
        except OSError as e:
            self._show_error(str(e))
            return

        result = chown_dialog(
            self.stdscr,
            file_count=len(files),
            current_owner=current_owner,
            current_group=current_group,
            filename=files[0] if len(files) == 1 else None
        )

        if result is None:
            return

        new_owner, new_group = result

        # Convert names to uid/gid
        try:
            if new_owner:
                try:
                    uid = pwd.getpwnam(new_owner).pw_uid
                except KeyError:
                    uid = int(new_owner)  # Try as numeric
            else:
                uid = -1  # Don't change
        except ValueError:
            self._show_error(f'Invalid user: {new_owner}')
            return

        try:
            if new_group:
                try:
                    gid = grp.getgrnam(new_group).gr_gid
                except KeyError:
                    gid = int(new_group)  # Try as numeric
            else:
                gid = -1  # Don't change
        except ValueError:
            self._show_error(f'Invalid group: {new_group}')
            return

        res = chown_files(files, self.active_panel.path, uid, gid)
        if not res.success:
            self._show_error(res.error)

        self.active_panel.refresh()

    def _prompt_create_file(self) -> None:
        """Prompt for filename and create it, then open in editor."""
        name = input_dialog(
            self.stdscr, 'Create file', 'Enter file name:'
        )
        if name:
            result = self.active_panel.create_file(name)
            if result.success:
                # Open the new file in editor
                edit_result = self.edit_current_file()
                if not edit_result.success:
                    # Show error - file was created but editor failed
                    show_error_dialog(
                        self.stdscr, 'Editor Error',
                        f'File created, but editor failed: {edit_result.error}'
                    )
            else:
                # Show file creation error
                show_error_dialog(
                    self.stdscr, 'Create File Failed',
                    result.error or 'Unknown error'
                )

    def _measure_dir_size(self) -> None:
        """Calculate and display directory size for current entry."""
        if not self.active_panel.entries:
            return

        if self.active_panel.cursor >= len(self.active_panel.entries):
            return

        entry = self.active_panel.entries[self.active_panel.cursor]

        # Skip if not a directory (silent no-op)
        if entry.name == '..':
            return

        full_path = self.active_panel.path / entry.name
        if not full_path.is_dir():
            return

        # Show calculating message
        self.stdscr.addstr(
            self.stdscr.getmaxyx()[0] - 2, 0,
            'Calculating...'.ljust(self.stdscr.getmaxyx()[1])
        )
        self.stdscr.refresh()

        # Calculate size and cache it
        size = self.active_panel.measure_dir_size(entry.name)
        if size < 0:
            show_error_dialog(
                self.stdscr, 'Error',
                f'Error calculating size for "{entry.name}"'
            )


def main_loop(stdscr: Any) -> int:
    """Entry point wrapped by curses.wrapper."""
    app = App(stdscr)
    app.setup()
    try:
        return app.run()
    finally:
        app.cleanup()


def run_app() -> int:
    """Run the application using curses.wrapper for safe setup/teardown."""
    return curses.wrapper(main_loop)
