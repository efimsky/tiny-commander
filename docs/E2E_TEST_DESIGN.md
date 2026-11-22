# Tiny Commander End-to-End Test Design

Tiny Commander's end-to-end test infrastructure validates the live `python -m tnc` terminal application inside real pseudo-terminals (`pty`) without any external dependencies.

## Architecture Overview

```
tests_e2e/ (live PTY suites & fuzz campaigns)
        │
        ▼
tests/terminal/driver.py (TerminalDriver, ExternalToolStub)
        ├── KeyMap + MouseEncoder (tests/terminal/input_encoding.py)
        ├── pty.openpty() + TIOCSWINSZ / SIGWINCH -> python -m tnc
        └── VirtualTerminal (tests/terminal/virtual_terminal.py)
                ▲
                │
tests/terminal/fuzzer.py (ActionFuzzer, SandboxDriverFactory, invariants)
```

Every component uses Python standard library modules only (`pty`, `termios`, `fcntl`, `select`, `signal`, `subprocess`, `curses.tigetstr`, `codecs`, `unicodedata`, `tempfile`, `hashlib`, `random`).

## Core Harness Components (`tests/terminal/`)

### 1. `VirtualTerminal` (`tests/terminal/virtual_terminal.py`)

Pure-stdlib VT100/ANSI screen emulator that maintains dual screen buffers (`_main` and `_alt` for `?47`/`?1047`/`?1049`), cursor state, SGR attributes (`Style`), and terminal modes (`in_alt_screen`, `cursor_visible`, `mouse_tracking`, `sgr_mouse`, `app_cursor_keys`, `auto_wrap`):

- **Unicode & Box Drawing**: Incremental UTF-8 decoding, DEC Special Graphics (`\x0e`/`\x0f`, ACS box-drawing borders `┌`, `─`, `│`, `└`, `┘`, `┐`), East Asian width-2 CJK characters with continuation cells (`Cell.is_continuation`), and combining marks (`Mn`/`Me`).
- **Grid Integrity**: Handles wide-character overlap clearing and resize clamping (`_ScreenState.resize()`), validated by `check_integrity()`.
- **Query API**:
  - Text & regions: `row_text()`, `lines()`, `text()`, `region()`, `find_all()`, `find_text()`, `contains()`
  - Styles & colors: `style_at()`, `row_styles()`, `region_styles()`, `styles_for_text()`, `find_styled_text()`
  - Diagnostics: `screenshot(with_ruler=True)` renders a coordinate-ruled dump with cursor and mode flags.

### 2. `KeyMap` & `MouseEncoder` (`tests/terminal/input_encoding.py`)

- **`KeyMap(term='xterm-256color')`**: Queries terminfo (`kcuu1`, `kf1`–`kf60`, `smcup`, `rmcup`, `cup`, `kmous`, `colors`, etc.) inside an **isolated subprocess** (`_load_terminfo_profile`) because `curses.setupterm()` is one-shot per process. This allows tests to inspect distinct `TERM` profiles (`xterm-256color`, `xterm-1006`, `vt100`, `dumb`) in one test run without cross-contamination, falling back to `_STATIC_KEY_FALLBACK` when needed.
  - Supports symbolic names (`up`, `down`, `tab`, `shift+tab`, `insert`, `delete`, `pgup`, `pgdn`, `f1`–`f12`, `shift+f*`, `ctrl+f*`, `alt+f*`), `alt+<key>` (preserving case), `ctrl+<a-z>`, aliases (`return`/`cr`, `escape`, `pageup`, `bs`, `btab`), and UTF-8 characters.
- **`MouseEncoder`**: Encodes 0-based `(x, y)` events in both:
  - **X10 protocol** (`\x1b[M...`, `x <= 222`, `y <= 222`)
  - **SGR 1006 protocol** (`\x1b[<btn;x+1;y+1M` / `m`, supporting wide terminals `cols > 222`).

### 3. `TerminalDriver` & `ExternalToolStub` (`tests/terminal/driver.py`)

