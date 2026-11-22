"""Comprehensive TDD tests for audited App and MenuBar fixes (#85, #90-#95, #103, #108, #110-#112)."""

import curses
import io
import os
import stat
import tempfile
import termios
import types
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr
from tnc.app import MENU_ACTION_MAP, Action, App
from tnc.config import Config
from tnc.file_ops import ChmodResult, ChownResult
from tnc.menu import Menu, MenuBar, MenuItem
from tnc.modal import Modal
from tnc.permissions import TriState


class _AppTestCase(unittest.TestCase):
    """Base test case isolating Config.default_path and curses setup."""

    def setUp(self) -> None:
        super().setUp()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmppath = Path(self.tmpdir.name).resolve()
        self.cfg_path = str(self.tmppath / '.tnc_test_config')
        self._patches = [
            mock.patch.dict(
                os.environ,
                {k: v for k, v in os.environ.items() if k not in ('EDITOR', 'PAGER')},
                clear=True,
            ),
            mock.patch.object(Config, 'default_path', return_value=self.cfg_path),
            mock.patch('curses.has_colors', return_value=False),
            mock.patch('curses.curs_set'),
            mock.patch('curses.doupdate'),
            mock.patch('curses.mousemask', return_value=(1, 0)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        Modal.button_translator = None
        for p in reversed(self._patches):
            p.stop()
        self.tmpdir.cleanup()
        super().tearDown()

    def make_app(self, rows: int = 24, cols: int = 80) -> App:
        stdscr = create_mock_stdscr(rows=rows, cols=cols)
        with mock.patch('os.getcwd', return_value=str(self.tmppath)):
            app = App(stdscr)
            app.setup()
        return app


class TestCtrlXStatusHint(_AppTestCase):
    """#85: draw() displays Ctrl+X chord status hint."""

    def test_draw_shows_ctrl_x_hint_when_pending(self) -> None:
        app = self.make_app()
        app.ctrl_x_pending = True
        with mock.patch.object(app.status_bar, 'render') as mock_render:
            app.draw()
        mock_render.assert_called_once()
        self.assertEqual(mock_render.call_args[0][5], '[Ctrl+X] c=chmod o=chown')

    def test_draw_prefers_escape_hint_if_both_pending(self) -> None:
        app = self.make_app()
        app.escape_pending = True
        app.ctrl_x_pending = True
        with mock.patch.object(app.status_bar, 'render') as mock_render:
            app.draw()
        self.assertEqual(mock_render.call_args[0][5], '[Esc] again to clear')


class TestMouseHooksAndButton5(_AppTestCase):
    """#90: Modal.button_translator lifecycle and BUTTON5_PRESSED fallback."""

    def test_setup_sets_and_cleanup_clears_modal_button_translator(self) -> None:
        app = self.make_app()
        self.assertEqual(Modal.button_translator, app._translate_button_state)
        app.cleanup()
        self.assertIsNone(Modal.button_translator)

    def test_enable_mouse_includes_button5_fallback_when_attr_missing(self) -> None:
        app = self.make_app()
        fake_curses = types.SimpleNamespace(
            BUTTON1_CLICKED=curses.BUTTON1_CLICKED,
            BUTTON1_DOUBLE_CLICKED=curses.BUTTON1_DOUBLE_CLICKED,
            BUTTON2_CLICKED=curses.BUTTON2_CLICKED,
            BUTTON3_CLICKED=curses.BUTTON3_CLICKED,
            BUTTON4_PRESSED=curses.BUTTON4_PRESSED,
            mousemask=mock.MagicMock(return_value=(1, 0)),
            error=curses.error,
        )
        with mock.patch('tnc.app.curses', fake_curses):
            result = app._enable_mouse()
        self.assertTrue(result)
        mask_arg = fake_curses.mousemask.call_args[0][0]
        self.assertTrue(mask_arg & 0x200000)


class TestOpenWithExternal(_AppTestCase):
    """#91: _open_with_external verb, shlex ValueError, whitespace tool, file_path."""

    def test_view_dotdot_uses_view_verb(self) -> None:
        app = self.make_app()
        app.config.pager = 'less'
        app.active_panel.cursor = 0  # '..'
        result = app.view_current_file()
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Cannot view parent directory')

    def test_view_directory_uses_view_verb(self) -> None:
        (self.tmppath / 'subdir').mkdir()
        app = self.make_app()
        app.config.pager = 'less'
        idx = next(i for i, e in enumerate(app.active_panel.entries) if e.name == 'subdir')
        app.active_panel.cursor = idx
        result = app.view_current_file()
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Cannot view directory')

    def test_invalid_shlex_returns_error_before_endwin(self) -> None:
        target = self.tmppath / 'a.txt'
        target.write_text('hi')
        app = self.make_app()
        with mock.patch('curses.endwin') as mock_endwin:
            result = app._open_with_external('vim "unterminated', 'editor', verb='edit', file_path=target)
        mock_endwin.assert_not_called()
        self.assertFalse(result.success)
        self.assertIn('Invalid editor command:', result.error)

    def test_whitespace_tool_returns_no_tool_configured_before_endwin(self) -> None:
        target = self.tmppath / 'a.txt'
        target.write_text('hi')
        app = self.make_app()
        with mock.patch('curses.endwin') as mock_endwin, \
             mock.patch('tnc.app.subprocess.run') as mock_run:
            result = app._open_with_external('   ', 'editor', verb='edit', file_path=target)
        mock_endwin.assert_not_called()
        mock_run.assert_not_called()
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'No editor configured')


class TestChmodChownErrorReporting(_AppTestCase):
    """#92: accurate recursive/non-recursive partial success and chown error precedence."""

    def test_chmod_recursive_partial_success_reports_item_counts(self) -> None:
        d = self.tmppath / 'dir1'
        d.mkdir()
        (d / 'ok.txt').write_text('ok')
        (d / 'fail.txt').write_text('fail')
        app = self.make_app()
        app.active_panel.selected = {'dir1'}

        from tnc.dialog import ChmodDialog
        fake_dialog = mock.MagicMock(spec=ChmodDialog)
        fake_dialog.show.return_value = 0o644
        fake_dialog.recursive = True
        fake_dialog.get_bit_state.return_value = TriState.CHECKED
        del fake_dialog.get_mode_masks

        fake_res = ChmodResult(
            success=False,
            error='fail.txt: Permission denied',
            changed_files=[str(d / 'ok.txt'), str(d)],
            errors=[f'{d / "fail.txt"}: Permission denied'],
        )
        with mock.patch('tnc.dialog.ChmodDialog', return_value=fake_dialog), \
             mock.patch('tnc.file_ops.chmod_recursive', return_value=fake_res), \
             mock.patch('tnc.app.show_error_dialog') as mock_err:
            app._prompt_chmod()

        mock_err.assert_called_once()
        msg = mock_err.call_args[0][2]
        self.assertIn('2 of 3', msg)
        details = mock_err.call_args[1].get('details') or []
        self.assertTrue(any('fail.txt' in item for item in details))

    def test_chown_uses_res_errors_even_when_res_error_is_empty(self) -> None:
        f = self.tmppath / 'a.txt'
        f.write_text('x')
        app = self.make_app()
        app.active_panel.selected = {'a.txt'}

        res = ChownResult(
            success=False,
            error='',
            changed_files=[],
            errors=['a.txt: Operation not permitted'],
        )
        with mock.patch('tnc.dialog.chown_dialog', return_value=(str(os.getuid()), '')), \
             mock.patch('tnc.file_ops.chown_files', return_value=res), \
             mock.patch('tnc.app.show_error_dialog') as mock_err:
            app._prompt_chown()

        mock_err.assert_called_once()
        details = mock_err.call_args[1].get('details') or []
        self.assertEqual(details, ['a.txt: Operation not permitted'])


class TestCreateFileAndRename(_AppTestCase):
    """#93: create hidden/padded file opens directly; rename adjusts scroll/selection/sibling."""

    def test_create_hidden_file_with_show_hidden_false_opens_created_file(self) -> None:
        (self.tmppath / 'other.txt').write_text('other')
        app = self.make_app()
        app.active_panel.show_hidden = False
        app.active_panel.refresh()
        app.config.editor = 'nano'

        with mock.patch('tnc.app.input_dialog', return_value=' .env '), \
             mock.patch('curses.endwin'), \
             mock.patch('tnc.app.subprocess.run') as mock_run:
            app._prompt_create_file()

        self.assertTrue((self.tmppath / '.env').exists())
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args, ['nano', str(self.tmppath / '.env')])
        # Sibling panel pointing at same directory was also refreshed (visible when show_hidden=True)
        right_names = [e.name for e in app.right_panel.entries]
        self.assertIn('.env', right_names)

    def test_rename_updates_selection_scroll_and_sibling_panel(self) -> None:
        for i in range(10):
            (self.tmppath / f'file{i:02d}.txt').write_text('x')
        app = self.make_app(rows=10, cols=80)  # visible_rows = 4
        app.active_panel.refresh()
        app.right_panel.refresh()
        idx = next(i for i, e in enumerate(app.active_panel.entries) if e.name == 'file00.txt')
        app.active_panel.cursor = idx
        app.active_panel.selected.add('file00.txt')

        with mock.patch('tnc.app.input_dialog', return_value='  zzz_renamed.txt  '):
            app._prompt_rename()

        self.assertNotIn('file00.txt', app.active_panel.selected)
        self.assertIn('zzz_renamed.txt', app.active_panel.selected)
        self.assertEqual(app.active_panel.entries[app.active_panel.cursor].name, 'zzz_renamed.txt')
        # Cursor must be visible within scroll window
        self.assertGreaterEqual(app.active_panel.cursor, app.active_panel.scroll_offset)
        self.assertLess(
            app.active_panel.cursor,
            app.active_panel.scroll_offset + app.active_panel.visible_rows,
        )
        # Sibling panel refreshed
        self.assertIn('zzz_renamed.txt', [e.name for e in app.right_panel.entries])


