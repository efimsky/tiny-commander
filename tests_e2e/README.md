# End-to-End Real Terminal Test Suite

`tests/terminal/` provides a zero-dependency PTY harness (`pty`, `termios`, `fcntl`, `select`, `curses.tigetstr`) and a pure-stdlib VT100/ANSI screen emulator (`VirtualTerminal`) for testing Tiny Commander in a real terminal with full keyboard, mouse (X10 and SGR 1006), `SIGWINCH` resize, and external tool (`$EDITOR`/`$PAGER`) support.

For architecture details, invariant definitions, fuzz profiles, and replay instructions, see [docs/E2E_TEST_DESIGN.md](../docs/E2E_TEST_DESIGN.md).

## Test Modules

| Module | Coverage |
|--------|----------|
| `test_harness_smoke.py` | Harness sanity checks: launch/quit terminal restoration, keyboard/mouse/resize basics, `$EDITOR`/`$PAGER` stubs, and live fuzzer smoke |
| `test_e2e_navigation_and_chrome.py` | Dual-pane navigation, directory history (`Alt+Left`/`Alt+Right`), sorting/hidden toggles, quick search (`/`), chrome rendering, and resize |
| `test_e2e_file_ops.py` | Copy (`F5`), move (`F6`), mkdir (`F7`), delete (`F8`), create file (`Shift+F4`), rename, directory size (`Alt+F3`), selection, and overwrite dialogs |
| `test_e2e_permissions_and_tools.py` | `Ctrl+X` chords (`c` chmod, `o` chown), permission/ownership modals, `$PAGER` (`F3`), `$EDITOR` (`F4`), executable files, and shell commands |
| `test_e2e_mouse_and_menus.py` | X10 & SGR mouse clicks, double-click, middle-click, right-click insert, scroll wheel, `F9`/`F2` menu dropdowns, and mouse options |
| `test_e2e_modals_and_config.py` | `F1` help modal, confirm/input/selection/error/summary modals, color themes, config persistence, and malformed-config warning dialogs |
| `test_e2e_combinations_and_fuzz.py` | Scripted cross-feature state collisions and seeded real-PTY `ActionFuzzer` campaigns with layout and `FilesystemShadowInvariant` checks |

## Running Tests

- **Fast mocked unit tests + harness unit tests:**
  ```bash
  python3 -m unittest discover -s tests -v
  ```
- **Full live-PTY E2E suite (isolated from shell `$PAGER`/`$EDITOR`):**
  ```bash
  env -u PAGER -u EDITOR python3 -m unittest discover -s tests_e2e -v
  ```
- **Specific E2E module:**
  ```bash
  env -u PAGER -u EDITOR python3 -m unittest tests_e2e.test_harness_smoke -v
  env -u PAGER -u EDITOR python3 -m unittest tests_e2e.test_e2e_combinations_and_fuzz -v
  ```

## Quick Example: Scripted Keyboard, Mouse & Resize Scenario

```python
from tests.terminal import ExternalToolStub, MouseButton, TerminalDriver

with TerminalDriver(rows=24, cols=80) as term:
    term.wait_ready()

    # Keyboard navigation & modal interaction
    term.press('tab')
    term.wait_for_text('[Right]')

    # Click directly on rendered UI labels
    term.click_text('F1')
    term.wait_for_text('Keyboard Shortcuts')
    term.press_esc_settled()

    # Scroll & double-click by coordinates
    term.scroll('down', 15, 5, steps=3)
    term.double_click(3, 2)

    # Dynamic terminal resize (TIOCSWINSZ + SIGWINCH)
    term.resize_and_wait(30, 100, lambda s: s.find_text('F10', row=29) is not None)

    term.click_text('F10', row=29)
    assert term.wait_exit() == 0
```

## Quick Example: Seeded Combination Fuzzing & Replay

`ActionFuzzer` runs reproducible seeded sequences mixing keyboard shortcuts, modal interactions, mouse clicks/wheels, and `SIGWINCH` resizes, automatically shrinking failing traces to a minimal reproducer via delta debugging:

```python
from tests.terminal import (
    ActionFuzzer,
    FilesystemShadowInvariant,
    FuzzConfig,
    SandboxDriverFactory,
    TerminalDriver,
    chrome_layout_invariant,
    default_invariants,
)

factory = SandboxDriverFactory(
    driver_factory=lambda *, cwd, args, rows, cols, term, env: TerminalDriver(
        cwd=cwd, rows=rows, cols=cols, term=term, env=env
    ),
    canaries={'secret.txt': 'do-not-touch'},
    rows=24,
    cols=80,
)
cfg = FuzzConfig(seed=42, steps=50, profile='mode_collisions', allow_destructive=False)
invariants = [
    *default_invariants(),
    ('chrome', chrome_layout_invariant),
    ('fs', FilesystemShadowInvariant(strict=True)),
]
report = ActionFuzzer(cfg, invariants=invariants).run(factory)
assert report.clean_exit

# Deterministically replay any recorded action trace
replay_report = ActionFuzzer(cfg, invariants=invariants).replay(factory, report.actions)
assert replay_report.clean_exit
```
