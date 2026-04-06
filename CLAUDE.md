# Tiny Commander (tnc)

## Project Overview

Tiny Commander is a lightweight, zero-dependency dual-pane file manager for Linux and macOS. It's inspired by Midnight Commander but prioritizes simplicity and portability over features.

**Key differentiator:** Zero external dependencies — just Python 3 standard library. If you have Python 3.13+, you can run tnc.

## Python Version

**Target: Python 3.13+**

Rationale (as of January 2026):
- **3.13 is in active support** until October 2026, security support until October 2029
- Ships on latest Ubuntu 24.04+, Fedora 41+, macOS (via Homebrew default)
- Modern Python with all the latest improvements
- Users installing a new tool in 2026 should have 3.13 available

Available features we can use:
- Pattern matching (`match`/`case`)
- `list[str]`, `dict[str, int]` type hints
- Walrus operator (`:=`)
- Exception groups and `except*`
- Improved error messages
- Free-threaded mode (experimental, not relevant for us)

This is a modern tool for modern systems. If someone is on an older Python, they can use mc.

## Architecture

- **Target platforms:** Linux, macOS (no Windows support planned)
- **Dependencies:** Python 3.13+ standard library only (`curses`, `os`, `shutil`, `pathlib`, `subprocess`)
- **Structure:** Clean Python package with logical module separation

## Code Principles

1. **Zero dependencies** — Never add imports outside stdlib. This is the core value proposition. Do not add third-party libraries unless there is an extremely compelling justification (there almost never is). If a stdlib solution exists, even if less elegant, use it. If no stdlib solution exists, implement it yourself or redesign to avoid the need.
2. **Simple and readable** — Code should be well-structured, easy to follow, and properly organized into modules. Favor clarity over cleverness.
3. **Fail gracefully** — Permission errors, broken symlinks, and weird filesystems should not crash the app.
4. **Sensible defaults** — Work well out of the box. Minimal configuration needed.
5. **Classic keybindings** — Respect muscle memory from mc where practical.

## Key Bindings (Target)

```
Tab         Switch active panel
Arrow keys  Navigate
Enter       Enter directory / open file with $EDITOR
F3          View file (pager)
F4          Edit file ($EDITOR)
F5          Copy
F6          Move
F7          Make directory
F8          Delete (with confirmation)
F9          Menu bar
F10         Quit
Insert      Toggle select current file
+           Select by pattern
-           Deselect by pattern
*           Invert selection
/           Quick search in current panel
Alt+Enter   Insert filename into command line
Alt+O       Open in Finder (macOS only)
Shift+F3    Cycle sort order (name/size/date/extension)
Ctrl+F3     Toggle reverse sort (terminal-dependent)
Shift+F4    Create new file (opens in $EDITOR after creation)
Alt+F3      Calculate directory size (cached for session)
```

## File Structure

```
tiny-commander/
├── CLAUDE.md             # This file
├── README.md             # User-facing documentation
├── tnc                   # Entry point script (runs tnc.main)
├── tnc/                  # Main package
│   ├── __init__.py
│   ├── __main__.py       # Allows `python -m tnc`
│   ├── app.py            # Main application class, event loop
│   ├── panel.py          # Panel class (directory listing, navigation, selection)
│   ├── file_ops.py       # Copy, move, delete, rename operations
│   ├── menu.py           # Menu bar (F9)
│   ├── command_line.py   # Command line input
│   ├── config.py         # Config file handling
│   ├── colors.py         # Color scheme management
│   ├── function_bar.py   # Bottom function key bar (F3-F10)
│   ├── status_bar.py     # Status line display
│   └── utils.py          # Utility functions (size formatting, etc.)
├── tests/                # Unit tests (TDD) - 500+ tests
│   ├── __init__.py
│   ├── test_panel.py
│   ├── test_file_ops.py
│   ├── test_navigation.py
│   ├── test_menu.py
│   ├── test_command_line.py
│   ├── test_config.py
│   ├── test_colors.py
│   ├── test_key_bindings.py
│   └── ... (40+ test files)
└── docs/                 # Documentation (synced to wiki)
```

## Development Guidelines

### Test-Driven Development (TDD)

**This project follows strict TDD. No exceptions.**

The workflow for every change is:

1. **Red** — Write a failing test first
2. **Green** — Write the minimum code to make it pass
3. **Refactor** — Clean up while keeping tests green

**No code without a test first.** If you're about to write implementation code, stop and write the test first.

### UX Reference

