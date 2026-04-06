"""Tests for ColorManager class (replacing global color state)."""

import unittest
from unittest import mock

from tnc.colors import ColorManager, PAIR_CURSOR, PAIR_NORMAL


class TestColorManagerInit(unittest.TestCase):
    """Tests for ColorManager initialization."""

    def test_default_colors_disabled(self):
        """New ColorManager has colors disabled by default."""
        manager = ColorManager()
        self.assertFalse(manager.colors_enabled)

    def test_default_classic_theme(self):
        """New ColorManager defaults to classic theme."""
        manager = ColorManager()
        self.assertTrue(manager.classic_theme)

    def test_can_set_classic_theme_on_init(self):
        """Can set classic_theme=False on initialization."""
        manager = ColorManager(classic_theme=False)
        self.assertFalse(manager.classic_theme)


class TestColorManagerInitColors(unittest.TestCase):
    """Tests for ColorManager.init_colors()."""

    @mock.patch('curses.has_colors', return_value=False)
    def test_init_colors_no_color_support(self, _mock_has_colors):
        """init_colors returns False when terminal has no colors."""
        manager = ColorManager()
        result = manager.init_colors()
        self.assertFalse(result)
        self.assertFalse(manager.colors_enabled)

    @mock.patch('curses.init_pair')
    @mock.patch('curses.use_default_colors')
    @mock.patch('curses.start_color')
    @mock.patch('curses.has_colors', return_value=True)
    def test_init_colors_with_color_support(self, _mock_has, _mock_start,
                                            _mock_default, _mock_init):
        """init_colors returns True and enables colors when supported."""
        manager = ColorManager()
        result = manager.init_colors()
        self.assertTrue(result)
        self.assertTrue(manager.colors_enabled)


class TestColorManagerSetTheme(unittest.TestCase):
    """Tests for ColorManager.set_classic_theme()."""

    def test_set_classic_theme_true(self):
        """set_classic_theme(True) enables classic theme."""
        manager = ColorManager(classic_theme=False)
        manager.set_classic_theme(True)
        self.assertTrue(manager.classic_theme)

    def test_set_classic_theme_false(self):
        """set_classic_theme(False) disables classic theme."""
        manager = ColorManager(classic_theme=True)
        manager.set_classic_theme(False)
        self.assertFalse(manager.classic_theme)

    @mock.patch('curses.init_pair')
    @mock.patch('curses.use_default_colors')
    @mock.patch('curses.start_color')
    @mock.patch('curses.has_colors', return_value=True)
    def test_set_theme_reapplies_colors_when_enabled(self, _mock_has,
                                                      _mock_start, _mock_default,
                                                      mock_init_pair):
        """set_classic_theme reapplies colors when colors are enabled."""
        manager = ColorManager()
        manager.init_colors()
        initial_calls = mock_init_pair.call_count

        manager.set_classic_theme(False)

        # Should have called init_pair again
        self.assertGreater(mock_init_pair.call_count, initial_calls)


class TestColorManagerGetAttr(unittest.TestCase):
    """Tests for ColorManager.get_attr()."""

    def test_get_attr_no_colors_returns_normal(self):
        """get_attr returns A_NORMAL when colors disabled."""
        import curses
        manager = ColorManager()
        attr = manager.get_attr(PAIR_NORMAL)
        self.assertEqual(attr, curses.A_NORMAL)

    def test_get_attr_with_bold(self):
        """get_attr with bold=True includes A_BOLD."""
        import curses
        manager = ColorManager()
        attr = manager.get_attr(PAIR_NORMAL, bold=True)
        self.assertTrue(attr & curses.A_BOLD)

    def test_get_attr_with_reverse(self):
        """get_attr with reverse=True includes A_REVERSE."""
        import curses
        manager = ColorManager()
        attr = manager.get_attr(PAIR_NORMAL, reverse=True)
        self.assertTrue(attr & curses.A_REVERSE)

    def test_get_attr_cursor_gets_reverse_when_no_colors(self):
        """Cursor pairs get reverse video when colors disabled."""
        import curses
        manager = ColorManager()
        attr = manager.get_attr(PAIR_CURSOR)
        self.assertTrue(attr & curses.A_REVERSE)


class TestColorManagerIsolation(unittest.TestCase):
    """Tests demonstrating state isolation between instances."""

    def test_separate_instances_have_separate_state(self):
        """Two ColorManager instances have independent state."""
        manager1 = ColorManager(classic_theme=True)
        manager2 = ColorManager(classic_theme=False)

        self.assertTrue(manager1.classic_theme)
        self.assertFalse(manager2.classic_theme)

    def test_modifying_one_does_not_affect_other(self):
        """Modifying one ColorManager doesn't affect another."""
        manager1 = ColorManager(classic_theme=True)
        manager2 = ColorManager(classic_theme=True)

        manager1.set_classic_theme(False)

        self.assertFalse(manager1.classic_theme)
        self.assertTrue(manager2.classic_theme)


if __name__ == '__main__':
    unittest.main()
