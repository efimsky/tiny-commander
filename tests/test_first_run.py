"""Tests for first-run editor/pager setup."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestNeedsSetup(unittest.TestCase):
    """Test detection of needing setup."""

    def test_needs_editor_setup_when_no_config_no_env(self):
        """Should need editor setup when not configured and no env."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            self.assertTrue(config.needs_editor_setup())

    def test_needs_pager_setup_when_no_config_no_env(self):
        """Should need pager setup when not configured and no env."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            self.assertTrue(config.needs_pager_setup())

    def test_no_editor_setup_when_env_set(self):
        """No editor setup needed when EDITOR env is set."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {'EDITOR': 'vim'}):
            config = Config()
            self.assertFalse(config.needs_editor_setup())

    def test_no_pager_setup_when_env_set(self):
        """No pager setup needed when PAGER env is set."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {'PAGER': 'less'}):
            config = Config()
            self.assertFalse(config.needs_pager_setup())

    def test_no_editor_setup_when_config_set(self):
        """No editor setup needed when configured."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            config.editor = 'nano'
            self.assertFalse(config.needs_editor_setup())

    def test_no_pager_setup_when_config_set(self):
        """No pager setup needed when configured."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            config.pager = 'more'
            self.assertFalse(config.needs_pager_setup())


class TestGetEditorPager(unittest.TestCase):
    """Test getting editor/pager with env precedence."""

    def test_get_editor_prefers_env(self):
        """EDITOR env should take precedence over config."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {'EDITOR': 'vim'}):
            config = Config()
            config.editor = 'nano'
            self.assertEqual(config.get_editor(), 'vim')

    def test_get_pager_prefers_env(self):
        """PAGER env should take precedence over config."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {'PAGER': 'less'}):
            config = Config()
            config.pager = 'more'
            self.assertEqual(config.get_pager(), 'less')

    def test_get_editor_falls_back_to_config(self):
        """Should use config when no EDITOR env."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            config.editor = 'nano'
            self.assertEqual(config.get_editor(), 'nano')

    def test_get_pager_falls_back_to_config(self):
        """Should use config when no PAGER env."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            config.pager = 'more'
            self.assertEqual(config.get_pager(), 'more')

    def test_get_editor_returns_none_when_unset(self):
        """Should return None when no editor configured or env."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            self.assertIsNone(config.get_editor())

    def test_get_pager_returns_none_when_unset(self):
        """Should return None when no pager configured or env."""
        from tnc.config import Config
        with mock.patch.dict(os.environ, {}, clear=True):
            config = Config()
            self.assertIsNone(config.get_pager())


class TestEditorOptions(unittest.TestCase):
    """Test editor/pager option lists."""

    def test_editor_options_available(self):
        """Should have standard editor options."""
        from tnc.config import Config
        options = Config.get_editor_options()
        self.assertIn('vi', options)
        self.assertIn('nano', options)

    def test_pager_options_available(self):
        """Should have standard pager options."""
        from tnc.config import Config
        options = Config.get_pager_options()
        self.assertIn('less', options)
        self.assertIn('more', options)


