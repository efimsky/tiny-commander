"""Tests for mouse support infrastructure."""

import curses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.app import Action, App
from tnc.config import Config
from tnc.panel import Panel


class TestConfigMouseEnabled(unittest.TestCase):
    """Test mouse_enabled config setting."""

    def test_mouse_enabled_default_true(self):
        """Mouse should be enabled by default."""
        config = Config()
        self.assertTrue(config.mouse_enabled)

    def test_load_mouse_enabled_yes(self):
        """Should load mouse_enabled = yes as True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = yes\n')
            f.flush()
            config = Config.load(f.name)
            self.assertTrue(config.mouse_enabled)

    def test_load_mouse_enabled_true(self):
        """Should load mouse_enabled = true as True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = true\n')
            f.flush()
            config = Config.load(f.name)
            self.assertTrue(config.mouse_enabled)

    def test_load_mouse_enabled_no(self):
        """Should load mouse_enabled = no as False."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = no\n')
            f.flush()
            config = Config.load(f.name)
            self.assertFalse(config.mouse_enabled)

    def test_load_mouse_enabled_false(self):
        """Should load mouse_enabled = false as False."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = false\n')
            f.flush()
            config = Config.load(f.name)
            self.assertFalse(config.mouse_enabled)

    def test_save_mouse_enabled_true(self):
        """Should save mouse_enabled = yes when True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / 'config')
            config = Config()
            config.mouse_enabled = True
            config.save(path)

            with open(path) as f:
                content = f.read()
            self.assertIn('mouse_enabled = yes', content)

    def test_save_mouse_enabled_false(self):
        """Should save mouse_enabled = no when False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / 'config')
            config = Config()
            config.mouse_enabled = False
            config.save(path)

            with open(path) as f:
                content = f.read()
            self.assertIn('mouse_enabled = no', content)

    def test_load_mouse_enabled_invalid_defaults_false(self):
        """Invalid mouse_enabled value should be treated as False."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = garbage\n')
            f.flush()
            config = Config.load(f.name)
            # Invalid values (not yes/true/1) are treated as False
            self.assertFalse(config.mouse_enabled)


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    mock_stdscr.getch.return_value = ord('q')
    return mock_stdscr


class TestMouseEnableDisable(unittest.TestCase):
    """Test mouse enable/disable methods."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_enable_mouse_calls_mousemask(self, mock_mousemask, _curs_set, _has_colors):
        """_enable_mouse should call curses.mousemask with click/scroll events."""
        mock_mousemask.return_value = 1  # Non-zero means success
        app = App(create_mock_stdscr())
        app.setup()

        app._enable_mouse()

        # Verify mousemask was called (specific events mask)
        self.assertTrue(mock_mousemask.called)
        args = mock_mousemask.call_args[0][0]
        # Should include click events but not ALL_MOUSE_EVENTS
        self.assertNotEqual(args, 0)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_disable_mouse_calls_mousemask_zero(self, mock_mousemask, _curs_set, _has_colors):
        """_disable_mouse should call curses.mousemask(0)."""
        app = App(create_mock_stdscr())
        app.setup()

        app._disable_mouse()

        mock_mousemask.assert_called_with(0)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_enable_mouse_returns_true_on_success(self, mock_mousemask, _curs_set, _has_colors):
        """_enable_mouse should return True when mouse is available."""
        mock_mousemask.return_value = 1  # Non-zero means success
        app = App(create_mock_stdscr())
        app.setup()

        result = app._enable_mouse()

        self.assertTrue(result)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_enable_mouse_returns_false_when_unavailable(self, mock_mousemask, _curs_set, _has_colors):
        """_enable_mouse should return False when mouse is not available."""
        mock_mousemask.return_value = 0  # Terminal doesn't support mouse
        app = App(create_mock_stdscr())
        app.setup()

        result = app._enable_mouse()

        self.assertFalse(result)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_setup_enables_mouse_when_config_enabled(self, mock_mousemask, _curs_set, _has_colors):
        """setup() should enable mouse when config.mouse_enabled is True."""
        mock_mousemask.return_value = 1  # Non-zero means success
        app = App(create_mock_stdscr())
        app.setup()

        # Mouse should be enabled by default (config.mouse_enabled defaults to True)
        # Verify mousemask was called with a non-zero event mask
        self.assertTrue(mock_mousemask.called)
        args = mock_mousemask.call_args[0][0]
        self.assertNotEqual(args, 0)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_setup_skips_mouse_when_config_disabled(self, mock_mousemask, _curs_set, _has_colors):
        """setup() should not enable mouse when config.mouse_enabled is False."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = no\n')
            config_path = f.name

        with mock.patch.object(Config, 'default_path', return_value=config_path):
            app = App(create_mock_stdscr())
            app.setup()

        # mousemask should not be called when mouse is disabled
        mock_mousemask.assert_not_called()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_toggle_when_terminal_unsupported(self, mock_mousemask, _curs_set, _has_colors):
        """Toggle should keep _mouse_active False when terminal doesn't support mouse."""
        mock_mousemask.return_value = 0  # Terminal doesn't support mouse

        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = no\n')
            config_path = f.name

        with mock.patch.object(Config, 'default_path', return_value=config_path):
            app = App(create_mock_stdscr())
            app.setup()

        # Mouse starts disabled
        self.assertFalse(app.mouse_enabled)

        # Try to toggle on, but terminal doesn't support it
        app._toggle_mouse()

        # _mouse_active should still be False because terminal doesn't support mouse
        self.assertFalse(app._mouse_active)


