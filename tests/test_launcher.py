"""Tests for bin/tnc launcher — selects newest Python 3.13+ on PATH."""

import os
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
    return _make_script_shim(directory, name, f"echo {marker}\nexit 0\n")


def _make_script_shim(directory: Path, name: str, body: str) -> Path:
    """Create an executable sh shim with the given body."""
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
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


class TncLauncherSymlinkResolutionTest(unittest.TestCase):
    """Verify bin/tnc resolves symlink chains to the real project root (#114)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="tnc-symlink-test-")).resolve()
        self.shims = self.tmpdir / "shims"
        self.shims.mkdir()
        _make_script_shim(
            self.shims,
            "python3.13",
            'printf "%s\\n" "$PYTHONPATH"\nexit 0\n',
        )
        self.expected_root = str(PROJECT_ROOT.resolve())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_launcher(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        extra_path: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        path_value = str(self.shims)
        if extra_path:
            path_value = f"{path_value}:{extra_path}"
        env = {"PATH": path_value, "HOME": str(self.tmpdir)}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            cmd,
            cwd=str(cwd or self.tmpdir),
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_absolute_symlink_resolves_project_root_from_outside_repo(self):
        local_bin = self.tmpdir / "local_bin"
        local_bin.mkdir()
        link = local_bin / "tnc"
        link.symlink_to(WRAPPER)

        result = self._run_launcher([str(link)])

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), self.expected_root)

    def test_relative_symlink_resolves_project_root_from_outside_repo(self):
        nested = self.tmpdir / "a" / "b"
        nested.mkdir(parents=True)
        link = nested / "tnc"
        link.symlink_to(os.path.relpath(WRAPPER, nested))

        result = self._run_launcher(["./a/b/tnc"])

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), self.expected_root)

    def test_chained_symlinks_resolve_project_root_from_outside_repo(self):
        dir1 = self.tmpdir / "dir1"
        dir2 = self.tmpdir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        hop2 = dir2 / "tnc-mid"
        hop2.symlink_to(os.path.relpath(WRAPPER, dir2))
        hop1 = dir1 / "tnc"
        hop1.symlink_to(hop2)

        result = self._run_launcher([str(hop1)])

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), self.expected_root)

    def test_symlink_invoked_via_path_from_outside_repo(self):
        local_bin = self.tmpdir / "local_bin"
        local_bin.mkdir()
        (local_bin / "tnc").symlink_to(WRAPPER)

        result = self._run_launcher(["tnc"], extra_path=str(local_bin))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), self.expected_root)

    def test_symlink_invoked_without_slash_via_sh_in_cwd(self):
        link_dir = self.tmpdir / "cwd_bin"
        link_dir.mkdir()
        (link_dir / "tnc").symlink_to(WRAPPER)

        result = self._run_launcher(["/bin/sh", "tnc"], cwd=link_dir)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), self.expected_root)

    def test_symlinked_parent_dir_resolves_project_root(self):
        bin_link = self.tmpdir / "bin_link"
        bin_link.symlink_to(WRAPPER.parent)

        result = self._run_launcher([str(bin_link / "tnc")])

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), self.expected_root)

    def test_preserves_existing_pythonpath(self):
        local_bin = self.tmpdir / "local_bin"
        local_bin.mkdir()
        link = local_bin / "tnc"
        link.symlink_to(WRAPPER)

        result = self._run_launcher(
            [str(link)], extra_env={"PYTHONPATH": "/existing/path"}
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            result.stdout.strip(), f"{self.expected_root}:/existing/path"
        )


if __name__ == "__main__":
    unittest.main()
