"""Live-PTY E2E tests for external tools, executables, dir size, and chmod/chown."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

from tests.terminal import ExternalToolStub, TerminalDriver
from tnc.utils import format_size


def _isolated_env(home_dir: Path, **overrides: str | None) -> dict[str, str | None]:
    """Return a clean environment dict isolating config and tool variables."""
    env: dict[str, str | None] = {
        'HOME': str(home_dir),
        'XDG_CONFIG_HOME': str(home_dir / '.config'),
        'EDITOR': None,
        'VISUAL': None,
        'PAGER': None,
    }
    env.update(overrides)
    return env


def _make_workspace(
    test_case: unittest.TestCase,
) -> tuple[Path, Path, Path, Path]:
    """Create isolated temp root with ``work``, ``home``, and ``tools`` subdirs."""
    tmp = tempfile.TemporaryDirectory(prefix='tnc_e2e_perms_')
    test_case.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    work = root / 'work'
    home = root / 'home'
    tools = root / 'tools'
    work.mkdir()
    home.mkdir()
    tools.mkdir()
    return root, work, home, tools


def _register_mode_restore(
    test_case: unittest.TestCase,
    targets: list[tuple[Path, int]],
) -> None:
    """Schedule mode restoration in LIFO cleanup before temp dir deletion."""
    def _restore() -> None:
        for path, mode in targets:
            try:
                if path.exists() and not path.is_symlink():
                    os.chmod(path, mode)
            except OSError:
                pass

    test_case.addCleanup(_restore)


def _navigate_to_entry(
    term: TerminalDriver,
    name: str,
    *,
    max_steps: int = 30,
) -> None:
    """Move cursor in active panel onto ``name`` using status bar feedback."""
    status_row = term.screen.rows - 3
    target_marker = f'  {name}  '
    if target_marker in term.screen.row_text(status_row):
        return

    if '  ..  ' not in term.screen.row_text(status_row):
        term.press('home')
        term.wait_until(
            lambda s: '  ..  ' in s.row_text(status_row),
            description='cursor reset to ..',
        )

    for _ in range(max_steps):
        current = term.screen.row_text(status_row)
        if target_marker in current:
            return
        term.press('down')
        term.wait_until(
            lambda s, prev=current: s.row_text(status_row) != prev,
            description=f'cursor advance toward {name!r}',
        )

    term.wait_until(
        lambda s: target_marker in s.row_text(status_row),
        description=f'cursor on {name!r}',
    )


def _find_panel_row_containing(
    term: TerminalDriver,
    needle: str,
    *,
    start_row: int = 2,
) -> str:
    """Return the first panel row text containing ``needle``."""
    end_row = term.screen.rows - 4
    for r in range(start_row, end_row):
        line = term.screen.row_text(r)
        if needle in line:
            return line
    raise AssertionError(f'{needle!r} not found in panel rows:\n{term.screen.screenshot()}')


def _finish_terminal_pause(term: TerminalDriver, *expected_texts: str) -> None:
    """Wait for main-screen output and press Space after tty.setraw settles."""
    term.wait_until(
        lambda s: not s.in_alt_screen
        and all(txt in s.text() for txt in expected_texts)
        and s.contains('[Press any key to continue]'),
        description=f'terminal pause with {expected_texts!r}',
    )
    # _run_in_terminal calls tty.setraw() (TCSAFLUSH); wait until output settles
    # so raw read(1) is blocked before sending Space.
    term.wait_stable()
    term.press('space')
    term.wait_ready(require_alt_screen=True)


def _quit_cleanly(test_case: unittest.TestCase, term: TerminalDriver) -> None:
    """Press F10 and assert Tiny Commander exits with status 0."""
    term.press('f10')
    test_case.assertEqual(term.wait_exit(), 0)


class TestExternalEditorAndPagerE2E(unittest.TestCase):
    """E2E tests for F4 editor, F3 pager, setup dialogs, and Shift+F4 create."""

    def test_f4_opens_editor_modifies_file_and_refreshes_size(self) -> None:
        _, work, home, tools = _make_workspace(self)
        target = work / 'notes.txt'
        target.write_text('hello', encoding='utf-8')  # 5 bytes

        append_payload = '\n' + ('x' * 2048)
        editor = ExternalToolStub.create(
            tools, 'stub_editor', append_text=append_payload
        )
        env = _isolated_env(home, EDITOR=str(editor.path))

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'notes.txt')
            before_row = _find_panel_row_containing(term, 'notes.txt')
            self.assertIn(' 5 ', before_row)

            raw_mark = len(term.raw_output)
            term.press('f4')
            term.wait_until(
                lambda _s: len(editor.calls()) == 1,
                description='editor invocation',
            )
            term.wait_ready(require_alt_screen=True)

            # Verify curses suspended alt-screen (rmcup) and re-entered it (smcup).
            delta = bytes(term.raw_output[raw_mark:])
            self.assertIn(b'\x1b[?1049l', delta)
            self.assertIn(b'\x1b[?1049h', delta)

            expected_size = format_size(len('hello') + len(append_payload))
            term.wait_until(
                lambda s: expected_size in s.row_text(s.rows - 3),
                description='refreshed size in status bar',
            )
            after_row = _find_panel_row_containing(term, 'notes.txt')
            self.assertIn(expected_size, after_row)

            _quit_cleanly(self, term)

        calls = editor.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(Path(calls[0]['argv'][-1]).resolve(), target.resolve())
        self.assertEqual(target.read_text(encoding='utf-8'), 'hello' + append_payload)

    def test_f4_unconfigured_editor_setup_cancel_and_custom_select(self) -> None:
        _, work, home, tools = _make_workspace(self)
        target = work / 'draft.txt'
        target.write_text('draft', encoding='utf-8')

        custom_editor = ExternalToolStub.create(
            tools, 'custom_editor', append_text='_edited'
        )
        env = _isolated_env(home)  # EDITOR, VISUAL, PAGER explicitly unset
        config_file = home / '.config' / 'tnc' / 'config'

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'draft.txt')

            # Cancel setup prompt with Esc -> surfaces cancellation error cleanly.
            term.press('f4')
            term.wait_for_text('Select Editor')
            term.wait_for_text('Custom...')
            term.press_esc_settled()

            term.wait_for_text('Editor setup cancelled')
            term.press_esc_settled()
            term.wait_until(
                lambda s: not s.contains('Editor setup cancelled'),
                description='error modal dismissed',
            )
            self.assertFalse(config_file.exists())
            self.assertEqual(target.read_text(encoding='utf-8'), 'draft')

            # Re-open setup prompt, choose Custom..., enter stub path, and verify edit runs.
            term.press('f4')
            term.wait_for_text('Select Editor')
            term.click_text('Custom...')
            term.wait_for_text('Enter custom command:')
            term.type_text(str(custom_editor.path))
            term.press('enter')

            term.wait_until(
                lambda _s: len(custom_editor.calls()) == 1,
                description='custom editor invocation',
            )
            term.wait_ready(require_alt_screen=True)

            _quit_cleanly(self, term)

        self.assertEqual(target.read_text(encoding='utf-8'), 'draft_edited')
        self.assertTrue(config_file.exists())
        self.assertIn(f'editor = {custom_editor.path}', config_file.read_text(encoding='utf-8'))

    def test_f4_visual_precedence_over_editor_and_config(self) -> None:
        _, work, home, tools = _make_workspace(self)
        target = work / 'visual_note.txt'
        target.write_text('start', encoding='utf-8')

        visual_ed = ExternalToolStub.create(tools, 'visual_ed', append_text='_via_visual')
        env_ed = ExternalToolStub.create(tools, 'env_ed', append_text='_via_editor')
        cfg_ed = ExternalToolStub.create(tools, 'cfg_ed', append_text='_via_cfg')

        cfg_path = home / '.config' / 'tnc' / 'config'
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(f'editor = {cfg_ed.path}\n', encoding='utf-8')

        env = _isolated_env(home, VISUAL=str(visual_ed.path), EDITOR=str(env_ed.path))
        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'visual_note.txt')
            term.press('f4')
            term.wait_until(
                lambda _s: len(visual_ed.calls()) == 1,
                description='$VISUAL editor invocation',
            )
            term.wait_ready(require_alt_screen=True)
            _quit_cleanly(self, term)

        self.assertEqual(len(visual_ed.calls()), 1)
        self.assertEqual(len(env_ed.calls()), 0)
        self.assertEqual(len(cfg_ed.calls()), 0)
        self.assertEqual(target.read_text(encoding='utf-8'), 'start_via_visual')

    def test_f4_auto_detects_new_editors_in_priority_and_runs_emacs_nw(self) -> None:
        _, work, home, tools = _make_workspace(self)
        target = work / 'edit_me.txt'
        target.write_text('init', encoding='utf-8')

        bin_dir = tools / 'path_bin'
        micro_stub = ExternalToolStub.create(bin_dir, 'micro', append_text='_micro')
        ExternalToolStub.create(bin_dir, 'hx', append_text='_hx')
        emacs_stub = ExternalToolStub.create(bin_dir, 'emacs', append_text='_emacs')
        ExternalToolStub.create(bin_dir, 'vi', append_text='_vi')

        config_file = home / '.config' / 'tnc' / 'config'
        env = _isolated_env(home, PATH=str(bin_dir))

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'edit_me.txt')

            # First-run F4 opens Select Editor with detected editors in priority order
            term.press('f4')
            term.wait_for_text('Select Editor')
            term.wait_for_text('1. micro')
            term.wait_for_text('2. hx')
            term.wait_for_text('3. emacs -nw')
            term.wait_for_text('4. vi')
            self.assertIsNotNone(term.screen.find_styled_text('1. micro', reverse=True))

            # Confirm pre-focused highest-priority detected editor ('micro')
            term.press('enter')
            term.wait_until(
                lambda _s: len(micro_stub.calls()) == 1,
                description='auto-detected micro invocation',
            )
            term.wait_ready(require_alt_screen=True)
            self.assertIn('editor = micro', config_file.read_text(encoding='utf-8'))

            # Switch configured editor to 'emacs -nw' via Options -> Editor settings
            term.press('f2')
            term.wait_for_text('Sort by name')
            term.press('right', 'right', 'right')
            term.wait_for_text('Editor settings')
            term.press('enter')
            term.wait_for_text('Select Editor')
            self.assertIsNotNone(term.screen.find_styled_text('1. micro', reverse=True))

            term.press('down', 'down')
            term.wait_until(
                lambda s: s.find_styled_text('3. emacs -nw', reverse=True) is not None,
                description='emacs -nw focused in Select Editor',
            )
            term.press('enter')
            term.wait_until(
                lambda s: not s.contains('Select Editor'),
                description='Select Editor closed after selecting emacs -nw',
            )
            self.assertIn('editor = emacs -nw', config_file.read_text(encoding='utf-8'))

            # Press F4 again and verify emacs is invoked with -nw and file path
            term.press('f4')
            term.wait_until(
                lambda _s: len(emacs_stub.calls()) == 1,
                description='emacs -nw invocation',
            )
            term.wait_ready(require_alt_screen=True)

            _quit_cleanly(self, term)

        emacs_calls = emacs_stub.calls()
        self.assertEqual(len(emacs_calls), 1)
        self.assertEqual(emacs_calls[0]['argv'][0], '-nw')
        self.assertEqual(Path(emacs_calls[0]['argv'][-1]).resolve(), target.resolve())
        self.assertEqual(target.read_text(encoding='utf-8'), 'init_micro_emacs')

    def test_f3_opens_pager_with_flag_and_surfaces_nonzero_exit(self) -> None:
        _, work, home, tools = _make_workspace(self)
        target = work / 'readme.txt'
        target.write_text('line1\nline2\n', encoding='utf-8')

        ok_pager = ExternalToolStub.create(tools, 'ok_pager', exit_code=0)
        env_ok = _isolated_env(home, PAGER=f'{ok_pager.path} --raw-flag')

        with TerminalDriver(rows=24, cols=80, cwd=work, home=home, env=env_ok) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'readme.txt')
            term.press('f3')
            term.wait_until(
                lambda _s: len(ok_pager.calls()) == 1,
                description='pager with flag invocation',
            )
            term.wait_ready(require_alt_screen=True)
            _quit_cleanly(self, term)

        calls = ok_pager.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['argv'][0], '--raw-flag')
        self.assertEqual(Path(calls[0]['argv'][-1]).resolve(), target.resolve())

        bad_pager = ExternalToolStub.create(tools, 'bad_pager', exit_code=2)
        env_bad = _isolated_env(home, PAGER=str(bad_pager.path))

        with TerminalDriver(rows=24, cols=80, cwd=work, home=home, env=env_bad) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'readme.txt')
            term.press('f3')
            term.wait_for_text('Pager exited with code 2')
            term.press('enter')
            term.wait_until(
                lambda s: not s.contains('Pager exited with code 2'),
                description='pager error modal dismissed',
            )
            _quit_cleanly(self, term)

        self.assertEqual(len(bad_pager.calls()), 1)

    def test_interactive_pager_scroll_and_shift_f4_create_file(self) -> None:
        # Note: tnc has no internal file viewer; F3 invokes external $PAGER,
        # Shift+F3 cycles sort order, and Shift+F4 creates a file + opens $EDITOR.
        _, work, home, tools = _make_workspace(self)
        (work / 'adir').mkdir()
        multi = work / 'multi.txt'
        multi.write_text(
            '\n'.join(f'PAGE_LINE_{i:02d}' for i in range(20)) + '\n',
            encoding='utf-8',
        )

        pager_script = tools / 'interactive_pager'
        pager_script.write_text(
            f'#!{sys.executable}\n'
            'import sys\n'
            'lines = open(sys.argv[-1], encoding="utf-8").read().splitlines()\n'
            'print("\\n".join(lines[:10]))\n'
            'print("[PAGER_PAGE_1]", flush=True)\n'
            'sys.stdin.readline()\n'
            'print("\\n".join(lines[10:20]))\n'
            'print("[PAGER_PAGE_2]", flush=True)\n'
            'sys.stdin.readline()\n',
            encoding='utf-8',
        )
        pager_script.chmod(0o755)
        editor = ExternalToolStub.create(tools, 'create_editor', append_text='created\n')
        env = _isolated_env(home, PAGER=str(pager_script), EDITOR=str(editor.path))

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()

            # F3 on directory shows error dialog cleanly.
            _navigate_to_entry(term, 'adir')
            term.press('f3')
            term.wait_for_text('Cannot view directory')
            term.press_esc_settled()
            term.wait_until(lambda s: not s.contains('Cannot view directory'))

            # F3 on multi-line file suspends alt-screen for interactive pager paging.
            _navigate_to_entry(term, 'multi.txt')
            term.press('f3')
            term.wait_until(
                lambda s: not s.in_alt_screen
                and s.contains('PAGE_LINE_00')
                and s.contains('[PAGER_PAGE_1]'),
                description='interactive pager page 1',
            )
            term.type_text('n\n')
            term.wait_until(
                lambda s: not s.in_alt_screen
                and s.contains('PAGE_LINE_19')
                and s.contains('[PAGER_PAGE_2]'),
                description='interactive pager page 2',
            )
            term.type_text('q\n')
            term.wait_ready(require_alt_screen=True)

            # Shift+F3 cycles sort order (vn -> vs) without leaving alt-screen.
            self.assertIn('vn ', term.screen.row_text(1))
            term.press('shift+f3')
            term.wait_until(
                lambda s: s.in_alt_screen and 'vs ' in s.row_text(1),
                description='Shift+F3 cycles sort order',
            )

            # Shift+F4 creates a new file and opens $EDITOR on it.
            term.press('shift+f4')
            term.wait_for_text('Create file')
            term.type_text('created.txt')
            term.press('enter')
            term.wait_until(
                lambda _s: len(editor.calls()) == 1,
                description='Shift+F4 editor invocation',
            )
            term.wait_ready(require_alt_screen=True)
            term.wait_for_text('created.txt')

            _quit_cleanly(self, term)

        self.assertEqual((work / 'created.txt').read_text(encoding='utf-8'), 'created\n')


class TestExecutablesAndCommandLineE2E(unittest.TestCase):
    """E2E tests for executing scripts with Enter and running shell commands."""

    def test_enter_on_executable_script_runs_and_returns(self) -> None:
        _, work, home, _ = _make_workspace(self)
        plain = work / 'plain.txt'
        plain.write_text('not executable', encoding='utf-8')

        script = work / 'run_marker.py'
        script.write_text(
            f'#!{sys.executable}\n'
            'print("EXEC_MARKER_ALPHA", flush=True)\n',
            encoding='utf-8',
        )
        script.chmod(0o755)
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=80, cwd=work, home=home, env=env) as term:
            term.wait_ready()

            # Non-executable file does not trigger terminal execution on Enter.
            _navigate_to_entry(term, 'plain.txt')
            term.press('enter')
            term.wait_stable(quiet_period=0.04, timeout=0.4)
            self.assertTrue(term.screen.in_alt_screen)
            self.assertFalse(term.screen.contains('[Press any key to continue]'))

            # Executable script shows '*' prefix, runs on main screen, and returns cleanly.
            _navigate_to_entry(term, 'run_marker.py')
            self.assertTrue(term.screen.contains('*run_marker.py'))
            term.press('enter')
            _finish_terminal_pause(term, 'EXEC_MARKER_ALPHA')

            self.assertTrue(term.screen.contains('*run_marker.py'))
            _quit_cleanly(self, term)

    def test_command_line_valid_and_failing_commands(self) -> None:
        _, work, home, _ = _make_workspace(self)
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=80, cwd=work, home=home, env=env) as term:
            term.wait_ready()

            # Valid shell command runs in panel cwd, prints output, and refreshes panels.
            term.type_text('echo CMD_MARKER_OK && touch cmd_created.txt')
            term.wait_for_text('CMD_MARKER_OK')
            term.press('enter')
            _finish_terminal_pause(term, 'CMD_MARKER_OK')

            self.assertTrue((work / 'cmd_created.txt').exists())
            term.wait_for_text('cmd_created.txt')

            # Failing command prints non-zero [Exit N] marker and returns cleanly.
            term.type_text('sh -c "echo CMD_FAIL_BODY; exit 7"')
            term.wait_for_text('CMD_FAIL_BODY')
            term.press('enter')
            _finish_terminal_pause(term, 'CMD_FAIL_BODY', '[Exit 7]')

            self.assertTrue(term.screen.contains('[Left]'))
            self.assertEqual(term.screen.row_text(1).count('┌─'), 2)
            _quit_cleanly(self, term)

    def test_sequential_commands_preserve_main_screen(self) -> None:
        _, work, home, _ = _make_workspace(self)
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=80, cwd=work, home=home, env=env) as term:
            term.wait_ready()

            term.type_text('echo SEQ_MARKER_ONE')
            term.wait_for_text('SEQ_MARKER_ONE')
            term.press('enter')
            _finish_terminal_pause(term, 'SEQ_MARKER_ONE')

            term.type_text('echo SEQ_MARKER_TWO')
            term.wait_for_text('SEQ_MARKER_TWO')
            term.press('enter')
            _finish_terminal_pause(term, 'SEQ_MARKER_ONE', 'SEQ_MARKER_TWO')

            _quit_cleanly(self, term)


class TestDirSizeE2E(unittest.TestCase):
    """E2E tests for Alt+F3 directory size calculation and symlink safety."""

    def test_alt_f3_calculates_bytes_k_m_and_persists_cache(self) -> None:
        _, work, home, _ = _make_workspace(self)
        d_bytes = work / 'd_bytes'
        d_kilo = work / 'd_kilo'
        d_mega = work / 'd_mega'
        d_bytes.mkdir()
        d_kilo.mkdir()
        d_mega.mkdir()

        (d_bytes / 'small.bin').write_bytes(b'a' * 345)
        (d_kilo / 'kilo.bin').write_bytes(b'b' * 2048)
        (d_mega / 'mega.bin').write_bytes(b'c' * (1024 * 1024))
        (work / 'plain.txt').write_bytes(b'd' * 12)
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            status_row = term.screen.rows - 3

            for dirname, expected in (
                ('d_bytes', '345'),
                ('d_kilo', '2.0K'),
                ('d_mega', '1.0M'),
            ):
                _navigate_to_entry(term, dirname)
                term.press('alt+f3')
                term.wait_until(
                    lambda s, exp=expected: f'Dir: {exp}' in s.row_text(status_row),
                    description=f'status bar Dir: {expected}',
                )
                row = _find_panel_row_containing(term, f'{dirname}/')
                self.assertIn(expected, row)

            # Alt+F3 on a regular file is a silent no-op.
            _navigate_to_entry(term, 'plain.txt')
            term.press('alt+f3')
            term.wait_stable(quiet_period=0.04, timeout=0.4)
            self.assertNotIn('Dir:', term.screen.row_text(status_row))
            self.assertFalse(term.screen.contains('Error'))

            # Entering a measured directory and returning preserves cached size.
            _navigate_to_entry(term, 'd_bytes')
            term.press('enter')
            term.wait_for_text('small.bin')
            term.press('home')
            term.wait_until(lambda s: '  ..  ' in s.row_text(status_row))
            term.press('enter')
            term.wait_until(
                lambda s: not s.contains('small.bin')
                and '  d_bytes  ' in s.row_text(status_row),
                description='returned from d_bytes to parent with cursor on d_bytes',
            )
            self.assertIn('Dir: 345', term.screen.row_text(status_row))
            self.assertIn('345', _find_panel_row_containing(term, 'd_bytes/'))

            _quit_cleanly(self, term)

    def test_alt_f3_recursive_dir_with_symlinks_avoids_loops(self) -> None:
        _, work, home, _ = _make_workspace(self)
        outside = work / 'outside_huge.bin'
        outside.write_bytes(b'z' * (2 * 1024 * 1024))

        tree = work / 'tree_dir'
        sub = tree / 'sub'
        sub.mkdir(parents=True)
        (sub / 'payload.bin').write_bytes(b'p' * 2048)
        loop_link = sub / 'loop'
        loop_link.symlink_to('..')
        ext_link = sub / 'ext_link'
        ext_link.symlink_to(outside)
        broken_link = sub / 'broken'
        broken_link.symlink_to('/nonexistent/target_path')

        expected_bytes = (
            2048
            + loop_link.lstat().st_size
            + ext_link.lstat().st_size
            + broken_link.lstat().st_size
        )
        expected_str = format_size(expected_bytes)
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            status_row = term.screen.rows - 3

            _navigate_to_entry(term, 'tree_dir')
            term.press('alt+f3')
            term.wait_until(
                lambda s: f'Dir: {expected_str}' in s.row_text(status_row),
                description=f'symlink-safe dir size {expected_str}',
            )
            row = _find_panel_row_containing(term, 'tree_dir/')
            self.assertIn(expected_str, row)
            self.assertNotIn('2.0M', row)

            _quit_cleanly(self, term)


class TestPermissionsChmodChownE2E(unittest.TestCase):
    """E2E tests for Ctrl+X chord, ChmodDialog, and ChownDialog."""

    def test_ctrl_x_chord_hint_escape_and_invalid_key(self) -> None:
        _, work, home, _ = _make_workspace(self)
        (work / 'sample.txt').write_text('x', encoding='utf-8')
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=110, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            cmdline_row = term.screen.rows - 2

            # Ctrl+X followed by Esc cancels chord cleanly without setting Esc hint.
            term.press('ctrl+x')
            term.wait_for_text('[Ctrl+X] c=chmod o=chown')
            term.press_esc_settled()
            term.wait_until(
                lambda s: not s.contains('[Ctrl+X] c=chmod o=chown'),
                description='Ctrl+X hint cleared by Esc',
            )
            self.assertFalse(term.screen.contains('Change Permissions'))
            self.assertFalse(term.screen.contains('Change Ownership'))
            self.assertFalse(term.screen.contains('[Esc] again to clear'))

            # Ctrl+X followed by invalid key dismisses chord without typing to command line.
            term.press('ctrl+x')
            term.wait_for_text('[Ctrl+X] c=chmod o=chown')
            term.press('z')
            term.wait_until(
                lambda s: not s.contains('[Ctrl+X] c=chmod o=chown'),
                description='Ctrl+X hint cleared by invalid key',
            )
            self.assertFalse(term.screen.row_text(cmdline_row).rstrip().endswith('z'))

            _quit_cleanly(self, term)

    def test_ctrl_x_c_chmod_single_file_toggles_bits_and_updates_mode(self) -> None:
        _, work, home, _ = _make_workspace(self)
        target = work / 'script.sh'
        target.write_text('#!/bin/sh\n', encoding='utf-8')
        os.chmod(target, 0o644)
        _register_mode_restore(self, [(target, 0o644)])
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'script.sh')

            term.press('ctrl+x')
            term.wait_for_text('[Ctrl+X] c=chmod o=chown')
            term.press('c')
            term.wait_for_text('Change Permissions')
            term.wait_for_text('Mode: 0644')

            # Move right twice to owner_exec; Enter toggles the focused checkbox.
            term.press('right', 'right', 'enter')
            term.wait_for_text('Mode: 0744')

            # Move down to group_exec; Space toggles it on.
            term.press('down', 'space')
            term.wait_for_text('Mode: 0754')

            # Tab twice (grid -> special -> buttons) to [ >OK< ], then Enter to apply.
            term.press('tab', 'tab')
            term.wait_for_text('[ >OK< ]')
            term.press('enter')
            term.wait_until(
                lambda s: not s.contains('Change Permissions'),
                description='ChmodDialog closed after apply',
            )
            term.wait_for_text('*script.sh')

            _quit_cleanly(self, term)

        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o754)

    def test_ctrl_x_c_chmod_recursive_click_mixed_symlinks_and_partial_errors(self) -> None:
        _, work, home, _ = _make_workspace(self)
        bundle = work / 'bundle'
        bundle.mkdir()
        run_sh = bundle / 'run.sh'
        note_txt = bundle / 'note.txt'
        run_sh.write_text('echo ok\n', encoding='utf-8')
        note_txt.write_text('note\n', encoding='utf-8')

        top_file = work / 'top.txt'
        outside = work / 'outside.txt'
        top_file.write_text('top\n', encoding='utf-8')
        outside.write_text('keep\n', encoding='utf-8')

        (bundle / 'link_ext').symlink_to(outside)

        non_root = os.geteuid() != 0
        locked = bundle / 'locked'
        restore_list: list[tuple[Path, int]] = [
            (bundle, 0o755),
            (run_sh, 0o644),
            (note_txt, 0o644),
            (top_file, 0o644),
            (outside, 0o644),
        ]
        if non_root:
            locked.mkdir()
            restore_list.insert(0, (locked, 0o755))
        _register_mode_restore(self, restore_list)

        # Mixed modes between bundle (0o751) and top.txt (0o644) keep exec & other_read MIXED.
        os.chmod(bundle, 0o751)
        os.chmod(top_file, 0o644)
        os.chmod(run_sh, 0o755)
        os.chmod(note_txt, 0o640)
        os.chmod(outside, 0o600)
        if non_root:
            os.chmod(locked, 0o000)

        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            status_row = term.screen.rows - 3

            _navigate_to_entry(term, 'bundle')
            term.press('insert')
            _navigate_to_entry(term, 'top.txt')
            term.press('insert')
            term.wait_until(
                lambda s: '2 selected' in s.row_text(status_row),
                description='2 items selected',
            )

            term.press('ctrl+x')
            term.wait_for_text('[Ctrl+X] c=chmod o=chown')
            term.press('c')
            term.wait_for_text('Change Permissions')
            term.wait_for_text('Changing permissions for 2 files')
            term.wait_for_text('[ ]  Apply recursively')

            # Toggle group_write (row 1, col 1) ON while leaving MIXED [~] bits untouched.
            term.press('down', 'right', 'space')
            term.wait_until(
                lambda s: any('Group' in line and '>[x]<' in line for line in s.lines()),
                description='group_write checked in grid',
            )

            # In ChmodDialog.render(), recursive checkbox is at [start_x+4, start_x+9)
            # while 'Apply recursively' starts at start_x+10, so offset_x=-4 hits '[ ]'.
            term.click_text('Apply recursively', offset_x=-4)
            term.wait_for_text('[x]< Apply recursively')

            term.click_text('OK')

            if non_root:
                term.wait_for_text('Chmod succeeded on 5 of 6 files.')
                term.wait_for_text('bundle')
                term.press('enter')
                term.wait_until(
                    lambda s: not s.contains('Chmod succeeded on'),
                    description='partial error modal dismissed',
                )

            term.wait_until(
                lambda s: not s.contains('Change Permissions'),
                description='ChmodDialog closed',
            )
            _quit_cleanly(self, term)

        self.assertEqual(stat.S_IMODE(bundle.stat().st_mode), 0o771)
        self.assertEqual(stat.S_IMODE(top_file.stat().st_mode), 0o664)
        self.assertEqual(stat.S_IMODE(run_sh.stat().st_mode), 0o775)
        self.assertEqual(stat.S_IMODE(note_txt.stat().st_mode), 0o660)
        # Symlink target must remain untouched.
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o600)

    def test_ctrl_x_o_chown_dialog_inspect_cancel_and_errors(self) -> None:
        _, work, home, _ = _make_workspace(self)
        target = work / 'owned.txt'
        target.write_text('data\n', encoding='utf-8')
        env = _isolated_env(home)

        with TerminalDriver(rows=24, cols=100, cwd=work, home=home, env=env) as term:
            term.wait_ready()
            _navigate_to_entry(term, 'owned.txt')

            # Open ChownDialog, inspect fields/buttons, and cancel cleanly with Esc.
            term.press('ctrl+x')
            term.wait_for_text('[Ctrl+X] c=chmod o=chown')
            term.press('o')
            term.wait_for_text('Change Ownership')
            term.wait_for_text('File: owned.txt')
            term.wait_for_text('Owner:')
            term.wait_for_text('Group:')
            term.wait_for_text('Note: Changing owner typically requires root')
            term.wait_for_text('[  OK  ]')
            term.wait_for_text('[Cancel]')
            term.press_esc_settled()
            term.wait_until(
                lambda s: not s.contains('Change Ownership'),
                description='ChownDialog cancelled with Esc',
            )

            # Invalid username triggers validation error modal cleanly.
            term.press('ctrl+x')
            term.wait_for_text('[Ctrl+X] c=chmod o=chown')
            term.press('o')
            term.wait_for_text('Change Ownership')
            term.press(*(['backspace'] * 40))
            term.type_text('baduser_e2e')
            term.wait_for_text('Owner: [baduser_e2e_')
            term.click_text('OK')
            term.wait_for_text('Invalid user: baduser_e2e')
            term.press('enter')
            term.wait_until(
                lambda s: not s.contains('Invalid user: baduser_e2e'),
                description='invalid user error dismissed',
            )

            # Unprivileged chown to root surfaces partial-success error modal cleanly.
            if os.geteuid() != 0:
                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X] c=chmod o=chown')
                term.press('o')
                term.wait_for_text('Change Ownership')
                term.press(*(['backspace'] * 40))
                term.type_text('root')
                term.wait_for_text('Owner: [root_')
                term.press('tab', 'tab')
                term.wait_for_text('[ >OK< ]')
                term.press('enter')
                term.wait_for_text('Chown succeeded on 0 of 1 files.')
                term.wait_for_text('Operation not permitted')
                term.press('enter')
                term.wait_until(
                    lambda s: not s.contains('Operation not permitted'),
                    description='unprivileged chown error dismissed',
                )

            _quit_cleanly(self, term)


if __name__ == '__main__':
    unittest.main()
