"""Python version check for Tiny Commander.

IMPORTANT: This module must use ONLY Python 3.0+ compatible syntax.
No type hints with | union, no list[str] generics, no walrus operator.
This ensures the version check itself doesn't crash on old Python.
"""

# Minimum required Python version
MIN_VERSION = (3, 13)


def check_python_version(version_info=None):
    """Check if Python version meets minimum requirements.

    Args:
        version_info: Tuple of (major, minor, micro) or None to use sys.version_info.

    Returns:
        None if version is OK, error message string if version is too old.
    """
    if version_info is None:
        import sys
        version_info = sys.version_info

    major = version_info[0]
    minor = version_info[1]

    if (major, minor) >= MIN_VERSION:
        return None

    return "tnc requires Python %d.%d or later. You have %d.%d." % (
        MIN_VERSION[0], MIN_VERSION[1], major, minor
    )
