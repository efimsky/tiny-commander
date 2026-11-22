"""Real-PTY subprocess driver and external tool stubs for E2E terminal tests."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
from typing import Any, Callable

from tests.terminal.input_encoding import KeyMap, MouseButton, MouseEncoder
from tests.terminal.virtual_terminal import VirtualTerminal


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TerminalTimeoutError(TimeoutError):
    """Timeout raised while waiting on terminal screen state or exit."""

    def __init__(
        self,
        message: str,
        *,
        screenshot: str = '',
        returncode: int | None = None,
    ) -> None:
        self.screenshot = screenshot
        self.returncode = returncode
        detail = f'{message} (returncode={returncode})\n{screenshot}'.rstrip()
        super().__init__(detail)


@dataclass
class ExternalToolStub:
    """Executable Python stub simulating an external $EDITOR or $PAGER."""

    path: Path
    log_path: Path

    @classmethod
    def create(
        cls,
        directory: Path | str,
        name: str,
        *,
        log_path: Path | None = None,
        exit_code: int = 0,
        append_text: str | None = None,
    ) -> 'ExternalToolStub':
        base = Path(directory)
        base.mkdir(parents=True, exist_ok=True)
        script = base / name
        log_file = Path(log_path) if log_path is not None else (base / f'{name}.calls.jsonl')
        code = (
            f'#!{sys.executable}\n'
            'import json, os, sys\n'
            f'log_path = {str(log_file)!r}\n'
            'entry = {"argv": sys.argv[1:], "cwd": os.getcwd()}\n'
            'with open(log_path, "a", encoding="utf-8") as fh:\n'
            '    fh.write(json.dumps(entry) + "\\n")\n'
            f'append_text = {append_text!r}\n'
            'if append_text is not None and sys.argv[1:]:\n'
            '    with open(sys.argv[-1], "a", encoding="utf-8") as target:\n'
            '        target.write(append_text)\n'
            f'sys.exit({int(exit_code)})\n'
        )
        script.write_text(code, encoding='utf-8')
        script.chmod(0o755)
        return cls(path=script, log_path=log_file)

    def calls(self) -> list[dict[str, Any]]:
        """Return parsed JSON invocation records."""
        if not self.log_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.log_path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records


def _rmtree_force(path: str | Path) -> None:
    """Recursively delete a directory tree, restoring permissions if needed."""
    def _onexc(func: Any, target: str, exc: BaseException) -> None:
        if isinstance(exc, PermissionError):
            parent = os.path.dirname(target)
            if parent:
                try:
                    os.chmod(parent, 0o700)
                except OSError:
                    pass
            try:
                os.chmod(target, 0o700 if os.path.isdir(target) else 0o600)
            except OSError:
                pass
            func(target)

    if os.path.exists(path):
        shutil.rmtree(path, onexc=_onexc)


class TerminalDriver:
    """Context manager driving Tiny Commander inside a real PTY with a VirtualTerminal."""

    def __init__(
        self,
        *,
        rows: int = 24,
        cols: int = 80,
        command: list[str] | None = None,
        cwd: str | Path | None = None,
        home: str | Path | None = None,
        term: str = 'xterm-256color',
        env: dict[str, str | None] | None = None,
        escdelay_ms: int = 25,
        default_timeout: float = 3.0,
        controlling_tty: bool = True,
    ) -> None:
        self.term = term
        self.escdelay_ms = escdelay_ms
        self.default_timeout = default_timeout
        self.controlling_tty = controlling_tty
        self.screen = VirtualTerminal(rows=rows, cols=cols)
        self.key_map = KeyMap(term)
        self._command = list(command) if command is not None else [sys.executable, '-m', 'tnc']

        self._temp_dirs: list[Path] = []
        if cwd is None:
            tmp_cwd = Path(tempfile.mkdtemp(prefix='tnc_e2e_cwd_'))
            self._temp_dirs.append(tmp_cwd)
            self.cwd = tmp_cwd
        else:
            self.cwd = Path(cwd)

        if home is None:
            tmp_home = Path(tempfile.mkdtemp(prefix='tnc_e2e_home_'))
            self._temp_dirs.append(tmp_home)
            self.home = tmp_home
        else:
            self.home = Path(home)

        base_env: dict[str, str] = {
            'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
            'HOME': str(self.home),
            'TERM': self.term,
            'LANG': 'en_US.UTF-8',
            'LC_ALL': 'en_US.UTF-8',
            'ESCDELAY': str(escdelay_ms),
            'PYTHONPATH': str(_REPO_ROOT),
        }
        if env:
            for k, v in env.items():
                if v is None:
                    base_env.pop(k, None)
                else:
                    base_env[k] = v
        self._env = base_env

        self._master_fd: int | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._eof = False
        self._last_click: tuple[float, int, int, int] | None = None
        self.raw_output = bytearray()

    def __enter__(self) -> 'TerminalDriver':
        self.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def start(self) -> None:
        """Spawn the child process attached to a fresh pseudo-terminal."""
        if self._proc is not None:
            return
        master_fd, slave_fd = pty.openpty()
        self._eof = False

        def _attach_ctty() -> None:
            os.setsid()
            try:
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)
            except OSError:
                pass

        try:
            self._set_winsize(slave_fd, self.screen.rows, self.screen.cols)
            popen_kwargs: dict[str, Any] = {
                'cwd': str(self.cwd),
                'stdin': slave_fd,
                'stdout': slave_fd,
                'stderr': slave_fd,
                'env': self._env,
                'close_fds': True,
            }
            if self.controlling_tty:
                popen_kwargs['preexec_fn'] = _attach_ctty
            else:
                popen_kwargs['start_new_session'] = True
            self._proc = subprocess.Popen(self._command, **popen_kwargs)
            self._master_fd = master_fd
        except BaseException:
            os.close(master_fd)
            raise
        finally:
            os.close(slave_fd)

    @staticmethod
    def _set_winsize(fd: int, rows: int, cols: int) -> None:
        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    @property
    def returncode(self) -> int | None:
        if self._proc is None:
            return None
        return self._proc.poll()

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def pump(self, timeout: float = 0.0) -> bytes:
        """Read any available PTY bytes and feed them into ``self.screen``."""
        if self._master_fd is None or self._eof:
            return b''
        collected = bytearray()
        deadline = time.monotonic() + max(0.0, timeout)
        first = True
        while True:
            wait = max(0.0, deadline - time.monotonic()) if first else 0.0
            first = False
            try:
                readable, _, _ = select.select([self._master_fd], [], [], wait)
            except (OSError, ValueError):
                self._eof = True
                break
            if not readable:
                break
            try:
                chunk = os.read(self._master_fd, 65536)
            except OSError:
                self._eof = True
                break
            if not chunk:
                self._eof = True
                break
            collected.extend(chunk)
            self.raw_output.extend(chunk)
            self.screen.feed(chunk)
        return bytes(collected)

    def wait_until(
        self,
        predicate: Callable[[VirtualTerminal], Any],
        timeout: float | None = None,
        *,
        description: str = 'screen condition',
    ) -> Any:
        """Poll PTY output until ``predicate(self.screen)`` returns a truthy value."""
        limit = self.default_timeout if timeout is None else timeout
        deadline = time.monotonic() + limit
        self.pump(0.0)
        result = predicate(self.screen)
        if result:
            return result
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            self.pump(min(0.05, remaining))
            result = predicate(self.screen)
            if result:
                return result
            if not self.is_alive() and not self._has_pending_read():
                break
        raise TerminalTimeoutError(
            f'Timed out after {limit:.2f}s waiting for {description}',
            screenshot=self.screen.screenshot(),
            returncode=self.returncode,
        )

    def _has_pending_read(self) -> bool:
        if self._master_fd is None or self._eof:
            return False
        try:
            r, _, _ = select.select([self._master_fd], [], [], 0.0)
            return bool(r)
        except (OSError, ValueError):
            return False

    def wait_for_text(
        self,
        needle: str,
        timeout: float | None = None,
        *,
        row: int | None = None,
        occurrence: int = 0,
    ) -> tuple[int, int]:
        """Wait until ``needle`` renders on screen and return its ``(col, row)``."""
        return self.wait_until(
            lambda scr: scr.find_text(needle, row=row, occurrence=occurrence),
            timeout=timeout,
            description=f'text {needle!r}',
        )

    def wait_stable(self, quiet_period: float = 0.04, timeout: float | None = None) -> None:
        """Drain output until the PTY stays quiet for ``quiet_period`` seconds."""
        limit = self.default_timeout if timeout is None else timeout
        deadline = time.monotonic() + limit
        last_activity = time.monotonic()
        while time.monotonic() < deadline:
            if self._eof and not self.is_alive():
                return
            if self.pump(min(0.02, quiet_period)):
                last_activity = time.monotonic()
            elif time.monotonic() - last_activity >= quiet_period or self._eof:
                return

    def wait_ready(
        self,
        timeout: float | None = None,
        *,
        require_alt_screen: bool | None = None,
        require_panels: bool | None = None,
    ) -> None:
        """Wait until Tiny Commander completes initial UI render."""
        req_alt = (
            self.key_map.supports_alt_screen
            if require_alt_screen is None
            else require_alt_screen
        )
        req_panels = (
            self.key_map.supports_cursor_addressing
            if require_panels is None
            else require_panels
        )
        self.wait_until(
            lambda scr: (not req_alt or scr.in_alt_screen)
            and (not req_panels or scr.contains('[Left]') or scr.contains('[Right]'))
            and scr.contains('F10'),
            timeout=timeout,
            description='Tiny Commander startup',
        )
        self.wait_stable(quiet_period=0.04, timeout=0.5)

    def wait_exit(self, timeout: float | None = None) -> int:
        """Drain remaining PTY output until process exits and return exit code."""
        if self._proc is None:
            raise RuntimeError('TerminalDriver was not started')
        limit = self.default_timeout if timeout is None else timeout
        deadline = time.monotonic() + limit
        while self._proc.poll() is None and time.monotonic() < deadline:
            self.pump(0.05)
        self.pump(0.02)
        rc = self._proc.poll()
        if rc is None:
            raise TerminalTimeoutError(
                f'Process did not exit within {limit:.2f}s',
                screenshot=self.screen.screenshot(),
                returncode=None,
            )
        return rc

    def send_bytes(self, data: bytes) -> None:
        """Write raw bytes to the PTY master."""
        if self._master_fd is None:
            raise RuntimeError('TerminalDriver is not open')
        view = memoryview(data)
        while view:
            written = os.write(self._master_fd, view)
            view = view[written:]

    def press(
        self,
        *keys: str,
        delay: float = 0.0,
        esc_settle: float = 0.05,
    ) -> None:
        """Send one or more symbolic key presses (e.g. 'down', 'f10', 'ctrl+x')."""
        for idx, key in enumerate(keys):
            if idx > 0:
                pause = delay
                if keys[idx - 1].lower().strip() in ('esc', 'escape'):
                    pause = max(pause, esc_settle)
                if pause > 0:
                    time.sleep(pause)
            self.send_bytes(self.key_map.encode(key))

    def press_esc_settled(self, settle: float = 0.05) -> None:
        """Send plain Escape and wait longer than ESCDELAY so it is not treated as Alt."""
        self.press('esc')
        time.sleep(settle)
        self.pump(0.0)

    def type_text(self, text: str) -> None:
        """Send literal UTF-8 text input to the PTY."""
        self.send_bytes(text.encode('utf-8'))

    def wait_mouse_settle(self, interval: float = 0.22) -> None:
        """Wait past ncurses mouseinterval so prior clicks do not coalesce."""
        if self._last_click is not None:
            elapsed = time.monotonic() - self._last_click[0]
            if elapsed < interval:
                time.sleep(interval - elapsed)
        self.pump(0.0)

    def click(
        self,
        x: int,
        y: int,
        button: MouseButton | int = MouseButton.LEFT,
        *,
        prevent_double_click_collapse: bool = True,
        settle: bool = False,
    ) -> None:
        """Send a mouse click at 0-based screen coordinate (x, y)."""
        btn_int = int(button)
        if prevent_double_click_collapse and self._last_click is not None:
            ts, lx, ly, lbtn = self._last_click
            if (lx, ly, lbtn) == (x, y, btn_int):
                elapsed = time.monotonic() - ts
                if elapsed < 0.20:
                    time.sleep(0.20 - elapsed)
        self.send_bytes(
            MouseEncoder.encode_click(btn_int, x, y, sgr=self.screen.sgr_mouse)
        )
        self._last_click = (time.monotonic(), x, y, btn_int)
        if settle:
            self.wait_mouse_settle()

    def double_click(
        self,
        x: int,
        y: int,
        button: MouseButton | int = MouseButton.LEFT,
        *,
        interval: float = 0.02,
    ) -> None:
        """Send two rapid clicks so curses synthesizes BUTTON*_DOUBLE_CLICKED."""
        self.click(x, y, button, prevent_double_click_collapse=True)
        if interval > 0:
            time.sleep(interval)
        self.click(x, y, button, prevent_double_click_collapse=False)

    def click_text(
        self,
        needle: str,
        *,
        row: int | None = None,
        occurrence: int = 0,
        offset_x: int = 0,
        button: MouseButton | int = MouseButton.LEFT,
        timeout: float | None = None,
        settle: bool = False,
    ) -> tuple[int, int]:
        """Locate ``needle`` on the rendered screen and click it."""
        col, found_row = self.wait_for_text(
            needle, timeout=timeout, row=row, occurrence=occurrence
        )
        target = (col + offset_x, found_row)
        self.click(target[0], target[1], button=button, settle=settle)
        return target

    def scroll(
        self,
        direction: str,
        x: int,
        y: int,
        steps: int = 1,
    ) -> None:
        """Send mouse scroll wheel events ('up' or 'down') at (x, y)."""
        seq = MouseEncoder.encode_wheel(direction, x, y, sgr=self.screen.sgr_mouse)
        for _ in range(steps):
            self.send_bytes(seq)

    def send_signal(self, sig: int) -> None:
        """Deliver a signal (e.g. signal.SIGINT) to the child process group."""
        if self._proc is not None and self.is_alive():
            try:
                os.killpg(self._proc.pid, sig)
            except ProcessLookupError:
                pass

    def resize(self, rows: int, cols: int) -> None:
        """Resize PTY and VirtualTerminal and deliver SIGWINCH."""
        if self._master_fd is None or self._proc is None:
            raise RuntimeError('TerminalDriver is not running')
        self.screen.resize(rows, cols)
        self._set_winsize(self._master_fd, rows, cols)
        self.send_signal(signal.SIGWINCH)

    def resize_and_wait(
        self,
        rows: int,
        cols: int,
        predicate: Callable[[VirtualTerminal], Any] | None = None,
        timeout: float | None = None,
    ) -> None:
        """Resize terminal and wait until dimensions and optional predicate stabilize."""
        self.resize(rows, cols)
        self.wait_until(
            lambda scr: scr.rows == rows
            and scr.cols == cols
            and (True if predicate is None else bool(predicate(scr))),
            timeout=timeout,
            description=f'resize to {rows}x{cols}',
        )
        self.wait_stable(quiet_period=0.03, timeout=0.4)

    def close(self, *, sigterm_timeout: float = 0.15) -> None:
        """Terminate child process if running and release PTY and owned temp dirs."""
        try:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    os.killpg(self._proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self._proc.wait(timeout=sigterm_timeout)
                except subprocess.TimeoutExpired:
                    if self._master_fd is not None:
                        try:
                            os.close(self._master_fd)
                        except OSError:
                            pass
                        self._master_fd = None
                    try:
                        os.killpg(self._proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        self._proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        pass
        finally:
            if self._master_fd is not None:
                try:
                    os.close(self._master_fd)
                except OSError:
                    pass
                self._master_fd = None
            for d in self._temp_dirs:
                try:
                    _rmtree_force(d)
                except OSError:
                    pass
            self._temp_dirs.clear()
