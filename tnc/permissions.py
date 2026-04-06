"""Permission utilities for chmod/chown dialogs."""

import grp
import os
import pwd
import stat
from enum import Enum, auto
from pathlib import Path


class TriState(Enum):
    """Tri-state value for checkboxes with mixed state."""

    UNCHECKED = auto()
    CHECKED = auto()
    MIXED = auto()


# Mapping of bit names to stat constants
_PERMISSION_BITS = {
    'owner_read': stat.S_IRUSR,
    'owner_write': stat.S_IWUSR,
    'owner_exec': stat.S_IXUSR,
    'group_read': stat.S_IRGRP,
    'group_write': stat.S_IWGRP,
    'group_exec': stat.S_IXGRP,
    'other_read': stat.S_IROTH,
    'other_write': stat.S_IWOTH,
    'other_exec': stat.S_IXOTH,
    'setuid': stat.S_ISUID,
    'setgid': stat.S_ISGID,
    'sticky': stat.S_ISVTX,
}


def mode_to_octal_string(mode: int) -> str:
    """Convert mode to octal string representation.

    Args:
        mode: File mode as integer.

    Returns:
        Octal string like '0755' or '4755'.
    """
    # Extract just the permission bits (bottom 12 bits)
    perms = mode & 0o7777
    return f'{perms:04o}'


def get_permission_bits(mode: int) -> dict[str, bool]:
    """Extract individual permission bits from mode.

    Args:
        mode: File mode as integer.

    Returns:
        Dictionary mapping bit names to boolean values.
    """
    return {
        name: bool(mode & bit_mask)
        for name, bit_mask in _PERMISSION_BITS.items()
    }


def set_permission_bit(mode: int, bit_name: str, value: bool) -> int:
    """Set or clear a specific permission bit.

    Args:
        mode: Current file mode.
        bit_name: Name of bit to modify (e.g., 'owner_exec').
        value: True to set, False to clear.

    Returns:
        New mode with bit modified.
    """
    bit_mask = _PERMISSION_BITS.get(bit_name)
    if bit_mask is None:
        return mode

    if value:
        return mode | bit_mask
    else:
        return mode & ~bit_mask


def get_common_mode(
    paths: list[Path]
) -> tuple[dict[str, TriState], int]:
    """Calculate common permission state across multiple files.

    For each permission bit, determines if all files have it set (CHECKED),
    none have it set (UNCHECKED), or some have it (MIXED).

    Args:
        paths: List of file paths to analyze.

    Returns:
        Tuple of (bit_states, failed_count) where:
        - bit_states: Dictionary mapping bit names to TriState values
        - failed_count: Number of files that could not be stat'd

        If all files fail to stat, bit_states will have all UNCHECKED values.
        Caller should check if failed_count == len(paths) to detect this.
    """
    if not paths:
        return {name: TriState.UNCHECKED for name in _PERMISSION_BITS}, 0

    # Get modes for all files
    modes = []
    failed_count = 0
    for path in paths:
        try:
            modes.append(path.stat().st_mode)
        except OSError:
            failed_count += 1
            continue

    if not modes:
        return {name: TriState.UNCHECKED for name in _PERMISSION_BITS}, failed_count

    result: dict[str, TriState] = {}

    for name, bit_mask in _PERMISSION_BITS.items():
        # Check if all files have this bit set or unset
        all_set = all(mode & bit_mask for mode in modes)
        none_set = all(not (mode & bit_mask) for mode in modes)

        if all_set:
            result[name] = TriState.CHECKED
        elif none_set:
            result[name] = TriState.UNCHECKED
        else:
            result[name] = TriState.MIXED

    return result, failed_count


def get_system_users() -> list[str]:
    """Get list of system usernames.

    Returns:
        Sorted list of usernames.
    """
    try:
        users = [entry.pw_name for entry in pwd.getpwall()]
        return sorted(users)
    except (KeyError, OSError):
        return []


def get_system_groups() -> list[str]:
    """Get list of system group names.

    Returns:
        Sorted list of group names.
    """
    try:
        groups = [entry.gr_name for entry in grp.getgrall()]
        return sorted(groups)
    except (KeyError, OSError):
        return []


def filter_by_prefix(items: list[str], prefix: str) -> list[str]:
    """Filter items by prefix (case-insensitive).

    Args:
        items: List of strings to filter.
        prefix: Prefix to match (case-insensitive).

    Returns:
        Sorted list of matching items.
    """
    prefix_lower = prefix.lower()
    matches = [item for item in items if item.lower().startswith(prefix_lower)]
    return sorted(matches)