class TestToggleHiddenPerPanel(_AppTestCase):
    """#94: Left/Right Toggle hidden menu items toggle the respective panel."""

    def test_menu_action_map_has_panel_specific_toggle_hidden(self) -> None:
        self.assertEqual(MENU_ACTION_MAP['toggle_hidden_left'], Action.TOGGLE_HIDDEN_LEFT)
        self.assertEqual(MENU_ACTION_MAP['toggle_hidden_right'], Action.TOGGLE_HIDDEN_RIGHT)
        self.assertEqual(MENU_ACTION_MAP['toggle_hidden'], Action.TOGGLE_HIDDEN)

    def test_toggle_hidden_right_toggles_right_panel_when_left_is_active(self) -> None:
        (self.tmppath / '.dot').write_text('secret')
        app = self.make_app()
        self.assertIs(app.active_panel, app.left_panel)
        self.assertTrue(app.left_panel.show_hidden)
        self.assertTrue(app.right_panel.show_hidden)

        app._action_handlers[Action.TOGGLE_HIDDEN_RIGHT]()
        self.assertTrue(app.left_panel.show_hidden)
        self.assertFalse(app.right_panel.show_hidden)

        app._action_handlers[Action.TOGGLE_HIDDEN_LEFT]()
        self.assertFalse(app.left_panel.show_hidden)


