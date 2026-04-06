"""Command line input for Tiny Commander."""

import curses
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

from tnc.colors import PAIR_CMDLINE, get_attr
from tnc.utils import safe_addstr


@dataclass
class CommandResult:
    """Result of executing a shell command."""

    stdout: str
    stderr: str
    returncode: int

    @property
    def success(self) -> bool:
        """Return True if command succeeded."""
        return self.returncode == 0


class CommandLine:
    """Command line input area at the bottom of the screen."""

    def __init__(self, path: str) -> None:
        """Initialize command line with current path.

        Args:
            path: Current directory path for prompt.
        """
        self.path = path
        self.input_text = ''
        self.cursor_pos = 0

    def set_path(self, path: str) -> None:
        """Update the current path for prompt.

        Args:
            path: New current directory path.
        """
        self.path = path

    def _insert_text(self, text: str) -> None:
        """Insert text at cursor position and advance cursor.

        Args:
            text: Text to insert.
        """
        self.input_text = (
            self.input_text[:self.cursor_pos] +
            text +
            self.input_text[self.cursor_pos:]
        )
        self.cursor_pos += len(text)

    def _clear(self) -> None:
        """Clear input text and reset cursor."""
        self.input_text = ''
        self.cursor_pos = 0

    def insert_filename(self, filename: str) -> None:
        """Insert a filename at the cursor position.

        Filenames with special characters are properly quoted.
        A leading space is added if there's non-whitespace text
        immediately before the cursor (mimics mc behavior).

        Args:
            filename: The filename to insert.
        """
        text = shlex.quote(filename)
        # Add leading space if there's non-whitespace before cursor
        if self.cursor_pos > 0 and not self.input_text[self.cursor_pos - 1].isspace():
            text = ' ' + text
        self._insert_text(text)

    def get_display_text(self, width: int) -> str:
        """Get the display text for rendering.

        Args:
            width: Available width for the command line.

        Returns:
            The formatted display text.
        """
        prompt = f'{self.path}> '
        max_prompt_len = width - len(self.input_text) - 1

        if len(prompt) > max_prompt_len:
            # Truncate path from the left
            available = max_prompt_len - 5  # '...> '
            if available > 0:
                prompt = '...' + self.path[-(available):] + '> '
            else:
                prompt = '> '

        return prompt + self.input_text

    def get_cursor_screen_pos(self, width: int) -> int:
        """Get cursor position on screen.

        Args:
            width: Available width.

        Returns:
            Screen position of cursor.
        """
        display = self.get_display_text(width)
        prompt_len = len(display) - len(self.input_text)
        return prompt_len + self.cursor_pos

    def handle_char(self, char: str) -> None:
        """Handle a character input.

        Args:
            char: The character typed.
        """
        self._insert_text(char)

    def handle_key(self, key: int) -> str | None:
        """Handle a key press.

        Args:
            key: The key code.

        Returns:
            The command to execute if Enter was pressed, None otherwise.
        """
        # Backspace
        if key in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.input_text = (
                    self.input_text[:self.cursor_pos - 1] +
                    self.input_text[self.cursor_pos:]
                )
                self.cursor_pos -= 1
            return None

        # Delete
        if key == curses.KEY_DC:
            if self.cursor_pos < len(self.input_text):
                self.input_text = (
                    self.input_text[:self.cursor_pos] +
                    self.input_text[self.cursor_pos + 1:]
                )
            return None

        # Left arrow
        if key == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            return None

        # Right arrow
        if key == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.input_text):
                self.cursor_pos += 1
            return None

        # Home
        if key == curses.KEY_HOME:
            self.cursor_pos = 0
            return None

        # End
        if key == curses.KEY_END:
            self.cursor_pos = len(self.input_text)
            return None

        # Escape
        if key == 27:
            self._clear()
            return None

        # Enter
        if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            command = self.input_text
            self._clear()
            return command

        return None

    def render(self, win: Any, y: int, width: int) -> int:
        """Render the command line to a curses window.

        Uses mc-style black on cyan coloring.

        Args:
            win: The curses window.
            y: Y position to render at.
            width: Available width.

        Returns:
            The x position where the cursor should be placed.
        """
        display = self.get_display_text(width)
        cmdline_attr = get_attr(PAIR_CMDLINE)

        # Clear the line with the command line background color
        safe_addstr(win, y, 0, ' ' * width, cmdline_attr)

        # Render the command line text
        safe_addstr(win, y, 0, display[:width - 1], cmdline_attr)

        # Return cursor position for the caller to set
        return self.get_cursor_screen_pos(width)

    def execute(self, command: str) -> CommandResult | None:
        """Execute a shell command.

        Args:
            command: The command to execute.

        Returns:
            CommandResult with output, or None if command is empty.
        """
        command = command.strip()
        if not command:
            return None

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.path,
                capture_output=True,
                text=True
            )
            return CommandResult(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode
            )
        except (OSError, subprocess.SubprocessError) as e:
            return CommandResult(
                stdout='',
                stderr=str(e),
                returncode=1
            )
        except UnicodeDecodeError as e:
            return CommandResult(
                stdout='',
                stderr=f'Output encoding error: {e}',
                returncode=1
            )
