"""Shared test helpers for Tiny Commander tests."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest import mock


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> Any:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    # Default to accepting dialogs (y key) to prevent tests from hanging
    mock_stdscr.getch.return_value = ord('y')
    return mock_stdscr


def find_entry_index(panel: Any, name: str) -> int:
    """Find entry index by name in panel."""
    for i, entry in enumerate(panel.entries):
        if entry.name == name:
            return i
    return -1


@contextmanager
def isolated_env(*unset_vars: str, clear: bool = False, **set_vars: str) -> Iterator[None]:
    """Temporarily unset or override os.environ keys within a block."""
    with mock.patch.dict(os.environ, {}, clear=clear):
        for name in unset_vars:
            os.environ.pop(name, None)
        os.environ.update(set_vars)
        yield


@contextmanager
def isolated_config(content: str | None = None) -> Iterator[Path]:
    """Point Config.default_path to a temporary file so ~/.config/tnc/config is untouched."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / 'config'
        if content is not None:
            config_path.write_text(content)
        with mock.patch('tnc.config.Config.default_path', return_value=str(config_path)):
            yield config_path
