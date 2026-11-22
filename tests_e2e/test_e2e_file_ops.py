"""End-to-end real-PTY tests for Tiny Commander selection and file operations."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.terminal import ExternalToolStub, TerminalDriver


class _FileOpsE2ECase(unittest.TestCase):
    """Shared PTY helpers for file-operation E2E scenarios."""

    COLS = 110
    ROWS = 24

    def _make_workspace(self) -> tuple[Path, Path]:
        """Create isolated temp root containing work and home directories."""
        root = Path(tempfile.mkdtemp(prefix='tnc_e2e_fops_')).resolve()
        self.addCleanup(self._cleanup_root, root)
        work = root / 'work'
        home = root / 'home'
        work.mkdir()
        home.mkdir()
        return work, home

    @staticmethod
    def _cleanup_root(root: Path) -> None:
        """Restore writable permissions recursively before removing temp root."""
        if not os.path.lexists(root):
            return

        def _chmod_safe(path: Path, mode: int) -> None:
            if not path.is_symlink():
                try:
                    os.chmod(path, mode)
                except OSError:
                    pass

        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dp = Path(dirpath)
            _chmod_safe(dp, 0o755)
            for d in dirnames:
                _chmod_safe(dp / d, 0o755)
            for f in filenames:
                _chmod_safe(dp / f, 0o644)
        shutil.rmtree(root, ignore_errors=True)

    @staticmethod
    def _isolated_env(
        home: Path,
        extra: dict[str, str | None] | None = None,
    ) -> dict[str, str | None]:
        """Build an isolated environment with XDG config inside temp home."""
        env: dict[str, str | None] = {
            'XDG_CONFIG_HOME': str(home / '.config'),
            'EDITOR': None,
            'VISUAL': None,
            'PAGER': None,
        }
        if extra:
            env.update(extra)
        return env

    def _open_driver(
        self,
        cwd: Path,
        home: Path,
        *,
        rows: int = ROWS,
        cols: int = COLS,
        env: dict[str, str | None] | None = None,
    ) -> TerminalDriver:
        return TerminalDriver(
            rows=rows,
            cols=cols,
            cwd=cwd,
            home=home,
            env=self._isolated_env(home, env),
        )

    def _assert_clean_screen(self, term: TerminalDriver) -> None:
        self.assertEqual(term.screen.check_integrity(), [])
        self.assertNotIn('Traceback (most recent call last)', term.screen.text())

    def _quit_cleanly(self, term: TerminalDriver) -> None:
        self._assert_clean_screen(term)
        term.press('f10')
        self.assertEqual(term.wait_exit(), 0)
        self.assertFalse(term.screen.in_alt_screen)

    @staticmethod
    def _panel_bounds(term: TerminalDriver, panel: str) -> tuple[int, int]:
        cols = term.screen.cols
        left_w = cols // 2
        if panel == 'left':
            return 0, left_w
        return left_w, cols - left_w

    def _panel_contains(self, term: TerminalDriver, panel: str, needle: str) -> bool:
        """Check whether ``needle`` appears inside the specified panel listing."""
        px, pw = self._panel_bounds(term, panel)
        body = '\n'.join(term.screen.region(2, px + 1, term.screen.rows - 6, pw - 2))
        return needle in body

    def _active_cursor_entry(
        self,
        term: TerminalDriver,
        *,
        panel: str = 'left',
    ) -> tuple[int, str] | None:
        """Return (row, trimmed_entry_text) for the highlighted cursor row."""
        px, pw = self._panel_bounds(term, panel)
        for r in range(2, term.screen.rows - 4):
            if term.screen.style_at(r, px + 1).bg == 6:
                text = term.screen.region(r, px + 1, 1, pw - 2)[0]
                return r, text
        return None

    @staticmethod
    def _entry_matches_row_text(row_text: str, name: str) -> bool:
        """Check whether panel row text represents entry ``name``."""
        candidates = (
            name + ' ',
            name + '/',
            '*' + name + ' ',
        )
        return any(row_text.startswith(cand) for cand in candidates)

    def _move_cursor_to(
        self,
        term: TerminalDriver,
        name: str,
        *,
        panel: str = 'left',
        max_steps: int = 40,
    ) -> int:
        """Move the active panel cursor onto ``name`` and return its screen row."""
        cur = self._active_cursor_entry(term, panel=panel)
        if cur is not None and self._entry_matches_row_text(cur[1], name):
            return cur[0]

        # Jump to '..' at top first so traversal order is deterministic.
        term.press('home')
        term.wait_until(
            lambda s: (c := self._active_cursor_entry(term, panel=panel)) is not None
            and c[1].startswith('..'),
            description='cursor at top entry',
        )
        if name == '..':
            cur = self._active_cursor_entry(term, panel=panel)
            assert cur is not None
            return cur[0]

        for _ in range(max_steps):
            cur = self._active_cursor_entry(term, panel=panel)
            if cur is not None and self._entry_matches_row_text(cur[1], name):
                return cur[0]
            prev_row = cur[0] if cur is not None else -1
            prev_text = cur[1] if cur is not None else ''
            term.press('down')
            term.wait_until(
                lambda _s: (
                    (nxt := self._active_cursor_entry(term, panel=panel)) is not None
                    and (nxt[0] != prev_row or nxt[1] != prev_text)
                ),
                timeout=0.5,
                description=f'cursor step toward {name!r}',
            )
            cur = self._active_cursor_entry(term, panel=panel)
            if cur is not None and self._entry_matches_row_text(cur[1], name):
                return cur[0]

        self.fail(f'Could not move {panel} cursor to {name!r}\n{term.screen.screenshot()}')

    def _setup_two_panels(
        self,
        term: TerminalDriver,
        left_subdir: str,
        right_subdir: str,
    ) -> None:
        """Navigate left panel into ``left_subdir`` and right panel into ``right_subdir``."""
        self._move_cursor_to(term, left_subdir, panel='left')
        term.press('enter')
        term.wait_until(
            lambda scr: f'/{left_subdir}' in scr.region(1, 0, 1, scr.cols // 2)[0],
            description=f'left panel in /{left_subdir}',
        )

        term.press('tab')
        term.wait_for_text('[Right]')

        self._move_cursor_to(term, right_subdir, panel='right')
        term.press('enter')
        term.wait_until(
            lambda scr: f'/{right_subdir}' in scr.region(
                1, scr.cols // 2, 1, scr.cols - scr.cols // 2
            )[0],
            description=f'right panel in /{right_subdir}',
        )

        term.press('tab')
        term.wait_for_text('[Left]')

    def _dismiss_summary(self, term: TerminalDriver, expected_text: str) -> None:
        """Wait for bottom-line SummaryModal and dismiss it cleanly."""
        term.wait_for_text(expected_text, row=term.screen.rows - 1)
        self._assert_clean_screen(term)
        term.press('enter')
        term.wait_until(
            lambda s: not s.contains(expected_text),
            description=f'summary {expected_text!r} dismissed',
        )

    def _dismiss_error(
        self,
        term: TerminalDriver,
        expected_title: str,
        expected_detail: str,
    ) -> None:
        """Wait for ErrorModal with expected title/detail and dismiss it."""
        term.wait_for_text(expected_title)
        term.wait_for_text(expected_detail)
        self._assert_clean_screen(term)
        term.press('enter')
        term.wait_until(
            lambda s: not s.contains(expected_title),
            description=f'error modal {expected_title!r} dismissed',
        )


class TestSelectionE2E(_FileOpsE2ECase):
    """E2E tests for Insert/Space selection, +, -, *, styling, and Esc clearing."""

    def test_insert_toggles_selection_advances_cursor_and_applies_styles(self) -> None:
        work, home = self._make_workspace()
        (work / 'alpha.txt').write_text('hello world!', encoding='utf-8')  # 12 bytes
        (work / 'beta.txt').write_text('12345', encoding='utf-8')
        (work / 'gamma.md').write_text('md', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._assert_clean_screen(term)

            # Pressing Insert on '..' advances cursor to alpha.txt without selecting '..'
            cur = self._active_cursor_entry(term, panel='left')
            self.assertIsNotNone(cur)
            assert cur is not None
            self.assertTrue(cur[1].startswith('..'))
            term.press('insert')
            term.wait_until(
                lambda _s: (c := self._active_cursor_entry(term)) is not None
                and c[1].startswith('alpha.txt'),
                description='cursor advances from .. to alpha.txt',
            )
            self.assertNotIn('selected', term.screen.row_text(term.screen.rows - 3))
            self.assertIsNone(term.screen.find_styled_text('..', fg=3))

            # Inspect initial cursor style on alpha.txt (black on cyan) and unselected beta.txt
            alpha_col, alpha_row = term.wait_for_text('alpha.txt')
            self.assertTrue(term.screen.style_at(alpha_row, alpha_col).matches(fg=0, bg=6, bold=False))
            beta_col, beta_row = term.wait_for_text('beta.txt')
            self.assertTrue(term.screen.style_at(beta_row, beta_col).matches(fg=7, bg=4, bold=False))

            # Toggle selection with Insert -> selects alpha.txt, advances cursor to beta.txt
            term.press('insert')
            term.wait_for_text('| 1 selected')
            cur_after = self._active_cursor_entry(term)
            self.assertIsNotNone(cur_after)
            assert cur_after is not None
            self.assertTrue(cur_after[1].startswith('beta.txt'))

            # Off-cursor selected entry uses PAIR_SELECTED (yellow bold on blue)
            self.assertIsNotNone(
                term.screen.find_styled_text('alpha.txt', fg=3, bg=4, bold=True)
            )
            self.assertTrue(term.screen.style_at(alpha_row, alpha_col).matches(fg=3, bg=4, bold=True))

            # Move cursor back onto alpha.txt -> uses PAIR_CURSOR_SELECTED (yellow bold on cyan)
            term.press('up')
            term.wait_until(
                lambda s: s.find_styled_text('alpha.txt', fg=3, bg=6, bold=True) is not None,
                description='cursor on selected alpha.txt styled yellow on cyan',
            )

            # Toggle Insert again on alpha.txt -> deselects and advances cursor
            term.press('insert')
            term.wait_until(
                lambda s: 'selected' not in s.row_text(s.rows - 3),
                description='selection count cleared after second Insert',
            )
            self.assertIsNone(term.screen.find_styled_text('alpha.txt', fg=3))

            self._quit_cleanly(term)

    def test_pattern_select_deselect_invert_menu_deselect_and_double_esc(self) -> None:
        work, home = self._make_workspace()
        (work / 'sub').mkdir()
        (work / 'a1.txt').write_text('1', encoding='utf-8')
        (work / 'a2.txt').write_text('2', encoding='utf-8')
        (work / 'b2.txt').write_text('3', encoding='utf-8')
        (work / 'notes.md').write_text('4', encoding='utf-8')

        with self._open_driver(work, home, cols=110) as term:
            term.wait_ready()

            # '+' select by glob *.txt
            term.press('+')
            term.wait_for_text('Select by pattern')
            term.type_text('*.txt')
            term.press('enter')
            term.wait_for_text('| 3 selected')
            for name in ('a1.txt', 'a2.txt', 'b2.txt'):
                self.assertIsNotNone(term.screen.find_styled_text(name, fg=3, bold=True))
            self.assertIsNone(term.screen.find_styled_text('notes.md', fg=3))
            self.assertIsNone(term.screen.find_styled_text('..', fg=3))

            # '-' deselect by glob *2.txt -> leaves only a1.txt selected
            term.press('-')
            term.wait_for_text('Deselect by pattern')
            term.type_text('*2.txt')
            term.press('enter')
            term.wait_for_text('| 1 selected')
            self.assertIsNotNone(term.screen.find_styled_text('a1.txt', fg=3, bold=True))
            self.assertIsNone(term.screen.find_styled_text('a2.txt', fg=3))
            self.assertIsNone(term.screen.find_styled_text('b2.txt', fg=3))

            # '*' invert selection -> selects sub/, a2.txt, b2.txt, notes.md (4), never '..'
            term.press('*')
            term.wait_for_text('| 4 selected')
            self.assertIsNone(term.screen.find_styled_text('a1.txt', fg=3))
            self.assertIsNone(term.screen.find_styled_text('..', fg=3))
            for name in ('sub/', 'a2.txt', 'b2.txt', 'notes.md'):
                self.assertIsNotNone(term.screen.find_styled_text(name, fg=3, bold=True))

            # Double-Esc clears command line after '[Esc] again to clear' (selection stays intact)
            term.type_text('echo hi')
            cmd_row = term.screen.rows - 2
            term.wait_for_text('echo hi', row=cmd_row)
            term.press_esc_settled()
            term.wait_for_text('[Esc] again to clear', row=term.screen.rows - 3)
            self.assertIn('| 4 selected', term.screen.row_text(term.screen.rows - 3))
            term.press_esc_settled()
            term.wait_until(
                lambda s: 'echo hi' not in s.row_text(cmd_row)
                and '[Esc] again' not in s.row_text(s.rows - 3),
                description='command line cleared on second Esc',
            )
            self.assertIn('| 4 selected', term.screen.row_text(term.screen.rows - 3))

            # Command -> Deselect all clears panel selection cleanly
            term.click_text(' Command ', row=0, settle=True)
            term.wait_for_text('Deselect all')
            term.click_text('Deselect all', settle=True)
            term.wait_until(
                lambda s: 'selected' not in s.row_text(s.rows - 3)
                and s.find_styled_text('a2.txt', fg=3) is None,
                description='Command -> Deselect all clears selection',
            )

            self._quit_cleanly(term)


class TestCopyMoveE2E(_FileOpsE2ECase):
    """E2E tests for F5 Copy and F6 Move across panels."""

    def test_f5_copy_single_file_cancel_and_confirm(self) -> None:
        work, home = self._make_workspace()
        src = work / 'src'
        dst = work / 'dst'
        src.mkdir()
        dst.mkdir()
        (src / 'hello.txt').write_text('hello world', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._setup_two_panels(term, 'src', 'dst')
            self._move_cursor_to(term, 'hello.txt', panel='left')

            # Cancel first via 'n'
            term.press('f5')
            term.wait_for_text('Copy "hello.txt" to')
            term.wait_for_text(f'/{work.name}/')
            self._assert_clean_screen(term)
            term.press('n')
            term.wait_until(lambda s: not s.contains('Copy "hello.txt" to'))
            self.assertFalse((dst / 'hello.txt').exists())

            # Confirm copy with 'y'
            term.press('f5')
            term.wait_for_text('Copy "hello.txt" to')
            term.press('y')
            self._dismiss_summary(term, 'Copied 1 file(s) [Press any key]')

            self.assertEqual((src / 'hello.txt').read_text(encoding='utf-8'), 'hello world')
            self.assertEqual((dst / 'hello.txt').read_text(encoding='utf-8'), 'hello world')
            self.assertTrue(self._panel_contains(term, 'left', 'hello.txt'))
            self.assertTrue(self._panel_contains(term, 'right', 'hello.txt'))

            self._quit_cleanly(term)

    def test_f5_copy_multi_selected_and_nested_directory_tree(self) -> None:
        work, home = self._make_workspace()
        src = work / 'src'
        dst_parent = work / 'dst'
        target_dir = dst_parent / 'custom_target'
        src.mkdir()
        target_dir.mkdir(parents=True)

        (src / 'one.txt').write_text('111', encoding='utf-8')
        (src / 'two.txt').write_text('222', encoding='utf-8')
        (src / 'skip.log').write_text('skip', encoding='utf-8')
        tree = src / 'tree'
        (tree / 'sub').mkdir(parents=True)
        (tree / 'empty_sub').mkdir()
        (tree / 'sub' / 'deep.txt').write_text('deep content', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._setup_two_panels(term, 'src', 'dst')

            # Navigate right panel deeper into custom_target to verify custom target path
            term.press('tab')
            term.wait_for_text('[Right]')
            self._move_cursor_to(term, 'custom_target', panel='right')
            term.press('enter')
            term.wait_until(
                lambda scr: '/custom_target' in scr.region(
                    1, scr.cols // 2, 1, scr.cols - scr.cols // 2
                )[0],
                description='right panel in custom_target',
            )
            term.press('tab')
            term.wait_for_text('[Left]')

            # Select tree/, one.txt, two.txt (leave skip.log unselected)
            for item in ('tree', 'one.txt', 'two.txt'):
                self._move_cursor_to(term, item, panel='left')
                term.press('insert')
            term.wait_for_text('| 3 selected')

            term.press('f5')
            term.wait_for_text('Copy 3 files to')
            term.wait_for_text(f'/{work.name}/{dst_parent.name}/')
            term.press('enter')
            self._dismiss_summary(term, 'Copied 3 file(s) [Press any key]')

            self.assertEqual((target_dir / 'one.txt').read_text(encoding='utf-8'), '111')
            self.assertEqual((target_dir / 'two.txt').read_text(encoding='utf-8'), '222')
            self.assertEqual(
                (target_dir / 'tree' / 'sub' / 'deep.txt').read_text(encoding='utf-8'),
                'deep content',
            )
            self.assertTrue((target_dir / 'tree' / 'empty_sub').is_dir())
            self.assertFalse((target_dir / 'skip.log').exists())
            # Source items remain and selection is cleared
            self.assertTrue((src / 'one.txt').exists())
            self.assertNotIn('selected', term.screen.row_text(term.screen.rows - 3))

            self._quit_cleanly(term)

    def test_f6_move_single_file_and_multi_selected_directory(self) -> None:
        work, home = self._make_workspace()
        src = work / 'src'
        dst = work / 'dst'
        src.mkdir()
        dst.mkdir()

        (src / 'single.txt').write_text('solo', encoding='utf-8')
        (src / 'm1.txt').write_text('first', encoding='utf-8')
        (src / 'm2.txt').write_text('second', encoding='utf-8')
        (src / 'keep.txt').write_text('stay', encoding='utf-8')
        (src / 'mdir').mkdir()
        (src / 'mdir' / 'nested.txt').write_text('nested-body', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._setup_two_panels(term, 'src', 'dst')

            # Move single file with F6
            self._move_cursor_to(term, 'single.txt', panel='left')
            term.press('f6')
            term.wait_for_text('Move "single.txt" to')
            term.press('y')
            self._dismiss_summary(term, 'Moved 1 file(s) [Press any key]')

            self.assertFalse((src / 'single.txt').exists())
            self.assertEqual((dst / 'single.txt').read_text(encoding='utf-8'), 'solo')
            self.assertEqual(len(term.screen.find_all('single.txt')), 1)

            # Move multi-selected files + directory with F6
            for item in ('mdir', 'm1.txt', 'm2.txt'):
                self._move_cursor_to(term, item, panel='left')
                term.press('insert')
            term.wait_for_text('| 3 selected')

            term.press('f6')
            term.wait_for_text('Move 3 files to')
            term.press('enter')
            self._dismiss_summary(term, 'Moved 3 file(s) [Press any key]')

            for item in ('mdir', 'm1.txt', 'm2.txt'):
                self.assertFalse((src / item).exists())
            self.assertEqual((dst / 'm1.txt').read_text(encoding='utf-8'), 'first')
            self.assertEqual((dst / 'm2.txt').read_text(encoding='utf-8'), 'second')
            self.assertEqual((dst / 'mdir' / 'nested.txt').read_text(encoding='utf-8'), 'nested-body')
            self.assertTrue((src / 'keep.txt').exists())

            self._quit_cleanly(term)


class TestOverwriteAndSymlinkGuardsE2E(_FileOpsE2ECase):
    """E2E tests for OverwriteModal buttons/Esc and symlink copy/move guards."""

    def test_overwrite_yes_no_and_esc_cancel(self) -> None:
        work, home = self._make_workspace()
        src = work / 'src'
        dst = work / 'dst'
        src.mkdir()
        dst.mkdir()

        for name in ('a.txt', 'b.txt', 'c.txt'):
            (src / name).write_text(f'src_{name}', encoding='utf-8')
            (dst / name).write_text(f'dst_{name}', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._setup_two_panels(term, 'src', 'dst')

            # Batch 1: select a.txt and b.txt -> click No on a.txt, click Yes on b.txt
            for name in ('a.txt', 'b.txt'):
                self._move_cursor_to(term, name, panel='left')
                term.press('insert')
            term.press('f5')
            term.wait_for_text('Copy 2 files to')
            term.press('y')

            # Panel.selected is a set so conflict order follows hash order.
            # Inspect the modal's prompted filename directly and choose No for
            # a.txt and Yes for b.txt regardless of iteration order.
            seen_conflicts: list[str] = []
            for step in (1, 2):
                _, title_row = term.wait_for_text(f'File already exists - {step} of 2')
                if step == 1:
                    for label in ('Yes', 'No', 'All', 'Skip', 'Older'):
                        self.assertTrue(term.screen.contains(label))
                    self._assert_clean_screen(term)
                sep_col = term.screen.row_text(title_row + 1).find('├')
                self.assertGreater(sep_col, 0)
                modal_name = term.screen.region(title_row + 2, sep_col + 2, 1, 20)[0].strip()
                self.assertIn(modal_name, ('a.txt', 'b.txt'))
                seen_conflicts.append(modal_name)
                btn_text = '  No  ' if modal_name == 'a.txt' else '< Yes >'
                term.click_text(btn_text, row=title_row + 6, settle=True)

            self.assertEqual(set(seen_conflicts), {'a.txt', 'b.txt'})
            self._dismiss_summary(term, 'Copied 1 file(s), skipped 1 [Press any key]')

            self.assertEqual((dst / 'a.txt').read_text(encoding='utf-8'), 'dst_a.txt')
            self.assertEqual((dst / 'b.txt').read_text(encoding='utf-8'), 'src_b.txt')

            # Batch 2: select a.txt and c.txt -> Esc cancels cleanly on first conflict
            for name in ('a.txt', 'c.txt'):
                self._move_cursor_to(term, name, panel='left')
                term.press('insert')
            term.press('f5')
            term.wait_for_text('Copy 2 files to')
            term.press('y')

            term.wait_for_text('File already exists - 1 of 2')
            term.press_esc_settled()
            self._dismiss_error(term, 'Operation cancelled', 'Copied 0 file(s), 1 failed')

            self.assertEqual((dst / 'a.txt').read_text(encoding='utf-8'), 'dst_a.txt')
            self.assertEqual((dst / 'c.txt').read_text(encoding='utf-8'), 'dst_c.txt')

            self._quit_cleanly(term)

    def test_overwrite_all_and_skip_across_multiple_conflicts(self) -> None:
        work, home = self._make_workspace()
        src = work / 'src'
        dst = work / 'dst'
        src.mkdir()
        dst.mkdir()

        for name in ('f1.txt', 'f2.txt', 'f3.txt'):
            (src / name).write_text(f'new_{name}', encoding='utf-8')
            (dst / name).write_text(f'old_{name}', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._setup_two_panels(term, 'src', 'dst')

            # Select all via '*' and Skip all via 's'
            term.press('*')
            term.wait_for_text('| 3 selected')
            term.press('f5')
            term.wait_for_text('Copy 3 files to')
            term.press('y')

            term.wait_for_text('File already exists - 1 of 3')
            term.press('s')
            self._dismiss_summary(term, 'Copied 0 file(s), skipped 3 [Press any key]')
            for name in ('f1.txt', 'f2.txt', 'f3.txt'):
                self.assertEqual((dst / name).read_text(encoding='utf-8'), f'old_{name}')

            # Select all via '*' and overwrite All via 'a'
            term.press('*')
            term.wait_for_text('| 3 selected')
            term.press('f5')
            term.wait_for_text('Copy 3 files to')
            term.press('y')

            term.wait_for_text('File already exists - 1 of 3')
            term.press('a')
            self._dismiss_summary(term, 'Copied 3 file(s) [Press any key]')
            for name in ('f1.txt', 'f2.txt', 'f3.txt'):
                self.assertEqual((dst / name).read_text(encoding='utf-8'), f'new_{name}')

            self._quit_cleanly(term)

    def test_symlink_copy_move_preserves_symlink_and_canary_and_type_guard(self) -> None:
        work, home = self._make_workspace()
        canary_dir = work.parent / 'external_canary'
        canary_dir.mkdir()
        canary_file = canary_dir / 'secret.txt'
        canary_file.write_text('CANARY_UNTOUCHED', encoding='utf-8')
        os.chmod(canary_file, 0o644)

        src = work / 'src'
        dst = work / 'dst'
        src.mkdir()
        dst.mkdir()

        (src / 'copy_link.txt').symlink_to(canary_file)
        (src / 'move_link.txt').symlink_to(canary_file)
        (src / 'guard_item').symlink_to(canary_file)
        (dst / 'guard_item').mkdir()
        (dst / 'guard_item' / 'precious.txt').write_text('keep me', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._setup_two_panels(term, 'src', 'dst')

            # F5 copy symlink -> destination stays symlink, external canary untouched
            self._move_cursor_to(term, 'copy_link.txt', panel='left')
            term.press('f5')
            term.wait_for_text('Copy "copy_link.txt" to')
            term.press('y')
            self._dismiss_summary(term, 'Copied 1 file(s) [Press any key]')

            dst_copy_link = dst / 'copy_link.txt'
            self.assertTrue(dst_copy_link.is_symlink())
            self.assertEqual(os.readlink(dst_copy_link), str(canary_file))
            self.assertTrue((src / 'copy_link.txt').is_symlink())
            self.assertEqual(canary_file.read_text(encoding='utf-8'), 'CANARY_UNTOUCHED')

            # F6 move symlink -> moved symlink stays symlink, source gone, canary untouched
            self._move_cursor_to(term, 'move_link.txt', panel='left')
            term.press('f6')
            term.wait_for_text('Move "move_link.txt" to')
            term.press('y')
            self._dismiss_summary(term, 'Moved 1 file(s) [Press any key]')

            dst_move_link = dst / 'move_link.txt'
            self.assertFalse(os.path.lexists(src / 'move_link.txt'))
            self.assertTrue(dst_move_link.is_symlink())
            self.assertEqual(os.readlink(dst_move_link), str(canary_file))
            self.assertEqual(canary_file.read_text(encoding='utf-8'), 'CANARY_UNTOUCHED')

            # Symlink overwrite guard: copy symlink over real directory is refused
            self._move_cursor_to(term, 'guard_item', panel='left')
            term.press('f5')
            term.wait_for_text('Copy "guard_item" to')
            term.press('y')
            self._dismiss_error(term, 'Copy completed with errors', 'Refusing to copy symlink')

            self.assertTrue((dst / 'guard_item').is_dir())
            self.assertFalse((dst / 'guard_item').is_symlink())
            self.assertEqual((dst / 'guard_item' / 'precious.txt').read_text(encoding='utf-8'), 'keep me')
            self.assertEqual(canary_file.read_text(encoding='utf-8'), 'CANARY_UNTOUCHED')

            self._quit_cleanly(term)


class TestMkdirCreateRenameDeleteE2E(_FileOpsE2ECase):
    """E2E tests for F7 mkdir, Shift+F4 create file, File->Rename, and F8 delete."""

    def test_f7_mkdir_create_cancel_and_error_modals(self) -> None:
        work, home = self._make_workspace()

        with self._open_driver(work, home) as term:
            term.wait_ready()

            # Esc cancels mkdir without creating anything
            term.press('f7')
            term.wait_for_text('Create directory')
            term.press_esc_settled()
            term.wait_until(lambda s: not s.contains('Create directory'))
            self.assertEqual(list(work.iterdir()), [])

            # Create alpha_dir and verify cursor moves to it
            term.press('f7')
            term.wait_for_text('Create directory')
            term.type_text('alpha_dir')
            term.press('enter')
            term.wait_for_text('alpha_dir/')
            self.assertTrue((work / 'alpha_dir').is_dir())
            cur = self._active_cursor_entry(term, panel='left')
            self.assertIsNotNone(cur)
            assert cur is not None
            self.assertTrue(cur[1].startswith('alpha_dir/'))

            # Duplicate directory error modal
            term.press('f7')
            term.wait_for_text('Create directory')
            term.type_text('alpha_dir')
            term.press('enter')
            self._dismiss_error(term, 'Mkdir Failed', 'Directory already exists')

            # Nested path separator rejected cleanly
            term.press('f7')
            term.wait_for_text('Create directory')
            term.type_text('bad/nested')
            term.press('enter')
            self._dismiss_error(term, 'Mkdir Failed', 'Invalid directory name')
            self.assertFalse((work / 'bad').exists())

            self._quit_cleanly(term)

    def test_shift_f4_create_file_normal_and_hidden_when_show_hidden_false(self) -> None:
        work, home = self._make_workspace()
        tools = home / 'tools'
        editor = ExternalToolStub.create(tools, 'stub_editor', append_text='created-ok')
        pager = ExternalToolStub.create(tools, 'stub_pager')

        (work / '.prehidden').write_text('hidden', encoding='utf-8')
        (work / 'visible.txt').write_text('vis', encoding='utf-8')

        with self._open_driver(
            work,
            home,
            env={'EDITOR': str(editor.path), 'PAGER': str(pager.path)},
        ) as term:
            term.wait_ready()
            self.assertEqual(len(term.screen.find_all('.prehidden')), 2)

            # Create normal file via Shift+F4 -> invokes stub $EDITOR and refreshes panel
            term.press('shift+f4')
            term.wait_for_text('Create file')
            term.type_text('fresh.txt')
            term.press('enter')
            term.wait_until(lambda _s: len(editor.calls()) == 1, description='stub editor call 1')
            term.wait_ready()

            self.assertEqual((work / 'fresh.txt').read_text(encoding='utf-8'), 'created-ok')
            self.assertTrue(self._panel_contains(term, 'left', 'fresh.txt'))
            self.assertTrue(self._panel_contains(term, 'right', 'fresh.txt'))

            # Toggle hidden files OFF on Left panel via Left menu
            term.click_text(' Left ', row=0, settle=True)
            term.wait_for_text('Toggle hidden')
            term.click_text('Toggle hidden', settle=True)
            term.wait_until(
                lambda s: len(s.find_all('.prehidden')) == 1,
                description='left panel hides dotfiles while right keeps showing them',
            )

            # Create hidden .secret while active Left panel has show_hidden=False
            term.press('shift+f4')
            term.wait_for_text('Create file')
            term.type_text('.secret')
            term.press('enter')
            term.wait_until(lambda _s: len(editor.calls()) == 2, description='stub editor call 2')
            term.wait_ready()

            self.assertEqual((work / '.secret').read_text(encoding='utf-8'), 'created-ok')
            self.assertTrue(editor.calls()[1]['argv'][-1].endswith('.secret'))
            # Right panel (same cwd, show_hidden=True) shows .secret; Left keeps it hidden
            cols_found = [c for c, _r in term.screen.find_all('.secret')]
            self.assertEqual(len(cols_found), 1)
            self.assertGreaterEqual(cols_found[0], term.screen.cols // 2)

            self._quit_cleanly(term)

    def test_file_menu_rename_edits_default_updates_disk_and_cursor(self) -> None:
        work, home = self._make_workspace()
        (work / 'aaa.txt').write_text('aaa', encoding='utf-8')
        (work / 'old_name.txt').write_text('rename me', encoding='utf-8')
        (work / 'zzz.txt').write_text('zzz', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()
            self._move_cursor_to(term, 'old_name.txt', panel='left')

            # Rename via File -> Rename (no direct F-key shortcut in tnc)
            term.click_text(' File ', row=0, settle=True)
            term.wait_for_text('Rename')
            term.click_text('Rename', settle=True)
            term.wait_for_text('Rename "old_name.txt" to:')

            # Edit pre-populated default_value with Home + Delete + typing
            term.press('home', 'delete', 'delete', 'delete')
            term.type_text('mid')
            term.press('enter')
            term.wait_until(
                lambda s: not s.contains('Rename "old_name.txt" to:')
                and self._panel_contains(term, 'left', 'mid_name.txt'),
                description='rename modal closed and mid_name.txt listed',
            )

            self.assertFalse((work / 'old_name.txt').exists())
            self.assertEqual((work / 'mid_name.txt').read_text(encoding='utf-8'), 'rename me')
            cur = self._active_cursor_entry(term, panel='left')
            self.assertIsNotNone(cur)
            assert cur is not None
            self.assertTrue(cur[1].startswith('mid_name.txt'))

            # Attempting rename onto existing file shows error modal
            term.click_text(' File ', row=0, settle=True)
            term.wait_for_text('Rename')
            term.click_text('Rename', settle=True)
            term.wait_for_text('Rename "mid_name.txt" to:')
            for _ in range(len('mid_name.txt')):
                term.press('backspace')
            term.type_text('aaa.txt')
            term.press('enter')
            self._dismiss_error(term, 'Error', 'Destination already exists')
            self.assertTrue((work / 'mid_name.txt').exists())
            self.assertTrue((work / 'aaa.txt').exists())

            self._quit_cleanly(term)

    def test_f8_delete_file_empty_dir_recursive_dir_and_multi_selected(self) -> None:
        work, home = self._make_workspace()
        (work / 'empty_dir').mkdir()
        (work / 'full_dir' / 'sub').mkdir(parents=True)
        (work / 'full_dir' / 'sub' / 'leaf.txt').write_text('leaf', encoding='utf-8')
        (work / 'del_file.txt').write_text('bye', encoding='utf-8')
        (work / 'keep.txt').write_text('keep', encoding='utf-8')
        (work / 'm1.txt').write_text('1', encoding='utf-8')
        (work / 'm2.txt').write_text('2', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()

            # F8 on '..' is a safe no-op
            self._move_cursor_to(term, '..', panel='left')
            term.press('f8')
            term.wait_stable(quiet_period=0.04, timeout=0.3)
            self.assertFalse(term.screen.contains('Delete Confirmation'))

            # Cancel delete of empty_dir with 'n', then confirm with 'y'
            self._move_cursor_to(term, 'empty_dir', panel='left')
            term.press('f8')
            term.wait_for_text('Delete Confirmation')
            term.wait_for_text('Delete "empty_dir"?')
            term.press('n')
            term.wait_until(lambda s: not s.contains('Delete Confirmation'))
            self.assertTrue((work / 'empty_dir').is_dir())

            term.press('f8')
            term.wait_for_text('Delete "empty_dir"?')
            term.press('y')
            term.wait_until(lambda _s: not self._panel_contains(term, 'left', 'empty_dir'))
            self.assertFalse((work / 'empty_dir').exists())

            # Recursive delete of non-empty directory via Enter (default Yes)
            self._move_cursor_to(term, 'full_dir', panel='left')
            term.press('f8')
            term.wait_for_text('Delete "full_dir"?')
            term.press('enter')
            term.wait_until(lambda _s: not self._panel_contains(term, 'left', 'full_dir'))
            self.assertFalse((work / 'full_dir').exists())

            # Delete single file
            self._move_cursor_to(term, 'del_file.txt', panel='left')
            term.press('f8')
            term.wait_for_text('Delete "del_file.txt"?')
            term.press('y')
            term.wait_until(lambda _s: not self._panel_contains(term, 'left', 'del_file.txt'))
            self.assertFalse((work / 'del_file.txt').exists())

            # Multi-selected delete
            for item in ('m1.txt', 'm2.txt'):
                self._move_cursor_to(term, item, panel='left')
                term.press('insert')
            term.wait_for_text('| 2 selected')
            term.press('f8')
            term.wait_for_text('Delete 2 files?')
            term.press('y')
            term.wait_until(
                lambda _s: not self._panel_contains(term, 'left', 'm1.txt')
                and not self._panel_contains(term, 'left', 'm2.txt'),
                description='multi-selected files deleted from screen',
            )
            self.assertFalse((work / 'm1.txt').exists())
            self.assertFalse((work / 'm2.txt').exists())
            self.assertTrue((work / 'keep.txt').exists())

            self._quit_cleanly(term)


class TestEdgeCasesAndErrorsE2E(_FileOpsE2ECase):
    """E2E tests for self-copy, recursive subdir copy, EACCES, and special filenames."""

    def test_copy_onto_self_and_into_own_subdirectory_errors(self) -> None:
        work, home = self._make_workspace()
        (work / 'parent_dir' / 'sub_dir').mkdir(parents=True)
        (work / 'parent_dir' / 'sub_dir' / 'inner.txt').write_text('inner', encoding='utf-8')
        (work / 'solo.txt').write_text('solo', encoding='utf-8')

        with self._open_driver(work, home) as term:
            term.wait_ready()

            # Same directory copy error (both panels start in work)
            self._move_cursor_to(term, 'solo.txt', panel='left')
            term.press('f5')
            term.wait_for_text('Copy "solo.txt" to')
            term.press('y')
            self._dismiss_error(term, 'Copy completed with errors', 'Cannot copy to same directory')
            self.assertEqual((work / 'solo.txt').read_text(encoding='utf-8'), 'solo')

            # Copy parent_dir into parent_dir/sub_dir error
            term.press('tab')
            term.wait_for_text('[Right]')
            self._move_cursor_to(term, 'parent_dir', panel='right')
            term.press('enter')
            term.wait_until(
                lambda scr: '/parent_dir' in scr.region(
                    1, scr.cols // 2, 1, scr.cols - scr.cols // 2
                )[0],
            )
            self._move_cursor_to(term, 'sub_dir', panel='right')
            term.press('enter')
            term.wait_until(
                lambda scr: '/sub_dir' in scr.region(
                    1, scr.cols // 2, 1, scr.cols - scr.cols // 2
                )[0],
            )
            term.press('tab')
            term.wait_for_text('[Left]')

            self._move_cursor_to(term, 'parent_dir', panel='left')
            term.press('f5')
            term.wait_for_text('Copy "parent_dir" to')
            term.press('y')
            self._dismiss_error(
                term,
                'Copy completed with errors',
                'Cannot copy directory into itself or a subdirectory',
            )
            self.assertFalse((work / 'parent_dir' / 'sub_dir' / 'parent_dir').exists())

            self._quit_cleanly(term)

    def test_permission_denied_copy_and_delete_errors(self) -> None:
        if os.geteuid() == 0:
            self.skipTest('Root bypasses chmod permission checks')

        work, home = self._make_workspace()
        src = work / 'src'
        dst = work / 'dst'
        locked = work / 'locked_dir'
        src.mkdir()
        dst.mkdir()
        locked.mkdir()

        unreadable = src / 'unreadable.txt'
        unreadable.write_text('secret', encoding='utf-8')
        protected = locked / 'protected.txt'
        protected.write_text('stay', encoding='utf-8')

        os.chmod(unreadable, 0o000)
        self.addCleanup(lambda: os.chmod(unreadable, 0o644) if unreadable.exists() else None)
        os.chmod(locked, 0o555)
        self.addCleanup(lambda: os.chmod(locked, 0o755) if locked.exists() else None)

        try:
            with self._open_driver(work, home) as term:
                term.wait_ready()
                self._setup_two_panels(term, 'src', 'dst')

                # Permission denied on copy (0o000 source file)
                self._move_cursor_to(term, 'unreadable.txt', panel='left')
                term.press('f5')
                term.wait_for_text('Copy "unreadable.txt" to')
                term.press('y')
                self._dismiss_error(term, 'Copy completed with errors', 'Permission denied')
                self.assertFalse((dst / 'unreadable.txt').exists())

                # Navigate left panel into locked_dir (0o555) and attempt delete
                self._move_cursor_to(term, '..', panel='left')
                term.press('enter')
                term.wait_until(
                    lambda scr: f'/{work.name}' in scr.region(1, 0, 1, scr.cols // 2)[0],
                )
                self._move_cursor_to(term, 'locked_dir', panel='left')
                term.press('enter')
                term.wait_until(
                    lambda scr: '/locked_dir' in scr.region(1, 0, 1, scr.cols // 2)[0],
                )

                self._move_cursor_to(term, 'protected.txt', panel='left')
                term.press('f8')
                term.wait_for_text('Delete "protected.txt"?')
                term.press('y')
                self._dismiss_error(term, 'Delete Failed', 'Permission denied')
                self.assertTrue(protected.exists())

                self._quit_cleanly(term)
        finally:
            if unreadable.exists():
                os.chmod(unreadable, 0o644)
            if locked.exists():
                os.chmod(locked, 0o755)

    def test_special_chars_spaces_quotes_dollar_and_unicode_ops(self) -> None:
        work, home = self._make_workspace()
        src = work / 'src'
        dst = work / 'dst'
        src.mkdir()
        dst.mkdir()

        sp_quote_dollar = "sp 'q' $v.txt"
        dbl_quote = 'd"q" file.txt'
        unicode_dir = 'café_папка'
        cjk_file = '日本語.txt'

        (src / sp_quote_dollar).write_text('sqd', encoding='utf-8')
        (src / dbl_quote).write_text('dq', encoding='utf-8')
        (src / unicode_dir).mkdir()
        (src / unicode_dir / 'inside.txt').write_text('in', encoding='utf-8')
        (src / cjk_file).write_text('cjk', encoding='utf-8')

        with self._open_driver(work, home, cols=120) as term:
            term.wait_ready()
            self._setup_two_panels(term, 'src', 'dst')

            # Copy filename with spaces, single quotes, and $
            self._move_cursor_to(term, sp_quote_dollar, panel='left')
            term.press('f5')
            term.wait_for_text(f'Copy "{sp_quote_dollar}" to')
            term.press('y')
            self._dismiss_summary(term, 'Copied 1 file(s) [Press any key]')
            self.assertEqual((dst / sp_quote_dollar).read_text(encoding='utf-8'), 'sqd')

            # Move filename with double quotes and space
            self._move_cursor_to(term, dbl_quote, panel='left')
            term.press('f6')
            term.wait_for_text(f'Move "{dbl_quote}" to')
            term.press('y')
            self._dismiss_summary(term, 'Moved 1 file(s) [Press any key]')
            self.assertFalse((src / dbl_quote).exists())
            self.assertEqual((dst / dbl_quote).read_text(encoding='utf-8'), 'dq')

            # Rename Unicode directory preserving accented + Cyrillic prefix
            self._move_cursor_to(term, unicode_dir, panel='left')
            term.click_text(' File ', row=0, settle=True)
            term.wait_for_text('Rename')
            term.click_text('Rename', settle=True)
            term.wait_for_text(f'Rename "{unicode_dir}" to:')
            term.type_text('_$2')
            term.press('enter')
            renamed_dir = f'{unicode_dir}_$2'
            term.wait_until(
                lambda s: not s.contains(f'Rename "{unicode_dir}" to:')
                and self._panel_contains(term, 'left', renamed_dir),
                description='unicode directory renamed and listed',
            )
            self.assertFalse((src / unicode_dir).exists())
            self.assertEqual((src / renamed_dir / 'inside.txt').read_text(encoding='utf-8'), 'in')

            # Delete wide-CJK Unicode file and renamed Unicode directory
            self._move_cursor_to(term, cjk_file, panel='left')
            term.press('f8')
            term.wait_for_text(f'Delete "{cjk_file}"?')
            term.press('y')
            term.wait_until(lambda _s: not self._panel_contains(term, 'left', cjk_file))
            self.assertFalse((src / cjk_file).exists())

            self._move_cursor_to(term, renamed_dir, panel='left')
            term.press('f8')
            term.wait_for_text(f'Delete "{renamed_dir}"?')
            term.press('y')
            term.wait_until(lambda _s: not self._panel_contains(term, 'left', renamed_dir))
            self.assertFalse((src / renamed_dir).exists())

            self._quit_cleanly(term)


if __name__ == '__main__':
    unittest.main()
