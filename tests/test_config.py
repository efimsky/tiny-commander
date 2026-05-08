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


class TestConfigParseWarnings(unittest.TestCase):
    """Config.load should validate values and surface warnings (issue #42)."""

    def test_empty_editor_value_is_rejected_with_warning(self):
        """`editor =` (empty) must not become an empty string."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / 'config'
            cfg_path.write_text('editor =\npager = less\n')
            config = Config.load(str(cfg_path))
            self.assertIsNone(config.editor,
                'Empty editor value should leave config.editor as None')
            self.assertTrue(any('editor' in w.lower() for w in config.parse_warnings),
                f'Expected a warning about editor, got: {config.parse_warnings!r}')

    def test_ambiguous_bool_value_warns(self):
        """`mouse_enabled = maybe` must warn rather than silently being False."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / 'config'
            cfg_path.write_text('mouse_enabled = maybe\n')
            config = Config.load(str(cfg_path))
            self.assertTrue(any('mouse_enabled' in w for w in config.parse_warnings),
                f'Expected a warning about mouse_enabled, got: {config.parse_warnings!r}')

    def test_clean_config_has_no_warnings(self):
        """A well-formed config file produces an empty warnings list."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / 'config'
            cfg_path.write_text('editor = nano\nmouse_enabled = yes\n')
            config = Config.load(str(cfg_path))
            self.assertEqual(config.parse_warnings, [])


class TestConfigLoadResilience(unittest.TestCase):
    """Config.load should not crash startup on weird/corrupt config files (issue #27)."""

    def test_load_returns_defaults_when_path_is_directory(self):
        """A directory at the config path must not crash startup."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / 'config'
            cfg_path.mkdir()
            config = Config.load(str(cfg_path))
            self.assertIsNotNone(config)

    def test_load_returns_defaults_on_invalid_utf8(self):
        """Non-UTF-8 bytes must not crash startup."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / 'config'
            cfg_path.write_bytes(b'\xff\xfe\x00\x00garbage\x80\x81')
            config = Config.load(str(cfg_path))
            self.assertIsNotNone(config)

    def test_load_returns_defaults_on_partial_invalid_utf8(self):
        """A mid-file decode error must not crash; we fall back to defaults."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / 'config'
            cfg_path.write_bytes(b'editor = nano\nbroken = \xff\xfe\n')
            # Should not raise UnicodeDecodeError
            config = Config.load(str(cfg_path))
            self.assertIsNotNone(config)


class TestConfigSaveErrorReporting(unittest.TestCase):
    """Config.save should report failure rather than crash the caller (issue #26)."""

    def test_save_returns_true_on_success(self):
        """Successful writes return True."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'
            config = Config()
            self.assertTrue(config.save(str(config_path)))

    def test_save_returns_false_when_path_unwritable(self):
        """When the open() raises OSError, save returns False rather than propagating."""
        from unittest import mock
        from tnc.config import Config

        config = Config()
        with mock.patch('builtins.open', side_effect=PermissionError('readonly')):
            result = config.save('/some/path/config')

        self.assertFalse(result)

    def test_save_returns_false_when_disk_full(self):
        """OSError during write must be swallowed and surface as a False return."""
        from unittest import mock
        from tnc.config import Config

        config = Config()
        m = mock.mock_open()
        m.return_value.write.side_effect = OSError('disk full')
        with mock.patch('builtins.open', m):
            result = config.save('/some/path/config')

        self.assertFalse(result)


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
