"""Zero-dependency real-PTY terminal test harness for Tiny Commander."""

from tests.terminal.driver import ExternalToolStub, TerminalDriver, TerminalTimeoutError
from tests.terminal.fuzzer import (
    ActionFuzzer,
    FilesystemShadowInvariant,
    FuzzAction,
    FuzzConfig,
    FuzzReport,
    InvariantError,
    SandboxDriverFactory,
    alt_screen_invariant,
    chrome_layout_invariant,
    default_invariants,
    screen_integrity_invariant,
)
from tests.terminal.input_encoding import KeyMap, MouseButton, MouseEncoder
from tests.terminal.virtual_terminal import Cell, DEFAULT_STYLE, Style, VirtualTerminal

__all__ = [
    'ActionFuzzer',
    'Cell',
    'DEFAULT_STYLE',
    'ExternalToolStub',
    'FilesystemShadowInvariant',
    'FuzzAction',
    'FuzzConfig',
    'FuzzReport',
    'InvariantError',
    'KeyMap',
    'MouseButton',
    'MouseEncoder',
    'SandboxDriverFactory',
    'Style',
    'TerminalDriver',
    'TerminalTimeoutError',
    'VirtualTerminal',
    'alt_screen_invariant',
    'chrome_layout_invariant',
    'default_invariants',
    'screen_integrity_invariant',
]
