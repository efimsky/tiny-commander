# Installation

## Requirements

- Python 3.13 or later
- Linux or macOS (Windows is not supported)

## Install from Source

```bash
# Clone the repository
git clone https://github.com/efimsky/tiny-commander.git
cd tiny-commander

# Run directly
python -m tnc

# Or make the entry script executable
chmod +x tnc
./tnc
```

## Add to PATH

To run `tnc` from anywhere:

```bash
# Option 1: Symlink to a directory in your PATH
ln -s /path/to/tiny-commander/tnc ~/.local/bin/tnc

# Option 2: Add the directory to your PATH in ~/.bashrc or ~/.zshrc
export PATH="$PATH:/path/to/tiny-commander"
```

## Verify Installation

```bash
tnc --version
```

## Uninstall

Simply remove the cloned directory and any symlinks you created.
