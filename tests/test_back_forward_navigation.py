"""Tests for Alt+Left / Alt+Right back/forward directory history navigation (issue #19)."""

import curses
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import create_mock_stdscr
from tnc.app import Action, App
from tnc.panel import Panel


class TestBackForwardStack(unittest.TestCase):
    """Per-panel back/forward stack semantics."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'alpha').mkdir()
        (self.root / 'beta').mkdir()
        (self.root / 'gamma').mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_navigate_back_returns_false_on_empty_stack(self) -> None:
        panel = Panel(str(self.root))
        self.assertFalse(panel.navigate_back())
        self.assertEqual(panel.path, self.root)

    def test_navigate_forward_returns_false_on_empty_stack(self) -> None:
        panel = Panel(str(self.root))
        self.assertFalse(panel.navigate_forward())
        self.assertEqual(panel.path, self.root)

    def test_change_directory_pushes_previous_path_to_back_stack(self) -> None:
        panel = Panel(str(self.root))
        panel.change_directory(self.root / 'alpha')
        self.assertEqual(panel._back_stack, [self.root])

    def test_change_directory_clears_forward_stack_on_manual_nav(self) -> None:
        panel = Panel(str(self.root))
        # Build up some forward history: root → alpha, then back.
        panel.change_directory(self.root / 'alpha')
        panel.navigate_back()
        self.assertEqual(panel._forward_stack, [self.root / 'alpha'])

        # Now make a manual nav to a different dir; forward must be cleared.
        panel.change_directory(self.root / 'beta')
        self.assertEqual(panel._forward_stack, [])

    def test_navigate_back_changes_dir_and_pushes_to_forward(self) -> None:
        panel = Panel(str(self.root))
        panel.change_directory(self.root / 'alpha')
        self.assertTrue(panel.navigate_back())
        self.assertEqual(panel.path, self.root)
        self.assertEqual(panel._forward_stack, [self.root / 'alpha'])
        self.assertEqual(panel._back_stack, [])

    def test_navigate_forward_changes_dir_and_pushes_to_back(self) -> None:
        panel = Panel(str(self.root))
        panel.change_directory(self.root / 'alpha')
        panel.navigate_back()
        # Pre-conditions
        self.assertEqual(panel.path, self.root)
        self.assertEqual(panel._forward_stack, [self.root / 'alpha'])

        self.assertTrue(panel.navigate_forward())
        self.assertEqual(panel.path, self.root / 'alpha')
        self.assertEqual(panel._back_stack, [self.root])
        self.assertEqual(panel._forward_stack, [])

    def test_back_forward_round_trip_preserves_state(self) -> None:
        # A (root) → B (alpha) → C (beta), back → B, back → A, forward → B, forward → C.
        panel = Panel(str(self.root))
        panel.change_directory(self.root / 'alpha')
        panel.change_directory(self.root / 'beta')
        self.assertEqual(panel.path, self.root / 'beta')

        self.assertTrue(panel.navigate_back())
        self.assertEqual(panel.path, self.root / 'alpha')
        self.assertTrue(panel.navigate_back())
        self.assertEqual(panel.path, self.root)

        self.assertTrue(panel.navigate_forward())
        self.assertEqual(panel.path, self.root / 'alpha')
        self.assertTrue(panel.navigate_forward())
        self.assertEqual(panel.path, self.root / 'beta')

        # After replaying all the way forward, forward stack is empty,
        # back stack contains the full prefix.
        self.assertEqual(panel._forward_stack, [])
        self.assertEqual(panel._back_stack, [self.root, self.root / 'alpha'])

    def test_change_directory_no_op_does_not_push(self) -> None:
        panel = Panel(str(self.root))
        panel.change_directory(self.root)  # same path
        self.assertEqual(panel._back_stack, [])

    def test_back_stack_respects_size_limit(self) -> None:
        # Create LIMIT+1 distinct directories and visit each one.
        limit = Panel._BACK_FORWARD_LIMIT
        dirs = []
        for i in range(limit + 1):
            d = self.root / f'd{i:03d}'
            d.mkdir()
            dirs.append(d)

        panel = Panel(str(self.root))
        for d in dirs:
            panel.change_directory(d)
            # Bounce off a sibling so each manual nav pushes a unique entry.
            panel.change_directory(self.root)

        # After 2*(limit+1) pushes the back stack is bounded.
        self.assertLessEqual(len(panel._back_stack), limit)
        # Oldest entries should have been evicted (FIFO from the front).
        self.assertNotIn(dirs[0], panel._back_stack)

    def test_panels_have_independent_stacks(self) -> None:
        panel_a = Panel(str(self.root))
        panel_b = Panel(str(self.root))
        panel_a.change_directory(self.root / 'alpha')
        # Panel B should be untouched.
        self.assertEqual(panel_b._back_stack, [])
        self.assertEqual(panel_b.path, self.root)

    def test_dotdot_navigation_pushes_to_back_stack(self) -> None:
        panel = Panel(str(self.root / 'alpha'))
        # '..' is at index 0
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root)
        # The '..' nav is a manual change, so back stack should contain alpha.
        self.assertEqual(panel._back_stack, [self.root / 'alpha'])

    def test_navigate_back_from_missing_directory_returns_to_existing(self) -> None:
        # Sitting in a directory that gets removed externally: Alt+Left should
        # still take us to the previous (still existing) location.
        panel = Panel(str(self.root))
        panel.change_directory(self.root / 'alpha')
        shutil.rmtree(self.root / 'alpha')

        self.assertTrue(panel.navigate_back())
        self.assertEqual(panel.path, self.root)

    def test_navigate_back_to_missing_target_sets_error_message(self) -> None:
        # Now the inverse: we navigate away from a directory that later gets
        # removed, and Alt+Left tries to return to it. We accept the path
        # (resolve doesn't require existence) but refresh surfaces the error.
        panel = Panel(str(self.root / 'alpha'))
        panel.change_directory(self.root)
        shutil.rmtree(self.root / 'alpha')

        self.assertTrue(panel.navigate_back())
        self.assertEqual(panel.path, self.root / 'alpha')
        self.assertIsNotNone(panel.error_message)

    def test_external_change_resets_back_forward_stacks(self) -> None:
        # An external (e.g. command-line) jump is a fresh start; both stacks
        # should be wiped so Alt+Left/Right don't pop into the prior session.
        panel = Panel(str(self.root))
        panel.change_directory(self.root / 'alpha')
        panel.change_directory(self.root / 'beta')
        # Pre-condition: stacks are populated
        self.assertEqual(len(panel._back_stack), 2)

        panel.change_directory(self.root / 'gamma', external=True)
        self.assertEqual(panel._back_stack, [])
        self.assertEqual(panel._forward_stack, [])


class TestAltLeftRightHandling(unittest.TestCase):
    """App-level Alt+Left / Alt+Right key routing."""

    def setUp(self) -> None:
        self.patches = [
            mock.patch('curses.has_colors', return_value=False),
            mock.patch('curses.curs_set'),
        ]
        for p in self.patches:
            p.start()

        self.tmp = tempfile.TemporaryDirectory()
        self.cwd_patch = mock.patch('os.getcwd', return_value=self.tmp.name)
        self.cwd_patch.start()

        self.app = App(create_mock_stdscr())
        self.app.setup()

    def tearDown(self) -> None:
        self.cwd_patch.stop()
        self.tmp.cleanup()
        for p in self.patches:
            p.stop()

    def _press_alt(self, follow_up_key: int) -> Action:
        """Simulate Alt+<follow_up_key> via the Esc-prefix sequence."""
        self.app.stdscr.nodelay.return_value = None
        self.app.stdscr.getch.return_value = follow_up_key
        return self.app.handle_key(27)  # Escape

    def test_alt_left_calls_active_panel_navigate_back(self) -> None:
        with mock.patch.object(self.app.active_panel, 'navigate_back') as mock_back, \
             mock.patch.object(self.app.command_line, 'set_path') as mock_set_path:
            mock_back.return_value = True
            self._press_alt(curses.KEY_LEFT)
            mock_back.assert_called_once_with()
            mock_set_path.assert_called_once_with(str(self.app.active_panel.path))

    def test_alt_right_calls_active_panel_navigate_forward(self) -> None:
        with mock.patch.object(self.app.active_panel, 'navigate_forward') as mock_fwd, \
             mock.patch.object(self.app.command_line, 'set_path') as mock_set_path:
            mock_fwd.return_value = True
            self._press_alt(curses.KEY_RIGHT)
            mock_fwd.assert_called_once_with()
            mock_set_path.assert_called_once_with(str(self.app.active_panel.path))

    def test_alt_left_returns_action_none(self) -> None:
        action = self._press_alt(curses.KEY_LEFT)
        self.assertEqual(action, Action.NONE)

    def test_alt_right_returns_action_none(self) -> None:
        action = self._press_alt(curses.KEY_RIGHT)
        self.assertEqual(action, Action.NONE)

    def test_plain_left_arrow_still_drives_command_line(self) -> None:
        # Plain Left (no preceding Esc) must continue to drive the command-line cursor
        # and must NOT call navigate_back.
        with mock.patch.object(self.app.active_panel, 'navigate_back') as mock_back, \
             mock.patch.object(self.app.command_line, 'handle_key') as mock_cl_key:
            self.app.handle_key(curses.KEY_LEFT)
            mock_back.assert_not_called()
            mock_cl_key.assert_called_once_with(curses.KEY_LEFT)

    def test_alt_left_on_empty_stack_is_silent(self) -> None:
        # Default app state: no prior navigation, back stack empty.
        original_path = self.app.active_panel.path
        action = self._press_alt(curses.KEY_LEFT)
        self.assertEqual(action, Action.NONE)
        self.assertEqual(self.app.active_panel.path, original_path)
