"""Configuration file handling for Tiny Commander."""

import os
import shutil
import sys
from pathlib import Path


class Config:
    """Configuration settings for Tiny Commander."""

    def __init__(self, path: str | None = None) -> None:
        """Initialize config with default values.

        Args:
            path: Path to config file. If None, uses default_path().
                  This enables test isolation by injecting a custom path.
        """
        self.path: str = path if path is not None else self.default_path()
        self.editor: str | None = None
        self.pager: str | None = None
        self.classic_colors: bool = True  # Default to classic mc-style blue theme
        self.mouse_enabled: bool = True  # Mouse support enabled by default
        self.mouse_swap: bool = False  # Swap mouse buttons (for left-handed users)
        self._unknown_keys: dict[str, str] = {}

    @classmethod
    def default_path(cls) -> str:
        """Get the default config file path.

        Returns:
            Path to config file (~/.config/tnc/config).
        """
        return str(Path.home() / '.config' / 'tnc' / 'config')

    @classmethod
    def load(cls, path: str) -> 'Config':
        """Load config from a file.

        Args:
            path: Path to config file.

        Returns:
            Config instance with values from file, or defaults if file missing.
        """
        config = cls(path=path)

        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Parse key=value
                    if '=' not in line:
                        continue

                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Set known keys
                    if key == 'editor':
                        config.editor = value
                    elif key == 'pager':
                        config.pager = value
                    elif key == 'classic_colors':
                        config.classic_colors = value.lower() in ('yes', 'true', '1')
                    elif key == 'mouse_enabled':
                        config.mouse_enabled = value.lower() in ('yes', 'true', '1')
                    elif key == 'mouse_swap':
                        config.mouse_swap = value.lower() in ('yes', 'true', '1')
                    else:
                        # Preserve unknown keys
                        config._unknown_keys[key] = value

        except (FileNotFoundError, PermissionError):
            # Return default config if file doesn't exist or can't be read
            pass

        return config

    def save(self, path: str | None = None) -> None:
        """Save config to a file.

        Args:
            path: Path to config file. If None, uses the stored path.
        """
        save_path = path if path is not None else self.path
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'w') as f:
            if self.editor is not None:
                f.write(f'editor = {self.editor}\n')
            if self.pager is not None:
                f.write(f'pager = {self.pager}\n')
            # Always write classic_colors setting
            f.write(f'classic_colors = {"yes" if self.classic_colors else "no"}\n')
            # Always write mouse_enabled setting
            f.write(f'mouse_enabled = {"yes" if self.mouse_enabled else "no"}\n')
            # Always write mouse_swap setting
            f.write(f'mouse_swap = {"yes" if self.mouse_swap else "no"}\n')
            for key, value in self._unknown_keys.items():
                f.write(f'{key} = {value}\n')

    def needs_editor_setup(self) -> bool:
        """Check if editor setup is needed.

        Returns:
            True if no editor is configured and EDITOR env is not set.
        """
        return not os.environ.get('EDITOR') and self.editor is None

    def needs_pager_setup(self) -> bool:
        """Check if pager setup is needed.

        Returns:
            True if no pager is configured and PAGER env is not set.
        """
        return not os.environ.get('PAGER') and self.pager is None

    def get_editor(self) -> str | None:
        """Get the editor to use, preferring env over config.

        Returns:
            Editor command, or None if not configured.
        """
        return os.environ.get('EDITOR') or self.editor

    def get_pager(self) -> str | None:
        """Get the pager to use, preferring env over config.

        Returns:
            Pager command, or None if not configured.
        """
        return os.environ.get('PAGER') or self.pager

    @staticmethod
    def get_editor_options() -> list[str]:
        """Get list of common editor options for setup dialog.

        Terminal editors are always included. GUI editors (TextEdit, Sublime,
        TextMate, VS Code) are only included on macOS.

        Returns:
            List of editor command names.
        """
        editors = ['vi', 'nano', 'vim', 'emacs']
        if sys.platform == 'darwin':
            editors.extend(['TextEdit', 'subl', 'mate', 'code'])
        return editors

    @staticmethod
    def get_pager_options() -> list[str]:
        """Get list of common pager options for setup dialog.

        Returns:
            List of pager command names.
        """
        return ['less', 'more']

    @staticmethod
    def get_available_editors() -> list[str]:
        """Get list of editors that are available on the system.

        Terminal editors (vi, vim, nano, emacs) are checked on all platforms.
        GUI editors (TextEdit, Sublime, TextMate, VS Code) are only checked
        on macOS. TextEdit is always available on macOS (it's a system app).

        Returns:
            List of editor names that are available on the system.
        """
        # Terminal editors - available on all platforms
        terminal_editors = ['vi', 'nano', 'vim', 'emacs']
        available = [cmd for cmd in terminal_editors if shutil.which(cmd)]

        # GUI editors - macOS only
        if sys.platform == 'darwin':
            # TextEdit uses 'open -e', so check if 'open' exists
            if shutil.which('open'):
                available.append('TextEdit')
            # Check for other GUI editors
            gui_editors = ['subl', 'mate', 'code']
            available.extend(cmd for cmd in gui_editors if shutil.which(cmd))

        return available

    @staticmethod
    def get_editor_command(editor_name: str) -> str:
        """Get the actual command to run for an editor.

        Maps display names to commands where they differ (e.g., TextEdit -> open -e).
        The TextEdit mapping only applies on macOS.

        Args:
            editor_name: The editor name (as shown in selection prompt).

        Returns:
            The actual command to execute.
        """
        if editor_name == 'TextEdit' and sys.platform == 'darwin':
            return 'open -e'
        return editor_name

    @staticmethod
    def get_available_pagers() -> list[str]:
        """Get list of pagers that are available on the system.

        Returns:
            List of pager commands that exist on the system.
        """
        candidates = ['less', 'more']
        return [cmd for cmd in candidates if shutil.which(cmd)]
