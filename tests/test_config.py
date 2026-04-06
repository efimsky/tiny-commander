"""Tests for config file read/write."""

import os
import tempfile
import unittest
from pathlib import Path


class TestConfigReadWrite(unittest.TestCase):
    """Test reading and writing config files."""

    def test_read_existing_config(self):
        """Should read existing config file."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('editor = nano\npager = less\n')

            config = Config.load(str(config_path))
            self.assertEqual(config.editor, 'nano')
            self.assertEqual(config.pager, 'less')

    def test_read_missing_config_returns_defaults(self):
        """Missing config should return default values."""
        from tnc.config import Config
        config = Config.load('/nonexistent/path/config')
        self.assertIsNone(config.editor)
        self.assertIsNone(config.pager)
        self.assertTrue(config.classic_colors)  # Default is True

    def test_write_config_creates_file(self):
        """Writing config should create the file."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'

            config = Config()
            config.editor = 'vim'
            config.pager = 'more'
            config.save(str(config_path))

            self.assertTrue(config_path.exists())
            content = config_path.read_text()
            self.assertIn('editor = vim', content)
            self.assertIn('pager = more', content)
            self.assertIn('classic_colors = yes', content)  # Always written

    def test_read_classic_colors_yes(self):
        """Should parse classic_colors=yes as True."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('classic_colors = yes\n')

            config = Config.load(str(config_path))
            self.assertTrue(config.classic_colors)

    def test_read_classic_colors_true(self):
        """Should parse classic_colors=true as True."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('classic_colors = true\n')

            config = Config.load(str(config_path))
            self.assertTrue(config.classic_colors)

    def test_read_classic_colors_no(self):
        """Should parse classic_colors=no as False."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('classic_colors = no\n')

            config = Config.load(str(config_path))
            self.assertFalse(config.classic_colors)

    def test_read_classic_colors_false(self):
        """Should parse classic_colors=false as False."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('classic_colors = false\n')

            config = Config.load(str(config_path))
            self.assertFalse(config.classic_colors)

    def test_write_classic_colors_false(self):
        """Should write classic_colors=no when False."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'

            config = Config()
            config.classic_colors = False
            config.save(str(config_path))

            content = config_path.read_text()
            self.assertIn('classic_colors = no', content)


class TestConfigDirectoryCreation(unittest.TestCase):
    """Test config directory creation."""

    def test_write_creates_directory_if_missing(self):
        """Writing config should create parent directory."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'newdir' / 'subdir' / 'config'

            config = Config()
            config.editor = 'nano'
            config.save(str(config_path))

            self.assertTrue(config_path.exists())


class TestConfigParsing(unittest.TestCase):
    """Test config file parsing edge cases."""

    def test_read_ignores_empty_lines(self):
        """Empty lines should be ignored."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('editor = nano\n\npager = less\n')

            config = Config.load(str(config_path))
            self.assertEqual(config.editor, 'nano')
            self.assertEqual(config.pager, 'less')

    def test_read_ignores_comments(self):
        """Comments should be ignored."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('# This is a comment\neditor = nano\n')

            config = Config.load(str(config_path))
            self.assertEqual(config.editor, 'nano')

    def test_read_handles_spaces_around_equals(self):
        """Spaces around = should be handled."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('editor=nano\npager  =  less\n')

            config = Config.load(str(config_path))
            self.assertEqual(config.editor, 'nano')
            self.assertEqual(config.pager, 'less')

    def test_read_handles_malformed_line(self):
        """Malformed lines should be ignored."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('this line has no equals sign\neditor = nano\n')

            config = Config.load(str(config_path))
            self.assertEqual(config.editor, 'nano')


class TestConfigPath(unittest.TestCase):
    """Test default config path."""

    def test_config_path_default(self):
        """Default path should be in .config/tnc/."""
        from tnc.config import Config
        path = Config.default_path()
        self.assertIn('.config/tnc/config', path)


class TestMouseSwapConfig(unittest.TestCase):
    """Test mouse_swap config setting."""

    def test_mouse_swap_default_false(self):
        """Default mouse_swap should be False (right-handed)."""
        from tnc.config import Config
        config = Config()
        self.assertFalse(config.mouse_swap)

    def test_mouse_swap_load_yes(self):
        """Should parse mouse_swap=yes as True."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('mouse_swap = yes\n')

            config = Config.load(str(config_path))
            self.assertTrue(config.mouse_swap)

    def test_mouse_swap_load_no(self):
        """Should parse mouse_swap=no as False."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('mouse_swap = no\n')

            config = Config.load(str(config_path))
            self.assertFalse(config.mouse_swap)

    def test_mouse_swap_save_true(self):
        """Should write mouse_swap=yes when True."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'

            config = Config()
            config.mouse_swap = True
            config.save(str(config_path))

            content = config_path.read_text()
            self.assertIn('mouse_swap = yes', content)

    def test_mouse_swap_save_false(self):
        """Should write mouse_swap=no when False."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'

            config = Config()
            config.mouse_swap = False
            config.save(str(config_path))

            content = config_path.read_text()
            self.assertIn('mouse_swap = no', content)


class TestConfigPreserveUnknown(unittest.TestCase):
    """Test preserving unknown config keys."""

    def test_write_preserves_unknown_keys(self):
        """Unknown keys should be preserved when saving."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config_path.write_text('editor = nano\nfuture_setting = value\n')

            config = Config.load(str(config_path))
            config.editor = 'vim'
            config.save(str(config_path))

            content = config_path.read_text()
            self.assertIn('editor = vim', content)
            self.assertIn('future_setting = value', content)


if __name__ == '__main__':
    unittest.main()