class TestExecuteKeyboardInterruptAndNonTty(_AppTestCase):
    """#95: KeyboardInterrupt and tcgetattr errors in _execute_command / _execute_file."""

    def test_execute_command_handles_keyboard_interrupt_and_non_tty(self) -> None:
        app = self.make_app()
        app.command_line.input_text = 'sleep 10'
        with mock.patch('curses.endwin'), \
             mock.patch('tnc.app.subprocess.run', side_effect=KeyboardInterrupt), \
             mock.patch('termios.tcgetattr', side_effect=termios.error(25, 'Inappropriate ioctl')), \
             mock.patch('builtins.print') as mock_print:
            app._execute_command()

        printed = ' '.join(str(c) for c in mock_print.call_args_list)
        self.assertIn('[Interrupted]', printed)
        app.stdscr.refresh.assert_called()

    def test_execute_file_handles_stringio_stdin_unsupported_operation(self) -> None:
        script = self.tmppath / 'run.sh'
        script.write_text('#!/bin/sh\necho ok\n')
        script.chmod(0o755)
        app = self.make_app()
        fake_stdin = io.StringIO('x')
        with mock.patch('curses.endwin'), \
             mock.patch('tnc.app.subprocess.run', return_value=mock.MagicMock(returncode=0)), \
             mock.patch('sys.stdin', fake_stdin), \
             mock.patch('builtins.print'):
            app._execute_file(script)

        app.stdscr.refresh.assert_called()


