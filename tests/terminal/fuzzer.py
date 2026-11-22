"""Seeded stateful action-combination fuzzer and shrinker for terminal UI testing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import random
import shutil
import stat
import sys
import tempfile
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
    profile: str = 'balanced'
    action_weights: dict[str, float] | None = None
    extra_keys: tuple[str, ...] = ()
    esc_settle_delay: float = 0.04


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


def screen_integrity_invariant(driver: Any, _step: int, _actions: list[FuzzAction]) -> str | None:
    """Verify VirtualTerminal grid invariants (no orphaned wide continuation cells)."""
    check_fn = getattr(driver.screen, 'check_integrity', None)
    if check_fn is None:
        return None
    errors = check_fn()
    if errors:
        return '; '.join(errors[:5])
    return None


def chrome_layout_invariant(driver: Any, _step: int, _actions: list[FuzzAction]) -> str | None:
    """Verify TUI chrome remains rendered and free of curses errors in alt-screen."""
    scr = driver.screen
    if not scr.in_alt_screen:
        return None
    text = scr.text()
    if 'curses.error' in text:
        return 'curses.error rendered on terminal screen'
    if scr.rows >= 15 and scr.cols >= 50:
        if not text.strip():
            return f'Blank alt-screen rendered at {scr.rows}x{scr.cols}'
        chrome_tokens = ('F10', 'F1', 'Left', 'Right', 'File', '│', '┌', '+', '..')
        if not any(tok in text for tok in chrome_tokens):
            return 'Expected panel/chrome structure missing from alt-screen'
    return screen_integrity_invariant(driver, _step, _actions)


def snapshot_tree(
    root: Path | str,
    *,
    ignore_names: Sequence[str] = (),
) -> tuple[dict[str, tuple[str, int, Any]], int, int]:
    """Capture a symlink-safe deterministic metadata & content snapshot of ``root``."""
    base = Path(root)
    ignored = set(ignore_names)
    entries: dict[str, tuple[str, int, Any]] = {}
    total_bytes = 0

    if not os.path.lexists(base):
        return entries, 0, 0

    def _entry_tuple(path: Path) -> tuple[str, int, Any]:
        st = os.lstat(path)
        mode = stat.S_IMODE(st.st_mode)
        if stat.S_ISLNK(st.st_mode):
            return ('symlink', mode, os.readlink(path))
        if stat.S_ISDIR(st.st_mode):
            return ('dir', mode, None)
        if stat.S_ISREG(st.st_mode):
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                digest = f'unreadable:{exc.errno}'
            return ('file', mode, (st.st_size, digest))
        return ('other', mode, st.st_size)

    root_kind, root_mode, root_meta = _entry_tuple(base)
    if root_kind != 'dir':
        entries['.'] = (root_kind, root_mode, root_meta)
        size = root_meta[0] if root_kind == 'file' and isinstance(root_meta, tuple) else 0
        return entries, 1, size

    for dirpath, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in ignored)
        filenames = sorted(f for f in filenames if f not in ignored)
        cur = Path(dirpath)
        for name in dirnames + filenames:
            full = cur / name
            rel = full.relative_to(base).as_posix()
            kind, mode, meta = _entry_tuple(full)
            entries[rel] = (kind, mode, meta)
            if kind == 'file' and isinstance(meta, tuple):
                total_bytes += meta[0]
            # Stop descending into directories without search/read permission
            if kind == 'dir' and (mode & 0o500) != 0o500 and os.geteuid() != 0:
                if name in dirnames:
                    dirnames.remove(name)

    return entries, len(entries), total_bytes


def _diff_snapshots(
    expected: dict[str, tuple[str, int, Any]],
    actual: dict[str, tuple[str, int, Any]],
    *,
    label: str = 'sandbox',
) -> str | None:
    if expected == actual:
        return None
    missing = sorted(set(expected) - set(actual))
    added = sorted(set(actual) - set(expected))
    changed = sorted(
        k for k in (set(expected) & set(actual))
        if expected[k] != actual[k]
    )
    parts: list[str] = []
    if missing:
        parts.append(f'missing={missing[:5]}')
    if added:
        parts.append(f'added={added[:5]}')
    if changed:
        parts.append(f'changed={changed[:5]}')
    return f'{label} snapshot mismatch ({", ".join(parts)})'


class FilesystemShadowInvariant:
    """Verify sandboxed filesystem integrity and external canary invariance."""

    def __init__(
        self,
        *,
        strict: bool = True,
        root: Path | str | None = None,
        canaries: Sequence[Path | str] = (),
        max_entries: int = 500,
        max_bytes: int = 20 * 1024 * 1024,
        ignore_names: Sequence[str] = (),
    ) -> None:
        self.strict = strict
        self.root = Path(root) if root is not None else None
        self.canaries = [Path(c) for c in canaries]
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.ignore_names = tuple(ignore_names)
        self._fixed_baseline: dict[str, tuple[str, int, Any]] | None = None
        if self.root is not None and self.strict:
            self._fixed_baseline, _, _ = snapshot_tree(
                self.root, ignore_names=self.ignore_names
            )
        self._canary_baselines: list[tuple[Path, dict[str, tuple[str, int, Any]]]] = [
            (c, snapshot_tree(c, ignore_names=self.ignore_names)[0])
            for c in self.canaries
        ]

    def __call__(
        self,
        driver: Any,
        _step: int,
        _actions: list[FuzzAction],
    ) -> str | None:
        # 1. Verify driver-attached canaries (outside sandbox)
        canary_root = getattr(driver, '_canary_root', None)
        canary_snap = getattr(driver, '_canary_initial_snapshot', None)
        if canary_root is not None and canary_snap is not None:
            cur_canary, _, _ = snapshot_tree(canary_root, ignore_names=self.ignore_names)
            err = _diff_snapshots(canary_snap, cur_canary, label='external_canary')
            if err is not None:
                return err

        # 2. Verify statically registered external canaries
        for c_path, c_expected in self._canary_baselines:
            cur_c, _, _ = snapshot_tree(c_path, ignore_names=self.ignore_names)
            err = _diff_snapshots(c_expected, cur_c, label=f'canary:{c_path.name}')
            if err is not None:
                return err

        # 3. Verify sandbox tree itself
        work_root = self.root if self.root is not None else getattr(driver, 'sandbox_root', None)
        if work_root is None:
            return None
        actual, count, total_bytes = snapshot_tree(work_root, ignore_names=self.ignore_names)
        if self.strict:
            baseline = (
                self._fixed_baseline
                if self._fixed_baseline is not None
                else getattr(driver, '_sandbox_initial_snapshot', None)
            )
            if baseline is None:
                self._fixed_baseline = actual
                return None
            return _diff_snapshots(baseline, actual, label='sandbox')

        if count > self.max_entries:
            return f'Sandbox entry count {count} exceeded limit {self.max_entries}'
        if total_bytes > self.max_bytes:
            return f'Sandbox total bytes {total_bytes} exceeded limit {self.max_bytes}'
        return None


class SandboxDriverFactory:
    """Create isolated TerminalDriver runs from a cloned template workspace."""

    def __init__(
        self,
        *,
        template_dir: Path | str | None = None,
        setup_fn: Callable[[Path, Path], dict[str, str | None] | None] | None = None,
        driver_factory: Callable[..., Any] | None = None,
        canaries: dict[str, str] | None = None,
        rows: int = 24,
        cols: int = 80,
        term: str = 'xterm-256color',
        env: dict[str, str | None] | None = None,
        args: Sequence[str] = (),
        ignore_names: Sequence[str] = (),
    ) -> None:
        self.template_dir = Path(template_dir) if template_dir is not None else None
        self.setup_fn = setup_fn
        self.driver_factory = driver_factory
        self.canaries = dict(canaries or {})
        self.rows = rows
        self.cols = cols
        self.term = term
        self.env = dict(env or {})
        self.args = list(args)
        self.ignore_names = tuple(ignore_names)

    def __call__(self) -> Any:
        from tests.terminal.driver import TerminalDriver, _rmtree_force

        run_root = Path(tempfile.mkdtemp(prefix='tnc_sandbox_'))
        try:
            work_dir = run_root / 'work'
            home_dir = run_root / 'home'
            canary_dir = run_root / 'canaries'
            home_dir.mkdir()
            canary_dir.mkdir()

            if self.template_dir is not None:
                shutil.copytree(self.template_dir, work_dir, symlinks=True)
            else:
                work_dir.mkdir()

            for rel_name, content in self.canaries.items():
                target = canary_dir / rel_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8')

            merged_env: dict[str, str | None] = {
                'HOME': str(home_dir),
                'XDG_CONFIG_HOME': str(home_dir / '.config'),
                'EDITOR': None,
                'VISUAL': None,
                'PAGER': None,
            }
            if self.setup_fn is not None:
                extra_env = self.setup_fn(work_dir, home_dir)
                if extra_env:
                    merged_env.update(extra_env)
            merged_env.update(self.env)

            work_snap, _, _ = snapshot_tree(work_dir, ignore_names=self.ignore_names)
            canary_snap, _, _ = snapshot_tree(canary_dir, ignore_names=self.ignore_names)

            spawn_args = [str(a).format(work=work_dir, home=home_dir, canary=canary_dir) for a in self.args]
            if self.driver_factory is not None:
                driver = self.driver_factory(
                    cwd=work_dir,
                    args=spawn_args,
                    rows=self.rows,
                    cols=self.cols,
                    term=self.term,
                    env=merged_env,
                )
            else:
                command = [sys.executable, '-m', 'tnc', *spawn_args] if spawn_args else None
                driver = TerminalDriver(
                    cwd=work_dir,
                    home=home_dir,
                    command=command,
                    rows=self.rows,
                    cols=self.cols,
                    term=self.term,
                    env=merged_env,
                )

            driver.sandbox_root = work_dir
            driver.sandbox_home = home_dir
            driver._sandbox_initial_snapshot = work_snap
            driver._canary_root = canary_dir
            driver._canary_initial_snapshot = canary_snap
            if hasattr(driver, '_temp_dirs'):
                driver._temp_dirs.append(str(run_root))
            return driver
        except Exception:
            _rmtree_force(run_root)
            raise


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
_DESTRUCTIVE_KEYS = ('enter', 'f5', 'f6', 'f7', 'f8', 'shift+f4', 'shift+f6')
_PANEL_SAFE_FKEYS = ('f1', 'f2', 'f9', 'shift+f3', 'ctrl+l')
_MODE_TRIGGERS = (
    '/', '+', '-', '*', 'ctrl+x', 'alt+enter', 'alt+left', 'alt+right',
    'alt+i', 'ctrl+u', 'ctrl+o',
)
_SAFE_TEXT_CHARS = ('a', 'b', 'x', '.', '_', ' ')
_CLICKABLE_LABELS = ('F1', 'F2', 'F9', '[Left]', '[Right]', '[ Cancel ]', '[ OK ]', '..')
_DESTRUCTIVE_MODAL_LABELS = ('[ OK ]', '[ Yes ]', '[ All ]', '[ Skip ]', '[ Cancel ]', '[ No ]')
_SAFE_MODAL_LABELS = ('[ Cancel ]', '[ No ]')
_CTRL_X_FOLLOWUPS = ('c', 'o', 'esc', 'x', 'space')

_FUZZ_PROFILES: dict[str, dict[str, float]] = {
    'balanced': {
        'nav': 2.0,
        'mode': 1.0,
        'text': 1.0,
        'destructive': 1.0,
        'click_pos': 1.0,
        'click_label': 1.0,
        'wheel': 1.0,
        'middle_click': 0.25,
        'double_click': 0.0,
        'resize': 1.0,
        'extra': 0.8,
    },
    'mode_collisions': {
        'nav': 1.5,
        'mode': 3.5,
        'text': 1.2,
        'destructive': 0.0,
        'click_pos': 0.8,
        'click_label': 1.0,
        'wheel': 0.5,
        'middle_click': 0.2,
        'double_click': 0.0,
        'resize': 1.5,
        'extra': 1.5,
    },
    'modal_and_mouse': {
        'nav': 1.2,
        'mode': 1.5,
        'text': 0.5,
        'destructive': 0.8,
        'click_pos': 2.0,
        'click_label': 2.5,
        'wheel': 1.5,
        'middle_click': 1.0,
        'double_click': 1.0,
        'resize': 1.2,
        'extra': 1.0,
    },
    'file_ops_safe': {
        'nav': 2.5,
        'mode': 2.0,
        'text': 1.0,
        'destructive': 0.0,
        'click_pos': 1.0,
        'click_label': 1.2,
        'wheel': 1.0,
        'middle_click': 0.3,
        'double_click': 0.0,
        'resize': 0.8,
        'extra': 1.0,
    },
    'file_ops_destructive': {
        'nav': 1.8,
        'mode': 1.2,
        'text': 0.8,
        'destructive': 2.5,
        'click_pos': 0.8,
        'click_label': 1.8,
        'wheel': 0.6,
        'middle_click': 0.2,
        'double_click': 0.6,
        'resize': 0.8,
        'extra': 1.2,
    },
}


class ActionFuzzer:
    """Seeded random-walk UI fuzzer with delta-debugging sequence shrinking."""

    def __init__(
        self,
        config: FuzzConfig | None = None,
        invariants: Sequence[tuple[str, InvariantFn]] | None = None,
    ) -> None:
        self.config = config or FuzzConfig()
        if self.config.profile not in _FUZZ_PROFILES:
            raise ValueError(f'Unknown fuzz profile: {self.config.profile!r}')
        self.invariants = list(invariants) if invariants is not None else default_invariants()

    def _category_weights(self) -> list[tuple[str, float]]:
        weights = dict(_FUZZ_PROFILES[self.config.profile])
        if self.config.action_weights:
            weights.update(self.config.action_weights)
        if not self.config.allow_destructive:
            weights['destructive'] = 0.0
            weights['double_click'] = 0.0
        if not self.config.allow_mouse:
            for key in ('click_pos', 'click_label', 'wheel', 'middle_click', 'double_click'):
                weights[key] = 0.0
        if not self.config.allow_resize:
            weights['resize'] = 0.0
        if not self.config.extra_keys:
            weights['extra'] = 0.0
        active = [(k, float(w)) for k, w in weights.items() if w > 0.0]
        if not active:
            return [('nav', 1.0)]
        return active

    @staticmethod
    def _weighted_pick(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
        total = sum(w for _, w in weighted)
        target = rng.random() * total
        upto = 0.0
        for name, weight in weighted:
            upto += weight
            if target <= upto:
                return name
        return weighted[-1][0]

    def _mouse_bounds(self, scr: Any) -> tuple[int, int]:
        max_x = max(0, scr.cols - 1)
        max_y = max(0, scr.rows - 1)
        if not getattr(scr, 'sgr_mouse', False):
            max_x = min(max_x, 222)
            max_y = min(max_y, 222)
        return max_x, max_y

    def next_action(
        self,
        rng: random.Random,
        driver: Any,
        history: Sequence[FuzzAction] | None = None,
    ) -> FuzzAction:
        """Choose the next deterministic-from-RNG action appropriate for current screen."""
        scr = driver.screen

        # Dismiss external-command "[Press any key to continue]" prompt smoothly
        if scr.contains('[Press any key to continue]') and rng.random() < 0.7:
            return FuzzAction('key', 'space', 'key(space)')

        # Boost ctrl+x two-key follow-up combinations
        if history and history[-1].kind == 'key' and history[-1].value == 'ctrl+x':
            if rng.random() < 0.65:
                if self.config.allow_resize and rng.random() < 0.2:
                    rows = rng.randint(self.config.min_rows, self.config.max_rows)
                    cols = rng.randint(self.config.min_cols, self.config.max_cols)
                    return FuzzAction('resize', (rows, cols), f'resize({rows},{cols})')
                follow = rng.choice(_CTRL_X_FOLLOWUPS)
                return FuzzAction('key', follow, f'key({follow})')

        # Modal-aware dismissal or interaction
        modal_candidates = _DESTRUCTIVE_MODAL_LABELS if self.config.allow_destructive else _SAFE_MODAL_LABELS
        visible_modal_btns = [lbl for lbl in modal_candidates if scr.find_text(lbl) is not None]
        if visible_modal_btns and rng.random() < 0.4:
            if rng.random() < 0.45:
                return FuzzAction('key', 'esc', 'key(esc)')
            lbl = rng.choice(visible_modal_btns)
            cx, cy = scr.find_text(lbl)
            return FuzzAction('click', (cx + 1, cy, int(MouseButton.LEFT)), f'click({cx + 1},{cy})')

        pick = self._weighted_pick(rng, self._category_weights())
        if pick == 'nav':
            k = rng.choice(_NAV_KEYS + _PANEL_SAFE_FKEYS)
            return FuzzAction('key', k, f'key({k})')
        if pick == 'extra':
            k = rng.choice(self.config.extra_keys)
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
            labels = _CLICKABLE_LABELS + (_DESTRUCTIVE_MODAL_LABELS if self.config.allow_destructive else ())
            visible = [lbl for lbl in labels if scr.find_text(lbl) is not None]
            if visible:
                lbl = rng.choice(visible)
                return FuzzAction('click_text', lbl, f'click_text({lbl!r})')
            pick = 'click_pos'

        max_x, max_y = self._mouse_bounds(scr)
        if pick == 'click_pos':
            x = rng.randint(0, max_x)
            y = rng.randint(0, max_y)
            btn = rng.choice((MouseButton.LEFT, MouseButton.RIGHT))
            if y == scr.rows - 1 and not self.config.allow_destructive:
                y = max(0, scr.rows - 2)
            return FuzzAction('click', (x, y, int(btn)), f'click({x},{y},{int(btn)})')
        if pick == 'middle_click':
            x = rng.randint(0, max_x)
            y = rng.randint(0, max(0, min(max_y, scr.rows - 2)))
            return FuzzAction('click', (x, y, int(MouseButton.MIDDLE)), f'middle_click({x},{y})')
        if pick == 'double_click':
            x = rng.randint(0, max_x)
            y = rng.randint(1, max(1, min(max_y, scr.rows - 2)))
            return FuzzAction('double_click', (x, y, int(MouseButton.LEFT)), f'double_click({x},{y})')
        if pick == 'wheel':
            x = rng.randint(0, max_x)
            y = rng.randint(1, max(1, min(max_y, scr.rows - 3)))
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

    def _settle_and_pump(self, driver: Any, *, action: FuzzAction | None = None) -> None:
        if self.config.step_settle_timeout > 0:
            extra = (
                self.config.esc_settle_delay
                if action is not None and action.kind == 'key' and action.value == 'esc'
                else 0.0
            )
            timeout = max(self.config.step_settle_timeout, extra)
            driver.wait_stable(quiet_period=min(0.02, timeout), timeout=timeout)
        else:
            driver.pump(0.0)

    def _finish_cleanly(self, driver: Any) -> tuple[bool | None, int | None]:
        if not self.config.quit_at_end:
            return None, driver.returncode
        try:
            for _ in range(4):
                if not driver.is_alive():
                    return True, driver.returncode
                if driver.screen.contains('[Press any key to continue]'):
                    driver.press('space')
                else:
                    driver.press('esc')
                self._settle_and_pump(driver, action=FuzzAction('key', 'esc'))
            if driver.is_alive():
                driver.press('f10')
                self._settle_and_pump(driver)
            if driver.is_alive() and (
                driver.screen.find_text('[ Yes ]') is not None
                or driver.screen.contains('(y/n)')
            ):
                driver.press('y')
            rc = driver.wait_exit(timeout=0.6)
            return True, rc
        except (TimeoutError, OSError):
            return not driver.is_alive(), driver.returncode

    def run(self, driver_factory: Callable[[], Any]) -> FuzzReport:
        """Execute a seeded fuzz run; shrink and raise InvariantError on violation."""
        rng = random.Random(self.config.seed)
        executed: list[FuzzAction] = []
        try:
            with driver_factory() as driver:
                driver.wait_ready()
                for step_idx in range(self.config.steps):
                    action = self.next_action(rng, driver, executed)
                    self.apply_action(driver, action)
                    executed.append(action)
                    self._settle_and_pump(driver, action=action)
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
                self._settle_and_pump(driver, action=action)
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
