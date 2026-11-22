"""End-to-end scripted collision tests and seeded real-PTY fuzz campaigns."""

from __future__ import annotations

from pathlib import Path
import stat
import tempfile
import unittest

from tests.terminal import (
    ActionFuzzer,
    ExternalToolStub,
    FilesystemShadowInvariant,
    FuzzAction,
    FuzzConfig,
    SandboxDriverFactory,
    TerminalDriver,
    chrome_layout_invariant,
    default_invariants,
    screen_integrity_invariant,
)


def _make_tools_setup(extra_setup=None):
    """Build a SandboxDriverFactory setup_fn with isolated noop editor/pager stubs."""
    def _setup(work_dir: Path, home_dir: Path) -> dict[str, str | None]:
        tools_dir = home_dir / '.tools'
        editor = ExternalToolStub.create(tools_dir, 'noop_editor')
        pager = ExternalToolStub.create(tools_dir, 'noop_pager')
        if extra_setup is not None:
            extra_setup(work_dir, home_dir)
        return {'EDITOR': str(editor.path), 'PAGER': str(pager.path)}

    return _setup


def _populate_mixed_fixture(work_dir: Path, _home_dir: Path) -> None:
    """Create mixed hidden, CJK, NFD, directory, and canary-symlink entries."""
    (work_dir / '.hidden_cfg').write_text('theme=classic\n', encoding='utf-8')
    (work_dir / '中文文档.txt').write_text('cjk-content\n', encoding='utf-8')
    (work_dir / 'cafe\u0301.txt').write_text('nfd-content\n', encoding='utf-8')
    (work_dir / 'alpha.txt').write_text('alpha\n', encoding='utf-8')
    (work_dir / 'beta.txt').write_text('beta\n', encoding='utf-8')
    (work_dir / 'sub_dir').mkdir()
    (work_dir / 'sub_dir' / 'nested.txt').write_text('nested\n', encoding='utf-8')
    (work_dir / 'link_to_canary').symlink_to('../canaries/secret.txt')


