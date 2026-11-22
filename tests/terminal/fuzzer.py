"""Seeded stateful action-combination fuzzer and shrinker for terminal UI testing."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Callable, Sequence

from tests.terminal.input_encoding import MouseButton


@dataclass(frozen=True, slots=True)
class FuzzAction:
    """Single reproducible user action executed against a terminal driver."""

    kind: str
    value: Any = None
    label: str = ''


@dataclass(frozen=True)
class FuzzConfig:
    """Configuration controlling a seeded ActionFuzzer run."""

    seed: int = 0
    steps: int = 100
    allow_destructive: bool = False
    allow_mouse: bool = True
    allow_resize: bool = True
    min_rows: int = 20
    max_rows: int = 40
    min_cols: int = 60
    max_cols: int = 120
    step_settle_timeout: float = 0.04
    max_shrink_attempts: int = 40
    quit_at_end: bool = True


InvariantFn = Callable[[Any, int, list[FuzzAction]], str | None]


def _inv_process_alive(driver: Any, _step: int, _actions: list[FuzzAction]) -> str | None:
    if not driver.is_alive():
        return f'Process exited unexpectedly with code {driver.returncode}'
    return None


def _inv_no_traceback_text(driver: Any, _step: int, _actions: list[FuzzAction]) -> str | None:
    screen_text = driver.screen.text()
    if 'Traceback (most recent call last)' in screen_text:
        return 'Python traceback rendered on terminal screen'
    return None


def _inv_screen_bounds_sane(driver: Any, _step: int, _actions: list[FuzzAction]) -> str | None:
    scr = driver.screen
    if scr.rows < 1 or scr.cols < 1:
        return f'Invalid screen dimensions {scr.rows}x{scr.cols}'
    if not (0 <= scr.cursor_row < scr.rows) or not (0 <= scr.cursor_col < scr.cols):
        return (
            f'Cursor out of bounds: ({scr.cursor_col}, {scr.cursor_row}) '
            f'in {scr.rows}x{scr.cols}'
        )
    return None


def alt_screen_invariant(driver: Any, _step: int, _actions: list[FuzzAction]) -> str | None:
    """Optional invariant enforcing that the process stays inside alternate screen."""
    if not driver.screen.in_alt_screen:
        return 'Expected terminal to remain in alternate screen while running'
    return None


def default_invariants() -> list[tuple[str, InvariantFn]]:
    """Return baseline safety and layout invariants checked after every fuzz step."""
    return [
        ('process_alive', _inv_process_alive),
        ('no_traceback_text', _inv_no_traceback_text),
        ('screen_bounds_sane', _inv_screen_bounds_sane),
    ]


class InvariantError(AssertionError):
    """Raised when a fuzzed sequence violates a terminal invariant."""

    def __init__(
        self,
        *,
        seed: int,
        step_index: int,
        invariant_name: str,
        reason: str,
        actions: list[FuzzAction],
        screenshot: str,
        minimal_actions: list[FuzzAction] | None = None,
    ) -> None:
        self.seed = seed
        self.step_index = step_index
        self.invariant_name = invariant_name
        self.reason = reason
        self.actions = list(actions)
        self.minimal_actions = list(minimal_actions) if minimal_actions is not None else None
        self.screenshot = screenshot
        shown = self.minimal_actions if self.minimal_actions is not None else self.actions
        labels = ', '.join(a.label or f'{a.kind}:{a.value!r}' for a in shown)
        super().__init__(
            f'Invariant {invariant_name!r} failed at step {step_index} '
            f'(seed={seed}): {reason}\n'
            f'Repro ({len(shown)} actions): [{labels}]\n{screenshot}'
        )


@dataclass
class FuzzReport:
    """Summary of a completed ActionFuzzer execution."""

    seed: int
    steps_executed: int
    actions: list[FuzzAction]
    clean_exit: bool | None
    exit_code: int | None
    final_screenshot: str


_NAV_KEYS = (
    'up', 'down', 'left', 'right', 'tab', 'home', 'end', 'pgup', 'pgdn',
    'insert', 'esc', 'backspace',
)
_DESTRUCTIVE_KEYS = ('enter', 'f5', 'f6', 'f7', 'f8', 'shift+f4')
_PANEL_SAFE_FKEYS = ('f1', 'f2', 'f9', 'shift+f3')
_MODE_TRIGGERS = ('/', '+', '-', '*', 'ctrl+x', 'alt+enter', 'alt+left', 'alt+right')
_SAFE_TEXT_CHARS = ('a', 'b', 'x', '.', '_', ' ')
_CLICKABLE_LABELS = ('F1', 'F2', 'F9', '[Left]', '[Right]', '[ Cancel ]', '[ OK ]', '..')


class ActionFuzzer:
    """Generates, executes, shrinks, and replays mixed keyboard/mouse/resize sequences."""

    def __init__(
        self,
        config: FuzzConfig | None = None,
        invariants: list[tuple[str, InvariantFn]] | None = None,
    ) -> None:
        self.config = config or FuzzConfig()
        self.invariants = invariants if invariants is not None else default_invariants()

    def next_action(self, rng: random.Random, driver: Any) -> FuzzAction:
        """Choose the next deterministic-from-RNG action appropriate for current screen."""
        scr = driver.screen
        modal_cancel_pos = scr.find_text('[ Cancel ]') or scr.find_text('[ No ]')
        if modal_cancel_pos is not None and rng.random() < 0.35:
            if rng.random() < 0.5:
                return FuzzAction('key', 'esc', 'key(esc)')
            cx, cy = modal_cancel_pos
            return FuzzAction('click', (cx + 1, cy, int(MouseButton.LEFT)), f'click({cx + 1},{cy})')

        choices: list[str] = ['nav', 'nav', 'mode', 'text']
        if self.config.allow_destructive:
            choices.append('destructive')
        if self.config.allow_mouse:
            choices.extend(['click_pos', 'click_label', 'wheel'])
        if self.config.allow_resize:
            choices.append('resize')

        pick = rng.choice(choices)
        if pick == 'nav':
            k = rng.choice(_NAV_KEYS + _PANEL_SAFE_FKEYS)
            return FuzzAction('key', k, f'key({k})')
        if pick == 'mode':
            seq = rng.choice(_MODE_TRIGGERS)
            return FuzzAction('key', seq, f'key({seq})')
        if pick == 'destructive':
            k = rng.choice(_DESTRUCTIVE_KEYS)
            return FuzzAction('key', k, f'key({k})')
        if pick == 'text':
            ch = rng.choice(_SAFE_TEXT_CHARS)
            return FuzzAction('text', ch, f'text({ch!r})')
        if pick == 'click_label':
            visible = [lbl for lbl in _CLICKABLE_LABELS if scr.find_text(lbl) is not None]
            if visible:
                lbl = rng.choice(visible)
                return FuzzAction('click_text', lbl, f'click_text({lbl!r})')
            pick = 'click_pos'
        if pick == 'click_pos':
            max_x = min(scr.cols - 1, 222)
            max_y = min(scr.rows - 1, 222)
            x = rng.randint(0, max(0, max_x))
            y = rng.randint(0, max(0, max_y))
            btn = rng.choice((MouseButton.LEFT, MouseButton.RIGHT))
            if y == scr.rows - 1 and not self.config.allow_destructive:
                y = max(0, scr.rows - 2)
            return FuzzAction('click', (x, y, int(btn)), f'click({x},{y},{int(btn)})')
        if pick == 'wheel':
            x = rng.randint(0, max(0, min(scr.cols - 1, 222)))
            y = rng.randint(1, max(1, min(scr.rows - 3, 222)))
            direction = rng.choice(('up', 'down'))
            return FuzzAction('wheel', (direction, x, y), f'wheel({direction},{x},{y})')

        rows = rng.randint(self.config.min_rows, self.config.max_rows)
        cols = rng.randint(self.config.min_cols, self.config.max_cols)
        return FuzzAction('resize', (rows, cols), f'resize({rows},{cols})')

    @staticmethod
    def apply_action(driver: Any, action: FuzzAction) -> None:
        """Execute a single FuzzAction on ``driver``."""
        kind = action.kind
        val = action.value
        if kind == 'key':
            driver.press(str(val))
        elif kind == 'text':
            driver.type_text(str(val))
        elif kind == 'click':
            x, y, btn = val
            driver.click(x, y, btn)
        elif kind == 'double_click':
            x, y, btn = val
            driver.double_click(x, y, btn)
        elif kind == 'click_text':
            if driver.screen.find_text(str(val)) is not None:
                driver.click_text(str(val))
        elif kind == 'wheel':
            direction, x, y = val
            driver.scroll(direction, x, y)
        elif kind == 'resize':
            rows, cols = val
            driver.resize(rows, cols)
        else:
            raise ValueError(f'Unknown FuzzAction kind: {kind!r}')

    def _check_invariants(
        self,
        driver: Any,
        step_index: int,
        executed: list[FuzzAction],
    ) -> None:
        for name, fn in self.invariants:
            reason = fn(driver, step_index, executed)
            if reason is not None:
                raise InvariantError(
                    seed=self.config.seed,
                    step_index=step_index,
                    invariant_name=name,
                    reason=reason,
                    actions=executed,
                    screenshot=driver.screen.screenshot(),
                )

    def _settle_and_pump(self, driver: Any) -> None:
        if self.config.step_settle_timeout > 0:
            driver.wait_stable(quiet_period=min(0.02, self.config.step_settle_timeout), timeout=self.config.step_settle_timeout)
        else:
            driver.pump(0.0)

    def _finish_cleanly(self, driver: Any) -> tuple[bool | None, int | None]:
        if not self.config.quit_at_end:
            return None, driver.returncode
        # Escape out of any nested menu/search/modal, then F10 (and 'y' if prompted)
        driver.press('esc')
        driver.press('esc')
        driver.press('f10')
        try:
            rc = driver.wait_exit(timeout=0.6)
            return True, rc
        except TimeoutError:
            driver.press('y')
            try:
                rc = driver.wait_exit(timeout=0.6)
                return True, rc
            except TimeoutError:
                return False, driver.returncode

    def run(self, driver_factory: Callable[[], Any]) -> FuzzReport:
        """Execute a seeded fuzz run; shrink and raise InvariantError on violation."""
        rng = random.Random(self.config.seed)
        executed: list[FuzzAction] = []
        try:
            with driver_factory() as driver:
                driver.wait_ready()
                for step_idx in range(self.config.steps):
                    action = self.next_action(rng, driver)
                    self.apply_action(driver, action)
                    executed.append(action)
                    self._settle_and_pump(driver)
                    self._check_invariants(driver, step_idx, executed)
                clean_exit, exit_code = self._finish_cleanly(driver)
                return FuzzReport(
                    seed=self.config.seed,
                    steps_executed=len(executed),
                    actions=executed,
                    clean_exit=clean_exit,
                    exit_code=exit_code,
                    final_screenshot=driver.screen.screenshot(),
                )
        except InvariantError as err:
            minimal = self.shrink(
                driver_factory,
                err.actions,
                target_invariant=err.invariant_name,
            )
            raise InvariantError(
                seed=err.seed,
                step_index=err.step_index,
                invariant_name=err.invariant_name,
                reason=err.reason,
                actions=err.actions,
                minimal_actions=minimal,
                screenshot=err.screenshot,
            ) from err

    def replay(
        self,
        driver_factory: Callable[[], Any],
        actions: Sequence[FuzzAction],
    ) -> FuzzReport:
        """Deterministically replay a fixed sequence of FuzzActions."""
        executed: list[FuzzAction] = []
        with driver_factory() as driver:
            driver.wait_ready()
            for step_idx, action in enumerate(actions):
                self.apply_action(driver, action)
                executed.append(action)
                self._settle_and_pump(driver)
                self._check_invariants(driver, step_idx, executed)
            clean_exit, exit_code = self._finish_cleanly(driver)
            return FuzzReport(
                seed=self.config.seed,
                steps_executed=len(executed),
                actions=executed,
                clean_exit=clean_exit,
                exit_code=exit_code,
                final_screenshot=driver.screen.screenshot(),
            )

    def shrink(
        self,
        driver_factory: Callable[[], Any],
        actions: Sequence[FuzzAction],
        target_invariant: str | None = None,
    ) -> list[FuzzAction]:
        """Minimize a failing action sequence while preserving the failure."""
        best = list(actions)
        if len(best) <= 1 or self.config.max_shrink_attempts <= 0:
            return best

        attempts = 0

        def still_fails(candidate: list[FuzzAction]) -> bool:
            nonlocal attempts
            if attempts >= self.config.max_shrink_attempts or not candidate:
                return False
            attempts += 1
            try:
                self.replay(driver_factory, candidate)
                return False
            except InvariantError as err:
                if target_invariant is None or err.invariant_name == target_invariant:
                    return True
                return False

        # Coarse chunk removal (binary delta debugging) then single-item pruning
        chunk = max(1, len(best) // 2)
        while chunk >= 1 and attempts < self.config.max_shrink_attempts and len(best) > 1:
            improved = False
            idx = 0
            while idx < len(best) and attempts < self.config.max_shrink_attempts and len(best) > 1:
                candidate = best[:idx] + best[idx + chunk:]
                if still_fails(candidate):
                    best = candidate
                    improved = True
                else:
                    idx += chunk
            if not improved or chunk > len(best) // 2:
                chunk //= 2

        return best
