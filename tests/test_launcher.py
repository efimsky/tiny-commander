"""Tests for bin/tnc launcher — selects newest Python 3.13+ on PATH."""

import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WRAPPER = PROJECT_ROOT / "bin" / "tnc"


def _make_shim(directory: Path, name: str, marker: str) -> Path:
    """Create an executable shim that prints `marker` and exits 0."""
    path = directory / name
    path.write_text("#!/bin/sh\necho " + marker + "\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class TncLauncherVersionSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="tnc-launcher-test-"))
        self.shims = self.tmpdir / "shims"
        self.shims.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, path_value: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(WRAPPER)],
            env={"PATH": path_value, "HOME": str(self.tmpdir)},
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_picks_highest_versioned_python(self):
        _make_shim(self.shims, "python3.13", "PICKED-3.13")
        _make_shim(self.shims, "python3.14", "PICKED-3.14")
        _make_shim(self.shims, "python3", "PICKED-PYTHON3")

        result = self._run(str(self.shims))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("PICKED-3.14", result.stdout)
        self.assertNotIn("PICKED-3.13", result.stdout)
        self.assertNotIn("PICKED-PYTHON3", result.stdout)

    def test_falls_back_to_python3_when_no_versioned_match(self):
        _make_shim(self.shims, "python3", "PICKED-PYTHON3")

        result = self._run(str(self.shims))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("PICKED-PYTHON3", result.stdout)

    def test_fails_cleanly_when_no_python_on_path(self):
        empty = self.tmpdir / "empty"
        empty.mkdir()

        result = self._run(str(empty))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.13", result.stderr)


if __name__ == "__main__":
    unittest.main()
