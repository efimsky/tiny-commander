"""Tests for toggle hidden files."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr, find_entry_index
from tnc.app import App


class HiddenFilesTestCase(unittest.TestCase):
    """Base class for hidden files tests with common setup."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmppath = Path(self.tmpdir.name)
        self.patcher_colors = mock.patch('curses.has_colors', return_value=False)
        self.patcher_curs = mock.patch('curses.curs_set')
        self.patcher_cwd = mock.patch('os.getcwd', return_value=self.tmpdir.name)
        self.patcher_colors.start()
        self.patcher_curs.start()
        self.patcher_cwd.start()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.patcher_cwd.stop()
        self.patcher_curs.stop()
        self.patcher_colors.stop()
        self.tmpdir.cleanup()

    def create_files(self, *names: str) -> None:
        """Create empty files in the temp directory."""
        for name in names:
            (self.tmppath / name).write_text('')

    def create_app(self) -> App:
        """Create and set up an App instance."""
        app = App(create_mock_stdscr())
        app.setup()
        return app

    def get_entry_names(self, panel) -> list[str]:
        """Get list of entry names from a panel."""
        return [e.name for e in panel.entries]


class TestHiddenFilesDefault(HiddenFilesTestCase):
    """Test hidden files shown by default."""

    def test_hidden_files_shown_by_default(self) -> None:
        """Hidden files should be visible by default."""
        self.create_files('.hidden', 'visible.txt')
        panel = self.create_app().active_panel

        names = self.get_entry_names(panel)
        self.assertIn('.hidden', names)
        self.assertIn('visible.txt', names)

    def test_show_hidden_true_by_default(self) -> None:
        """show_hidden should be True by default."""
        panel = self.create_app().active_panel
        self.assertTrue(panel.show_hidden)


class TestToggleHidden(HiddenFilesTestCase):
    """Test toggling hidden files visibility."""

    def test_toggle_hides_dotfiles(self) -> None:
        """Toggling should hide dotfiles."""
        self.create_files('.hidden', 'visible.txt')
        panel = self.create_app().active_panel

        self.assertTrue(panel.show_hidden)
        panel.toggle_hidden()
        self.assertFalse(panel.show_hidden)

        names = self.get_entry_names(panel)
        self.assertNotIn('.hidden', names)
        self.assertIn('visible.txt', names)

    def test_toggle_shows_dotfiles(self) -> None:
        """Toggling again should show dotfiles."""
        self.create_files('.hidden', 'visible.txt')
        panel = self.create_app().active_panel

        panel.toggle_hidden()  # Hide
        panel.toggle_hidden()  # Show again

        self.assertTrue(panel.show_hidden)
        self.assertIn('.hidden', self.get_entry_names(panel))

    def test_dotdot_visible_when_hidden_off(self) -> None:
        """'..' should always be visible even when hiding dotfiles."""
        self.create_files('.hidden')
        panel = self.create_app().active_panel

        panel.toggle_hidden()

        names = self.get_entry_names(panel)
        self.assertIn('..', names)
        self.assertNotIn('.hidden', names)

    def test_setting_persists_after_refresh(self) -> None:
        """Hidden setting should persist after panel refresh."""
        self.create_files('.hidden')
        panel = self.create_app().active_panel

        panel.toggle_hidden()
        panel.refresh()

        self.assertFalse(panel.show_hidden)
        self.assertNotIn('.hidden', self.get_entry_names(panel))


class TestPanelsIndependent(HiddenFilesTestCase):
    """Test that panels have independent hidden settings."""

    def test_panels_have_independent_setting(self) -> None:
        """Left and right panels should have independent show_hidden settings."""
        self.create_files('.hidden', 'visible.txt')
        app = self.create_app()

        app.right_panel.toggle_hidden()

        left_names = self.get_entry_names(app.left_panel)
        right_names = self.get_entry_names(app.right_panel)

        self.assertIn('.hidden', left_names)
        self.assertNotIn('.hidden', right_names)


class TestCursorAdjustment(HiddenFilesTestCase):
    """Test cursor adjustment when hiding files."""

    def test_cursor_adjusts_when_hiding(self) -> None:
        """Cursor should adjust when current file becomes hidden."""
        self.create_files('.hidden', 'visible.txt')
        panel = self.create_app().active_panel

        panel.cursor = find_entry_index(panel, '.hidden')
        panel.toggle_hidden()

        current_entry = panel.entries[panel.cursor]
        is_dotfile = current_entry.name.startswith('.') and current_entry.name != '..'
        self.assertFalse(is_dotfile)


if __name__ == '__main__':
    unittest.main()
