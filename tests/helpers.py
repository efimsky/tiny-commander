"""Shared test helpers for Tiny Commander tests."""

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
