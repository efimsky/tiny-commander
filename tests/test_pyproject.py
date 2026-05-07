"""Structural checks for pyproject.toml.

These guard against mis-sectioned keys (e.g. core `[project]` metadata
accidentally landing under `[project.scripts]`), which silently breaks
`pip install .` and registers bogus console scripts.
"""

import tomllib
import unittest
from pathlib import Path


PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


class PyprojectStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with PYPROJECT.open("rb") as f:
            cls.data = tomllib.load(f)

    def test_project_has_required_metadata(self):
        project = self.data["project"]
        self.assertEqual(project.get("name"), "tiny-commander")
        self.assertEqual(project.get("version"), "0.1.0")
        self.assertEqual(project.get("readme"), "README.md")
        self.assertTrue(project.get("description"))

    def test_project_scripts_only_exposes_tnc(self):
        scripts = self.data["project"].get("scripts", {})
        self.assertEqual(scripts, {"tnc": "tnc.__main__:main"})


if __name__ == "__main__":
    unittest.main()