class TestMouseEventDetection(unittest.TestCase):
    """Test KEY_MOUSE event detection in run loop."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    @mock.patch('curses.getmouse')
    def test_key_mouse_calls_handle_mouse(self, mock_getmouse, mock_mousemask, _doupdate, _curs_set, _has_colors):
        """KEY_MOUSE should route to handle_mouse method."""
        mock_getmouse.return_value = (0, 10, 5, 0, curses.BUTTON1_CLICKED)
        mock_mousemask.return_value = 1  # Non-zero means success

        mock_stdscr = create_mock_stdscr()
        # Return KEY_MOUSE once, then F10 to quit
        mock_stdscr.getch.side_effect = [curses.KEY_MOUSE, curses.KEY_F10]

        app = App(mock_stdscr)
        app.setup()
        app.handle_mouse = mock.MagicMock(return_value=Action.NONE)

        app.run()

        app.handle_mouse.assert_called_once_with(10, 5, curses.BUTTON1_CLICKED)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    @mock.patch('curses.getmouse')
    def test_getmouse_error_handled_gracefully(self, mock_getmouse, mock_mousemask, _doupdate, _curs_set, _has_colors):
        """getmouse() errors should be caught and ignored."""
        mock_getmouse.side_effect = curses.error('no mouse event')
        mock_mousemask.return_value = 1  # Non-zero means success

        mock_stdscr = create_mock_stdscr()
        mock_stdscr.getch.side_effect = [curses.KEY_MOUSE, curses.KEY_F10]

        app = App(mock_stdscr)
        app.setup()

        # Should not raise exception
        app.run()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_handle_mouse_returns_action_none(self, mock_mousemask, _curs_set, _has_colors):
        """handle_mouse should return Action.NONE (placeholder for now)."""
        mock_mousemask.return_value = 1  # Non-zero means success
        app = App(create_mock_stdscr())
        app.setup()

        result = app.handle_mouse(10, 5, curses.BUTTON1_CLICKED)

        self.assertEqual(result, Action.NONE)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    @mock.patch('curses.mousemask')
    @mock.patch('curses.getmouse')
    def test_key_mouse_ignored_when_inactive(self, mock_getmouse, mock_mousemask, _doupdate, _curs_set, _has_colors):
        """KEY_MOUSE should be ignored when _mouse_active is False."""
        mock_getmouse.return_value = (0, 10, 5, 0, curses.BUTTON1_CLICKED)
        mock_mousemask.return_value = 0  # Terminal doesn't support mouse

        mock_stdscr = create_mock_stdscr()
        # Return KEY_MOUSE once, then F10 to quit
        mock_stdscr.getch.side_effect = [curses.KEY_MOUSE, curses.KEY_F10]

        app = App(mock_stdscr)
        app.setup()
        app.handle_mouse = mock.MagicMock(return_value=Action.NONE)

        app.run()

        # handle_mouse should NOT be called because _mouse_active is False
        app.handle_mouse.assert_not_called()


class TestMouseToggle(unittest.TestCase):
    """Test mouse toggle via Options menu."""

    def test_toggle_mouse_action_exists(self):
        """TOGGLE_MOUSE action should exist in Action enum."""
        self.assertTrue(hasattr(Action, 'TOGGLE_MOUSE'))

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_toggle_mouse_disables_when_enabled(self, mock_mousemask, _curs_set, _has_colors):
        """_toggle_mouse should disable mouse when currently enabled."""
        mock_mousemask.return_value = 1  # Non-zero means success
        app = App(create_mock_stdscr())
        app.setup()

        # Mouse is enabled by default after setup
        self.assertTrue(app.mouse_enabled)

        app._toggle_mouse()

        self.assertFalse(app.mouse_enabled)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_toggle_mouse_enables_when_disabled(self, mock_mousemask, _curs_set, _has_colors):
        """_toggle_mouse should enable mouse when currently disabled."""
        mock_mousemask.return_value = 1  # Non-zero means success

        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write('mouse_enabled = no\n')
            config_path = f.name

        with mock.patch.object(Config, 'default_path', return_value=config_path):
            app = App(create_mock_stdscr())
            app.setup()

        # Mouse is disabled via config
        self.assertFalse(app.mouse_enabled)

        app._toggle_mouse()

        self.assertTrue(app.mouse_enabled)


class TestMenuMouseOption(unittest.TestCase):
    """Test Options menu has Mouse support item."""

    def test_options_menu_has_mouse_support_item(self):
        """Options menu should have 'Mouse support' item."""
        from tnc.menu import MenuBar

        menu_bar = MenuBar()

        # Find Options menu
        options_menu = None
        for menu in menu_bar.menus:
            if menu.name == 'Options':
                options_menu = menu
                break

        self.assertIsNotNone(options_menu, "Options menu not found")

        # Check for Mouse support item
        mouse_item = None
        for item in options_menu.items:
            if item.name == 'Mouse support':
                mouse_item = item
                break

        self.assertIsNotNone(mouse_item, "'Mouse support' item not found in Options menu")
        self.assertEqual(mouse_item.action, 'toggle_mouse')


class TestMouseSwapAction(unittest.TestCase):
    """Test mouse button swap action and menu."""

    def test_toggle_mouse_swap_action_exists(self):
        """TOGGLE_MOUSE_SWAP action should exist in Action enum."""
        self.assertTrue(hasattr(Action, 'TOGGLE_MOUSE_SWAP'))

    def test_menu_action_map_has_toggle_mouse_swap(self):
        """MENU_ACTION_MAP should map 'toggle_mouse_swap' to Action."""
        from tnc.app import MENU_ACTION_MAP
        self.assertIn('toggle_mouse_swap', MENU_ACTION_MAP)
        self.assertEqual(MENU_ACTION_MAP['toggle_mouse_swap'], Action.TOGGLE_MOUSE_SWAP)

    def test_options_menu_has_swap_mouse_buttons_item(self):
        """Options menu should have 'Swap mouse buttons' item."""
        from tnc.menu import MenuBar

        menu_bar = MenuBar()

        # Find Options menu
        options_menu = None
        for menu in menu_bar.menus:
            if menu.name == 'Options':
                options_menu = menu
                break

        self.assertIsNotNone(options_menu, "Options menu not found")

        # Check for Swap mouse buttons item
        swap_item = None
        for item in options_menu.items:
            if item.name == 'Swap mouse buttons':
                swap_item = item
                break

        self.assertIsNotNone(swap_item, "'Swap mouse buttons' item not found in Options menu")
        self.assertEqual(swap_item.action, 'toggle_mouse_swap')


class TestMouseButtonTranslation(unittest.TestCase):
    """Test mouse button state translation for swap."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_translate_button_state_no_swap(self, mock_mousemask, _curs_set, _has_colors):
        """Without swap, button state should be unchanged."""
        mock_mousemask.return_value = 1
        app = App(create_mock_stdscr())
        app.setup()
        app.config.mouse_swap = False

        # BUTTON1_CLICKED should remain unchanged
        result = app._translate_button_state(curses.BUTTON1_CLICKED)
        self.assertEqual(result, curses.BUTTON1_CLICKED)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_translate_button_state_swap_button1_to_button3(self, mock_mousemask, _curs_set, _has_colors):
        """With swap, BUTTON1_CLICKED should become BUTTON3_CLICKED."""
        mock_mousemask.return_value = 1
        app = App(create_mock_stdscr())
        app.setup()
        app.config.mouse_swap = True

        result = app._translate_button_state(curses.BUTTON1_CLICKED)
        self.assertEqual(result, curses.BUTTON3_CLICKED)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_translate_button_state_swap_button3_to_button1(self, mock_mousemask, _curs_set, _has_colors):
        """With swap, BUTTON3_CLICKED should become BUTTON1_CLICKED."""
        mock_mousemask.return_value = 1
        app = App(create_mock_stdscr())
        app.setup()
        app.config.mouse_swap = True

        result = app._translate_button_state(curses.BUTTON3_CLICKED)
        self.assertEqual(result, curses.BUTTON1_CLICKED)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_translate_button_state_swap_double_click(self, mock_mousemask, _curs_set, _has_colors):
        """With swap, BUTTON1_DOUBLE_CLICKED should become BUTTON3_DOUBLE_CLICKED."""
        mock_mousemask.return_value = 1
        app = App(create_mock_stdscr())
        app.setup()
        app.config.mouse_swap = True

        result = app._translate_button_state(curses.BUTTON1_DOUBLE_CLICKED)
        # Double-click swaps to right double-click (or single if not available)
        expected = getattr(curses, 'BUTTON3_DOUBLE_CLICKED', curses.BUTTON3_CLICKED)
        self.assertEqual(result, expected)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_translate_button_state_swap_button3_double_to_button1_double(self, mock_mousemask, _curs_set, _has_colors):
        """With swap, BUTTON3_DOUBLE_CLICKED should become BUTTON1_DOUBLE_CLICKED."""
        mock_mousemask.return_value = 1
        app = App(create_mock_stdscr())
        app.setup()
        app.config.mouse_swap = True

        b3_double = getattr(curses, 'BUTTON3_DOUBLE_CLICKED', 0)
        if b3_double:  # Only test if the constant exists
            result = app._translate_button_state(b3_double)
            self.assertEqual(result, curses.BUTTON1_DOUBLE_CLICKED)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_translate_button_state_scroll_unchanged(self, mock_mousemask, _curs_set, _has_colors):
        """Scroll wheel should not be affected by swap."""
        mock_mousemask.return_value = 1
        app = App(create_mock_stdscr())
        app.setup()
        app.config.mouse_swap = True

        # BUTTON4_PRESSED (scroll up) should remain unchanged
        result = app._translate_button_state(curses.BUTTON4_PRESSED)
        self.assertEqual(result, curses.BUTTON4_PRESSED)