class TestChmodMixedBitsPreservation(_AppTestCase):
    """#103: _prompt_chmod preserves untouched MIXED bits across multiple files."""

    def test_non_recursive_mixed_bits_preserved(self) -> None:
        f1 = self.tmppath / 'a.sh'
        f2 = self.tmppath / 'b.txt'
        f1.write_text('a')
        f2.write_text('b')
        os.chmod(f1, 0o755)  # rwxr-xr-x
        os.chmod(f2, 0o644)  # rw-r--r--

        app = self.make_app()
        app.active_panel.selected = {'a.sh', 'b.txt'}

        from tnc.dialog import ChmodDialog
        real_init = ChmodDialog.__init__
        created: list[ChmodDialog] = []

        def spy_init(self_dlg, *args, **kwargs):
            real_init(self_dlg, *args, **kwargs)
            created.append(self_dlg)

        def fake_show(self_dlg, _win):
            # Leave owner_exec, group_exec, other_exec MIXED; clear other_read
            self_dlg.set_bit_state('other_read', TriState.UNCHECKED)
            return self_dlg.get_result_mode()

        with mock.patch.object(ChmodDialog, '__init__', spy_init), \
             mock.patch.object(ChmodDialog, 'show', fake_show):
            app._prompt_chmod()

        self.assertEqual(len(created), 1)
        # a.sh kept its exec bits (0o751), b.txt stayed non-exec (0o640)
        self.assertEqual(stat.S_IMODE(f1.stat().st_mode), 0o751)
        self.assertEqual(stat.S_IMODE(f2.stat().st_mode), 0o640)

    def test_recursive_mixed_bits_preserved_and_skips_symlinks(self) -> None:
        d1 = self.tmppath / 'd1'
        f_top = self.tmppath / 'f_top.txt'
        d1.mkdir()
        f_top.write_text('top')
        os.chmod(d1, 0o755)
        os.chmod(f_top, 0o644)  # exec bits are MIXED between d1 and f_top
        sub_exec = d1 / 'run.sh'
        sub_doc = d1 / 'doc.txt'
        outside = self.tmppath / 'outside.txt'
        sub_exec.write_text('1')
        sub_doc.write_text('2')
        outside.write_text('3')
        os.chmod(sub_exec, 0o755)
        os.chmod(sub_doc, 0o640)
        os.chmod(outside, 0o600)
        (d1 / 'link.txt').symlink_to(outside)

        app = self.make_app()
        app.active_panel.selected = {'d1', 'f_top.txt'}

        from tnc.dialog import ChmodDialog

        def fake_show(self_dlg, _win):
            # Toggle group_write ON, keep MIXED exec bits untouched, enable recursive
            self_dlg.set_bit_state('group_write', TriState.CHECKED)
            self_dlg.recursive = True
            return self_dlg.get_result_mode()

        with mock.patch.object(ChmodDialog, 'show', fake_show):
            app._prompt_chmod()

        # group_write (+0o020) and common other_read (+0o004) applied; MIXED exec bits preserved!
        self.assertEqual(stat.S_IMODE(d1.stat().st_mode), 0o775)
        self.assertEqual(stat.S_IMODE(f_top.stat().st_mode), 0o664)
        self.assertEqual(stat.S_IMODE(sub_exec.stat().st_mode), 0o775)
        self.assertEqual(stat.S_IMODE(sub_doc.stat().st_mode), 0o664)
        # Symlink target must NOT be modified
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o600)

    def test_non_recursive_partial_failure_counts_correctly(self) -> None:
        (self.tmppath / 'a.txt').write_text('a')
        (self.tmppath / 'b.txt').write_text('b')
        app = self.make_app()
        app.active_panel.selected = {'a.txt', 'b.txt'}

        from tnc.dialog import ChmodDialog
        fake_res = ChmodResult(
            success=False,
            error='b.txt: Permission denied',
            changed_files=['a.txt'],
            errors=['b.txt: Permission denied'],
        )
        with mock.patch.object(ChmodDialog, 'show', return_value=0o644), \
             mock.patch('tnc.file_ops.chmod_files', return_value=fake_res), \
             mock.patch('tnc.app.show_error_dialog') as mock_err:
            app._prompt_chmod()

        mock_err.assert_called_once()
        self.assertIn('1 of 2', mock_err.call_args[0][2])
        self.assertEqual(mock_err.call_args[1]['details'], ['b.txt: Permission denied'])

    def test_uses_get_mode_masks_hook_when_present(self) -> None:
        f1 = self.tmppath / 'a.txt'
        f2 = self.tmppath / 'b.txt'
        f1.write_text('a')
        f2.write_text('b')
        os.chmod(f1, 0o755)
        os.chmod(f2, 0o644)

        app = self.make_app()
        app.active_panel.selected = {'a.txt', 'b.txt'}

        fake_dialog = mock.MagicMock()
        fake_dialog.show.return_value = 0o640
        fake_dialog.recursive = False
        fake_dialog.get_bit_state.side_effect = (
            lambda b: TriState.MIXED if b == 'owner_exec' else TriState.CHECKED
        )
        fake_dialog.get_mode_masks.return_value = (0o640, 0o005)

        with mock.patch('tnc.dialog.ChmodDialog', return_value=fake_dialog):
            app._prompt_chmod()

        fake_dialog.get_mode_masks.assert_called_once()
        # owner_exec preserved per file, other_read+other_exec cleared
        self.assertEqual(stat.S_IMODE(f1.stat().st_mode), 0o750)
        self.assertEqual(stat.S_IMODE(f2.stat().st_mode), 0o640)