- **`TerminalDriver`**: Context manager spawning `python -m tnc` inside a fresh `pty.openpty()` with a controlling TTY (`setsid` + `TIOCSCTTY`), deterministic `TERM`/`LANG`/`LC_ALL`/`ESCDELAY=25`, and isolated `cwd`/`home` temp directories.
  - **Synchronization**: `wait_ready()`, `wait_until()`, `wait_for_text()`, `wait_stable()`, `wait_exit()`.
  - **Input**: `press()`, `press_esc_settled()` (waits past `ESCDELAY` so plain `Esc` is not coalesced into an `Alt+` chord), `type_text()`, `click()`, `double_click()`, `click_text()`, `scroll()`, `wait_mouse_settle()`, `resize()`, `resize_and_wait()`, `send_signal()`.
  - **Teardown**: `close()` terminates the child process group (`SIGTERM`, escalating to `SIGKILL` if needed), closes the PTY master fd, and removes owned temp directories.
- **`ExternalToolStub`**: Generates executable Python scripts simulating `$EDITOR` or `$PAGER`, recording JSONL invocation records (`argv`, `cwd`) and optionally appending text so tests never depend on host `vim`/`nano`/`less` binaries.

### 4. `ActionFuzzer`, `SandboxDriverFactory` & Invariants (`tests/terminal/fuzzer.py`)

- **`SandboxDriverFactory`**: Creates per-run isolated sandbox directories (`work/`, `home/`, `canaries/`), copies optional `template_dir` or invokes `setup_fn(work_dir, home_dir)`, writes external canary files, strips ambient `EDITOR`/`VISUAL`/`PAGER` by default, and snapshots both `work/` and `canaries/` via `snapshot_tree()`. Note: when passing `TerminalDriver` via `driver_factory`, adapt the `args=` parameter if the target constructor does not accept `args`.
- **`FilesystemShadowInvariant`**:
  - `strict=True`: Asserts zero mutations anywhere in `work/` or `canaries/` across every fuzz step (used for navigation, search, sort, selection, modal, and read-only campaigns).
  - `strict=False`: Allows bounded mutations in `work/` (`max_entries`, `max_bytes`) while asserting external canaries remain byte-for-byte identical even when symlinks inside `work/` point to `../canaries/secret.txt`.
- **Additional Invariants**:
  - `default_invariants()`: `process_alive`, `no_traceback_text`, `screen_bounds_sane`.
  - `alt_screen_invariant`: Enforces continuous alternate-screen state.
  - `screen_integrity_invariant`: Validates `VirtualTerminal.check_integrity()` (no orphaned wide continuation cells or out-of-bounds cursors).
  - `chrome_layout_invariant`: Ensures zero `curses.error` text, non-blank alt-screen, and rendered panel/chrome markers (`F10`, `F1`, `Left`, `Right`, `│`, `┌`, etc.) at sizes `>= 15x50`, plus screen integrity.

## E2E Test Suites (`tests_e2e/`)

| Suite | Focus |
|-------|-------|
| `tests_e2e/test_harness_smoke.py` | Baseline PTY launch/exit restoration, basic navigation/mkdir/delete, mouse/wheel/double-click, live resize, `$EDITOR`/`$PAGER` stubs, and live fuzzer smoke |
| `tests_e2e/test_e2e_navigation_and_chrome.py` | Dual-pane navigation, directory history (`Alt+Left`/`Alt+Right`), sorting and hidden-file toggles, quick search (`/`), status/command/function bars, and terminal resize |
| `tests_e2e/test_e2e_file_ops.py` | Copy (`F5`), move (`F6`), mkdir (`F7`), delete (`F8`), create file (`Shift+F4`), rename, directory size (`Alt+F3`), multi-selection, and overwrite confirmation flows |
| `tests_e2e/test_e2e_permissions_and_tools.py` | `Ctrl+X` chords (`c` chmod, `o` chown), `ChmodDialog`/`ChownDialog`, `$PAGER` (`F3`), `$EDITOR` (`F4`), executable execution, and command-line shell execution |
| `tests_e2e/test_e2e_mouse_and_menus.py` | X10 & SGR 1006 mouse clicks, double-click, middle-click, right-click filename insert, scroll wheel, `F9`/`F2` menu bar & dropdowns, and mouse swap/toggle |
| `tests_e2e/test_e2e_modals_and_config.py` | `F1` help modal, confirm/input/selection/error/summary dialogs, classic/modern color themes, config persistence, and malformed-config warning dialogs |
| `tests_e2e/test_e2e_combinations_and_fuzz.py` | Scripted cross-feature collisions (`TestScriptedFeatureCollisionsE2E`) and seeded PTY fuzz campaigns (`TestFuzzCampaignsE2E`) |

