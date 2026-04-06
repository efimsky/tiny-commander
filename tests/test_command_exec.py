"""Tests for shell command execution."""

import tempfile
import unittest
from pathlib import Path

from tnc.command_line import CommandLine, CommandResult


class TestCommandOutput(unittest.TestCase):
    """Test command output capture."""

    def test_command_output_captured(self):
        """Output should be captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmdline = CommandLine(tmpdir)
            result = cmdline.execute('echo hello')

            self.assertEqual(result.stdout.strip(), 'hello')
            self.assertEqual(result.returncode, 0)

    def test_command_runs_in_correct_directory(self):
        """Command should run in specified directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmdline = CommandLine(tmpdir)
            result = cmdline.execute('pwd')

            # Resolve because macOS uses /private/var symlinks
            expected = str(Path(tmpdir).resolve())
            self.assertIn(expected, result.stdout.strip())


class TestCommandErrors(unittest.TestCase):
    """Test command error handling."""

    def test_command_error_captured(self):
        """Errors should be captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmdline = CommandLine(tmpdir)
            result = cmdline.execute('ls /nonexistent_directory_abc123')

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(len(result.stderr) > 0)


class TestComplexCommands(unittest.TestCase):
    """Test complex command scenarios."""

    def test_command_with_pipes(self):
        """Piped commands should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmdline = CommandLine(tmpdir)
            result = cmdline.execute('echo hello | tr h H')

            self.assertEqual(result.stdout.strip(), 'Hello')

    def test_command_with_environment_variables(self):
        """Environment variables should be expanded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmdline = CommandLine(tmpdir)
            result = cmdline.execute('echo $HOME')

            # Should resolve to a path
            self.assertTrue(result.stdout.strip().startswith('/'))


class TestEmptyCommand(unittest.TestCase):
    """Test empty command handling."""

    def test_empty_command_returns_none(self):
        """Empty command should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmdline = CommandLine(tmpdir)
            result = cmdline.execute('')

            self.assertIsNone(result)

    def test_whitespace_only_returns_none(self):
        """Whitespace-only command should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmdline = CommandLine(tmpdir)
            result = cmdline.execute('   ')

            self.assertIsNone(result)


class TestCommandResult(unittest.TestCase):
    """Test CommandResult dataclass."""

    def test_command_result_fields(self):
        """CommandResult should have correct fields."""
        result = CommandResult(
            stdout='output',
            stderr='error',
            returncode=1
        )
        self.assertEqual(result.stdout, 'output')
        self.assertEqual(result.stderr, 'error')
        self.assertEqual(result.returncode, 1)

    def test_success_property(self):
        """Success property should reflect returncode."""
        success = CommandResult(stdout='', stderr='', returncode=0)
        failure = CommandResult(stdout='', stderr='', returncode=1)

        self.assertTrue(success.success)
        self.assertFalse(failure.success)


class TestSpacesInPath(unittest.TestCase):
    """Test handling of paths with spaces."""

    def test_command_with_spaces_in_path(self):
        """Should work with spaces in cwd."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_with_space = Path(tmpdir, 'my folder')
            path_with_space.mkdir()

            cmdline = CommandLine(str(path_with_space))
            result = cmdline.execute('pwd')

            self.assertIn('my folder', result.stdout)


if __name__ == '__main__':
    unittest.main()
