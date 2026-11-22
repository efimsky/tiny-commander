"""Real-PTY E2E tests for modals, live resize, CLI/launcher, config, and lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import unittest

from tests.terminal import ExternalToolStub, MouseButton, TerminalDriver
from tnc import __version__ as tnc_version
from tnc._version_check import check_python_version
from tnc.config import Config

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BIN_TNC = _REPO_ROOT / 'bin' / 'tnc'
_ISOLATED_ENV: dict[str, str | None] = {
    'EDITOR': None,
    'PAGER': None,
    'VISUAL': None,
}


def _write_config(home: Path, content: str | bytes) -> Path:
    """Create `$HOME/.config/tnc/config` inside an isolated home directory."""
    cfg_path = home / '.config' / 'tnc' / 'config'
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        cfg_path.write_bytes(content)
    else:
        cfg_path.write_text(content, encoding='utf-8')
    return cfg_path


def _assert_terminal_restored(testcase: unittest.TestCase, term: TerminalDriver) -> None:
    """Verify alt-screen, mouse tracking, SGR mouse, and cursor visibility are restored."""
    testcase.assertFalse(term.screen.in_alt_screen)
    testcase.assertFalse(term.screen.mouse_tracking)
    testcase.assertFalse(term.screen.sgr_mouse)
    testcase.assertTrue(term.screen.cursor_visible)


def _open_options_menu(term: TerminalDriver) -> None:
    """Open the top Options menu dropdown via F2 + Right navigation."""
    term.press('f2')
    term.wait_for_text('Sort by name')
    term.press('right', 'right', 'right')
    term.wait_for_text('Editor settings')


def _trigger_copy_same_dir_error(term: TerminalDriver) -> None:
    """Trigger a real ErrorModal by attempting F5 copy when both panels share cwd."""
    term.press('f5')
    term.wait_for_text('Copy')
    term.press('y')
    term.wait_for_text('Copy completed with errors')
    term.wait_for_text('Cannot copy to same directory')


def _quit_cleanly(testcase: unittest.TestCase, term: TerminalDriver) -> None:
    """Send F10, assert exit code 0, and verify full terminal restoration."""
    term.press('f10')
    testcase.assertEqual(term.wait_exit(), 0)
    _assert_terminal_restored(testcase, term)


class TestModalsKeyboardMouseAndResize(unittest.TestCase):
    """End-to-end modal keyboard, mouse, and live-resize tests inside a real PTY."""

    def test_help_modal_sections_scrolling_and_dismiss(self) -> None:
        with TerminalDriver(rows=24, cols=80, env=_ISOLATED_ENV) as term:
            term.wait_ready()

            term.press('f1')
            term.wait_for_text('Keyboard Shortcuts')
            self.assertIn('Navigation', term.screen.text())
            self.assertIn('Up/Down/PgUp/PgDn to scroll (1-', term.screen.text())

            term.press('down')
            term.wait_for_text('(2-')
            term.press('pgdn')
            term.wait_until(
                lambda s: s.contains('Selection') and s.contains('Other'),
                description='HelpModal PgDn to bottom sections',
            )
            term.press('pgup')
            term.wait_for_text('(2-')
            term.press('up')
            term.wait_for_text('(1-')
            term.wait_for_text('Navigation')

            # Dismiss via Esc
            term.press_esc_settled()
            term.wait_until(
                lambda s: not s.contains('Keyboard Shortcuts'),
                description='HelpModal close on Esc',
            )

            # Re-open and dismiss via Enter
            term.press('f1')
            term.wait_for_text('Keyboard Shortcuts')
            term.press('enter')
            term.wait_until(
                lambda s: not s.contains('Keyboard Shortcuts'),
                description='HelpModal close on Enter',
            )

            # Re-open via F1 function-bar click, ignore outside click, close via OK click
            term.click_text('F1', row=23, settle=True)
            term.wait_for_text('Keyboard Shortcuts')
            term.click(2, 2, settle=True)
            self.assertTrue(term.screen.contains('Keyboard Shortcuts'))
            term.click_text('< OK >', settle=True)
            term.wait_until(
                lambda s: not s.contains('Keyboard Shortcuts'),
                description='HelpModal close on OK button click',
            )

            _quit_cleanly(self, term)

    def test_input_dialog_cursor_editing_and_mouse_actions(self) -> None:
        with tempfile.TemporaryDirectory() as cwd_str:
            cwd = Path(cwd_str)
            (cwd / 'existing.txt').write_text('x', encoding='utf-8')

            with TerminalDriver(rows=24, cols=80, cwd=cwd, env=_ISOLATED_ENV) as term:
                term.wait_ready()

                term.press('f7')
                term.wait_for_text('Create directory')
                self.assertIn('Enter directory name:', term.screen.text())
                self.assertIn('< OK >', term.screen.text())
                self.assertIn('Cancel', term.screen.text())

                # Cursor editing: type, left, insert, home, delete, end, backspace
                term.type_text('abef')
                term.wait_for_text('> abef')
                term.press('left', 'left', delay=0.01)
                term.type_text('cd')
                term.wait_for_text('> abcdef')
                term.press('home')
                term.press('delete')
                term.wait_for_text('> bcdef')
                term.press('end')
                term.press('backspace')
                term.wait_for_text('> bcde')

                # Non-ASCII UTF-8 bytes and Tab must not crash InputDialog
                term.type_text('é')
                term.press('tab')
                term.wait_stable()
                self.assertTrue(term.screen.contains('> bcde'))

                # Click inside text field at offset 2 ('d') to reposition cursor, then insert
                field_col, field_row = term.wait_for_text('> bcde')
                term.click(field_col + 4, field_row, settle=True)
                term.type_text('X')
                term.wait_for_text('> bcXde')

                # Click < OK > to confirm and create directory
                term.click_text('< OK >', settle=True)
                term.wait_until(
                    lambda s: not s.contains('Create directory') and s.contains('bcXde'),
                    description='InputDialog OK click creates directory',
                )
                self.assertTrue((cwd / 'bcXde').is_dir())

                # Cancel via Esc
                term.press('f7')
                term.wait_for_text('Create directory')
                term.type_text('cancelled_esc')
                term.press_esc_settled()
                term.wait_until(lambda s: not s.contains('Create directory'))
                self.assertFalse((cwd / 'cancelled_esc').exists())

                # Cancel via Cancel button click
                term.press('f7')
                term.wait_for_text('Create directory')
                term.type_text('cancelled_btn')
                term.click_text('Cancel', settle=True)
                term.wait_until(lambda s: not s.contains('Create directory'))
                self.assertFalse((cwd / 'cancelled_btn').exists())

                _quit_cleanly(self, term)

    def test_input_dialog_create_file_shift_f4_with_stub_editor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            cwd.mkdir()
            editor = ExternalToolStub.create(root / 'tools', 'stub_editor', append_text='created!')

            env = {
                'EDITOR': str(editor.path),
                'PAGER': None,
                'VISUAL': None,
            }
            with TerminalDriver(rows=24, cols=80, cwd=cwd, env=env) as term:
                term.wait_ready()

                term.press('shift+f4')
                term.wait_for_text('Create file')
                self.assertIn('Enter file name:', term.screen.text())
                term.type_text('draft.tx')
                term.press('home', 'right', 'end', delay=0.01)
                term.type_text('t')
                term.wait_for_text('> draft.txt')

                term.click_text('< OK >', settle=True)
                term.wait_until(lambda _s: len(editor.calls()) == 1, description='editor called for new file')
                term.wait_ready()
                self.assertEqual((cwd / 'draft.txt').read_text(encoding='utf-8'), 'created!')

                # Cancel Shift+F4 creates nothing
                term.press('shift+f4')
                term.wait_for_text('Create file')
                term.type_text('aborted.txt')
                term.click_text('Cancel', settle=True)
                term.wait_until(lambda s: not s.contains('Create file'))
                self.assertFalse((cwd / 'aborted.txt').exists())
                self.assertEqual(len(editor.calls()), 1)

                _quit_cleanly(self, term)

    def test_confirm_dialog_navigation_hotkeys_and_mouse(self) -> None:
        with tempfile.TemporaryDirectory() as cwd_str:
            cwd = Path(cwd_str)
            (cwd / 'a.txt').write_text('alpha', encoding='utf-8')
            (cwd / 'b.txt').write_text('beta', encoding='utf-8')

            with TerminalDriver(rows=24, cols=80, cwd=cwd, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                term.press('down')
                term.wait_for_text('a.txt')

                # Arrow / Tab button switching + Enter on No
                term.press('f8')
                term.wait_for_text('Delete Confirmation')
                self.assertIn('< Yes >', term.screen.text())
                term.press('right')
                term.wait_for_text('< No >')
                term.press('left')
                term.wait_for_text('< Yes >')
                term.press('tab')
                term.wait_for_text('< No >')
                term.press('enter')
                term.wait_until(lambda s: not s.contains('Delete Confirmation'))
                self.assertTrue((cwd / 'a.txt').exists())

                # Hotkey 'n' cancels
                term.press('f8')
                term.wait_for_text('Delete Confirmation')
                term.press('n')
                term.wait_until(lambda s: not s.contains('Delete Confirmation'))
                self.assertTrue((cwd / 'a.txt').exists())

                # Esc cancels
                term.press('f8')
                term.wait_for_text('Delete Confirmation')
                term.press_esc_settled()
                term.wait_until(lambda s: not s.contains('Delete Confirmation'))
                self.assertTrue((cwd / 'a.txt').exists())

                # Mouse click on No cancels
                term.press('f8')
                term.wait_for_text('Delete Confirmation')
                term.click_text('  No  ', settle=True)
                term.wait_until(lambda s: not s.contains('Delete Confirmation'))
                self.assertTrue((cwd / 'a.txt').exists())

                # Mouse click on Yes confirms delete of a.txt
                term.press('f8')
                term.wait_for_text('Delete Confirmation')
                term.click_text('< Yes >', settle=True)
                term.wait_until(
                    lambda s: not s.contains('Delete Confirmation')
                    and s.find_text('b.txt', row=21) is not None,
                    description='a.txt deleted via Yes click',
                )
                self.assertFalse((cwd / 'a.txt').exists())

                # Hotkey 'y' confirms delete of b.txt
                term.press('f8')
                term.wait_for_text('Delete Confirmation')
                term.press('y')
                term.wait_until(
                    lambda s: not s.contains('Delete Confirmation')
                    and s.find_text('1 of 1', row=21) is not None,
                    description='b.txt deleted via y hotkey',
                )
                self.assertFalse((cwd / 'b.txt').exists())

                _quit_cleanly(self, term)

    def test_error_dialog_real_copy_same_dir_and_dismissal(self) -> None:
        with tempfile.TemporaryDirectory() as cwd_str:
            cwd = Path(cwd_str)
            (cwd / 'sample.txt').write_text('content', encoding='utf-8')

            with TerminalDriver(rows=24, cols=80, cwd=cwd, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                term.press('down')
                term.wait_for_text('sample.txt')

                # Dismiss via Enter
                _trigger_copy_same_dir_error(term)
                term.press('enter')
                term.wait_until(lambda s: not s.contains('Copy completed with errors'))

                # Dismiss via Esc
                _trigger_copy_same_dir_error(term)
                term.press_esc_settled()
                term.wait_until(lambda s: not s.contains('Copy completed with errors'))

                # Ignore outside click; dismiss via OK click
                _trigger_copy_same_dir_error(term)
                term.click(1, 1, settle=True)
                self.assertTrue(term.screen.contains('Copy completed with errors'))
                term.click_text('< OK >', settle=True)
                term.wait_until(lambda s: not s.contains('Copy completed with errors'))

                _quit_cleanly(self, term)

    def test_f2_menu_navigation_and_selection_dialog_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            home = root / 'home'
            cwd.mkdir()
            home.mkdir()
            (cwd / 'file.txt').write_text('data', encoding='utf-8')

            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=_ISOLATED_ENV) as term:
                term.wait_ready()

                # F2 opens menu dropdown; test horizontal & vertical navigation + Up/Esc close
                term.press('f2')
                term.wait_for_text('Sort by name')
                term.press('right')
                term.wait_for_text('Permissions...')
                term.press('right')
                term.wait_for_text('Toggle select')
                term.press('right')
                term.wait_for_text('Editor settings')
                term.press('down')
                term.wait_until(
                    lambda s: s.find_styled_text('Pager settings', reverse=True) is not None
                    or s.contains('Pager settings'),
                    description='dropdown item highlight',
                )
                term.press('up')
                term.press('up')  # Up from item 0 closes dropdown
                term.wait_until(lambda s: not s.contains('Editor settings'))

                # Re-opening with F2 remembers last active menu (Options); Esc closes
                term.press('f2')
                term.wait_for_text('Editor settings')
                term.press_esc_settled()
                term.wait_until(lambda s: not s.contains('Editor settings'))

                # Open Options -> Editor settings -> SelectionDialog
                term.press('f2')
                term.wait_for_text('Editor settings')
                term.press('enter')
                term.wait_for_text('Select Editor')
                self.assertIn('Custom...', term.screen.text())
                self.assertIn('[Esc] to cancel', term.screen.text())

                # Move arrow down to highlight Custom..., enter custom mode, then Esc out cleanly
                for _ in range(len(Config.get_available_editors()) + 2):
                    if term.screen.find_styled_text('Custom...', reverse=True) is not None:
                        break
                    term.press('down')
                    term.wait_stable()
                self.assertIsNotNone(term.screen.find_styled_text('Custom...', reverse=True))
                term.press('enter')
                term.wait_for_text('Enter custom command:')
                term.type_text('custom_ed')
                term.wait_for_text('> custom_ed_')
                # First Esc exits custom input back to option list; second Esc cancels dialog
                term.press_esc_settled()
                term.wait_for_text('1-')
                self.assertFalse(term.screen.contains('Enter custom command:'))
                term.press_esc_settled()
                term.wait_until(lambda s: not s.contains('Select Editor'))
                cfg_file = home / '.config' / 'tnc' / 'config'
                self.assertFalse(cfg_file.exists())

                # Mouse: click Options menu -> Pager settings -> select option '1'
                term.click_text('Options', row=0, settle=True)
                term.wait_for_text('Pager settings')
                term.click_text('Pager settings', settle=True)
                term.wait_for_text('Select Pager')
                pagers = Config.get_available_pagers()
                self.assertTrue(pagers, 'Expected at least one pager installed on system')
                term.press('1')
                term.wait_until(lambda s: not s.contains('Select Pager'))

                _quit_cleanly(self, term)

            saved = Config.load(str(home / '.config' / 'tnc' / 'config'))
            self.assertEqual(saved.pager, Config.get_available_pagers()[0])

    def test_chmod_dialog_tab_navigation_and_mouse(self) -> None:
        with tempfile.TemporaryDirectory() as cwd_str:
            cwd = Path(cwd_str)
            target = cwd / 'perm.txt'
            target.write_text('hello', encoding='utf-8')
            target.chmod(0o644)

            with TerminalDriver(rows=24, cols=80, cwd=cwd, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                term.press('down')
                term.wait_for_text('perm.txt')

                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X]')
                term.press('c')
                term.wait_for_text('Change Permissions')
                term.wait_for_text('Mode: 0644')

                # Toggle Owner Execute bit (+x -> 0744)
                term.press('right', 'right', 'space', delay=0.01)
                term.wait_for_text('Mode: 0744')

                # Tab through sections (grid -> special -> buttons), toggle button focus, confirm
                term.press('tab', 'tab', delay=0.01)
                term.wait_for_text('[ >OK< ]')
                term.press('right')
                term.wait_for_text('[>Cancel<]')
                term.press('left')
                term.wait_for_text('[ >OK< ]')
                term.press('enter')
                term.wait_until(lambda s: not s.contains('Change Permissions'))
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o744)

                # Re-open and cancel via Cancel button click
                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X]')
                term.press('c')
                term.wait_for_text('Change Permissions')
                term.press('space')
                term.wait_for_text('Mode: 0344')
                term.click_text('Cancel', settle=True)
                term.wait_until(lambda s: not s.contains('Change Permissions'))
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o744)

                _quit_cleanly(self, term)

    def test_modal_live_resize_resilience(self) -> None:
        with tempfile.TemporaryDirectory() as cwd_str:
            cwd = Path(cwd_str)
            target = cwd / 'item.txt'
            target.write_text('hello', encoding='utf-8')
            target.chmod(0o644)

            with TerminalDriver(rows=24, cols=80, cwd=cwd, env=_ISOLATED_ENV) as term:
                term.wait_ready()

                # 1. HelpModal live resize 18x60 -> 32x110 (mouse dismiss + Esc dismiss)
                term.press('f1')
                term.wait_for_text('Keyboard Shortcuts')
                term.resize_and_wait(18, 60, predicate=lambda s: s.contains('< OK >'))
                self.assertEqual(term.screen.check_integrity(), [])
                term.resize_and_wait(32, 110, predicate=lambda s: s.contains('< OK >'))
                self.assertEqual(term.screen.check_integrity(), [])
                term.click_text('< OK >', settle=True)
                term.wait_until(lambda s: not s.contains('Keyboard Shortcuts'))

                term.press('f1')
                term.wait_for_text('Keyboard Shortcuts')
                term.resize_and_wait(18, 60, predicate=lambda s: s.contains('< OK >'))
                self.assertEqual(term.screen.check_integrity(), [])
                term.press_esc_settled()
                term.wait_until(lambda s: not s.contains('Keyboard Shortcuts'))

                # 2. InputDialog live resize 18x60 -> 32x110
                term.resize_and_wait(24, 80, predicate=lambda s: s.contains('F10'))
                term.press('f7')
                term.wait_for_text('Create directory')
                term.type_text('resize_me')
                term.resize_and_wait(
                    18, 60,
                    predicate=lambda s: s.contains('Cancel') and s.contains('resize_me'),
                )
                self.assertEqual(term.screen.check_integrity(), [])
                term.resize_and_wait(
                    32, 110,
                    predicate=lambda s: s.contains('Cancel') and s.contains('resize_me'),
                )
                self.assertEqual(term.screen.check_integrity(), [])
                term.click_text('Cancel', settle=True)
                term.wait_until(lambda s: not s.contains('Create directory'))

                # 3. ChmodDialog live resize 18x60 -> 32x110
                term.press('down')
                term.wait_for_text('item.txt')
                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X]')
                term.press('c')
                term.wait_for_text('Change Permissions')
                term.resize_and_wait(
                    18, 60,
                    predicate=lambda s: s.contains('Cancel') and s.contains('Change Permissions'),
                )
                self.assertEqual(term.screen.check_integrity(), [])
                term.resize_and_wait(
                    32, 110,
                    predicate=lambda s: s.contains('Cancel') and s.contains('Change Permissions'),
                )
                self.assertEqual(term.screen.check_integrity(), [])
                term.click_text('Cancel', settle=True)
                term.wait_until(lambda s: not s.contains('Change Permissions'))

                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X]')
                term.press('c')
                term.wait_for_text('Change Permissions')
                term.resize_and_wait(
                    18, 60,
                    predicate=lambda s: s.contains('Cancel') and s.contains('Change Permissions'),
                )
                self.assertEqual(term.screen.check_integrity(), [])
                term.press_esc_settled()
                term.wait_until(lambda s: not s.contains('Change Permissions'))

                raw_text = term.raw_output.decode('utf-8', errors='replace')
                self.assertNotIn('Traceback', raw_text)
                self.assertNotIn('curses.error', raw_text)

                _quit_cleanly(self, term)


class TestStartupConfigCLIAndLifecycle(unittest.TestCase):
    """End-to-end startup, launcher/CLI, config persistence, and signal lifecycle tests."""

    def test_launcher_bin_tnc_and_cwd_startup(self) -> None:
        self.assertEqual(tnc_version, '0.1.0')
        self.assertIn('3.13', check_python_version((3, 12, 0)) or '')

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'my_workspace'
            work.mkdir()
            (work / 'alpha.txt').write_text('a', encoding='utf-8')
            (work / 'subdir').mkdir()

            link_dir = root / 'bin_links'
            link_dir.mkdir()
            tnc_link = link_dir / 'tnc'
            tnc_link.symlink_to(_BIN_TNC)

            # Launch via symlinked bin/tnc launcher in a custom cwd
            with TerminalDriver(
                rows=24,
                cols=80,
                command=[str(tnc_link)],
                cwd=work,
                env=_ISOLATED_ENV,
            ) as term:
                term.wait_ready()
                # Both left & right panels start in cwd and list the same files
                alpha_hits = term.screen.find_all('alpha.txt')
                self.assertTrue(any(col < 40 for col, _ in alpha_hits), alpha_hits)
                self.assertTrue(any(col >= 40 for col, _ in alpha_hits), alpha_hits)
                self.assertIn(f'{work.name}>', term.screen.row_text(22))
                _quit_cleanly(self, term)

            # Extra unparsed CLI args do not crash tnc.__main__ startup
            with TerminalDriver(
                rows=24,
                cols=80,
                command=[sys.executable, '-m', 'tnc', '--version'],
                cwd=work,
                env=_ISOLATED_ENV,
            ) as term:
                term.wait_ready()
                self.assertIn('alpha.txt', term.screen.text())
                _quit_cleanly(self, term)

    def test_config_file_load_honors_all_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            home = root / 'home'
            xdg_other = root / 'xdg_unused'
            cwd.mkdir()
            home.mkdir()
            xdg_other.mkdir()
            (cwd / 'note.txt').write_text('hello', encoding='utf-8')

            editor = ExternalToolStub.create(root / 'tools', 'cfg_ed')
            pager = ExternalToolStub.create(root / 'tools', 'cfg_pg')

            # 1. Modern colors, mouse disabled, custom editor & pager via ~/.config/tnc/config
            _write_config(
                home,
                f'editor = {editor.path}\n'
                f'pager = {pager.path}\n'
                'classic_colors = no\n'
                'mouse_enabled = no\n'
                'mouse_swap = no\n',
            )
            env = {
                **_ISOLATED_ENV,
                'XDG_CONFIG_HOME': str(xdg_other),
            }
            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=env) as term:
                term.wait_ready()
                self.assertIsNone(term.screen.style_at(1, 0).bg)
                self.assertFalse(term.screen.mouse_tracking)

                # With mouse_enabled=no, clicking right panel keeps focus on [Left]
                term.click(60, 5, settle=True)
                self.assertIn('[Left]', term.screen.text())
                self.assertNotIn('[Right]', term.screen.text())

                # Config editor & pager work when env vars are unset
                term.press('down')
                term.wait_for_text('note.txt')
                term.press('f3')
                term.wait_until(lambda _s: len(pager.calls()) == 1)
                term.wait_ready()
                term.press('f4')
                term.wait_until(lambda _s: len(editor.calls()) == 1)
                term.wait_ready()

                _quit_cleanly(self, term)

            # 2. Classic colors, mouse enabled, mouse_swap = yes
            _write_config(
                home,
                'classic_colors = yes\n'
                'mouse_enabled = yes\n'
                'mouse_swap = yes\n',
            )
            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                self.assertEqual(term.screen.style_at(1, 0).bg, 4)
                self.assertTrue(term.screen.mouse_tracking)

                # Swapped right-click acts as primary click (switches panel & opens Help)
                term.click(60, 5, button=MouseButton.RIGHT, settle=True)
                term.wait_for_text('[Right]')

                f1_col, f1_row = term.wait_for_text('F1', row=23)
                term.click(f1_col, f1_row, button=MouseButton.RIGHT, settle=True)
                term.wait_for_text('Keyboard Shortcuts')
                ok_col, ok_row = term.wait_for_text('< OK >')
                term.click(ok_col, ok_row, button=MouseButton.RIGHT, settle=True)
                term.wait_until(lambda s: not s.contains('Keyboard Shortcuts'))

                # Swapped left-click on file entry inserts filename into command line
                note_col, note_row = term.wait_for_text('note.txt')
                term.click(note_col, note_row, button=MouseButton.LEFT, settle=True)
                term.wait_for_text('note.txt', row=22)

                _quit_cleanly(self, term)

    def test_tui_options_toggle_persists_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            home = root / 'home'
            cwd.mkdir()
            home.mkdir()
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')

            cfg_path = _write_config(
                home,
                'classic_colors = yes\n'
                'mouse_enabled = yes\n'
                'mouse_swap = no\n'
                'future_setting = keep_me\n',
            )

            # Session 1: toggle Classic colors and Swap mouse buttons from Options menu
            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                self.assertEqual(term.screen.style_at(1, 0).bg, 4)

                _open_options_menu(term)
                term.press('down', 'down', 'enter', delay=0.01)  # Classic colors
                term.wait_until(
                    lambda s: s.style_at(1, 0).bg is None,
                    description='Classic colors toggled to modern transparent theme',
                )

                # F2 re-opens the remembered Options menu directly
                term.press('f2')
                term.wait_for_text('Swap mouse buttons')
                term.press('down', 'down', 'down', 'down', 'enter', delay=0.01)  # Swap mouse buttons
                term.wait_stable()

                _quit_cleanly(self, term)

            saved_text = cfg_path.read_text(encoding='utf-8')
            self.assertIn('classic_colors = no', saved_text)
            self.assertIn('mouse_swap = yes', saved_text)
            self.assertIn('future_setting = keep_me', saved_text)

            # Session 2: restart in same HOME and verify persisted settings take effect
            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                self.assertIsNone(term.screen.style_at(1, 0).bg)
                term.click(60, 5, button=MouseButton.RIGHT, settle=True)
                term.wait_for_text('[Right]')
                _quit_cleanly(self, term)

    def test_malformed_and_corrupted_config_resilience(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            home = root / 'home'
            cwd.mkdir()
            home.mkdir()
            (cwd / 'doc.txt').write_text('doc', encoding='utf-8')
            pager = ExternalToolStub.create(root / 'tools', 'fallback_pg')

            # 1. Malformed lines + invalid bool + empty editor -> Config warnings modal + valid pager kept
            cfg_path = _write_config(
                home,
                'line_without_equals\n'
                'editor =\n'
                'mouse_enabled = maybe\n'
                f'pager = {pager.path}\n',
            )
            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=_ISOLATED_ENV) as term:
                term.wait_for_text('Config warnings')
                self.assertIn('Issues found in', term.screen.text())
                term.press('enter')
                term.wait_ready()

                term.press('down')
                term.wait_for_text('doc.txt')
                term.press('f3')
                term.wait_until(lambda _s: len(pager.calls()) == 1)
                term.wait_ready()
                _quit_cleanly(self, term)

            # 2. Invalid non-UTF-8 binary config -> graceful startup with defaults
            _write_config(home, b'\xff\xfe\x00\x00garbage\x80\x81')
            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                self.assertEqual(term.screen.style_at(1, 0).bg, 4)
                _quit_cleanly(self, term)

            # 3. Directory at config path -> graceful startup with defaults
            cfg_path.unlink()
            cfg_path.mkdir()
            with TerminalDriver(rows=24, cols=80, cwd=cwd, home=home, env=_ISOLATED_ENV) as term:
                term.wait_ready()
                _quit_cleanly(self, term)

    def test_hostile_host_env_isolation_and_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            home_cfg = root / 'home_cfg'
            home_empty = root / 'home_empty'
            cwd.mkdir()
            home_cfg.mkdir()
            home_empty.mkdir()
            (cwd / 'target.txt').write_text('body', encoding='utf-8')

            tools = root / 'tools'
            cfg_ed = ExternalToolStub.create(tools, 'cfg_ed')
            cfg_pg = ExternalToolStub.create(tools, 'cfg_pg')
            env_ed = ExternalToolStub.create(tools, 'env_ed')
            env_pg = ExternalToolStub.create(tools, 'env_pg')

            _write_config(home_cfg, f'editor = {cfg_ed.path}\npager = {cfg_pg.path}\n')

            # 1. Explicit EDITOR/PAGER env vars take precedence over ~/.config/tnc/config
            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home_cfg,
                env={'EDITOR': str(env_ed.path), 'PAGER': str(env_pg.path)},
            ) as term:
                term.wait_ready()
                term.press('down')
                term.wait_for_text('target.txt')
                term.press('f3')
                term.wait_until(lambda _s: len(env_pg.calls()) == 1)
                term.wait_ready()
                term.press('f4')
                term.wait_until(lambda _s: len(env_ed.calls()) == 1)
                term.wait_ready()
                _quit_cleanly(self, term)

            self.assertEqual(len(cfg_pg.calls()), 0)
            self.assertEqual(len(cfg_ed.calls()), 0)

            # 2. Isolated env (None) ignores outer shell EDITOR/PAGER and uses config
            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home_cfg,
                env=_ISOLATED_ENV,
            ) as term:
                term.wait_ready()
                term.press('down')
                term.wait_for_text('target.txt')
                term.press('f3')
                term.wait_until(lambda _s: len(cfg_pg.calls()) == 1)
                term.wait_ready()
                term.press('f4')
                term.wait_until(lambda _s: len(cfg_ed.calls()) == 1)
                term.wait_ready()
                _quit_cleanly(self, term)

            # 3. Isolated env with empty config prompts setup dialogs instead of outer EDITOR/PAGER
            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                home=home_empty,
                env=_ISOLATED_ENV,
            ) as term:
                term.wait_ready()
                term.press('down')
                term.wait_for_text('target.txt')

                term.press('f3')
                term.wait_for_text('Select Pager')
                term.press_esc_settled()
                term.wait_for_text('Pager setup cancelled')
                term.press('enter')
                term.wait_until(lambda s: not s.contains('Pager setup cancelled'))

                term.press('f4')
                term.wait_for_text('Select Editor')
                term.press_esc_settled()
                term.wait_for_text('Editor setup cancelled')
                term.press('enter')
                term.wait_until(lambda s: not s.contains('Editor setup cancelled'))

                _quit_cleanly(self, term)

    def test_clean_exit_restoration_and_signal_shutdown(self) -> None:
        # 1. Clean F10 exit
        with TerminalDriver(rows=24, cols=80, env=_ISOLATED_ENV) as term:
            term.wait_ready()
            self.assertTrue(term.screen.in_alt_screen)
            self.assertTrue(term.screen.mouse_tracking)
            _quit_cleanly(self, term)

        # 2. SIGINT and SIGTERM both exit promptly and restore terminal modes
        for sig in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=sig.name):
                with TerminalDriver(rows=24, cols=80, env=_ISOLATED_ENV) as term:
                    term.wait_ready()
                    term.send_signal(sig)
                    rc = term.wait_exit(timeout=2.0)
                    self.assertNotEqual(rc, 0)
                    _assert_terminal_restored(self, term)


if __name__ == '__main__':
    unittest.main()
