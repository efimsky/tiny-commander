"""Entry point for running tnc as a module."""

import sys

# Check Python version BEFORE importing modules that use 3.10+ syntax
from tnc._version_check import check_python_version

_version_error = check_python_version()
if _version_error:
    sys.stderr.write(_version_error + "\n")
    sys.exit(1)

from tnc.app import run_app


def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