class TestMenuBarFixes(_AppTestCase):
    """#108: disabled item handling, width clamping, unhandled key consumption."""

    def test_switching_menus_skips_leading_disabled_item(self) -> None:
        bar = MenuBar()
        bar.menus[1] = Menu('File', [
            MenuItem('Disabled', 'disabled_act', enabled=False),
            MenuItem('Enabled', 'enabled_act', enabled=True),
        ])
        bar.dropdown_open = True
        bar.selected_menu = 0
        bar.handle_key(curses.KEY_RIGHT)
        self.assertEqual(bar.selected_menu, 1)
        self.assertEqual(bar.selected_item, 1)

    def test_get_selected_action_returns_empty_for_disabled_item(self) -> None:
        bar = MenuBar()
        bar.menus[0] = Menu('Test', [MenuItem('Disabled', 'some_action', enabled=False)])
        bar.selected_menu = 0
        bar.selected_item = 0
        self.assertEqual(bar.get_selected_action(), '')

    def test_render_dropdown_clamps_x_and_truncates_on_narrow_terminal(self) -> None:
        bar = MenuBar()
        bar.dropdown_open = True
        bar.selected_menu = 4  # 'Right' menu normally starts around x=30
        win = mock.MagicMock()
        bar.render(win, y=0, width=40)
        win.reset_mock()

        bar.render_dropdown(win, y=1, width=40)
        for _y, start_x, end_x, _idx in bar.dropdown_positions:
            self.assertGreaterEqual(start_x, 0)
            self.assertLessEqual(end_x, 40)

        # Ultra-narrow terminal (width < item_width) truncates item_text
        win.reset_mock()
        bar.render_dropdown(win, y=1, width=10)
        for call in win.addstr.call_args_list:
            text = call[0][2]
            self.assertLessEqual(len(text), 10)
        for _y, start_x, end_x, _idx in bar.dropdown_positions:
            self.assertEqual(start_x, 0)
            self.assertLessEqual(end_x, 10)

    def test_dropdown_open_consumes_letters_tab_f3_but_allows_f9_f2_f10(self) -> None:
        app = self.make_app()
        app.menu.open_dropdown(0)

        # Letter should NOT leak into command_line
        self.assertEqual(app.handle_key(ord('a')), Action.NONE)
        self.assertEqual(app.command_line.input_text, '')

        # Tab should NOT switch panels while dropdown open
        self.assertEqual(app.handle_key(ord('\t')), Action.NONE)
        self.assertIs(app.active_panel, app.left_panel)

        # F3 should NOT trigger VIEW while dropdown open
        self.assertEqual(app.handle_key(curses.KEY_F3), Action.NONE)

        # F10 still quits, and MenuBar directly returns False for F9/F2/F10
        self.assertIs(app.menu.handle_key(curses.KEY_F10), False)
        self.assertIs(app.menu.handle_key(curses.KEY_F2), False)
        self.assertIs(app.menu.handle_key(curses.KEY_F9), False)
        self.assertEqual(app.handle_key(curses.KEY_F10), Action.QUIT)

        # F2 returns Action.MENU so run loop can toggle closed
        self.assertEqual(app.handle_key(curses.KEY_F2), Action.MENU)

        # F9 toggles dropdown closed
        app.handle_key(curses.KEY_F9)
        self.assertFalse(app.menu.dropdown_open)


