# Architecture

## Overview

Tiny Commander is a terminal-based dual-pane file manager built with Python's curses library.

## Design Principles

1. **Zero dependencies** — Only Python standard library
2. **Simple and readable** — Clear module separation, favor clarity
3. **Fail gracefully** — Never crash on filesystem errors
4. **MC-compatible UX** — Familiar keybindings and behavior

## Module Structure

```
tnc/
├── __init__.py         # Package marker, version info
├── __main__.py         # Entry point for `python -m tnc`
├── app.py              # Main application, event loop
├── panel.py            # Panel: directory listing, navigation, selection
├── file_ops.py         # Copy, move, delete, rename operations
├── menu.py             # F9 menu bar system
├── command_line.py     # Bottom command line input
├── config.py           # Config file read/write
├── colors.py           # Color scheme management
├── function_bar.py     # Bottom function key bar (F3-F10)
├── status_bar.py       # Status line display
└── utils.py            # Utility functions (size formatting, etc.)
```

## Component Responsibilities

### app.py — Application Core

- Initialize curses
- Main event loop
- Route key events to appropriate handlers
- Coordinate between panels, menu, command line
- Clean shutdown

### panel.py — Panel

- List directory contents
- Track current position and selection
- Navigate (up, down, enter, parent)
- Sort entries (name, size, date, extension)
- Handle selection (toggle, select all, invert, patterns)

### file_ops.py — File Operations

- Copy files/directories
- Move files/directories
- Delete files/directories
- Rename files/directories
- Create directories
- Handle errors gracefully
- Overwrite confirmation logic

### menu.py — Menu System

- Render dropdown menus
- Handle keyboard navigation
- Dispatch menu actions
- Menu structure definition

### command_line.py — Command Line

- Capture user input
- Execute shell commands
- Insert filename at cursor
- Display command output

### config.py — Configuration

- Find/create config directory
- Read config file
- Write config file
- First-run setup prompts

### colors.py — Color Management

- Initialize curses color pairs
- Define color scheme constants
- Provide color pair lookups

### function_bar.py — Function Key Bar

- Render F3-F10 function key hints
- Display at bottom of screen

### status_bar.py — Status Bar

- Display current file info (size, permissions, date)
- Show selection count
- Show panel indicator (Left/Right)

### utils.py — Utilities

- Human-readable size formatting
- Common helper functions

## Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                        app.py                           │
│            (event loop, curses rendering)               │
└─────────────────────────────────────────────────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   panel.py    │   │   menu.py     │   │command_line.py│
│ (both panels) │   │ (menu bar)    │   │ (shell input) │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │
        ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  file_ops.py  │   │  config.py    │   │  colors.py    │
│(copy/move/del)│   │  (settings)   │   │ (color pairs) │
└───────────────┘   └───────────────┘   └───────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ function_bar  │   │  status_bar   │   │   utils.py    │
│  (F3-F10)     │   │  (file info)  │   │  (helpers)    │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Key Abstractions

### Panel

Represents one side of the dual-pane view. Contains:
- `path`: Current directory
- `entries`: List of files/directories
- `cursor`: Current position
- `selected`: Set of selected entries

### Entry

Represents a file or directory:
- `name`: Filename
- `is_dir`: Boolean
- `size`: File size in bytes
- `mtime`: Modification time

## Error Handling Strategy

All filesystem operations are wrapped in try/except:

```python
try:
    # filesystem operation
except PermissionError:
    # show "Permission denied" message
except FileNotFoundError:
    # show "File not found" message
except OSError as e:
    # show generic error message
```

Never let exceptions propagate to crash the application.

## Terminal Handling

- Initialize with `curses.wrapper()` for clean setup/teardown
- Handle `SIGWINCH` for terminal resize
- Use `curses.curs_set(0)` to hide cursor in panels
- Restore terminal state on exit (even on crash)