class TestMouseSwapToggle(unittest.TestCase):
    """Test toggling mouse swap setting."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_toggle_mouse_swap_toggles_config(self, mock_mousemask, _curs_set, _has_colors):
        """_toggle_mouse_swap should toggle config.mouse_swap."""
        mock_mousemask.return_value = 1
        app = App(create_mock_stdscr())
        app.setup()

        # Default is False
        self.assertFalse(app.config.mouse_swap)

        app._toggle_mouse_swap()

        self.assertTrue(app.config.mouse_swap)

        app._toggle_mouse_swap()

        self.assertFalse(app.config.mouse_swap)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_toggle_mouse_swap_saves_config(self, mock_mousemask, _curs_set, _has_colors):
        """_toggle_mouse_swap should save config to file."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / 'config')

            with mock.patch.object(Config, 'default_path', return_value=config_path):
                app = App(create_mock_stdscr())
                app.setup()

                app._toggle_mouse_swap()

                # Check file was saved with mouse_swap = yes
                with open(config_path) as f:
                    content = f.read()
                self.assertIn('mouse_swap = yes', content)


class TestPanelRenderPosition(unittest.TestCase):
    """Test panel render position tracking."""

    def test_panel_has_render_position_attributes(self):
        """Panel should have render_x, render_y, render_width, render_height."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            self.assertTrue(hasattr(panel, 'render_x'))
            self.assertTrue(hasattr(panel, 'render_y'))
            self.assertTrue(hasattr(panel, 'render_width'))
            self.assertTrue(hasattr(panel, 'render_height'))

    def test_render_stores_position(self):
        """render() should store the position it was rendered at."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()

            panel.render(mock_win, x=5, y=3)

            self.assertEqual(panel.render_x, 5)
            self.assertEqual(panel.render_y, 3)
            self.assertEqual(panel.render_width, 40)
            self.assertEqual(panel.render_height, 20)


