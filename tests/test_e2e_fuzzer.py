"""Unit tests for the seeded stateful ActionFuzzer engine using an in-memory fake driver."""

import unittest

from tests.terminal.fuzzer import (
    ActionFuzzer,
    FuzzAction,
    FuzzConfig,
    InvariantError,
    default_invariants,
)
from tests.terminal.virtual_terminal import VirtualTerminal


class _FakeDriver:
    """In-memory stand-in for TerminalDriver to test fuzzing & shrinking cleanly."""

    def __init__(self, *, rows: int = 24, cols: int = 80, bug_mode: str | None = None) -> None:
        self.screen = VirtualTerminal(rows=rows, cols=cols)
        self.screen.feed('\x1b[?1049h[Left] /tmp  F1Help F9Menu F10Quit')
        self._alive = True
        self.returncode: int | None = None
        self.bug_mode = bug_mode
        self.saw_f9 = False
        self.saw_resize = False
        self.history: list[FuzzAction] = []

    def is_alive(self) -> bool:
        return self._alive

    def pump(self, timeout: float = 0.0) -> bytes:
        return b''

    def wait_ready(self, timeout: float = 1.0) -> None:
        return None

    def wait_stable(self, quiet_period: float = 0.01, timeout: float = 0.1) -> None:
        return None

    def press(self, *keys: str, delay: float = 0.0) -> None:
        for k in keys:
            if k == 'f9':
                self.saw_f9 = True
            if k == 'f10' and self.bug_mode != 'ignore_quit':
                self._alive = False
                self.returncode = 0
                self.screen.feed('\x1b[?1049l')

    def type_text(self, text: str) -> None:
        self.screen.feed(text)

    def click(self, x: int, y: int, button: int = 0) -> None:
        if self.bug_mode == 'combo_crash' and self.saw_f9 and self.saw_resize:
            self._alive = False
            self.returncode = 1
            self.screen.feed('\r\nTraceback (most recent call last):\r\nBoom')

    def double_click(self, x: int, y: int, button: int = 0) -> None:
        pass

    def click_text(self, needle: str, **kwargs) -> tuple[int, int]:
        pos = self.screen.find_text(needle)
        if pos is None:
            return (0, 0)
        self.click(pos[0], pos[1])
        return pos

    def scroll(self, direction: str, x: int, y: int, steps: int = 1) -> None:
        pass

    def resize(self, rows: int, cols: int) -> None:
        self.saw_resize = True
        self.screen.resize(rows, cols)

    def wait_exit(self, timeout: float = 1.0) -> int:
        return 0 if self.returncode is None else self.returncode

    def close(self) -> None:
        pass

    def __enter__(self) -> '_FakeDriver':
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


class TestActionFuzzer(unittest.TestCase):
    """Test deterministic fuzzing, invariant checks, shrinking, and replay."""

    def test_same_seed_produces_identical_action_trace(self) -> None:
        cfg = FuzzConfig(seed=123, steps=25, step_settle_timeout=0.0, quit_at_end=False)
        r1 = ActionFuzzer(cfg).run(lambda: _FakeDriver())
        r2 = ActionFuzzer(cfg).run(lambda: _FakeDriver())

        self.assertEqual(r1.seed, 123)
        self.assertEqual(r1.steps_executed, 25)
        self.assertEqual(r1.actions, r2.actions)
        self.assertEqual(len(r1.actions), 25)

    def test_detects_bug_shrinks_and_replays(self) -> None:
        def trigger_driver_factory() -> _FakeDriver:
            return _FakeDriver(bug_mode='combo_crash')

        # Build a sequence with lots of noise around a minimal 3-step bug (f9 + resize + click)
        noise = [FuzzAction('key', 'down', 'down') for _ in range(12)]
        actions = (
            noise[:6]
            + [FuzzAction('key', 'f9', 'f9')]
            + noise[6:10]
            + [FuzzAction('resize', (30, 90), 'resize(30,90)')]
            + noise[10:]
            + [FuzzAction('click', (5, 5, 0), 'click(5,5)')]
        )

        fuzzer = ActionFuzzer(
            FuzzConfig(seed=7, steps=len(actions), max_shrink_attempts=50, quit_at_end=False),
            invariants=default_invariants(),
        )
        minimal = fuzzer.shrink(trigger_driver_factory, actions, target_invariant='process_alive')
        self.assertLessEqual(len(minimal), 3)
        kinds = [a.kind for a in minimal]
        self.assertIn('resize', kinds)
        self.assertIn('click', kinds)

        # Replay of the minimal sequence must reproduce the InvariantError
        with self.assertRaises(InvariantError) as ctx:
            fuzzer.replay(trigger_driver_factory, minimal)
        self.assertEqual(ctx.exception.invariant_name, 'process_alive')
        self.assertIn('Traceback', ctx.exception.screenshot + ctx.exception.reason + '\n'.join(repr(a) for a in minimal))

    def test_run_raises_invariant_error_with_minimal_actions(self) -> None:
        class _FailAtFive(_FakeDriver):
            def press(self, *keys: str, delay: float = 0.0) -> None:
                super().press(*keys, delay=delay)
                if len(self.history) >= 4:
                    self._alive = False
                    self.returncode = 2

        orig_apply = ActionFuzzer.apply_action

        def _factory() -> _FailAtFive:
            d = _FailAtFive()
            return d

        # Use an explicit stateful invariant that triggers after 5 actions on the driver
        count = {'n': 0}

        def custom_inv(driver, step_idx, executed):
            if len(executed) >= 6:
                return f'triggered at {len(executed)}'
            return None

        cfg = FuzzConfig(seed=99, steps=15, step_settle_timeout=0.0, max_shrink_attempts=30, quit_at_end=False)
        fuzzer = ActionFuzzer(cfg, invariants=[('six_actions', custom_inv)])
        with self.assertRaises(InvariantError) as ctx:
            fuzzer.run(_factory)
        err = ctx.exception
        self.assertEqual(err.seed, 99)
        self.assertEqual(err.step_index, 5)
        self.assertEqual(err.invariant_name, 'six_actions')
        self.assertEqual(len(err.actions), 6)
        self.assertIsNotNone(err.minimal_actions)
        self.assertEqual(len(err.minimal_actions), 6)

    def test_traceback_invariant_catches_screen_traceback(self) -> None:
        class _TraceDriver(_FakeDriver):
            def type_text(self, text: str) -> None:
                self.screen.feed('Traceback (most recent call last):\r\nZeroDivisionError')

        fuzzer = ActionFuzzer(FuzzConfig(seed=1, steps=2, step_settle_timeout=0.0, quit_at_end=False))
        with self.assertRaises(InvariantError) as ctx:
            fuzzer.replay(lambda: _TraceDriver(), [FuzzAction('text', 'abc', 'type(abc)')])
        self.assertEqual(ctx.exception.invariant_name, 'no_traceback_text')


if __name__ == '__main__':
    unittest.main()
