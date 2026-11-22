# End-to-End Real Terminal Test Harness

`tests/terminal/` provides a zero-dependency PTY harness (`pty`, `termios`, `fcntl`, `select`, `curses.tigetstr`) and a pure-stdlib VT100/ANSI screen emulator (`VirtualTerminal`) for testing Tiny Commander in a real terminal with full keyboard, mouse, resize, and external tool (`$EDITOR`/`$PAGER`) support.

## Running Tests

- **Fast mocked unit tests + harness unit tests (~1s):**
  ```bash
  python3 -m unittest discover -s tests
  ```
- **Live-PTY E2E tests:**
  ```bash
  python3 -m unittest discover -s tests_e2e -v
  ```
- **Specific E2E scenario:**
  ```bash
  python3 -m unittest tests_e2e.test_harness_smoke -v
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
    term.press('esc')

    # Scroll & double-click by coordinates
    term.scroll('down', 15, 5, steps=3)
    term.double_click(3, 2)

    # Dynamic terminal resize (TIOCSWINSZ + SIGWINCH)
    term.resize(30, 100)
    term.wait_until(lambda s: s.find_text('F10', row=29) is not None)

    term.click_text('F10', row=29)
    assert term.wait_exit() == 0
```

## Quick Example: Seeded Combination Fuzzing

`ActionFuzzer` runs reproducible seeded sequences mixing keyboard shortcuts, modal interactions, mouse clicks/wheels, and `SIGWINCH` resizes, automatically shrinking failing traces to a minimal reproducer:

```python
from tests.terminal import ActionFuzzer, FuzzConfig, TerminalDriver

cfg = FuzzConfig(seed=42, steps=100, allow_destructive=False)
report = ActionFuzzer(cfg).run(lambda: TerminalDriver(rows=24, cols=80))
assert report.clean_exit
```