class TestScriptedFeatureCollisionsE2E(unittest.TestCase):
    """High-risk cross-feature state collisions executed in real PTYs."""

    def test_quick_search_collides_with_menu_help_and_resize_unwinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'apricot.txt').write_text('ap', encoding='utf-8')
            (cwd / 'beta.txt').write_text('b', encoding='utf-8')
            (cwd / 'subdir').mkdir()

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                env={'VISUAL': None, 'EDITOR': None, 'PAGER': None},
            ) as term:
                term.wait_ready()

                # 1. Start quick search, open F9 menu on top, Esc exits search first,
                #    live resize keeps menu usable, second Esc closes menu.
                term.press('/')
                term.type_text('ap')
                term.wait_until(
                    lambda s: s.contains('/ap')
                    and 'apricot.txt' in '\n'.join(s.region(2, 1, 18, 38))
                    and 'beta.txt' not in '\n'.join(s.region(2, 1, 18, 38)),
                    description='quick search /ap filter on left panel',
                )

                term.press('f9')
                term.wait_for_text('Sort by name')

                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('/ap')
                    and s.contains('1 of 5')
                    and s.contains('Sort by name'),
                    description='Esc exits search while F9 dropdown stays open',
                )

                term.resize_and_wait(
                    28,
                    96,
                    lambda s: s.find_text('F10', row=27) is not None
                    and s.contains('Sort by name'),
                )

                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Sort by name')
                    and 'beta.txt' in '\n'.join(s.region(2, 1, 22, 46)),
                    description='second Esc closes F9 dropdown',
                )

                # Panels remain interactive after unwinding search + menu + resize
                term.press('tab')
                term.wait_for_text('[Right]')
                term.press('tab')
                term.wait_for_text('[Left]')

                # 2. Start quick search, open F1 help modal, Esc closes help first,
                #    live resize keeps search active, second Esc exits search cleanly.
                term.press('/')
                term.type_text('be')
                term.wait_until(
                    lambda s: s.contains('/be')
                    and 'beta.txt' in '\n'.join(s.region(2, 1, 22, 46))
                    and 'alpha.txt' not in '\n'.join(s.region(2, 1, 22, 46)),
                    description='quick search /be filter on left panel',
                )

                term.press('f1')
                term.wait_for_text('Keyboard Shortcuts')

                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Keyboard Shortcuts') and s.contains('/be'),
                    description='Esc closes F1 modal while search remains active',
                )

                term.resize_and_wait(
                    24,
                    80,
                    lambda s: s.find_text('F10', row=23) is not None
                    and s.contains('/be'),
                )

                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('/be')
                    and 'alpha.txt' in '\n'.join(s.region(2, 1, 18, 38)),
                    description='second Esc exits quick search',
                )

                term.press('tab')
                term.wait_for_text('[Right]')
                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_ctrl_x_prefix_resize_and_cancellation_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            target = cwd / 'target.txt'
            target.write_text('hello\n', encoding='utf-8')
            target.chmod(0o644)

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                env={'VISUAL': None, 'EDITOR': None, 'PAGER': None},
            ) as term:
                term.wait_ready()
                term.press('down')
                term.wait_for_text('target.txt', row=21)

                # Ctrl+X -> live resize -> 'c' opens ChmodDialog -> Esc cancels
                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X] c=chmod', row=21)

                term.resize_and_wait(
                    28,
                    96,
                    lambda s: s.contains('[Ctrl+X] c=chmod o=chown')
                    and s.find_text('F10', row=27) is not None,
                )

                term.press('c')
                term.wait_for_text('Change Permissions')
                self.assertTrue(term.screen.contains('File: target.txt'))

                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Change Permissions')
                    and not s.contains('[Ctrl+X] c=chmod o=chown')
                    and s.contains('[Left]'),
                    description='ChmodDialog dismissed via Esc and Ctrl+X hint cleared',
                )
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

                # Ctrl+X -> F9 consumes chord and clears hint without opening dropdown
                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X] c=chmod o=chown')
                term.press('f9')
                term.wait_until(
                    lambda s: not s.contains('[Ctrl+X] c=chmod o=chown'),
                    description='Ctrl+X hint clears after F9',
                )
                self.assertFalse(term.screen.contains('Sort by name'))

                # Ctrl+X -> Esc cancels chord without setting escape_pending hint
                term.type_text('ls')
                term.wait_for_text('ls', row=26)
                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X] c=chmod o=chown')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('[Ctrl+X] c=chmod o=chown'),
                    description='Ctrl+X hint clears after Esc',
                )
                self.assertFalse(term.screen.contains('[Esc] again to clear'))
                self.assertIsNotNone(term.screen.find_text('ls', row=26))

                # Double-Esc clears command line before exiting
                term.press_esc_settled()
                term.wait_for_text('[Esc] again to clear')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('[Esc] again to clear')
                    and s.find_text('ls', row=26) is None,
                    description='double-Esc clears command line',
                )

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_selection_panel_switch_sort_ctrl_u_f5_cancel_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / 'alpha.txt').write_text('alpha', encoding='utf-8')
            (cwd / 'beta.txt').write_text('beta', encoding='utf-8')
            (cwd / 'gamma.md').write_text('gamma', encoding='utf-8')
            dest = cwd / 'dest'
            dest.mkdir()

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                env={'VISUAL': None, 'EDITOR': None, 'PAGER': None},
            ) as term:
                term.wait_ready()

                # Multi-selection using Insert and '+' select-by-pattern
                term.press('down', 'down')  # '..' -> 'dest' -> 'alpha.txt'
                term.wait_for_text('alpha.txt', row=21)
                term.press('insert')
                term.wait_for_text('| 1 selected')

                term.press('+')
                term.wait_for_text('Select by pattern')
                term.type_text('*.txt')
                term.press('enter')
                term.wait_until(
                    lambda s: not s.contains('Select by pattern')
                    and s.contains('| 2 selected'),
                    description='pattern selection shows 2 selected',
                )

                # Tab panel switch + sort change (Shift+F3 cycle & Ctrl+F3 reverse)
                term.press('tab')
                term.wait_for_text('[Right]')
                term.press('shift+f3')
                term.wait_for_text('vs')
                term.press('ctrl+f3')
                term.wait_for_text('^s')

                # Ctrl+U (unmapped swap shortcut in tnc) must not crash or inject text
                term.press('ctrl+u')
                term.wait_stable()
                self.assertIsNone(chrome_layout_invariant(term, 0, []))

                # Switch back to left panel: selection survives panel switch & sort change
                term.press('tab')
                term.wait_until(
                    lambda s: s.contains('[Left]') and s.contains('| 2 selected'),
                    description='left panel retains 2 selected',
                )

                # F5 Copy modal -> Esc cancels without clearing selection or mutating dest
                term.press('f5')
                term.wait_for_text('Copy 2 files')
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('Copy 2 files')
                    and s.contains('| 2 selected'),
                    description='F5 Esc cancel preserves selection',
                )
                self.assertEqual(list(dest.iterdir()), [])

                # Double-Esc clears command line cleanly while preserving file selection,
                # and '-' deselect-by-pattern clears the file selection cleanly.
                term.type_text('echo sel')
                term.wait_for_text('echo sel', row=22)
                term.press_esc_settled()
                term.wait_for_text('[Esc] aga', row=21)
                term.press_esc_settled()
                term.wait_until(
                    lambda s: not s.contains('[Esc] aga')
                    and s.find_text('echo sel', row=22) is None
                    and s.contains('| 2 selected'),
                    description='double-Esc clears command line without dropping file selection',
                )

                term.press('-')
                term.wait_for_text('Deselect by pattern')
                term.type_text('*')
                term.press('enter')
                term.wait_until(
                    lambda s: not s.contains('Deselect by pattern')
                    and not s.contains('selected'),
                    description='deselect pattern clears multi-selection',
                )

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_modal_live_shrink_and_grow_then_mouse_dismiss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / 'sample.txt').write_text('sample\n', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                env={'VISUAL': None, 'EDITOR': None, 'PAGER': None},
            ) as term:
                term.wait_ready()

                # 1. F1 HelpModal -> shrink (18, 60) -> grow (34, 110) -> click [< OK >]
                term.press('f1')
                term.wait_for_text('Keyboard Shortcuts')
                term.resize_and_wait(
                    18,
                    60,
                    lambda s: s.contains('Keyboard Shortcuts') and s.contains('scroll'),
                )
                term.resize_and_wait(
                    34,
                    110,
                    lambda s: s.contains('Keyboard Shortcuts') and s.contains('[< OK >]'),
                )
                term.click_text('[< OK >]')
                term.wait_until(
                    lambda s: not s.contains('Keyboard Shortcuts')
                    and s.find_text('F10', row=33) is not None,
                    description='HelpModal closed and panels expanded to 34x110',
                )

                # 2. F5 ConfirmModal -> shrink (18, 60) -> grow (34, 110) -> click [  No  ]
                term.press('down')
                term.wait_for_text('sample.txt', row=31)
                term.press('f5')
                term.wait_for_text('Copy "sample.txt"')
                term.resize_and_wait(
                    18,
                    60,
                    lambda s: s.contains('Copy') and s.contains('No'),
                )
                term.resize_and_wait(
                    34,
                    110,
                    lambda s: s.contains('Copy') and s.contains('[  No  ]'),
                )
                term.click_text('[  No  ]')
                term.wait_until(
                    lambda s: not s.contains('Copy "sample.txt"')
                    and s.find_text('F10', row=33) is not None,
                    description='ConfirmModal closed via [  No  ] click',
                )

                # 3. ChmodDialog -> shrink (18, 60) -> grow (34, 110) -> click [Cancel]
                term.press('ctrl+x')
                term.wait_for_text('[Ctrl+X] c=chmod o=chown')
                term.press('c')
                term.wait_for_text('Change Permissions')
                term.resize_and_wait(
                    18,
                    60,
                    lambda s: s.contains('Change Permissions') and s.contains('[Cancel]'),
                )
                term.resize_and_wait(
                    34,
                    110,
                    lambda s: s.contains('Change Permissions') and s.contains('[Cancel]'),
                )
                term.click_text('[Cancel]')
                term.wait_until(
                    lambda s: not s.contains('Change Permissions')
                    and s.find_text('F10', row=33) is not None,
                    description='ChmodDialog closed via [Cancel] click',
                )

                self.assertIsNone(chrome_layout_invariant(term, 0, []))
                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_cmdline_alt_enter_execute_and_return_preserves_panel_and_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / 'hello file.txt').write_text('content\n', encoding='utf-8')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                env={'VISUAL': None, 'EDITOR': None, 'PAGER': None},
            ) as term:
                term.wait_ready()

                term.press('down')
                term.wait_for_text('hello file.txt', row=21)

                term.type_text('echo ')
                term.press('alt+enter')
                term.wait_for_text("echo 'hello file.txt'", row=22)

                term.press('enter')
                term.wait_until(
                    lambda s: not s.in_alt_screen
                    and s.contains('[Press any key to continue]')
                    and s.contains('hello file.txt'),
                    description='command output and Press-any-key prompt',
                )
                term.wait_stable()

                term.press('space')
                term.wait_until(
                    lambda s: s.in_alt_screen
                    and s.contains('[Left]')
                    and s.find_text('F10', row=23) is not None
                    and s.find_text("echo 'hello file.txt'", row=22) is None,
                    description='return from external command to panels',
                )

                self.assertTrue(term.screen.contains('hello file.txt'))
                self.assertIsNone(term.screen.find_text("echo 'hello file.txt'", row=22))
                self.assertIsNotNone(term.screen.find_text('hello file.txt', row=21))
                self.assertEqual(term.screen.cursor_row, 22)

                term.press('tab')
                term.wait_for_text('[Right]')
                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)


