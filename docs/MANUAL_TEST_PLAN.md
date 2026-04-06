# Tiny Commander - Manual Regression Test Plan

## Overview

This document provides a comprehensive manual test plan for Tiny Commander. Execute these tests before each release to ensure all features work correctly.

**Test Environment Requirements:**
- macOS or Linux system
- Python 3.13+
- Native terminal (iTerm2, Terminal.app, gnome-terminal, etc.)
- Optional: ttyd for web-based testing

**Test Data Setup:**
Before testing, create a test directory structure:
```bash
mkdir -p ~/tnc-test/{dir1,dir2,dir3,"dir with spaces","unicode_папка"}
touch ~/tnc-test/{file1.txt,file2.txt,file3.md,"file with spaces.txt"}
echo "test content" > ~/tnc-test/file1.txt
ln -s ~/tnc-test/file1.txt ~/tnc-test/symlink.txt
ln -s /nonexistent ~/tnc-test/broken_symlink.txt
chmod 000 ~/tnc-test/no_access_dir 2>/dev/null || mkdir ~/tnc-test/no_access_dir && chmod 000 ~/tnc-test/no_access_dir
```

---

## Test Categories

1. [Navigation Tests](#1-navigation-tests)
2. [Panel Management Tests](#2-panel-management-tests)
3. [Selection Tests](#3-selection-tests)
4. [File Operations Tests](#4-file-operations-tests)
5. [Search Tests](#5-search-tests)
6. [Menu Tests](#6-menu-tests)
7. [View/Edit Tests](#7-viewedit-tests)
8. [UI/Display Tests](#8-uidisplay-tests)
9. [Error Handling Tests](#9-error-handling-tests)
10. [Edge Cases](#10-edge-cases)

---

## 1. Navigation Tests

### NAV-001: Arrow Key Navigation - Down
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch `python -m tnc` | App starts, cursor on first item |
| 2 | Press Down arrow | Cursor moves to next item |
| 3 | Press Down arrow multiple times | Cursor moves down sequentially |
| 4 | Press Down at last item | Cursor stays at last item (no wrap) |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### NAV-002: Arrow Key Navigation - Up
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate cursor to middle of list | Cursor is not at top |
| 2 | Press Up arrow | Cursor moves up one item |
| 3 | Press Up at first item (`..`) | Cursor stays at first item |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### NAV-003: Enter Directory
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate cursor to a directory | Directory is highlighted |
| 2 | Press Enter | Panel changes to show directory contents |
| 3 | Verify path in header | Header shows new path |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### NAV-004: Navigate Up (Parent Directory)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Enter a subdirectory | Panel shows subdirectory |
| 2 | Navigate cursor to `..` | `..` is highlighted |
| 3 | Press Enter | Panel shows parent directory |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### NAV-005: Home Key
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate cursor to middle of list | Cursor not at top |
| 2 | Press Home | Cursor jumps to first item |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### NAV-006: End Key
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Cursor at top of list | Cursor on first item |
| 2 | Press End | Cursor jumps to last item |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### NAV-007: Page Down
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | In directory with many items | Cursor visible |
| 2 | Press Page Down | Cursor moves down one page |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### NAV-008: Page Up
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to bottom of list | Cursor at bottom |
| 2 | Press Page Up | Cursor moves up one page |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 2. Panel Management Tests

### PNL-001: Switch Panels with Tab
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch app | Left panel is active |
| 2 | Press Tab | Right panel becomes active (visual indicator) |
| 3 | Press Tab again | Left panel becomes active again |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### PNL-002: Independent Panel Navigation
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate left panel to directory A | Left shows A |
| 2 | Press Tab | Right panel active |
| 3 | Navigate right panel to directory B | Right shows B |
| 4 | Press Tab | Left panel still shows A |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### PNL-003: Panel Resize on Terminal Resize
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch app in terminal | Both panels visible |
| 2 | Resize terminal window | Panels adjust to new size |
| 3 | Content remains visible | No truncation or overflow |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 3. Selection Tests

### SEL-001: Toggle Selection with Insert
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to a file | File highlighted |
| 2 | Press Insert | File selected (color change), cursor moves down |
| 3 | Press Insert on same file | File deselected |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SEL-002: Multiple Selection
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press Insert on file1 | file1 selected |
| 2 | Navigate to file2 | Cursor on file2 |
| 3 | Press Insert on file2 | file2 also selected |
| 4 | Both files show selected | Visual confirmation |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SEL-003: Invert Selection (*)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select some files with Insert | Some files selected |
| 2 | Press * | Previously selected files deselected, others selected |
| 3 | Press * again | Original selection restored |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SEL-004: Select by Pattern (+)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press + | Prompt appears: "Select pattern:" |
| 2 | Type `*.txt` and Enter | All .txt files selected |
| 3 | Verify selection | Only .txt files show as selected |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SEL-005: Deselect by Pattern (-)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select all files with * | All files selected |
| 2 | Press - | Prompt appears: "Deselect pattern:" |
| 3 | Type `*.txt` and Enter | .txt files deselected, others remain |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SEL-006: Selection Persists During Navigation
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select some files | Files selected |
| 2 | Navigate up/down | Selection preserved |
| 3 | Switch panels and back | Selection still preserved |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SEL-007: Cannot Select `..`
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate cursor to `..` | `..` highlighted |
| 2 | Press Insert | `..` NOT selected, cursor moves down |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 4. File Operations Tests

### FOP-001: Copy Single File (F5)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Left panel: navigate to file | File highlighted |
| 2 | Right panel: different directory | Panels show different dirs |
| 3 | Press F5 | File copied to right panel |
| 4 | Verify | File exists in both locations |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-002: Copy Multiple Files (F5)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select multiple files with Insert | Multiple files selected |
| 2 | Press F5 | All selected files copied |
| 3 | Verify | All files exist in destination |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-003: Copy Directory (F5)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to a directory | Directory highlighted |
| 2 | Press F5 | Directory and contents copied |
| 3 | Verify | Directory structure preserved |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-004: Move Single File (F6)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to file in left panel | File highlighted |
| 2 | Press F6 | File moved to right panel |
| 3 | Verify | File only in destination, removed from source |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-005: Move Multiple Files (F6)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select multiple files | Files selected |
| 2 | Press F6 | All files moved |
| 3 | Verify | Files only in destination |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-006: Create Directory (F7)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press F7 | Prompt: "Create directory:" |
| 2 | Type `newdir` and Enter | Directory created |
| 3 | Cursor moves to new directory | New dir highlighted |
| 4 | Verify | Directory exists on filesystem |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-007: Create Directory with Spaces (F7)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press F7 | Prompt appears |
| 2 | Type `my new folder` and Enter | Directory created with spaces |
| 3 | Verify | Directory name preserved correctly |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-008: Create Directory - Empty Name Rejected
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press F7 | Prompt appears |
| 2 | Press Enter without typing | Error: name cannot be empty |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-009: Create Directory - Duplicate Name
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press F7 | Prompt appears |
| 2 | Type existing directory name | Error: already exists |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-010: Delete Single File (F8)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to file | File highlighted |
| 2 | Press F8 | Confirmation: Delete "filename"? (y/n) |
| 3 | Press y | File deleted |
| 4 | Verify | File removed from listing and filesystem |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-011: Delete Multiple Files (F8)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select multiple files | Files selected |
| 2 | Press F8 | Confirmation: Delete N files? (y/n) |
| 3 | Press y | All selected files deleted |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-012: Delete Directory (F8)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to directory | Directory highlighted |
| 2 | Press F8, confirm with y | Directory and contents deleted |
| 3 | Verify | Directory removed recursively |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-013: Delete Cancelled
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to file, Press F8 | Confirmation appears |
| 2 | Press n | Delete cancelled |
| 3 | Verify | File still exists |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-014: Cannot Delete `..`
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to `..` | `..` highlighted |
| 2 | Press F8 | No confirmation, nothing deleted |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-015: Copy to Same Directory Fails
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Both panels in same directory | Same path shown |
| 2 | Select file, press F5 | Error: Cannot copy to same directory |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### FOP-016: Overwrite Confirmation
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | File exists in both panels | Same filename in source and dest |
| 2 | Copy file (F5) | Overwrite prompt appears |
| 3 | Options available | Yes, No, Yes All, No All, Cancel |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 5. Search Tests

### SRH-001: Start Quick Search (/)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press / | Search mode activated |
| 2 | Visual indicator | Search prompt/indicator visible |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SRH-002: Search Finds Match
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press / | Search mode |
| 2 | Type partial filename | Cursor jumps to matching file |
| 3 | Type more characters | Cursor updates to best match |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SRH-003: Search - No Match
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press / | Search mode |
| 2 | Type non-existent name | Cursor stays, no crash |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SRH-004: Exit Search with Escape
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start search, type text | In search mode |
| 2 | Press Escape | Search cancelled, cursor returns to original |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SRH-005: Confirm Search with Enter
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start search, find file | Cursor on matched file |
| 2 | Press Enter | Search mode exits, cursor stays on match |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### SRH-006: Search Backspace
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | In search, type `test` | Searching for "test" |
| 2 | Press Backspace | Now searching for "tes" |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 6. Menu Tests

### MNU-001: Toggle Menu (F9)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press F9 | Menu bar appears at top |
| 2 | Press F9 again | Menu bar hidden |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### MNU-002: Menu Navigation
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open menu with F9 | Menu visible |
| 2 | Press Left/Right | Navigate between menu items |
| 3 | Press Down | Open dropdown |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### MNU-003: Menu Escape
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open menu | Menu visible |
| 2 | Press Escape | Menu closes |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 7. View/Edit Tests

### VED-001: View File (F3)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to text file | File highlighted |
| 2 | Press F3 | File opens in pager ($PAGER or less) |
| 3 | Exit pager | Returns to tnc |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-002: Edit File (F4)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to text file | File highlighted |
| 2 | Press F4 | File opens in editor ($EDITOR) |
| 3 | Exit editor | Returns to tnc, panel refreshed |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-003: View/Edit Directory Fails
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to directory | Directory highlighted |
| 2 | Press F3 or F4 | Error: Cannot view/edit directory |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-004: View/Edit `..` Fails
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to `..` | `..` highlighted |
| 2 | Press F3 or F4 | Error or no action |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-005: Alt+Enter Inserts Filename
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to file | File highlighted |
| 2 | Press Alt+Enter | Filename inserted into command line |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-006: Create New File (Shift+F4)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press Shift+F4 | Prompt: "Create file:" |
| 2 | Type `newfile.txt` and Enter | File created, opens in editor |
| 3 | Exit editor | Returns to tnc, cursor on new file |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-007: Create File - Empty Name Rejected
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press Shift+F4 | Prompt appears |
| 2 | Press Enter without typing | No file created (error or no action) |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-008: Create File - Duplicate Name
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press Shift+F4 | Prompt appears |
| 2 | Type existing filename | Error: File already exists |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-009: Calculate Directory Size (Alt+F3)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to a directory | Directory highlighted |
| 2 | Press Alt+F3 | "Calculating..." shown briefly |
| 3 | Size appears | Directory size shown in panel listing and status bar |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-010: Directory Size - Not a Directory
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to a file | File highlighted |
| 2 | Press Alt+F3 | Nothing happens (silent no-op) |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-011: Directory Size - Cache Persists
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Calculate dir size with Alt+F3 | Size displayed |
| 2 | Navigate into another directory | Leave current dir |
| 3 | Return to parent | Cached size still shown |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-012: Cycle Sort Order (Shift+F3)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View panel (default: name sort) | Files sorted by name, header shows "vn" |
| 2 | Press Shift+F3 | Sorted by size (largest first), header shows "vs" |
| 3 | Press Shift+F3 | Sorted by date (newest first), header shows "vd" |
| 4 | Press Shift+F3 | Sorted by extension, header shows "ve" |
| 5 | Press Shift+F3 | Back to name sort, header shows "vn" |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### VED-013: Toggle Reverse Sort (Ctrl+F3 or Menu)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View panel sorted by name | Header shows "vn", files A→Z |
| 2 | Press Ctrl+F3 (or use Left menu "Reverse sort") | Header shows "^n", files Z→A |
| 3 | Press Ctrl+F3 again | Header shows "vn", back to A→Z |
| 4 | Change sort to size (Shift+F3) | Resets to "vs" (normal direction) |
| 5 | Toggle reverse on size sort | Header shows "^s", smallest files first |

**Note:** Ctrl+F3 is terminal-dependent. Use Left/Right menu "Reverse sort" if Ctrl+F3 doesn't work.

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 8. UI/Display Tests

### UID-000: Function Key Bar Display
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch app | Bottom bar shows: F3 View F4 Edit F5 Copy F6 Move F7 Mkdir F8 Delete F10 Quit |
| 2 | Hold Shift (if terminal supports) | Labels change to show Shift actions |
| 3 | Press Shift+F3 | Sort cycles (verifies key works) |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-001: Panel Headers Show Sort Indicator and Path
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch app | Both panels show "vn /path" (sort indicator + path) |
| 2 | Navigate to subdirectory | Header updates to new path, indicator unchanged |
| 3 | Change sort order | Indicator updates (e.g., "vs", "vd", "ve") |
| 4 | Toggle reverse sort | Arrow changes (e.g., "^n" instead of "vn") |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-002: File Sizes Displayed
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View panel with files | File sizes shown (K, M, G suffixes) |
| 2 | Directories show no size | Directories indicated differently |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-003: Directory Indicator
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View panel with dirs and files | Directories have trailing / |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-004: Symlink Display
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View panel with symlinks | Symlinks visually indicated |
| 2 | Broken symlink | Different indicator for broken |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-005: Active Panel Indicator
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Left panel active | Left panel has visual indicator |
| 2 | Press Tab | Right panel has indicator, left loses it |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-006: Selection Color (Yellow)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select file with Insert | Selected file turns **yellow** |
| 2 | Select multiple files | All selected files show yellow |
| 3 | Invert selection (*) | Previously unselected turn yellow, selected return to normal |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-007: Directory Color (Blue)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View panel with directories | Directories appear in **blue** |
| 2 | Directories distinct from files | Files are default color, directories blue |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-008: Cursor Highlight (Cyan Background)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View active panel | Cursor position has **cyan background** |
| 2 | Navigate with arrows | Cyan highlight follows cursor |
| 3 | Switch panels (Tab) | Inactive panel loses cyan highlight |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-009: Cursor on Selected File (Yellow on Cyan)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select a file with Insert | File turns yellow, cursor moves down |
| 2 | Navigate cursor back to selected file | File shows **yellow text on cyan background** |
| 3 | Both states visible | Can distinguish selected + cursor from just cursor |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-010: Menu Bar Colors
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press F9 to open menu | Menu bar appears with **cyan background** |
| 2 | Selected menu item | Selected item highlighted (yellow on cyan) |
| 3 | Open dropdown | Dropdown has distinct colors |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-011: Non-Color Terminal Fallback
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run in terminal without color (TERM=dumb) | App doesn't crash |
| 2 | Selection visible | Selected files use bold text |
| 3 | Cursor visible | Cursor uses reverse video |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### UID-012: Long Filenames
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create file with very long name | File in listing |
| 2 | Name truncated appropriately | No overflow, readable |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 9. Error Handling Tests

### ERR-001: Permission Denied - Read Directory
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to no-access directory | Error displayed |
| 2 | App doesn't crash | Returns to previous state |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### ERR-002: Permission Denied - Create Directory
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to read-only directory | In restricted dir |
| 2 | Press F7, try to create | Error: Permission denied |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### ERR-003: Permission Denied - Delete
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Try to delete protected file | Select file, F8, y |
| 2 | Error shown | Permission denied message |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### ERR-004: Broken Symlink - Display
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View directory with broken symlink | Symlink visible |
| 2 | Different indicator | Visually distinct from valid |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### ERR-005: Broken Symlink - Operations
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select broken symlink | Symlink selected |
| 2 | Delete (F8) | Symlink deleted successfully |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## 10. Edge Cases

### EDG-001: Unicode Filenames
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to unicode dir/file | Name displayed correctly |
| 2 | Operations work | Copy, move, delete succeed |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### EDG-002: Filenames with Spaces
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View files with spaces | Names displayed correctly |
| 2 | Operations work | No issues with spaces |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### EDG-003: Empty Directory
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Enter empty directory | Shows only `..` |
| 2 | Navigation works | Can navigate back out |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### EDG-004: Hidden Files (dotfiles)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | View directory with dotfiles | Dotfiles visible in listing |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### EDG-005: Large Directory (1000+ files)
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to large directory | All files load |
| 2 | Navigation responsive | No significant lag |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### EDG-006: Deep Directory Nesting
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate deep (10+ levels) | Path shown correctly |
| 2 | Operations work | Copy/move handle deep paths |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

### EDG-007: Quit Commands
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Press F10 | App exits cleanly |
| 2 | Press Ctrl+C | App exits cleanly |

**Status:** [ ] Pass  [ ] Fail  [ ] Blocked

---

## Exit Criteria

**Pass:** All tests marked Pass
**Conditional Pass:** All critical tests pass, known issues documented
**Fail:** Any critical test fails without documented workaround

### Critical Tests
- NAV-001 through NAV-004 (basic navigation)
- PNL-001 (panel switching)
- FOP-001, FOP-004, FOP-006, FOP-010 (core operations)
- EDG-007 (quit)

---

## Test Execution Log

| Date | Tester | Version | Result | Notes |
|------|--------|---------|--------|-------|
| | | | | |

---

## Known Issues

Track issues found during testing by referencing GitHub issue numbers.

| Test ID | Issue # | Description |
|---------|---------|-------------|
| NAV-003 | #38 | Enter key fails in ttyd |
| MNU-001 | #40 | F9 menu not appearing |
