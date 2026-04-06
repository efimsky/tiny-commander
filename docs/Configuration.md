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
| `editor` | Program to edit files (F4) | Value of `$EDITOR`, or prompt on first use |
| `pager` | Program to view files (F3) | Value of `$PAGER`, or prompt on first use |

## Environment Variables

Environment variables take precedence over config file settings:

| Variable | Description |
|----------|-------------|
| `$EDITOR` | Preferred text editor |
| `$PAGER` | Preferred file viewer |

If you have `$EDITOR` set in your shell, tnc will use it regardless of what's in the config file.

## First Run

On first use, if no editor/pager is configured and no environment variable is set, tnc will prompt you to choose:

- **Editor options:** vi, nano
- **Pager options:** less, more

Your selection is saved to the config file for future sessions.

## Manual Configuration

You can create or edit the config file manually:

```bash
mkdir -p ~/.config/tnc
echo "editor = vim" > ~/.config/tnc/config
echo "pager = less" >> ~/.config/tnc/config
```

## Resetting Configuration

To reset to defaults, delete the config file:

```bash
rm ~/.config/tnc/config
```

Tnc will prompt you again on next launch.
