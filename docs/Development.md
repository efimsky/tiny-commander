# Development Guide

## Getting Started

```bash
git clone https://github.com/efimsky/tiny-commander.git
cd tiny-commander
```

## Requirements

- Python 3.13+
- No external dependencies

## Running Tests

```bash
# Run all tests
python -m unittest discover -s tests -v

# Run specific test file
python -m unittest tests.test_panel

# Run specific test
python -m unittest tests.test_panel.TestPanel.test_navigate_down
```

## Test-Driven Development (TDD)

**This project follows strict TDD. No exceptions.**

### The Workflow

1. **Red** — Write a failing test first
2. **Green** — Write the minimum code to make it pass
3. **Refactor** — Clean up while keeping tests green

### Rules

- No implementation code without a test first
- If you're about to write code, stop and write the test first
- Tests should be fast (no I/O waits, no sleeps)
- Mock external dependencies (curses, filesystem when appropriate)

### Test Naming Convention

```python
def test_<method>_<scenario>_<expected_result>(self):
    """Example: test_navigate_down_at_bottom_stays_at_bottom"""
```

## Code Style

- Use type hints for function signatures
- Keep functions small and focused
- Handle all filesystem errors gracefully (try/except)
- Prefer clarity over cleverness

## Zero Dependencies Policy

**Never add imports outside the Python standard library.**

This is the core value proposition of the project. If a stdlib solution exists, even if less elegant, use it. If no stdlib solution exists, implement it yourself or redesign to avoid the need.

## UX Reference

When in doubt about how something should behave, check Midnight Commander (mc). We're not reinventing the wheel — mc has decades of UX refinement.

## Project Structure

```
tiny-commander/
├── tnc/                  # Main package
│   ├── __init__.py
│   ├── __main__.py       # Entry point for python -m tnc
│   ├── app.py            # Main application class, event loop
│   ├── panel.py          # Panel class (navigation, selection)
│   ├── file_ops.py       # Copy, move, delete, rename operations
│   ├── menu.py           # Menu bar (F9)
│   ├── command_line.py   # Command line input
│   ├── config.py         # Configuration handling
│   ├── colors.py         # Color scheme management
│   ├── function_bar.py   # Bottom function key bar (F3-F10)
│   ├── status_bar.py     # Status line display
│   └── utils.py          # Utility functions
├── tests/                # Unit tests (500+ tests)
├── docs/                 # Documentation (synced to wiki)
└── .github/workflows/    # CI/CD
```

## What to Test

| Component | Test Strategy |
|-----------|---------------|
| Panel class | Unit test navigation, sorting, refresh logic |
| File operations | Use `tempfile.TemporaryDirectory`, verify results |
| UI rendering | Mock curses `stdscr`, verify `addstr` calls |
| Keybindings | Test handler functions return correct actions |
| Config | Test read/write/create with temp files |
| Error handling | Force errors with mocks, verify graceful handling |

## What NOT to Test

- Curses library internals
- Actual terminal rendering (that's manual QA)
- External tools ($EDITOR, $PAGER behavior)

## Manual QA Checklist

Some things need real terminal testing:

1. Navigation in deep directory trees
2. Copy/move between panels
3. Handling of permission denied
4. Symlinks (valid and broken)
5. Files with unicode names
6. Very long filenames
7. Terminal resize during operation
8. Empty directories
9. Keybindings work in both Linux and macOS terminals
