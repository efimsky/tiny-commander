"""Tests for color initialization and management."""

import unittest
from unittest.mock import MagicMock, patch


class TestColorInitialization(unittest.TestCase):
    """Tests for color pair initialization."""

    def test_init_colors_with_color_support(self):
        """Colors should be initialized when terminal supports colors."""
        with patch('tnc.colors.curses') as mock_curses:
            mock_curses.has_colors.return_value = True
            mock_curses.COLORS = 256
            mock_curses.COLOR_PAIRS = 256
            mock_curses.COLOR_BLACK = 0
            mock_curses.COLOR_RED = 1
            mock_curses.COLOR_GREEN = 2
            mock_curses.COLOR_YELLOW = 3
            mock_curses.COLOR_BLUE = 4
            mock_curses.COLOR_MAGENTA = 5
            mock_curses.COLOR_CYAN = 6
            mock_curses.COLOR_WHITE = 7

            from tnc.colors import init_colors
            result = init_colors()

            self.assertTrue(result)
            mock_curses.start_color.assert_called_once()
            mock_curses.use_default_colors.assert_called_once()
            # Should have called init_pair for each color pair
            self.assertGreater(mock_curses.init_pair.call_count, 0)

    def test_init_colors_without_color_support(self):
        """Should return False when terminal doesn't support colors."""
        with patch('tnc.colors.curses') as mock_curses:
            mock_curses.has_colors.return_value = False

            from tnc.colors import init_colors
            result = init_colors()

            self.assertFalse(result)
            mock_curses.start_color.assert_not_called()


class TestColorPairConstants(unittest.TestCase):
    """Tests for color pair constants."""

    def test_color_pair_constants_exist(self):
        """All expected color pair constants should be defined."""
        from tnc import colors

        # File type colors
        self.assertTrue(hasattr(colors, 'PAIR_NORMAL'))
        self.assertTrue(hasattr(colors, 'PAIR_DIRECTORY'))
        self.assertTrue(hasattr(colors, 'PAIR_SELECTED'))
        self.assertTrue(hasattr(colors, 'PAIR_EXECUTABLE'))
        self.assertTrue(hasattr(colors, 'PAIR_SYMLINK'))
        self.assertTrue(hasattr(colors, 'PAIR_BROKEN_LINK'))
        self.assertTrue(hasattr(colors, 'PAIR_HIDDEN'))

        # Cursor colors
        self.assertTrue(hasattr(colors, 'PAIR_CURSOR'))
        self.assertTrue(hasattr(colors, 'PAIR_CURSOR_SELECTED'))

        # Menu colors
        self.assertTrue(hasattr(colors, 'PAIR_MENU_BAR'))
        self.assertTrue(hasattr(colors, 'PAIR_MENU_SELECTED'))
        self.assertTrue(hasattr(colors, 'PAIR_DROPDOWN'))
        self.assertTrue(hasattr(colors, 'PAIR_DROPDOWN_SELECTED'))

        # UI element colors
        self.assertTrue(hasattr(colors, 'PAIR_FKEY'))
        self.assertTrue(hasattr(colors, 'PAIR_FKEY_LABEL'))
        self.assertTrue(hasattr(colors, 'PAIR_STATUS'))
        self.assertTrue(hasattr(colors, 'PAIR_CMDLINE'))
        self.assertTrue(hasattr(colors, 'PAIR_PANEL'))

    def test_color_pair_constants_are_unique(self):
        """All color pair constants should have unique values."""
        from tnc import colors

        pairs = [
            colors.PAIR_NORMAL,
            colors.PAIR_DIRECTORY,
            colors.PAIR_SELECTED,
            colors.PAIR_EXECUTABLE,
            colors.PAIR_SYMLINK,
            colors.PAIR_BROKEN_LINK,
            colors.PAIR_HIDDEN,
            colors.PAIR_CURSOR,
            colors.PAIR_CURSOR_SELECTED,
            colors.PAIR_MENU_BAR,
            colors.PAIR_MENU_SELECTED,
            colors.PAIR_DROPDOWN,
            colors.PAIR_DROPDOWN_SELECTED,
            colors.PAIR_FKEY,
            colors.PAIR_FKEY_LABEL,
            colors.PAIR_STATUS,
            colors.PAIR_CMDLINE,
            colors.PAIR_PANEL,
        ]
        self.assertEqual(len(pairs), len(set(pairs)), "Color pair constants must be unique")

    def test_pair_normal_is_zero(self):
        """PAIR_NORMAL must be 0 (curses reserves pair 0 for default colors)."""
        from tnc import colors
        self.assertEqual(colors.PAIR_NORMAL, 0)


