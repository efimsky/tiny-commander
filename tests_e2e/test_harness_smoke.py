"""Live-PTY smoke tests verifying the real-terminal test harness against tnc."""

from pathlib import Path
import tempfile
import unittest

from tests.terminal import (
    ActionFuzzer,
    ExternalToolStub,
    FuzzConfig,
    TerminalDriver,
)


class TestTerminalHarnessSmoke(unittest.TestCase):
    """End-to-end smoke suite running real `python3 -m tnc` inside a PTY."""

    def test_launch_render_and_quit_restores_terminal(self) -> None:
        with TerminalDriver(rows=24, cols=80) as term:
            term.wait_ready()
            self.assertTrue(term.screen.in_alt_screen)
            self.assertTrue(term.screen.mouse_tracking)
            self.assertIn('[Left]', term.screen.text())
            self.assertIn('Quit', term.screen.row_text(23))

            term.press('f10')
            rc = term.wait_exit()

        self.assertEqual(rc, 0)
        self.assertFalse(term.screen.in_alt_screen)
        self.assertFalse(term.screen.mouse_tracking)
        self.assertTrue(term.screen.cursor_visible)

    def test_keyboard_navigation_mkdir_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as cwd:
            (Path(cwd) / 'alpha.txt').write_text('alpha', encoding='utf-8')
            (Path(cwd) / 'beta.txt').write_text('beta', encoding='utf-8')

            with TerminalDriver(rows=24, cols=80, cwd=cwd) as term:
                term.wait_ready()
                term.press('down')
                term.press('tab')
                term.wait_for_text('[Right]')

                # F7 Create Directory
                term.press('f7')
                term.wait_for_text('Create directory')
                term.type_text('smoke_dir')
                term.press('enter')
                term.wait_for_text('smoke_dir')
                self.assertTrue((Path(cwd) / 'smoke_dir').is_dir())

                # F8 Delete the newly created directory
                term.press('f8')
                term.wait_for_text('Delete Confirmation')
                term.press('y')
                term.wait_until(lambda s: not s.contains('Delete Confirmation') and not s.contains('smoke_dir'))
                self.assertFalse((Path(cwd) / 'smoke_dir').exists())

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

    def test_mouse_panel_switch_help_modal_wheel_and_f10_quit(self) -> None:
        with tempfile.TemporaryDirectory() as cwd:
            (Path(cwd) / 'sub').mkdir()
            for i in range(40):
                (Path(cwd) / f'f{i:02d}.txt').write_text('x', encoding='utf-8')

            with TerminalDriver(rows=40, cols=90, cwd=cwd) as term:
                term.wait_ready()

                # Click right panel area to switch focus
                term.click(65, 5)
                term.wait_for_text('[Right]')

                # Click F1 on function bar to open HelpModal, then dismiss cleanly
                term.click_text('F1')
                term.wait_for_text('Keyboard Shortcuts')
                term.press('esc')
                term.wait_until(lambda s: not s.contains('Keyboard Shortcuts'))

                # Scroll left panel with mouse wheel down/up
                term.click(15, 5)
                term.wait_for_text('[Left]')
                term.scroll('down', 15, 5, steps=3)
                term.wait_stable()
                term.scroll('up', 15, 5, steps=3)
                term.wait_stable()

                # Double-click 'sub' directory entry to enter it
                col, row = term.wait_for_text('sub')
                term.double_click(col, row)
                term.wait_for_text('/sub')

                # Click F10 on function bar to quit cleanly
                term.click_text('F10', row=39)
                self.assertEqual(term.wait_exit(), 0)

    def test_live_terminal_resize_updates_layout(self) -> None:
        with TerminalDriver(rows=24, cols=80) as term:
            term.wait_ready()
            self.assertIsNotNone(term.screen.find_text('F10', row=23))

            term.resize(30, 100)
            term.wait_until(
                lambda s: s.rows == 30 and s.cols == 100 and s.find_text('F10', row=29) is not None,
                description='30x100 resize redraw',
            )

            term.resize(24, 80)
            term.wait_until(
                lambda s: s.rows == 24 and s.cols == 80 and s.find_text('F10', row=23) is not None,
                description='24x80 resize redraw',
            )

            term.press('f10')
            self.assertEqual(term.wait_exit(), 0)

    def test_external_editor_and_pager_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            cwd.mkdir()
            target = cwd / 'notes.txt'
            target.write_text('initial', encoding='utf-8')

            tools = root / 'tools'
            editor = ExternalToolStub.create(tools, 'fake_editor', append_text='\nedited')
            pager = ExternalToolStub.create(tools, 'fake_pager')

            with TerminalDriver(
                rows=24,
                cols=80,
                cwd=cwd,
                env={'VISUAL': None, 'EDITOR': str(editor.path), 'PAGER': str(pager.path)},
            ) as term:
                term.wait_ready()
                # Move off '..' onto 'notes.txt'
                term.press('down')
                term.wait_stable()

                # F3 View -> fake_pager
                term.press('f3')
                term.wait_until(lambda _s: len(pager.calls()) == 1, description='pager invocation')
                term.wait_ready()

                # F4 Edit -> fake_editor (modifies file & returns)
                term.press('f4')
                term.wait_until(lambda _s: len(editor.calls()) == 1, description='editor invocation')
                term.wait_ready()

                term.press('f10')
                self.assertEqual(term.wait_exit(), 0)

            self.assertEqual(len(pager.calls()), 1)
            self.assertTrue(pager.calls()[0]['argv'][-1].endswith('notes.txt'))
            self.assertEqual(len(editor.calls()), 1)
            self.assertTrue(editor.calls()[0]['argv'][-1].endswith('notes.txt'))
            self.assertEqual(target.read_text(encoding='utf-8'), 'initial\nedited')

    def test_seeded_action_fuzzer_live_pty_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / 'work'
            cwd.mkdir()
            (cwd / 'dir_a').mkdir()
            (cwd / 'alpha.txt').write_text('a', encoding='utf-8')
            (cwd / 'beta.md').write_text('b', encoding='utf-8')

            tools = root / 'tools'
            editor = ExternalToolStub.create(tools, 'noop_editor')
            pager = ExternalToolStub.create(tools, 'noop_pager')

            def make_driver() -> TerminalDriver:
                return TerminalDriver(
                    rows=24,
                    cols=80,
                    cwd=cwd,
                    env={'VISUAL': None, 'EDITOR': str(editor.path), 'PAGER': str(pager.path)},
                )

            cfg = FuzzConfig(
                seed=7,
                steps=20,
                allow_destructive=False,
                allow_mouse=True,
                allow_resize=True,
                min_rows=22,
                max_rows=32,
                min_cols=70,
                max_cols=110,
                step_settle_timeout=0.05,
            )
            report = ActionFuzzer(cfg).run(make_driver)
            self.assertEqual(report.steps_executed, 20)
            self.assertTrue(report.clean_exit)
            self.assertEqual(report.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