class TestQuickSearchExitOnPanelSwitch(_AppTestCase):
    """#110: Switching panels via Tab or mouse click exits active quick search."""

    def test_tab_switch_exits_quick_search(self) -> None:
        (self.tmppath / 'alpha.txt').write_text('a')
        (self.tmppath / 'beta.txt').write_text('b')
        app = self.make_app()
        app.left_panel.start_search()
        app.left_panel.handle_search_char('a')
        self.assertTrue(app.left_panel.search_mode)

        app.handle_key(ord('\t'))

        self.assertIs(app.active_panel, app.right_panel)
        self.assertFalse(app.left_panel.search_mode)
        self.assertIn('beta.txt', [e.name for e in app.left_panel.entries])

    def test_mouse_click_other_panel_exits_quick_search(self) -> None:
        (self.tmppath / 'alpha.txt').write_text('a')
        (self.tmppath / 'beta.txt').write_text('b')
        app = self.make_app()
        app.draw()
        app.left_panel.start_search()
        app.left_panel.handle_search_char('a')
        self.assertTrue(app.left_panel.search_mode)

        app.handle_mouse(50, 5, curses.BUTTON1_CLICKED)

        self.assertIs(app.active_panel, app.right_panel)
        self.assertFalse(app.left_panel.search_mode)
        self.assertIn('beta.txt', [e.name for e in app.left_panel.entries])


class TestLayoutResizeAndCursesGuards(_AppTestCase):
    """#111: Width resize detection, odd-width gap fix, curs_set/move guards."""

    def test_odd_terminal_width_has_no_gap(self) -> None:
        app = self.make_app(rows=24, cols=81)
        self.assertEqual(app.left_panel.width, 40)
        self.assertEqual(app.right_panel.width, 41)
        self.assertEqual(app.left_panel.width + app.right_panel.width, 81)

        app.stdscr.getmaxyx.return_value = (24, 101)
        app.draw()
        self.assertEqual(app.left_panel.width, 50)
        self.assertEqual(app.right_panel.width, 51)

    def test_draw_resizes_when_only_width_changes(self) -> None:
        app = self.make_app(rows=24, cols=80)
        app.stdscr.getmaxyx.return_value = (24, 120)
        app.draw()
        self.assertEqual(app.left_panel.width, 60)
        self.assertEqual(app.right_panel.width, 60)

    def test_setup_and_draw_survive_curs_set_and_move_errors(self) -> None:
        stdscr = create_mock_stdscr(rows=24, cols=80)
        stdscr.move.side_effect = curses.error('move failed')
        with mock.patch('curses.curs_set', side_effect=curses.error('no curs_set')):
            app = App(stdscr)
            app.setup()
            app.draw()  # Should not raise


class TestClickFeedbackTiming(_AppTestCase):
    """#112: function bar click feedback is rendered before being cleared."""

    def test_draw_renders_click_feedback_then_clears(self) -> None:
        app = self.make_app()
        app.function_bar.show_click_feedback('F5')
        seen_during_render: list[str | None] = []

        orig_render = app.function_bar.render

        def spy_render(*args, **kwargs):
            seen_during_render.append(app.function_bar.highlight_button)
            return orig_render(*args, **kwargs)

        with mock.patch.object(app.function_bar, 'render', side_effect=spy_render):
            app.draw()

        self.assertEqual(seen_during_render, ['F5'])
        self.assertIsNone(app.function_bar.highlight_button)


if __name__ == '__main__':
    unittest.main()