## Fuzz Profiles, Shrinking & Replay

### Profiles (`_FUZZ_PROFILES`)

| Profile | Emphasis |
|---------|----------|
| `balanced` | General mix of navigation, mode triggers, text, mouse, resize, and optional destructive keys |
| `mode_collisions` | Heavy mode triggers (`/`, `+`, `-`, `*`, `ctrl+x`, `alt+enter`, `alt+left`/`right`, etc.) + resizes + `nav` (`destructive=0.0`) |
| `modal_and_mouse` | High weight on `click_label`, `click_pos`, `wheel`, `middle_click`, `double_click`, and mode/modal triggers |
| `file_ops_safe` | Read-only panel navigation, sorting, quick search, selection, and non-mutating F-keys (`F1`/`F2`/`F3`/`F9`) under strict FS invariance |
| `file_ops_destructive` | High weight on `F5`/`F6`/`F7`/`F8`/`Shift+F4`/`Shift+F6`/`Enter` and modal confirmation buttons (`allow_destructive=True`) |

### Delta-Debugging Shrinking

When any invariant fails during `ActionFuzzer.run()`, `ActionFuzzer.shrink()` automatically runs binary chunk deletion followed by single-action pruning (up to `FuzzConfig.max_shrink_attempts`) while preserving the target invariant failure. The raised `InvariantError` reports:

- `seed`, `step_index`, `invariant_name`, and `reason`
- `actions` (full trace) and `minimal_actions` (shrunk reproducer)
- `screenshot` (terminal grid snapshot at failure)

### Deterministic Reproduction with `ActionFuzzer.replay()`

To reproduce a failing or recorded trace against a fresh PTY:

```python
from tests.terminal import ActionFuzzer, FuzzAction, FuzzConfig, SandboxDriverFactory, TerminalDriver

factory = SandboxDriverFactory(
    driver_factory=lambda *, cwd, args, rows, cols, term, env: TerminalDriver(
        cwd=cwd, rows=rows, cols=cols, term=term, env=env
    ),
    canaries={'secret.txt': 'CANARY_DO_NOT_TOUCH'},
)
cfg = FuzzConfig(seed=42, steps=40, profile='mode_collisions', allow_destructive=False)
fuzzer = ActionFuzzer(cfg)

# Replay a captured FuzzReport trace or manually reconstructed FuzzAction list
report = fuzzer.run(factory)
fuzzer.replay(factory, report.actions)
```

## Running Locally & in CI

Run unit and harness tests (~1s):

```bash
python3 -m unittest discover -s tests -v
```

Run the full E2E PTY suite (unset `PAGER`/`EDITOR` so host shell defaults do not leak into tests):

```bash
env -u PAGER -u EDITOR python3 -m unittest discover -s tests_e2e -v
```

Run combinations and fuzz campaigns specifically, with or without host `EDITOR`/`PAGER` set:

```bash
env -u PAGER -u EDITOR python3 -m unittest tests_e2e.test_e2e_combinations_and_fuzz -v
EDITOR=vim PAGER=cat python3 -m unittest tests_e2e.test_e2e_combinations_and_fuzz -v
```

In GitHub Actions (`.github/workflows/tests.yml`), both unit tests and E2E PTY suites run on `ubuntu-latest` and `macos-latest` across Python `3.13` and `3.14` with a 15-minute job timeout.
