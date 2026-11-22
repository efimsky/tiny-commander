"""Real-PTY E2E tests for mouse input (X10/SGR), menus, function bar, and mouse config."""

from __future__ import annotations

from contextlib import contextmanager
import curses
from pathlib import Path
import sys
import tempfile
from typing import Iterator
import unittest

from tests.terminal import MouseButton, TerminalDriver


def _isolated_env(xdg_config_home: Path) -> dict[str, str | None]:
    """Build an isolated environment dict with editor/pager vars unset."""
    return {
        'XDG_CONFIG_HOME': str(xdg_config_home),
        'EDITOR': None,
        'VISUAL': None,
        'PAGER': None,
    }


@contextmanager
def _isolated_dirs() -> Iterator[tuple[Path, Path, Path]]:
    """Create isolated temp (cwd, home, xdg_config_home) directories."""
    with tempfile.TemporaryDirectory(prefix='tnc_e2e_mouse_') as tmp:
        root = Path(tmp)
        cwd = root / 'work'
        home = root / 'home'
        xdg = root / 'xdg_config'
        cwd.mkdir()
        home.mkdir()
        xdg.mkdir()
        yield cwd, home, xdg


class TestPanelAndFunctionBarMouseX10AndSGR(unittest.TestCase):
    """Test panel mouse clicks, SGR wide coordinates, double-click, wheel, and FunctionBar."""

    def test_left_click_switches_panel_focus_and_selects_row(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'beta.txt').write_text('b', encoding='utf-8')
            (cwd / 'gamma.txt').write_text('c', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                self.assertTrue(term.screen.mouse_tracking)
                self.assertFalse(term.screen.sgr_mouse)
                self.assertIn('[Left]', term.screen.row_text(21))

                # Click 'beta.txt' in the right panel (second occurrence on screen)
                r_alpha_col, r_alpha_row = term.wait_for_text('alpha.txt', occurrence=1)
                r_beta_col, r_beta_row = term.wait_for_text('beta.txt', occurrence=1)
                term.click(r_beta_col, r_beta_row, settle=True)
                term.wait_until(
                    lambda s: '[Right]' in s.row_text(21) and 'beta.txt' in s.row_text(21),
                    description='right panel focus and beta.txt selection',
                )
                self.assertIn('3 of 4', term.screen.row_text(21))
                self.assertNotEqual(
                    term.screen.styles_for_text('beta.txt', row=r_beta_row, occurrence=1)[0],
                    term.screen.styles_for_text('alpha.txt', row=r_alpha_row, occurrence=1)[0],
                )
                self.assertGreaterEqual(r_alpha_col, 40)

                # Click 'gamma.txt' in the left panel (first occurrence on screen)
                l_gamma_col, l_gamma_row = term.wait_for_text('gamma.txt', occurrence=0)
                self.assertLess(l_gamma_col, 40)
                term.click(l_gamma_col, l_gamma_row, settle=True)
                term.wait_until(
                    lambda s: '[Left]' in s.row_text(21) and 'gamma.txt' in s.row_text(21),
                    description='left panel focus and gamma.txt selection',
                )
                self.assertIn('4 of 4', term.screen.row_text(21))

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_wide_sgr_mouse_clicks_past_column_223(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'beta.txt').write_text('b', encoding='utf-8')
            (cwd / 'gamma.txt').write_text('c', encoding='utf-8')

            with TerminalDriver(
                rows=28,
                cols=240,
                term='xterm-1006',
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                self.assertTrue(term.screen.mouse_tracking)
                self.assertTrue(term.screen.sgr_mouse)
                status_row = 25
                self.assertIn('[Left]', term.screen.row_text(status_row))

                _, beta_row = term.wait_for_text('beta.txt', occurrence=1)
                _, gamma_row = term.wait_for_text('gamma.txt', occurrence=1)

                # Click past column 223 in Right panel (cols 120..239) using SGR encoding
                term.click(230, beta_row, settle=True)
                term.wait_until(
                    lambda s: '[Right]' in s.row_text(status_row)
                    and 'beta.txt' in s.row_text(status_row),
                    description='SGR click at col 230 activates right panel and selects beta.txt',
                )

                term.click(235, gamma_row, settle=True)
                term.wait_until(
                    lambda s: '[Right]' in s.row_text(status_row)
                    and 'gamma.txt' in s.row_text(status_row),
                    description='SGR click at col 235 selects gamma.txt',
                )

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_double_click_enters_directory_and_double_click_parent_returns(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            sub_dir = cwd / 'sub_dir'
            sub_dir.mkdir()
            (sub_dir / 'nested.txt').write_text('inside', encoding='utf-8')
            (cwd / 'top_file.txt').write_text('outside', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                col, row = term.wait_for_text('sub_dir', occurrence=0)
                self.assertLess(col, 40)

                term.double_click(col, row)
                term.wait_until(
                    lambda s: s.contains('nested.txt') and '/sub_dir' in s.row_text(22),
                    description='double-click enters sub_dir',
                )

                term.wait_mouse_settle()
                up_col, up_row = term.wait_for_text('..', row=2, occurrence=0)
                self.assertLess(up_col, 40)
                term.double_click(up_col, up_row)
                term.wait_until(
                    lambda s: not s.contains('nested.txt')
                    and any(c < 40 for c, _ in s.find_all('top_file.txt'))
                    and 'sub_dir' in s.row_text(21),
                    description='double-click on .. returns to parent directory',
                )

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_mouse_wheel_scrolls_up_and_platform_gated_down(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            for i in range(30):
                (cwd / f'f{i:02d}.txt').write_text('x', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                term.press('end')
                term.wait_until(
                    lambda s: '31 of 31' in s.row_text(21) and 'f29.txt' in s.row_text(21),
                    description='End moves cursor to last entry',
                )
                self.assertFalse(any(c < 40 for c, _ in term.screen.find_all('f10.txt')))

                # Wheel up always scrolls cursor & viewport upward
                term.scroll('up', 15, 5, steps=3)
                term.wait_until(
                    lambda s: '28 of 31' in s.row_text(21) and 'f26.txt' in s.row_text(21),
                    description='wheel up moves cursor up 3 rows',
                )

                term.scroll('up', 15, 5, steps=16)
                term.wait_until(
                    lambda s: '12 of 31' in s.row_text(21)
                    and any(c < 40 for c, _ in s.find_all('f10.txt')),
                    description='wheel up scrolls earlier entries back into view',
                )

                # macOS system ncurses 6.0 ABI 4 lacks BUTTON5_PRESSED
                if hasattr(curses, 'BUTTON5_PRESSED'):
                    term.scroll('down', 15, 5, steps=2)
                    term.wait_until(
                        lambda s: '14 of 31' in s.row_text(21),
                        description='wheel down moves cursor down when BUTTON5_PRESSED exists',
                    )

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_function_bar_mouse_clicks_help_mkdir_menu_and_quit(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()

                # F1 -> Help modal -> Esc
                term.click_text('F1', row=23)
                term.wait_for_text('Keyboard Shortcuts')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Keyboard Shortcuts'),
                    description='Esc dismisses Help modal',
                )

                # F7 -> Mkdir modal -> Esc
                term.click_text('F7', row=23)
                term.wait_for_text('Create directory')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Create directory'),
                    description='Esc dismisses Mkdir modal',
                )

                # F9 -> MenuBar dropdown -> Esc
                term.click_text('F9', row=23, settle=True)
                term.wait_for_text('Sort by name')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Sort by name'),
                    description='Esc dismisses MenuBar dropdown',
                )
                self.assertTrue(term.is_alive())
                self.assertIn('[Left]', term.screen.row_text(21))

                # F10 -> clean quit
                term.click_text('F10', row=23)
                rc = term.wait_exit()

            self.assertEqual(rc, 0)
            self.assertFalse(term.screen.in_alt_screen)
            self.assertFalse(term.screen.mouse_tracking)
            self.assertTrue(term.screen.cursor_visible)


class TestMenuBarMouseAndKeyboard(unittest.TestCase):
    """Test MenuBar keyboard navigation/wrapping, mouse clicks, and disabled items."""

    def test_keyboard_menu_bar_wrap_dropdown_execute_and_esc(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            (cwd / '.hidden_note').write_text('secret', encoding='utf-8')
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'zebra.txt').write_text('z', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                self.assertTrue(any(c < 40 for c, _ in term.screen.find_all('.hidden_note')))

                # F9 opens first menu ('Left')
                term.press('f9')
                col, _ = term.wait_for_text('Sort by name')
                self.assertLess(col, 10)

                # Left arrow wraps from first menu ('Left') to last menu ('Right')
                term.press('left')
                term.wait_until(
                    lambda s: (pos := s.find_text('Sort by name')) is not None and pos[0] >= 25,
                    description='Left arrow wraps menu bar to Right menu',
                )

                # Right arrow wraps from last menu ('Right') back to 'Left'
                term.press('right')
                term.wait_until(
                    lambda s: (pos := s.find_text('Sort by name')) is not None and pos[0] < 10,
                    description='Right arrow wraps menu bar back to Left menu',
                )

                # Cycle right across all remaining top-level menus
                term.press('right')
                term.wait_for_text('Permissions...')
                term.press('right')
                term.wait_for_text('Invert selection')
                term.press('right')
                term.wait_for_text('Swap mouse buttons')
                term.press('right')
                term.wait_until(
                    lambda s: (pos := s.find_text('Reverse sort')) is not None and pos[0] >= 25,
                    description='Right menu dropdown opened',
                )
                term.press('right')
                term.wait_until(
                    lambda s: (pos := s.find_text('Reverse sort')) is not None and pos[0] < 10,
                    description='Wrapped back to Left menu dropdown',
                )

                selected_style = term.screen.styles_for_text('Sort by name')[0]
                unselected_style = term.screen.styles_for_text('Toggle hidden')[0]
                self.assertNotEqual(selected_style, unselected_style)

                # Down/Up inside dropdown
                for _ in range(5):
                    term.press('down')
                term.wait_until(
                    lambda s: s.styles_for_text('Toggle hidden')[0] == selected_style,
                    description='Down moves selection to Toggle hidden',
                )
                term.press('up')
                term.wait_until(
                    lambda s: s.styles_for_text('Reverse sort')[0] == selected_style,
                    description='Up moves selection to Reverse sort',
                )
                term.press('down')
                term.wait_until(
                    lambda s: s.styles_for_text('Toggle hidden')[0] == selected_style,
                    description='Down returns selection to Toggle hidden',
                )

                # Enter executes selected menu command ('toggle_hidden_left')
                term.press('enter')
                term.wait_until(
                    lambda s: not s.contains('Sort by name')
                    and all(c >= 40 for c, _ in s.find_all('.hidden_note'))
                    and 'of 3' in s.row_text(21),
                    description='Toggle hidden hides dotfiles in left panel',
                )

                # F9 -> Esc closes dropdown without quitting
                term.press('f9')
                term.wait_for_text('Sort by name')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Sort by name'),
                    description='Esc closes dropdown without quitting',
                )
                self.assertTrue(term.is_alive())
                self.assertIn('[Left]', term.screen.row_text(21))

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_mouse_menu_open_execute_and_outside_click_dismiss(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            (cwd / '.hidden_file').write_text('secret', encoding='utf-8')
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'beta.txt').write_text('b', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                self.assertTrue(any(c < 40 for c, _ in term.screen.find_all('.hidden_file')))

                # Open Left menu via mouse and click 'Toggle hidden'
                term.click_text('Left', row=0)
                term.wait_for_text('Toggle hidden')
                term.click_text('Toggle hidden', settle=True)
                term.wait_until(
                    lambda s: not s.contains('Sort by name')
                    and all(c >= 40 for c, _ in s.find_all('.hidden_file'))
                    and 'of 3' in s.row_text(21),
                    description='mouse click Toggle hidden executes command',
                )

                # Open Command menu via mouse and click 'Select all'
                term.click_text('Command', row=0)
                term.wait_for_text('Select all')
                term.click_text('Select all', settle=True)
                term.wait_until(
                    lambda s: not s.contains('Select all') and '| 2 selected' in s.row_text(21),
                    description='mouse click Select all selects 2 visible files',
                )

                # Open File menu, switch to Options, then dismiss by clicking empty panel area
                term.click_text('File', row=0)
                term.wait_for_text('Permissions...')
                term.click_text('Options', row=0)
                term.wait_for_text('Classic colors')
                self.assertFalse(term.screen.contains('Permissions...'))

                term.click(15, 15, settle=True)
                term.wait_until(
                    lambda s: not s.contains('Classic colors'),
                    description='clicking empty panel area dismisses dropdown',
                )

                # Keyboard input works immediately after settled click
                term.press('tab')
                term.wait_for_text('[Right]')

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_disabled_menu_item_skipped_by_keyboard_and_ignored_on_click(self) -> None:
        helper_script = (
            'import curses, os\n'
            'from tnc.app import App\n'
            'from tnc.menu import MenuItem\n'
            'def _main(stdscr):\n'
            '    app = App(stdscr)\n'
            '    app.setup()\n'
            '    app.menu.menus[0].items.insert(\n'
            '        1, MenuItem("Disabled Action", "toggle_hidden_left", enabled=False)\n'
            '    )\n'
            '    try:\n'
            '        return app.run()\n'
            '    finally:\n'
            '        app.cleanup()\n'
            'os.environ.setdefault("ESCDELAY", "25")\n'
            'raise SystemExit(curses.wrapper(_main))\n'
        )
        with _isolated_dirs() as (cwd, home, xdg):
            (cwd / '.hidden_sentinel').write_text('h', encoding='utf-8')
            (cwd / 'a_first.txt').write_text('a', encoding='utf-8')
            (cwd / 'b_second.txt').write_text('bb', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                command=[sys.executable, '-c', helper_script],
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                self.assertTrue(any(c < 40 for c, _ in term.screen.find_all('.hidden_sentinel')))

                # Open Left menu; item 0 ('Sort by name') is selected, item 1 is disabled
                term.press('f9')
                term.wait_for_text('Disabled Action')
                selected_style = term.screen.styles_for_text('Sort by name')[0]
                disabled_style = term.screen.styles_for_text('Disabled Action')[0]
                self.assertNotEqual(selected_style, disabled_style)

                # Down skips over disabled item to index 2 ('Sort by size')
                term.press('down')
                term.wait_until(
                    lambda s: s.styles_for_text('Sort by size')[0] == selected_style
                    and s.styles_for_text('Disabled Action')[0] == disabled_style,
                    description='Down arrow skips over disabled item',
                )

                # Up skips over disabled item back to index 0 ('Sort by name')
                term.press('up')
                term.wait_until(
                    lambda s: s.styles_for_text('Sort by name')[0] == selected_style
                    and s.styles_for_text('Disabled Action')[0] == disabled_style,
                    description='Up arrow skips over disabled item',
                )

                # Clicking disabled item neither moves selection, closes dropdown, nor fires action
                term.click_text('Disabled Action', settle=True)
                term.wait_stable(quiet_period=0.06)
                self.assertTrue(term.screen.contains('Disabled Action'))
                self.assertTrue(term.screen.contains('Sort by size'))
                self.assertEqual(term.screen.styles_for_text('Sort by name')[0], selected_style)
                self.assertEqual(term.screen.styles_for_text('Disabled Action')[0], disabled_style)
                self.assertIn('1 of 4', term.screen.row_text(21))

                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Disabled Action'),
                    description='Esc closes dropdown after disabled click check',
                )
                self.assertTrue(any(c < 40 for c, _ in term.screen.find_all('.hidden_sentinel')))
                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)


class TestMouseToggleAndLeftHandedSwap(unittest.TestCase):
    """Test left-handed mouse button swap and mouse enable/disable persistence."""

    def test_left_handed_mouse_swap_swaps_primary_and_secondary_clicks(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            sub_dir = cwd / 'sub_dir'
            sub_dir.mkdir()
            (sub_dir / 'nested.txt').write_text('inside', encoding='utf-8')
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'beta.txt').write_text('b', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()

                # Enable 'Swap mouse buttons' via Options menu
                term.click_text('Options', row=0)
                term.wait_for_text('Swap mouse buttons')
                term.click_text('Swap mouse buttons', settle=True)
                term.wait_until(
                    lambda s: not s.contains('Swap mouse buttons'),
                    description='Swap mouse buttons menu closes',
                )

                # Right click now acts as primary click (switches panel & selects row)
                r_col, r_row = term.wait_for_text('beta.txt', occurrence=1)
                term.click(r_col, r_row, button=MouseButton.RIGHT, settle=True)
                term.wait_until(
                    lambda s: '[Right]' in s.row_text(21) and 'beta.txt' in s.row_text(21),
                    description='right click activates right panel when swapped',
                )
                self.assertNotIn('beta.txt', term.screen.row_text(22))

                # Right click on F1 opens Help modal
                term.click_text('F1', row=23, button=MouseButton.RIGHT)
                term.wait_for_text('Keyboard Shortcuts')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Keyboard Shortcuts'),
                    description='Help modal dismissed after swapped F1 click',
                )

                # Left click now acts as secondary click (inserts filename into command line)
                l_col, l_row = term.wait_for_text('alpha.txt', occurrence=0)
                term.click(l_col, l_row, button=MouseButton.LEFT, settle=True)
                term.wait_until(
                    lambda s: '[Left]' in s.row_text(21) and 'alpha.txt' in s.row_text(22),
                    description='left click inserts filename into command line when swapped',
                )

                # Clear command line before double-click test, and verify swapped double-click
                term.press_esc_settled()
                term.press_esc_settled()
                if hasattr(curses, 'BUTTON3_DOUBLE_CLICKED'):
                    sub_col, sub_row = term.wait_for_text('sub_dir', occurrence=0)
                    term.double_click(sub_col, sub_row, button=MouseButton.RIGHT)
                    term.wait_until(
                        lambda s: s.contains('nested.txt') and '/sub_dir' in s.row_text(22),
                        description='right double-click enters directory when swapped',
                    )

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

            cfg_path = home / '.config' / 'tnc' / 'config'
            self.assertTrue(cfg_path.exists())
            cfg_text = cfg_path.read_text(encoding='utf-8')
            self.assertIn('mouse_swap = yes', cfg_text)
            self.assertIn('mouse_enabled = yes', cfg_text)

    def test_disable_mouse_and_config_persistence(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'beta.txt').write_text('b', encoding='utf-8')

            # Session 1: disable mouse via Options -> Mouse support
            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                self.assertTrue(term.screen.mouse_tracking)

                term.click_text('Options', row=0)
                term.wait_for_text('Mouse support')
                term.click_text('Mouse support', settle=True)
                term.wait_until(
                    lambda s: not s.contains('Mouse support') and not s.mouse_tracking,
                    description='mouse tracking disabled after toggling Mouse support off',
                )

                # Mouse clicks are ignored when mouse is disabled
                term.click(60, 4, settle=True)
                term.wait_stable(quiet_period=0.06)
                self.assertIn('[Left]', term.screen.row_text(21))

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

            cfg_path = home / '.config' / 'tnc' / 'config'
            self.assertTrue(cfg_path.exists())
            cfg_text = cfg_path.read_text(encoding='utf-8')
            self.assertIn('mouse_enabled = no', cfg_text)
            self.assertIn('mouse_swap = no', cfg_text)

            # Session 2: persisted mouse_enabled=no starts with mouse tracking off,
            # then re-enable via keyboard menu navigation
            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()
                self.assertFalse(term.screen.mouse_tracking)

                term.press('f9')
                term.wait_for_text('Sort by name')
                for _ in range(3):
                    term.press('right')
                term.wait_for_text('Mouse support')
                selected_style = term.screen.styles_for_text('Editor settings')[0]
                for _ in range(3):
                    term.press('down')
                term.wait_until(
                    lambda s: s.styles_for_text('Mouse support')[0] == selected_style,
                    description='keyboard selects Mouse support item',
                )
                term.press('enter')
                term.wait_until(
                    lambda s: not s.contains('Mouse support') and s.mouse_tracking,
                    description='mouse tracking re-enabled via keyboard menu',
                )

                r_col, r_row = term.wait_for_text('beta.txt', occurrence=1)
                term.click(r_col, r_row, settle=True)
                term.wait_until(
                    lambda s: '[Right]' in s.row_text(21) and 'beta.txt' in s.row_text(21),
                    description='mouse clicks work again after re-enabling mouse support',
                )

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

            cfg_text_after = cfg_path.read_text(encoding='utf-8')
            self.assertIn('mouse_enabled = yes', cfg_text_after)

    def test_preexisting_mouse_swap_config_loaded_and_toggled_off(self) -> None:
        with _isolated_dirs() as (cwd, home, xdg):
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'beta.txt').write_text('b', encoding='utf-8')

            cfg_path = home / '.config' / 'tnc' / 'config'
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text('mouse_enabled = yes\nmouse_swap = yes\n', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home,
                env=_isolated_env(xdg),
            ) as term:
                term.wait_ready()

                # Loaded swap setting means RIGHT click performs primary selection
                r_col, r_row = term.wait_for_text('beta.txt', occurrence=1)
                term.click(r_col, r_row, button=MouseButton.RIGHT, settle=True)
                term.wait_until(
                    lambda s: '[Right]' in s.row_text(21) and 'beta.txt' in s.row_text(21),
                    description='preloaded mouse_swap uses RIGHT as primary click',
                )

                # Toggle swap back off using RIGHT click on Options -> Swap mouse buttons
                term.click_text('Options', row=0, button=MouseButton.RIGHT)
                term.wait_for_text('Swap mouse buttons')
                term.click_text('Swap mouse buttons', button=MouseButton.RIGHT, settle=True)
                term.wait_until(
                    lambda s: not s.contains('Swap mouse buttons'),
                    description='Swap mouse buttons toggled off',
                )

                # Standard LEFT click now performs primary selection again
                l_col, l_row = term.wait_for_text('alpha.txt', occurrence=0)
                term.click(l_col, l_row, button=MouseButton.LEFT, settle=True)
                term.wait_until(
                    lambda s: '[Left]' in s.row_text(21) and 'alpha.txt' in s.row_text(21),
                    description='LEFT click restored as primary click after swap off',
                )
                self.assertNotIn('alpha.txt', term.screen.row_text(22))

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

            cfg_text = cfg_path.read_text(encoding='utf-8')
            self.assertIn('mouse_swap = no', cfg_text)
            self.assertIn('mouse_enabled = yes', cfg_text)


if __name__ == '__main__':
    unittest.main()