class TestPanelContainsPoint(unittest.TestCase):
    """Test panel.contains_point() hit detection."""

    def test_contains_point_inside_panel(self):
        """Point inside panel should return True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Point well inside the panel
            self.assertTrue(panel.contains_point(20, 10))

    def test_contains_point_outside_panel_left(self):
        """Point left of panel should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=10, y=0)

            # Point to the left of panel (panel starts at x=10)
            self.assertFalse(panel.contains_point(5, 10))

    def test_contains_point_outside_panel_right(self):
        """Point right of panel should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Point beyond right edge (panel is 40 wide, so x=40 is outside)
            self.assertFalse(panel.contains_point(40, 10))

    def test_contains_point_outside_panel_top(self):
        """Point above panel should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=5)

            # Point above panel (panel starts at y=5)
            self.assertFalse(panel.contains_point(20, 3))

    def test_contains_point_outside_panel_bottom(self):
        """Point below panel should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Point below panel (panel is 20 high, so y=20 is outside)
            self.assertFalse(panel.contains_point(20, 20))

    def test_contains_point_at_boundary(self):
        """Points at exact boundary should be inside."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=10, y=5)

            # Top-left corner (exactly at boundary)
            self.assertTrue(panel.contains_point(10, 5))
            # Bottom-right corner (exclusive boundary)
            self.assertFalse(panel.contains_point(50, 25))
            # Just inside bottom-right
            self.assertTrue(panel.contains_point(49, 24))


