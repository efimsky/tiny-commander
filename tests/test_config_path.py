"""Tests for Config path injection."""

import os
import tempfile
import unittest
from pathlib import Path

from tnc.config import Config


class TestConfigPathInjection(unittest.TestCase):
    """Tests for injectable config path."""

    def test_config_stores_path(self):
        """Config instance stores its file path."""
        config = Config(path='/custom/path/config')
        self.assertEqual(config.path, '/custom/path/config')

    def test_config_default_path_when_none(self):
        """Config uses default_path() when path is None."""
        config = Config()
        self.assertEqual(config.path, Config.default_path())

    def test_load_stores_path(self):
        """Config.load() stores the path in the instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config')
            Path(config_path).write_text('editor = nano\n')

            config = Config.load(config_path)
            self.assertEqual(config.path, config_path)

    def test_save_uses_stored_path(self):
        """Config.save() uses stored path when no argument given."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config')
            config = Config(path=config_path)
            config.editor = 'vim'

            config.save()

            content = Path(config_path).read_text()
            self.assertIn('editor = vim', content)

    def test_save_with_explicit_path_overrides(self):
        """Config.save(path) uses explicit path, not stored path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stored_path = os.path.join(tmpdir, 'stored')
            explicit_path = os.path.join(tmpdir, 'explicit')
            config = Config(path=stored_path)
            config.editor = 'nano'

            config.save(explicit_path)

            self.assertFalse(Path(stored_path).exists())
            self.assertTrue(Path(explicit_path).exists())

    def test_load_missing_file_still_stores_path(self):
        """Config.load() for missing file still stores the path."""
        config = Config.load('/nonexistent/path/config')
        self.assertEqual(config.path, '/nonexistent/path/config')


class TestConfigTestIsolation(unittest.TestCase):
    """Tests demonstrating test isolation with injectable path."""

    def test_isolated_config_does_not_touch_user_config(self):
        """Creating Config with custom path doesn't read user's config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'test_config')
            config = Config(path=config_path)

            # Default values, not user's config
            self.assertIsNone(config.editor)
            self.assertIsNone(config.pager)

    def test_save_and_reload_with_same_path(self):
        """Save and reload cycle works with injected path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config')

            # Save config
            config1 = Config(path=config_path)
            config1.editor = 'emacs'
            config1.pager = 'less'
            config1.classic_colors = False
            config1.save()

            # Reload and verify
            config2 = Config.load(config_path)
            self.assertEqual(config2.editor, 'emacs')
            self.assertEqual(config2.pager, 'less')
            self.assertFalse(config2.classic_colors)


if __name__ == '__main__':
    unittest.main()
