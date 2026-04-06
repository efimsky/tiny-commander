"""Utility functions for Tiny Commander."""

import curses
import stat
import time


def safe_addstr(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """Write string to curses window, ignoring boundary errors.

    This is a wrapper around win.addstr() that silently handles curses.error
    exceptions, which commonly occur when writing to the edges of a window.

    Args:
        win: A curses window object.
        y: Row position (0-indexed from top).
        x: Column position (0-indexed from left).
        text: The string to write.
        attr: Optional curses attribute (e.g., curses.A_BOLD). Defaults to 0.
    """
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def format_size(size: int) -> str:
    """Format a file size in human-readable form.

    Args:
        size: Size in bytes.

    Returns:
        Human-readable size string (e.g., '1.5K', '2.0M', '3.0G').
    """
    if size < 0:
        return '?'
    if size < 1024:
        return str(size)

    for unit in ['K', 'M', 'G', 'T']:
        size = size / 1024
        if size < 1024:
            return f'{size:.1f}{unit}'

    return f'{size:.1f}P'


def format_permissions(mode: int) -> str:
    """Format file permissions as Unix-style string.

    Args:
        mode: File mode from os.stat().st_mode.

    Returns:
        10-character permission string (e.g., '-rw-r--r--', 'drwxrwxrwt').
    """
    # File type character
    if stat.S_ISDIR(mode):
        type_char = 'd'
    elif stat.S_ISLNK(mode):
        type_char = 'l'
    elif stat.S_ISREG(mode):
        type_char = '-'
    elif stat.S_ISCHR(mode):
        type_char = 'c'
    elif stat.S_ISBLK(mode):
        type_char = 'b'
    elif stat.S_ISFIFO(mode):
        type_char = 'p'
    elif stat.S_ISSOCK(mode):
        type_char = 's'
    else:
        type_char = '?'

    # Permission bits
    perms = ''
    for who in ('USR', 'GRP', 'OTH'):
        r = 'r' if mode & getattr(stat, f'S_IR{who}') else '-'
        w = 'w' if mode & getattr(stat, f'S_IW{who}') else '-'
        x = 'x' if mode & getattr(stat, f'S_IX{who}') else '-'
        perms += r + w + x

    # Handle special bits (setuid, setgid, sticky)
    perms_list = list(perms)
    if mode & stat.S_ISUID:
        perms_list[2] = 's' if perms_list[2] == 'x' else 'S'
    if mode & stat.S_ISGID:
        perms_list[5] = 's' if perms_list[5] == 'x' else 'S'
    if mode & stat.S_ISVTX:
        perms_list[8] = 't' if perms_list[8] == 'x' else 'T'

    return type_char + ''.join(perms_list)


def format_mtime(timestamp: float) -> str:
    """Format a modification time in human-readable form.

    Recent files (< 6 months) show: "MMM DD HH:MM" (e.g., "Jan 15 14:32")
    Older files show: "MMM DD  YYYY" (e.g., "Jan 15  2024")

    This matches traditional ls -l and Midnight Commander behavior.

    Args:
        timestamp: Unix timestamp (from stat().st_mtime).

    Returns:
        12-character formatted date string.

    Note:
        Uses %e (space-padded day) which is POSIX but works on
        target platforms (Linux, macOS).
    """
    now = time.time()
    # 6-month threshold matches ls -l behavior
    six_months_seconds = 180 * 24 * 60 * 60

    local_time = time.localtime(timestamp)
    age = now - timestamp

    # Recent file: "MMM DD HH:MM", Old/future file: "MMM DD  YYYY"
    if 0 <= age < six_months_seconds:
        return time.strftime('%b %e %H:%M', local_time)
    return time.strftime('%b %e  %Y', local_time)
