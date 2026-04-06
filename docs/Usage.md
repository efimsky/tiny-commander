# Usage

## Starting Tiny Commander

```bash
# Start in current directory
tnc

# Or with Python module syntax
python -m tnc
```

Both panels start in the current working directory (`$PWD`).

## Interface Overview



### Components

1. **Menu Bar** — Access with F9. Contains Left, File, Command, Options, Right menus.
2. **Left Panel** — Directory listing. Active when highlighted.
3. **Right Panel** — Directory listing. Switch with Tab.
4. **Command Line** — Run shell commands in the active panel's directory.
5. **Function Key Bar** — Quick reference for common operations.

## Basic Navigation

- Use **arrow keys** to move up and down in the file list
- Press **Enter** to enter a directory or open a file
- Press **Tab** to switch between left and right panels
- The `..` entry takes you to the parent directory

## File Operations

All file operations work on:
- Selected files (if any are selected)
- Current file (if nothing is selected)

The destination for copy/move is always the other panel.

### Copy (F5)

1. Navigate to the file(s) you want to copy
2. Select multiple files with Insert if needed
3. Press F5
4. Confirm the operation

### Move (F6)

Same as copy, but files are moved instead of copied.

### Delete (F8)

1. Navigate to the file(s) you want to delete
2. Press F8
3. Confirm deletion (this cannot be undone)

### Create Directory (F7)

1. Press F7
2. Enter the directory name
3. Press Enter to create

## Command Line

The command line at the bottom executes commands in the active panel's directory.

- Type your command and press Enter
- Press **Alt+Enter** to insert the current filename
- Output is displayed temporarily, then returns to panels

## Quick Search

Press `/` to start searching in the current panel. Type to filter files by name.

## Quitting

Press **F10** to quit Tiny Commander. You can also use **Ctrl+C** (standard terminal interrupt).