class TestAvailablePrograms(unittest.TestCase):
    """Test detection of available editors/pagers on system."""

    def test_get_available_editors_filters_installed(self):
        """Only returns editors that exist on system (Linux)."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'linux'):
            with mock.patch('tnc.config.shutil.which') as mock_which:
                mock_which.side_effect = lambda cmd: cmd if cmd in ['vi', 'nano'] else None
                result = Config.get_available_editors()
                self.assertEqual(result, ['vi', 'nano'])

    def test_get_available_editors_returns_empty_when_none_found(self):
        """Returns empty list when no editors installed (Linux)."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'linux'):
            with mock.patch('tnc.config.shutil.which', return_value=None):
                result = Config.get_available_editors()
                self.assertEqual(result, [])

    def test_get_available_editors_includes_gui_editors(self):
        """Should check for GUI editors like subl, mate, code on macOS."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'darwin'):
            with mock.patch('tnc.config.shutil.which') as mock_which:
                mock_which.side_effect = lambda cmd: cmd if cmd in ['code', 'subl'] else None
                result = Config.get_available_editors()
                self.assertIn('code', result)
                self.assertIn('subl', result)

    def test_get_available_pagers_filters_installed(self):
        """Only returns pagers that exist on system."""
        from tnc.config import Config
        with mock.patch('tnc.config.shutil.which') as mock_which:
            mock_which.side_effect = lambda cmd: cmd if cmd == 'less' else None
            result = Config.get_available_pagers()
            self.assertEqual(result, ['less'])

    def test_get_available_pagers_returns_empty_when_none_found(self):
        """Returns empty list when no pagers installed."""
        from tnc.config import Config
        with mock.patch('tnc.config.shutil.which', return_value=None):
            result = Config.get_available_pagers()
            self.assertEqual(result, [])


class TestMacOSEditors(unittest.TestCase):
    """Test macOS-specific editor support."""

    def test_gui_editors_only_on_macos(self):
        """GUI editors (subl, mate, code) should only appear on macOS."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'linux'):
            with mock.patch('tnc.config.shutil.which') as mock_which:
                # All editors "installed"
                mock_which.side_effect = lambda cmd: cmd
                result = Config.get_available_editors()
                # Terminal editors should be present
                self.assertIn('vi', result)
                self.assertIn('nano', result)
                # GUI editors should NOT be present on Linux
                self.assertNotIn('subl', result)
                self.assertNotIn('mate', result)
                self.assertNotIn('code', result)
                self.assertNotIn('TextEdit', result)

    def test_gui_editors_appear_on_macos(self):
        """GUI editors should appear on macOS when installed."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'darwin'):
            with mock.patch('tnc.config.shutil.which') as mock_which:
                mock_which.side_effect = lambda cmd: cmd if cmd in ['vi', 'subl', 'code'] else None
                result = Config.get_available_editors()
                self.assertIn('vi', result)
                self.assertIn('subl', result)
                self.assertIn('code', result)

    def test_textedit_available_when_open_exists_on_macos(self):
        """TextEdit should be available when 'open' command exists on macOS."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'darwin'):
            with mock.patch('tnc.config.shutil.which') as mock_which:
                mock_which.side_effect = lambda cmd: cmd if cmd == 'open' else None
                result = Config.get_available_editors()
                self.assertIn('TextEdit', result)

    def test_textedit_not_available_on_linux(self):
        """TextEdit should not appear on Linux."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'linux'):
            with mock.patch('tnc.config.shutil.which', return_value=None):
                result = Config.get_available_editors()
                self.assertNotIn('TextEdit', result)

    def test_get_editor_command_returns_open_e_for_textedit(self):
        """TextEdit display name should map to 'open -e' command on macOS."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'darwin'):
            self.assertEqual(Config.get_editor_command('TextEdit'), 'open -e')

    def test_get_editor_command_returns_same_for_regular_editors(self):
        """Regular editor names should return unchanged."""
        from tnc.config import Config
        self.assertEqual(Config.get_editor_command('vim'), 'vim')
        self.assertEqual(Config.get_editor_command('nano'), 'nano')
        self.assertEqual(Config.get_editor_command('code'), 'code')

    def test_get_editor_command_textedit_unchanged_on_linux(self):
        """TextEdit should not be mapped on Linux."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'linux'):
            self.assertEqual(Config.get_editor_command('TextEdit'), 'TextEdit')

    def test_editor_options_include_gui_on_macos(self):
        """get_editor_options should include GUI editors on macOS."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'darwin'):
            options = Config.get_editor_options()
            self.assertIn('TextEdit', options)
            self.assertIn('subl', options)

    def test_editor_options_exclude_gui_on_linux(self):
        """get_editor_options should exclude GUI editors on Linux."""
        from tnc.config import Config
        with mock.patch('tnc.config.sys.platform', 'linux'):
            options = Config.get_editor_options()
            self.assertNotIn('TextEdit', options)
            self.assertNotIn('subl', options)
            # Terminal editors should still be present
            self.assertIn('vi', options)
            self.assertIn('nano', options)


class TestSaveFromSetup(unittest.TestCase):
    """Test saving config from setup."""

    def test_save_editor_choice(self):
        """Should save editor choice to config."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'

            config = Config()
            config.editor = 'nano'
            config.save(str(config_path))

            loaded = Config.load(str(config_path))
            self.assertEqual(loaded.editor, 'nano')

    def test_save_pager_choice(self):
        """Should save pager choice to config."""
        from tnc.config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config'

            config = Config()
            config.pager = 'less'
            config.save(str(config_path))

            loaded = Config.load(str(config_path))
            self.assertEqual(loaded.pager, 'less')


if __name__ == '__main__':
    unittest.main()