class TestFuzzCampaignsE2E(unittest.TestCase):
    """Seeded real-PTY fuzz campaigns using ActionFuzzer and shadow invariants."""

    def _make_mixed_factory(
        self,
        *,
        rows: int = 24,
        cols: int = 80,
        term: str = 'xterm-256color',
        driver_factory=None,
    ) -> SandboxDriverFactory:
        return SandboxDriverFactory(
            setup_fn=_make_tools_setup(_populate_mixed_fixture),
            driver_factory=driver_factory,
            canaries={'secret.txt': 'CANARY_DO_NOT_TOUCH'},
            rows=rows,
            cols=cols,
            term=term,
        )

    def test_mode_collisions_campaign_two_seeds(self) -> None:
        factory = self._make_mixed_factory(rows=24, cols=80)
        invariants = [
            *default_invariants(),
            ('chrome', chrome_layout_invariant),
            ('fs_shadow', FilesystemShadowInvariant(strict=True)),
        ]
        for seed in (101, 202):
            cfg = FuzzConfig(
                seed=seed,
                steps=40,
                profile='mode_collisions',
                allow_destructive=False,
                allow_mouse=True,
                allow_resize=True,
                min_rows=18,
                max_rows=32,
                min_cols=60,
                max_cols=115,
                extra_keys=('ctrl+x', 'alt+enter', 'shift+f3', 'f1', 'f2', 'f9'),
                step_settle_timeout=0.04,
            )
            report = ActionFuzzer(cfg, invariants=invariants).run(factory)
            self.assertEqual(report.steps_executed, 40)
            self.assertTrue(report.clean_exit)
            self.assertEqual(report.exit_code, 0)

    def test_modal_and_mouse_wide_sgr_campaign(self) -> None:
        factory = self._make_mixed_factory(rows=28, cols=230, term='xterm-1006')
        invariants = [
            *default_invariants(),
            ('chrome', chrome_layout_invariant),
            ('fs_shadow', FilesystemShadowInvariant(strict=True)),
        ]
        cfg = FuzzConfig(
            seed=303,
            steps=45,
            profile='modal_and_mouse',
            allow_destructive=False,
            allow_mouse=True,
            allow_resize=False,
            extra_keys=('f1', 'f2', 'f9', 'ctrl+x', 'shift+f3'),
            step_settle_timeout=0.04,
        )
        report = ActionFuzzer(cfg, invariants=invariants).run(factory)
        self.assertEqual(report.steps_executed, 45)
        self.assertTrue(report.clean_exit)
        self.assertEqual(report.exit_code, 0)

        # Also exercise explicit SGR wide-coordinate (>222) clicks, double-click,
        # middle-click, wheel, and modal/menu clicks under strict FS invariance.
        sgr_steps = [
            FuzzAction('click', (225, 5, 0), 'sgr_click_right_panel(225,5)'),
            FuzzAction('wheel', ('down', 225, 5), 'sgr_wheel_down(225,5)'),
            FuzzAction('wheel', ('up', 225, 5), 'sgr_wheel_up(225,5)'),
            FuzzAction('click', (225, 3, 0), 'sgr_select_sub_dir(225,3)'),
            FuzzAction('double_click', (225, 3, 0), 'sgr_double_click(225,3)'),
            FuzzAction('click', (225, 2, 1), 'sgr_middle_click_parent(225,2)'),
            FuzzAction('key', 'f9', 'key(f9)'),
            FuzzAction('key', 'esc', 'key(esc)'),
            FuzzAction('key', 'f1', 'key(f1)'),
            FuzzAction('click_text', '[< OK >]', 'click_text([< OK >])'),
        ]
        sgr_invariants = [
            *invariants,
            ('sgr_active', lambda d, _s, _a: None if d.screen.sgr_mouse else 'Expected SGR mouse active'),
        ]
        rep = ActionFuzzer(
            FuzzConfig(seed=304, steps=len(sgr_steps), step_settle_timeout=0.04),
            invariants=sgr_invariants,
        ).replay(factory, sgr_steps)
        self.assertTrue(rep.clean_exit)
        self.assertEqual(rep.exit_code, 0)

    def test_file_ops_safe_campaign_never_mutates_filesystem(self) -> None:
        factory = self._make_mixed_factory(rows=24, cols=80)
        invariants = [
            *default_invariants(),
            ('chrome', chrome_layout_invariant),
            ('fs_shadow', FilesystemShadowInvariant(strict=True)),
        ]
        cfg = FuzzConfig(
            seed=404,
            steps=45,
            profile='file_ops_safe',
            allow_destructive=False,
            allow_mouse=True,
            allow_resize=True,
            extra_keys=('f1', 'f2', 'f3', 'f9', 'shift+f3', 'ctrl+f3'),
            step_settle_timeout=0.04,
        )
        report = ActionFuzzer(cfg, invariants=invariants).run(factory)
        self.assertEqual(report.steps_executed, 45)
        self.assertTrue(report.clean_exit)
        self.assertEqual(report.exit_code, 0)

    def test_file_ops_destructive_campaign_preserves_external_canary(self) -> None:
        factory = self._make_mixed_factory(rows=24, cols=80)
        invariants = [
            *default_invariants(),
            ('chrome', chrome_layout_invariant),
            ('fs_shadow', FilesystemShadowInvariant(strict=False, max_entries=400)),
        ]
        cfg = FuzzConfig(
            seed=707,
            steps=45,
            profile='file_ops_destructive',
            allow_destructive=True,
            allow_mouse=True,
            allow_resize=True,
            extra_keys=('f5', 'f6', 'f7', 'f8', 'f9', 'insert', '+'),
            step_settle_timeout=0.04,
        )
        report = ActionFuzzer(cfg, invariants=invariants).run(factory)
        self.assertEqual(report.steps_executed, 45)
        self.assertTrue(report.clean_exit)
        self.assertEqual(report.exit_code, 0)

    def test_narrow_and_resize_storm_campaign(self) -> None:
        factory = self._make_mixed_factory(rows=24, cols=80)
        invariants = [
            *default_invariants(),
            ('integrity', screen_integrity_invariant),
            ('chrome', chrome_layout_invariant),
            ('fs_shadow', FilesystemShadowInvariant(strict=True)),
        ]
        cfg = FuzzConfig(
            seed=606,
            steps=45,
            profile='balanced',
            allow_destructive=False,
            allow_mouse=True,
            allow_resize=True,
            min_rows=14,
            max_rows=32,
            min_cols=48,
            max_cols=140,
            action_weights={'resize': 3.0, 'mode': 1.5, 'nav': 1.5},
            extra_keys=('f1', 'f9', 'ctrl+x', 'shift+f3'),
            step_settle_timeout=0.04,
        )
        report = ActionFuzzer(cfg, invariants=invariants).run(factory)
        self.assertEqual(report.steps_executed, 45)
        self.assertTrue(report.clean_exit)
        self.assertEqual(report.exit_code, 0)

    def test_seeded_determinism_cleanup_and_replay(self) -> None:
        created_roots: list[str] = []

        def tracking_driver(
            *,
            cwd: Path,
            args: list[str] | tuple[str, ...] = (),
            rows: int = 24,
            cols: int = 80,
            term: str = 'xterm-256color',
            env: dict[str, str | None] | None = None,
        ) -> TerminalDriver:
            created_roots.append(str(cwd.parent))
            del args
            return TerminalDriver(
                cwd=cwd,
                rows=rows,
                cols=cols,
                term=term,
                env=env,
            )

        factory = self._make_mixed_factory(rows=24, cols=80, driver_factory=tracking_driver)
        invariants = [
            *default_invariants(),
            ('chrome', chrome_layout_invariant),
            ('fs_shadow', FilesystemShadowInvariant(strict=True)),
        ]
        cfg = FuzzConfig(
            seed=42,
            steps=35,
            profile='file_ops_safe',
            allow_destructive=False,
            extra_keys=('f1', 'f2', 'f3', 'f9', 'shift+f3'),
            step_settle_timeout=0.05,
        )

        fuzzer = ActionFuzzer(cfg, invariants=invariants)
        r1 = fuzzer.run(factory)
        r2 = fuzzer.run(factory)
        replayed = fuzzer.replay(factory, r1.actions)

        self.assertEqual(r1.steps_executed, 35)
        self.assertTrue(r1.clean_exit)
        self.assertEqual(r1.exit_code, 0)
        self.assertEqual(r1.actions, r2.actions)
        self.assertTrue(replayed.clean_exit)
        self.assertEqual(replayed.exit_code, 0)
        self.assertEqual(replayed.actions, r1.actions)
        self.assertEqual(len(created_roots), 3)
        for root in created_roots:
            self.assertFalse(Path(root).exists(), f'Sandbox dir leaked: {root}')


if __name__ == '__main__':
    unittest.main()
