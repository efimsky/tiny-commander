# Configuration

## Config File Location

Tiny Commander stores its configuration at:

```
~/.config/tnc/config
```

The file is created automatically on first use when you select your preferred editor or pager.

## Config File Format

Simple `key = value` format:

```
editor = nano
pager = less
```

## Available Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `editor` | Program to edit files (F4) | Value of `$VISUAL` or `$EDITOR`, or prompt on first use |
| `pager` | Program to view files (F3) | Value of `$PAGER`, or prompt on first use |

## Environment Variables

Environment variables take precedence over config file settings:

| Variable | Description |
|----------|-------------|
| `$VISUAL` | Preferred text editor (checked before `$EDITOR`) |
| `$EDITOR` | Preferred text editor |
| `$PAGER` | Preferred file viewer |

If you have `$VISUAL` or `$EDITOR` set in your shell, tnc will use it regardless of what's in the config file.

## Supported Editors

tnc resolves editors using the fallback chain: `$VISUAL` → `$EDITOR` → `editor` in config → first detected known editor on `PATH` → `vi`.

- **Terminal editors (auto-detected in priority order):** `micro`, `ne`, `hx` / `helix`, `kak` (`kakoune`), `nvim` (`neovim`), `nano`, `vim`, `emacs -nw`, `vi`
- **macOS GUI editors (listed when available):** `TextEdit` (`open -e`), `subl`, `mate`, `code`
- **Custom commands:** Select `Custom...` in the editor dialog or set `$VISUAL` / `$EDITOR` / `editor` with arguments (for example `emacs -nw` or `code --wait`)

## First Run

On first use, if no editor/pager is configured and no environment variable is set, tnc scans your `PATH` and prompts you to choose from the installed editors (falling back to `vi` if none of the known terminal editors are found), plus a `Custom...` option:

- **Terminal editors:** `micro`, `ne`, `hx` / `helix`, `kak`, `nvim`, `nano`, `vim`, `emacs -nw`, `vi`
- **macOS GUI editors:** `TextEdit`, `subl`, `mate`, `code`
- **Pager options:** `less`, `more`

Your selection is saved to the config file for future sessions.

## Manual Configuration

You can create or edit the config file manually:

```bash
mkdir -p ~/.config/tnc
echo "editor = micro" > ~/.config/tnc/config
echo "pager = less" >> ~/.config/tnc/config
```

## Resetting Configuration

To reset to defaults, delete the config file:

```bash
rm ~/.config/tnc/config
```

Tnc will prompt you again on next launch.