**Midnight Commander (mc) is the reference** for all UX decisions. When in doubt about how something should behave, look at how mc does it. We're not trying to reinvent the wheel — mc has decades of UX refinement. Our goal is a simpler, dependency-free alternative with familiar behavior.

#### Test Structure

```
tests/
├── __init__.py
├── helpers.py            # Test utilities
├── test_app.py           # Application lifecycle tests
├── test_colors.py        # Color scheme tests
├── test_command_exec.py  # Command execution tests
├── test_command_line.py  # Command line input tests
├── test_config.py        # Config parsing tests
├── test_create_file.py   # File creation tests (Shift+F4)
├── test_delete.py        # Delete operation tests (F8)
├── test_dir_size.py      # Directory size calculation tests (Alt+F3)
├── test_display.py       # Display/rendering tests
├── test_dropdown.py      # Menu dropdown tests
├── test_edit.py          # Edit operation tests (F4)
├── test_f5_copy.py       # Copy operation tests (F5)
├── test_file_ops.py      # File operations tests
├── test_filename_insert.py # Alt+Enter tests
├── test_first_run.py     # First-run setup tests
├── test_function_bar.py  # Function key bar tests
├── test_hidden.py        # Hidden files toggle tests
├── test_key_bindings.py  # Key binding tests
├── test_menu.py          # Menu bar tests
├── test_mkdir.py         # Mkdir tests (F7)
├── test_move.py          # Move operation tests (F6)
├── test_navigation_history.py # Navigation history tests
├── test_navigation.py    # Panel navigation tests
├── test_overwrite.py     # Overwrite confirmation tests
├── test_panel_switch.py  # Panel switching tests (Tab)
├── test_panel.py         # Panel class tests
├── test_pattern_selection.py # Pattern select/deselect tests
├── test_prompt.py        # Prompt/dialog tests
├── test_quick_search.py  # Quick search tests (/)
├── test_quit.py          # Quit tests (F10)
├── test_selection.py     # File selection tests
├── test_sort_cycle.py    # Sort cycle tests (Shift+F3)
├── test_sort.py          # Sorting tests
├── test_status_bar.py    # Status bar tests
├── test_ui.py            # UI rendering tests (mocked curses)
├── test_utils.py         # Utility function tests
└── test_view.py          # View operation tests (F3)
```

#### Testing Approach

- **Use only `unittest`** from stdlib — no pytest, no dependencies
- **Mock `curses`** for UI tests — don't require a real terminal
- **Mock filesystem** using `tempfile` and `unittest.mock` for file operation tests
- **Keep tests fast** — no I/O waits, no sleeps
- **Test edge cases explicitly** — permission errors, symlinks, unicode names, empty dirs

#### Preventing Hanging Tests

Tests can hang indefinitely due to curses dialog loops. Follow these rules:

1. **Mock `curses.doupdate`** when tests call `app.draw()`, `do_copy()`, `do_move()`, or any method that triggers screen refresh:
   ```python
   @mock.patch('curses.has_colors', return_value=False)
   @mock.patch('curses.curs_set')
   @mock.patch('curses.doupdate')  # Required for draw()
   def test_something(self, _mock_doupdate, _mock_curs_set, _mock_has_colors):
   ```

2. **Use valid dialog keys** when mocking `getch()`. Dialogs loop until Y/N/Enter/Escape:
   ```python
   # WRONG - 'q' is not a valid dialog key, causes infinite loop
   stdscr.getch.return_value = ord('q')

   # CORRECT - use valid keys
   stdscr.getch.return_value = ord('n')  # or ord('y'), 27 (Escape), ord('\n')
   ```

3. **Use `side_effect` for multi-key sequences**:
   ```python
   # First key ignored, second key exits dialog
   stdscr.getch.side_effect = [ord('x'), ord('n')]
   ```

4. **Run tests with timeout** during development:
   ```bash
   timeout 30 python -m unittest discover -s tests
   ```

#### Running Tests

```bash
# Run all tests
python -m unittest discover -s tests

# Run specific test file
python -m unittest tests.test_panel

# Run with verbose output
python -m unittest discover -s tests -v
```

#### What to Test

| Component | Test Strategy |
|-----------|---------------|
| `Panel` class | Unit test navigation, sorting, refresh logic |
| File operations | Use `tempfile.TemporaryDirectory`, verify results |
| UI rendering | Mock curses `stdscr`, verify `addstr` calls |
| Keybindings | Test handler functions return correct actions |
| Error handling | Force errors with mocks, verify graceful handling |

#### What NOT to Test

