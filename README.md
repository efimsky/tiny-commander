# Tiny Commander (tnc)

A lightweight dual-pane file manager for Linux and macOS, inspired by Midnight Commander and FAR Manager.

**Zero dependencies.** Just Python 3.13+ standard library.



## Why tnc?

- **No dependencies** — If you have Python 3.13+, you're ready to go
- **Familiar** — MC-style keybindings and workflow
- **Simple** — Does one thing well: manage files with two panels

## Philosophy

tnc is not trying to be everything. Midnight Commander is a fantastic, feature-rich file manager — but that richness comes with complexity and dependencies.

tnc deliberately stays small:

- **No VFS** — We won't browse archives or remote filesystems
- **No built-in editor** — Your `$EDITOR` is better than anything we'd write
- **No plugins** — Complexity we don't need
- **No Windows** — Focus on doing Unix well

If you need those features, use mc. It's great. But if you want a simple, portable file manager that works anywhere Python runs, tnc is for you.

## Installation

```bash
# Clone the repository
git clone https://github.com/efimsky/tiny-commander.git
cd tiny-commander

# Run directly
python -m tnc

# Or make executable and add to PATH
chmod +x tnc
./tnc
```

## Requirements

- Python 3.13 or later
- Linux or macOS (no Windows support)

## Usage

### Key Bindings

| Key | Action |
|-----|--------|
| `Tab` | Switch active panel |
| `↑` `↓` | Navigate files |
| `Enter` | Enter directory / open file |
| `F3` | View file (pager) |
| `F4` | Edit file |
| `F5` | Copy to other panel |
| `F6` | Move to other panel |
| `F7` | Create directory |
| `F8` | Delete (with confirmation) |
| `F9` | Menu bar |
| `F10` | Quit |
| `Insert` | Toggle selection |
| `+` | Select by pattern |
| `-` | Deselect by pattern |
| `*` | Invert selection |
| `/` | Quick search |
| `Alt+Enter` | Insert filename into command line |
| `Shift+F3` | Cycle sort order (name/size/date/extension) |
| `Ctrl+F3` | Toggle reverse sort (terminal-dependent) |
| `Shift+F4` | Create new file (opens in editor) |
| `Alt+F3` | Calculate directory size (cached) |

### Command Line

The command line at the bottom runs commands in the active panel's directory:

```
/home/user/documents> ls -la
```

Press `Alt+Enter` to insert the currently selected filename.

### Configuration

On first use, tnc creates `~/.config/tnc/config` to store your preferences:

```
editor = nano
pager = less
```

Environment variables (`$EDITOR`, `$PAGER`) take precedence over config file settings.

## Development

### Requirements

- Python 3.13+
- No external dependencies (stdlib only)

### Running Tests

```bash
python -m unittest discover -s tests -v
```

### TDD Workflow

This project follows strict Test-Driven Development:

1. **Red** — Write a failing test
2. **Green** — Write minimum code to pass
3. **Refactor** — Clean up, keeping tests green

No implementation code without a test first.

### Project Structure

```
tiny-commander/
├── tnc/                  # Main package
│   ├── __init__.py
│   ├── __main__.py       # Entry point for python -m tnc
│   ├── app.py            # Main application, event loop
│   ├── panel.py          # Panel class (navigation, selection)
│   ├── file_ops.py       # Copy, move, delete, rename operations
│   ├── menu.py           # Menu bar (F9)
│   ├── command_line.py   # Command line input
│   ├── config.py         # Configuration handling
│   ├── colors.py         # Color scheme management
│   ├── function_bar.py   # Bottom function key bar (F3-F10)
│   ├── status_bar.py     # Status line display
│   └── utils.py          # Utility functions
└── tests/                # Unit tests (500+ tests)
```

### Contributing

1. Read `CLAUDE.md` for project guidelines
2. Write tests first, then implementation
3. Keep it simple — no external dependencies
