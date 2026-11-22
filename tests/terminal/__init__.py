"""Zero-dependency real-PTY terminal test harness for Tiny Commander."""

from tests.terminal.driver import ExternalToolStub, TerminalDriver, TerminalTimeoutError
from tests.terminal.fuzzer import (
    ActionFuzzer,
    FuzzAction,
    FuzzConfig,
    FuzzReport,
    InvariantError,
    alt_screen_invariant,
    default_invariants,
)
from tests.terminal.input_encoding import KeyMap, MouseButton, MouseEncoder
from tests.terminal.virtual_terminal import Cell, DEFAULT_STYLE, Style, VirtualTerminal

__all__ = [
    'ActionFuzzer',
    'alt_screen_invariant',
    'Cell',
    'DEFAULT_STYLE',
    'ExternalToolStub',
    'FuzzAction',
    'FuzzConfig',
    'FuzzReport',
    'InvariantError',
    'KeyMap',
    'MouseButton',
    'MouseEncoder',
    'Style',
    'TerminalDriver',
    'TerminalTimeoutError',
    'VirtualTerminal',
    'default_invariants',
]