class TestGetAttr(unittest.TestCase):
    """Tests for get_attr helper function."""

    def setUp(self):
        """Save original _colors_enabled state."""
        import tnc.colors as colors_module
        self._original_colors_enabled = colors_module._default_manager._colors_enabled

    def tearDown(self):
        """Restore original _colors_enabled state."""
        import tnc.colors as colors_module
        colors_module._default_manager._colors_enabled = self._original_colors_enabled

    def test_get_attr_with_colors(self):
        """get_attr should return color pair when colors are enabled."""
        with patch('tnc.colors.curses') as mock_curses:
            mock_curses.color_pair.return_value = 256  # Some color pair value
            mock_curses.A_BOLD = 2097152

            from tnc.colors import get_attr, PAIR_SELECTED
            import tnc.colors as colors_module
            colors_module._default_manager._colors_enabled = True

            attr = get_attr(PAIR_SELECTED, bold=True)

            mock_curses.color_pair.assert_called_with(PAIR_SELECTED)
            self.assertEqual(attr, 256 | mock_curses.A_BOLD)

    def test_get_attr_without_colors(self):
        """get_attr should return fallback attrs when colors disabled."""
        with patch('tnc.colors.curses') as mock_curses:
            mock_curses.A_BOLD = 2097152
            mock_curses.A_REVERSE = 262144
            mock_curses.A_NORMAL = 0

            from tnc.colors import get_attr, PAIR_SELECTED
            import tnc.colors as colors_module
            colors_module._default_manager._colors_enabled = False

            attr = get_attr(PAIR_SELECTED, bold=True)

            # Without colors, should use A_BOLD as fallback
            self.assertEqual(attr, mock_curses.A_BOLD)

    def test_get_attr_cursor_fallback_uses_reverse(self):
        """Cursor pairs should use reverse video in fallback mode."""
        with patch('tnc.colors.curses') as mock_curses:
            mock_curses.A_BOLD = 2097152
            mock_curses.A_REVERSE = 262144
            mock_curses.A_NORMAL = 0

            from tnc.colors import get_attr, PAIR_CURSOR
            import tnc.colors as colors_module
            colors_module._default_manager._colors_enabled = False

            attr = get_attr(PAIR_CURSOR)

            # Cursor should use reverse video for visibility without colors
            self.assertEqual(attr, mock_curses.A_REVERSE)


class TestColorsEnabled(unittest.TestCase):
    """Tests for colors_enabled function."""

    def setUp(self):
        """Save original _colors_enabled state."""
        import tnc.colors as colors_module
        self._original_colors_enabled = colors_module._default_manager._colors_enabled

    def tearDown(self):
        """Restore original _colors_enabled state."""
        import tnc.colors as colors_module
        colors_module._default_manager._colors_enabled = self._original_colors_enabled

    def test_colors_enabled_returns_state(self):
        """colors_enabled should return the current color state."""
        from tnc import colors

        colors._default_manager._colors_enabled = True
        self.assertTrue(colors.colors_enabled())

        colors._default_manager._colors_enabled = False
        self.assertFalse(colors.colors_enabled())


class TestInitColorsAndGetAttrIntegration(unittest.TestCase):
    """Integration tests for init_colors and get_attr working together."""

    def setUp(self):
        """Save original _colors_enabled state."""
        import tnc.colors as colors_module
        self._original_colors_enabled = colors_module._default_manager._colors_enabled

    def tearDown(self):
        """Restore original _colors_enabled state."""
        import tnc.colors as colors_module
        colors_module._default_manager._colors_enabled = self._original_colors_enabled

    def test_get_attr_uses_colors_after_init_colors_succeeds(self):
        """get_attr should use color pairs after init_colors returns True."""
        with patch('tnc.colors.curses') as mock_curses:
            # Setup for successful color initialization
            mock_curses.has_colors.return_value = True
            mock_curses.COLOR_BLUE = 4
            mock_curses.COLOR_YELLOW = 3
            mock_curses.COLOR_WHITE = 7
            mock_curses.COLOR_CYAN = 6
            mock_curses.COLOR_BLACK = 0
            mock_curses.color_pair.return_value = 512
            mock_curses.A_BOLD = 2097152

            from tnc.colors import init_colors, get_attr, PAIR_SELECTED

            # Initialize colors
            result = init_colors()
            self.assertTrue(result)

            # Now get_attr should use color_pair
            attr = get_attr(PAIR_SELECTED, bold=True)
            mock_curses.color_pair.assert_called_with(PAIR_SELECTED)
            self.assertEqual(attr, 512 | mock_curses.A_BOLD)

    def test_get_attr_uses_fallback_after_init_colors_fails(self):
        """get_attr should use fallback attrs after init_colors returns False."""
        with patch('tnc.colors.curses') as mock_curses:
            # Setup for failed color initialization
            mock_curses.has_colors.return_value = False
            mock_curses.A_BOLD = 2097152
            mock_curses.A_NORMAL = 0

            from tnc.colors import init_colors, get_attr, PAIR_SELECTED

            # Initialize colors (will fail)
            result = init_colors()
            self.assertFalse(result)

            # Now get_attr should use fallback
            attr = get_attr(PAIR_SELECTED, bold=True)
            mock_curses.color_pair.assert_not_called()
            self.assertEqual(attr, mock_curses.A_BOLD)


class TestThemeToggle(unittest.TestCase):
    """Tests for theme toggle functionality."""

    def setUp(self):
        """Save original theme state."""
        import tnc.colors as colors_module
        self._original_classic_theme = colors_module._default_manager._classic_theme

    def tearDown(self):
        """Restore original theme state."""
        import tnc.colors as colors_module
        colors_module._default_manager._classic_theme = self._original_classic_theme

    def test_is_classic_theme_returns_state(self):
        """is_classic_theme should return the current theme state."""
        from tnc.colors import is_classic_theme, set_classic_theme

        set_classic_theme(True)
        self.assertTrue(is_classic_theme())

        set_classic_theme(False)
        self.assertFalse(is_classic_theme())

    def test_set_classic_theme_changes_state(self):
        """set_classic_theme should change the theme state."""
        import tnc.colors as colors_module

        colors_module.set_classic_theme(True)
        self.assertTrue(colors_module._default_manager._classic_theme)

        colors_module.set_classic_theme(False)
        self.assertFalse(colors_module._default_manager._classic_theme)

    def test_default_theme_is_classic(self):
        """Default theme should be classic (blue background)."""
        import importlib
        import tnc.colors as colors_module
        # Reload module to reset to default state
        importlib.reload(colors_module)
        self.assertTrue(colors_module._default_manager._classic_theme)


if __name__ == '__main__':
    unittest.main()