- Curses library internals
- Actual terminal rendering (that's manual QA)
- External tools ($EDITOR, $PAGER behavior)

#### Test Naming Convention

```python
def test_<method>_<scenario>_<expected_result>(self):
    """Example: test_navigate_down_at_bottom_stays_at_bottom"""
```

### When modifying code:

- Keep functions small and focused
- Use type hints for function signatures
- Handle all filesystem errors with try/except — never let the app crash
- Test on both Linux and macOS when making terminal/curses changes
- Keep modules focused on a single responsibility

### UI Layout

```
┌ Left   File   Command   Options   Right ──────────────────────────────┐
├─ /home/user/documents ────────────┬─ /home/user/downloads ────────────┤
│ ..                                │ ..                                │
│ ▶ projects/                       │   file1.pdf                       │
│   notes/                          │   file2.zip                       │
│   readme.txt              4.2K    │   image.png                 128K  │
│   data.csv               12.0M    │                                   │
│                                   │                                   │
├───────────────────────────────────┴───────────────────────────────────┤
│ /home/user/documents> _                                               │
├───────────────────────────────────────────────────────────────────────┤
│ F3 View  F4 Edit  F5 Copy  F6 Move  F7 Mkdir  F8 Delete  F10 Quit     │
└───────────────────────────────────────────────────────────────────────┘
```

**Menu Bar (F9)**
- **Left/Right** — Panel-specific options (sort by name/size/date/extension, toggle hidden files)
- **File** — View, Edit, Copy, Move, Delete, Rename, Mkdir
- **Command** — Select all, Deselect all, Invert selection, Select by pattern
- **Options** — Editor/pager settings

**Command Line**
- Always visible at bottom of screen
- Shows current directory as prompt (active panel's path)
- `Alt+Enter` inserts currently selected filename
- Commands execute in the active panel's directory
- Output shown temporarily, then returns to panels

**File Operations**
- **Copy/Move destination** — Always the other panel (no prompt for destination)
- **Delete** — Always requires confirmation
- **Overwrite** — Prompt when destination exists, with "apply to all" option for batch operations
- **Hidden files** — Always shown (toggle available in menu)

### Manual QA Checklist

Automated tests cover logic, but some things need real terminal testing:

1. Navigation in deep directory trees
2. Copy/move between panels
3. Handling of permission denied
4. Symlinks (valid and broken)
5. Files with unicode names
6. Very long filenames
7. Terminal resize during operation
8. Empty directories
9. Colors render correctly on various terminals
10. Keybindings work in both Linux and macOS terminals

### Interactive Testing with ttyd

For interactive testing without a physical terminal, use [ttyd](https://github.com/tsl0922/ttyd) to expose the app via a web browser:

```bash
# Install ttyd (macOS)
brew install ttyd

# Run tiny-commander through ttyd
ttyd -W -p 7681 python -m tnc

# Open in browser
open http://localhost:7681
```

**Testing capabilities:**
- Arrow key navigation
- Tab to switch panels
- Insert key for selection toggle
- * for invert selection
- / for quick search
- Escape to exit search
- F7 mkdir
- F8 delete
- F9 menu (if working)
- F10 to quit

**Known limitations when testing via ttyd + browser:**
- **F5/F6 captured by browser** — F5 triggers page refresh, F6 focuses address bar. Test copy/move in native terminal.
- **Enter key sends `\n`** — Some web terminals send linefeed instead of carriage return, which may cause Enter key issues (see issue #38)
- **Colors may not render** — Selection highlighting may not be visible depending on terminal emulation

**For complete testing**, use a native terminal (iTerm2, Terminal.app, gnome-terminal, etc.) in addition to ttyd.

**Full test plan:** See `docs/MANUAL_TEST_PLAN.md` for comprehensive regression testing checklist.

## Configuration

**Location:** `~/.config/tnc/config`

Created on first use when user selects editor/pager preferences. Simple key=value format, parsed manually (no external dependencies).

```
editor = nano
pager = less
```

**Behavior:**
- If `$EDITOR` is set, use it (environment takes precedence)
- If not set and config exists, use config value
- If neither, prompt user on first use and save to config

## Out of Scope (Intentionally)

- VFS (browsing archives, remote filesystems)
- Built-in editor or viewer (shell out to $EDITOR/$PAGER)
- Themes/colors customization
- Plugins
- Windows support

## Useful References

- [Python curses documentation](https://docs.python.org/3/library/curses.html)
- [Midnight Commander source](https://github.com/MidnightCommander/mc) (for behavior reference)
- [ANSI escape codes](https://en.wikipedia.org/wiki/ANSI_escape_code)