class TestPanelEntryAtPoint(unittest.TestCase):
    """Test panel.entry_at_point() coordinate to entry mapping."""

    def test_entry_at_point_first_entry(self):
        """Click on first entry row should return index 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # First entry row is y=1 (y=0 is header)
            result = panel.entry_at_point(20, 1)
            self.assertEqual(result, 0)

    def test_entry_at_point_second_entry(self):
        """Click on second entry row should return index 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Second entry row is y=2
            result = panel.entry_at_point(20, 2)
            self.assertEqual(result, 1)

    def test_entry_at_point_with_offset(self):
        """Click should account for panel's render position."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=10, y=5)

            # First entry is at y = render_y + 1 = 6
            result = panel.entry_at_point(20, 6)
            self.assertEqual(result, 0)

    def test_entry_at_point_header_returns_none(self):
        """Click on header row should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Header is at y=0
            result = panel.entry_at_point(20, 0)
            self.assertIsNone(result)

    def test_entry_at_point_outside_panel_returns_none(self):
        """Click outside panel should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Click outside panel bounds
            result = panel.entry_at_point(50, 10)
            self.assertIsNone(result)

    def test_entry_at_point_past_entries_returns_none(self):
        """Click on empty row (past entries) should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Only create one file, so only 2 entries (.. and file)
            Path(tmpdir, 'file1.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Click on row 10 (only 2 entries exist)
            result = panel.entry_at_point(20, 10)
            self.assertIsNone(result)

    def test_entry_at_point_with_scroll_offset(self):
        """Click should account for scroll offset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files to enable scrolling
            for i in range(30):
                Path(tmpdir, f'file{i:02d}.txt').touch()

            panel = Panel(tmpdir, width=40, height=10)  # Small height
            mock_win = mock.MagicMock()
            panel.render(mock_win, x=0, y=0)

            # Scroll down
            panel.scroll_offset = 5

            # Click on first visible row (y=1) should return scroll_offset + 0 = 5
            result = panel.entry_at_point(20, 1)
            self.assertEqual(result, 5)


class TestPanelClickRouting(unittest.TestCase):
    """Test App.handle_mouse() routes clicks to correct panel."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_click_left_panel_makes_it_active(self, mock_mousemask, _curs_set, _has_colors):
        """Clicking left panel should make it active."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Make right panel active first
        app.active_panel = app.right_panel
        app.left_panel.is_active = False
        app.right_panel.is_active = True

        # Simulate render to set panel positions
        app.left_panel.render_x = 0
        app.left_panel.render_y = 0
        app.left_panel.render_width = 40
        app.left_panel.render_height = 21
        app.right_panel.render_x = 40
        app.right_panel.render_y = 0
        app.right_panel.render_width = 40
        app.right_panel.render_height = 21

        # Click in left panel area
        app.handle_mouse(10, 5, curses.BUTTON1_CLICKED)

        self.assertEqual(app.active_panel, app.left_panel)
        self.assertTrue(app.left_panel.is_active)
        self.assertFalse(app.right_panel.is_active)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_click_right_panel_makes_it_active(self, mock_mousemask, _curs_set, _has_colors):
        """Clicking right panel should make it active."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Left panel is active by default
        self.assertEqual(app.active_panel, app.left_panel)

        # Simulate render positions
        app.left_panel.render_x = 0
        app.left_panel.render_y = 0
        app.left_panel.render_width = 40
        app.left_panel.render_height = 21
        app.right_panel.render_x = 40
        app.right_panel.render_y = 0
        app.right_panel.render_width = 40
        app.right_panel.render_height = 21

        # Click in right panel area
        app.handle_mouse(50, 5, curses.BUTTON1_CLICKED)

        self.assertEqual(app.active_panel, app.right_panel)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_click_moves_cursor_to_entry(self, mock_mousemask, _curs_set, _has_colors):
        """Single click should move cursor to clicked entry."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Simulate render positions
        app.left_panel.render_x = 0
        app.left_panel.render_y = 0
        app.left_panel.render_width = 40
        app.left_panel.render_height = 21

        # Cursor starts at 0
        app.left_panel.cursor = 0

        # Create mock entry_at_point to return index 3
        with mock.patch.object(app.left_panel, 'entry_at_point', return_value=3):
            app.handle_mouse(10, 5, curses.BUTTON1_CLICKED)

        self.assertEqual(app.left_panel.cursor, 3)


class TestPanelDoubleClick(unittest.TestCase):
    """Test double-click enters directory."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_double_click_calls_enter(self, mock_mousemask, _curs_set, _has_colors):
        """Double-click should call panel.enter()."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Simulate render positions
        app.left_panel.render_x = 0
        app.left_panel.render_y = 0
        app.left_panel.render_width = 40
        app.left_panel.render_height = 21

        with mock.patch.object(app.left_panel, 'entry_at_point', return_value=1):
            with mock.patch.object(app.left_panel, 'enter', return_value=None) as mock_enter:
                app.handle_mouse(10, 5, curses.BUTTON1_DOUBLE_CLICKED)
                mock_enter.assert_called_once()


class TestPanelRightClick(unittest.TestCase):
    """Test right-click inserts filename."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_right_click_inserts_filename(self, mock_mousemask, _curs_set, _has_colors):
        """Right-click should insert filename into command line."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / 'testfile.txt'
            test_file.touch()

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            # Change panel to tmpdir
            app.left_panel.path = Path(tmpdir)
            app.left_panel.refresh()

            # Simulate render positions
            app.left_panel.render_x = 0
            app.left_panel.render_y = 0
            app.left_panel.render_width = 40
            app.left_panel.render_height = 21

            # Find the index of testfile.txt
            file_idx = None
            for i, entry in enumerate(app.left_panel.entries):
                if entry.name == 'testfile.txt':
                    file_idx = i
                    break

            self.assertIsNotNone(file_idx, "Test file not found in entries")

            with mock.patch.object(app.left_panel, 'entry_at_point', return_value=file_idx):
                app.handle_mouse(10, 5, curses.BUTTON3_CLICKED)

            # Cursor should move to clicked entry
            self.assertEqual(app.left_panel.cursor, file_idx)
            # Filename should be in command line
            self.assertIn('testfile.txt', app.command_line.input_text)


class TestPanelScrollWheel(unittest.TestCase):
    """Test scroll wheel navigation."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_scroll_up_navigates_up(self, mock_mousemask, _curs_set, _has_colors):
        """Scroll up should call navigate_up()."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Simulate render positions
        app.left_panel.render_x = 0
        app.left_panel.render_y = 0
        app.left_panel.render_width = 40
        app.left_panel.render_height = 21

        with mock.patch.object(app.left_panel, 'navigate_up') as mock_nav:
            app.handle_mouse(10, 5, curses.BUTTON4_PRESSED)
            mock_nav.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_scroll_down_navigates_down(self, mock_mousemask, _curs_set, _has_colors):
        """Scroll down should call navigate_down()."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Simulate render positions
        app.left_panel.render_x = 0
        app.left_panel.render_y = 0
        app.left_panel.render_width = 40
        app.left_panel.render_height = 21

        # BUTTON5_PRESSED may not exist on all platforms
        button5 = getattr(curses, 'BUTTON5_PRESSED', 0x200000)

        with mock.patch.object(app.left_panel, 'navigate_down') as mock_nav:
            app.handle_mouse(10, 5, button5)
            mock_nav.assert_called_once()


class TestPanelClickEdgeCases(unittest.TestCase):
    """Test edge cases for panel mouse clicks."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_header_click_does_not_move_cursor(self, mock_mousemask, _curs_set, _has_colors):
        """Clicking header row should not move cursor."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            app.left_panel.path = Path(tmpdir)
            app.left_panel.refresh()
            app.left_panel.cursor = 2  # Set cursor to third entry

            # Simulate render positions
            app.left_panel.render_x = 0
            app.left_panel.render_y = 0
            app.left_panel.render_width = 40
            app.left_panel.render_height = 21

            # Click on header row (y=0)
            app.handle_mouse(10, 0, curses.BUTTON1_CLICKED)

            # Cursor should not have moved
            self.assertEqual(app.left_panel.cursor, 2)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_click_between_panels_does_nothing(self, mock_mousemask, _curs_set, _has_colors):
        """Clicking between panels should return Action.NONE and not change active panel."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Simulate render positions with a gap between panels (unrealistic but tests boundary)
        app.left_panel.render_x = 0
        app.left_panel.render_y = 0
        app.left_panel.render_width = 35
        app.left_panel.render_height = 21
        app.right_panel.render_x = 45  # Gap from 35-45
        app.right_panel.render_y = 0
        app.right_panel.render_width = 35
        app.right_panel.render_height = 21

        original_active = app.active_panel

        # Click in the gap
        result = app.handle_mouse(40, 10, curses.BUTTON1_CLICKED)

        self.assertEqual(result, Action.NONE)
        self.assertEqual(app.active_panel, original_active)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_right_click_on_dotdot_inserts_nothing(self, mock_mousemask, _curs_set, _has_colors):
        """Right-click on '..' should not insert anything into command line."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory and navigate into it
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            app.left_panel.path = subdir
            app.left_panel.refresh()

            # Simulate render positions
            app.left_panel.render_x = 0
            app.left_panel.render_y = 0
            app.left_panel.render_width = 40
            app.left_panel.render_height = 21

            # Find index of '..'
            dotdot_idx = None
            for i, entry in enumerate(app.left_panel.entries):
                if entry.name == '..':
                    dotdot_idx = i
                    break

            self.assertIsNotNone(dotdot_idx, "'..' entry not found")

            # Clear command line
            app.command_line.input_text = ''

            with mock.patch.object(app.left_panel, 'entry_at_point', return_value=dotdot_idx):
                app.handle_mouse(10, 5, curses.BUTTON3_CLICKED)

            # Command line should still be empty
            self.assertEqual(app.command_line.input_text, '')

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_click_below_entries_does_nothing(self, mock_mousemask, _curs_set, _has_colors):
        """Clicking below all entries should not move cursor."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            # Only '..' entry in an empty directory
            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            app.left_panel.path = Path(tmpdir)
            app.left_panel.refresh()
            original_cursor = app.left_panel.cursor

            # Simulate render positions
            app.left_panel.render_x = 0
            app.left_panel.render_y = 0
            app.left_panel.render_width = 40
            app.left_panel.render_height = 21

            # Click on row 10 (only 1 entry exists at row 1)
            app.handle_mouse(10, 10, curses.BUTTON1_CLICKED)

            # Cursor should not have moved
            self.assertEqual(app.left_panel.cursor, original_cursor)


class TestMiddleClickEnter(unittest.TestCase):
    """Test middle mouse button (scroll wheel click) acts as Enter."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_middle_click_calls_enter_on_active_panel(self, mock_mousemask, _curs_set, _has_colors):
        """Middle-click should call enter() on the active panel."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        with mock.patch.object(app.active_panel, 'enter', return_value=None) as mock_enter:
            app.handle_mouse(10, 5, curses.BUTTON2_CLICKED)
            mock_enter.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_middle_click_works_anywhere_on_screen(self, mock_mousemask, _curs_set, _has_colors):
        """Middle-click should work regardless of click position."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Test various positions - all should trigger enter()
        test_positions = [
            (0, 0),      # Top-left corner
            (79, 23),    # Bottom-right corner
            (40, 12),    # Center
            (100, 100),  # Outside visible area
        ]

        for x, y in test_positions:
            with mock.patch.object(app.active_panel, 'enter', return_value=None) as mock_enter:
                app.handle_mouse(x, y, curses.BUTTON2_CLICKED)
                mock_enter.assert_called_once()

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_middle_click_does_not_switch_panels(self, mock_mousemask, _curs_set, _has_colors):
        """Middle-click should not switch the active panel."""
        mock_mousemask.return_value = 1
        mock_stdscr = create_mock_stdscr(rows=24, cols=80)
        app = App(mock_stdscr)
        app.setup()

        # Ensure left panel is active
        app.active_panel = app.left_panel

        # Simulate render positions for right panel
        app.right_panel.render_x = 40
        app.right_panel.render_y = 0
        app.right_panel.render_width = 40
        app.right_panel.render_height = 21

        # Middle-click on right panel area
        with mock.patch.object(app.left_panel, 'enter', return_value=None):
            app.handle_mouse(50, 5, curses.BUTTON2_CLICKED)

        # Active panel should still be left panel
        self.assertIs(app.active_panel, app.left_panel)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_middle_click_enters_directory(self, mock_mousemask, _curs_set, _has_colors):
        """Middle-click should enter directory when cursor is on directory."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            # Resolve symlinks for macOS (/var -> /private/var)
            tmpdir = Path(tmpdir).resolve()
            subdir = tmpdir / 'subdir'
            subdir.mkdir()

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            app.left_panel.path = tmpdir
            app.left_panel.refresh()
            # Cursor on subdir (after '..')
            app.left_panel.cursor = 1

            original_path = app.left_panel.path

            app.handle_mouse(10, 5, curses.BUTTON2_CLICKED)

            # Should have entered the directory
            self.assertEqual(app.left_panel.path, subdir)
            self.assertNotEqual(app.left_panel.path, original_path)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.mousemask')
    def test_middle_click_ignores_command_line(self, mock_mousemask, _curs_set, _has_colors):
        """Middle-click should enter directory even if command line has text."""
        mock_mousemask.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            # Resolve symlinks for macOS (/var -> /private/var)
            tmpdir = Path(tmpdir).resolve()
            subdir = tmpdir / 'subdir'
            subdir.mkdir()

            mock_stdscr = create_mock_stdscr(rows=24, cols=80)
            app = App(mock_stdscr)
            app.setup()

            app.left_panel.path = tmpdir
            app.left_panel.refresh()
            app.left_panel.cursor = 1  # On subdir

            # Set command line text (Enter key would execute this)
            app.command_line.input_text = "ls -la"

            app.handle_mouse(10, 5, curses.BUTTON2_CLICKED)

            # Should have entered directory, not executed command
            self.assertEqual(app.left_panel.path, subdir)


if __name__ == '__main__':
    unittest.main()
