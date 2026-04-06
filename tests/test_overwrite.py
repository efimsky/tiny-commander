"""Tests for overwrite confirmation."""

import tempfile
import unittest
from pathlib import Path

from tnc.file_ops import (
    OverwriteChoice,
    OverwriteHandler,
    copy_files_with_overwrite,
    move_files_with_overwrite,
)


class MockOverwriteHandler(OverwriteHandler):
    """Mock handler that returns pre-configured responses."""

    def __init__(self, responses: list[OverwriteChoice]):
        self.responses = responses
        self.prompt_count = 0
        self._index = 0

    def prompt(
        self,
        filename: str,
        source_size: int,
        dest_size: int,
        source_mtime: float,
        dest_mtime: float,
        current: int,
        total: int
    ) -> OverwriteChoice:
        self.prompt_count += 1
        if self._index < len(self.responses):
            choice = self.responses[self._index]
            self._index += 1
            return choice
        return OverwriteChoice.NO


class TestNoConflict(unittest.TestCase):
    """Test when there's no conflict."""

    def test_no_prompt_when_no_conflict(self):
        """No prompt when destination doesn't exist."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'file.txt').write_text('source')
                handler = MockOverwriteHandler([])

                copy_files_with_overwrite(
                    ['file.txt'], source_dir, dest_dir, handler
                )

                self.assertEqual(handler.prompt_count, 0)
                self.assertEqual(Path(dest_dir, 'file.txt').read_text(), 'source')


class TestOverwritePrompt(unittest.TestCase):
    """Test overwrite prompting."""

    def test_prompt_when_conflict_exists(self):
        """Should prompt when file exists at destination."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'file.txt').write_text('source')
                Path(dest_dir, 'file.txt').write_text('dest')
                handler = MockOverwriteHandler([OverwriteChoice.YES])

                copy_files_with_overwrite(
                    ['file.txt'], source_dir, dest_dir, handler
                )

                self.assertEqual(handler.prompt_count, 1)


class TestOverwriteYes(unittest.TestCase):
    """Test YES response."""

    def test_yes_overwrites_file(self):
        """YES should overwrite the destination file."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'file.txt').write_text('new content')
                Path(dest_dir, 'file.txt').write_text('old content')
                handler = MockOverwriteHandler([OverwriteChoice.YES])

                copy_files_with_overwrite(
                    ['file.txt'], source_dir, dest_dir, handler
                )

                self.assertEqual(
                    Path(dest_dir, 'file.txt').read_text(),
                    'new content'
                )


class TestOverwriteNo(unittest.TestCase):
    """Test NO response."""

    def test_no_skips_file(self):
        """NO should keep original destination file."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'file.txt').write_text('new content')
                Path(dest_dir, 'file.txt').write_text('original')
                handler = MockOverwriteHandler([OverwriteChoice.NO])

                copy_files_with_overwrite(
                    ['file.txt'], source_dir, dest_dir, handler
                )

                self.assertEqual(
                    Path(dest_dir, 'file.txt').read_text(),
                    'original'
                )


class TestOverwriteYesAll(unittest.TestCase):
    """Test YES_ALL response."""

    def test_yes_to_all_applies_to_remaining(self):
        """YES_ALL should overwrite all remaining conflicts."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                for name in ['a.txt', 'b.txt', 'c.txt']:
                    Path(source_dir, name).write_text(f'source_{name}')
                    Path(dest_dir, name).write_text(f'dest_{name}')
                handler = MockOverwriteHandler([OverwriteChoice.YES_ALL])

                copy_files_with_overwrite(
                    ['a.txt', 'b.txt', 'c.txt'], source_dir, dest_dir, handler
                )

                # Only asked once
                self.assertEqual(handler.prompt_count, 1)
                # All files should be overwritten
                for name in ['a.txt', 'b.txt', 'c.txt']:
                    self.assertEqual(
                        Path(dest_dir, name).read_text(),
                        f'source_{name}'
                    )


class TestOverwriteNoAll(unittest.TestCase):
    """Test NO_ALL response."""

    def test_no_to_all_skips_remaining(self):
        """NO_ALL should skip all remaining conflicts."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                for name in ['a.txt', 'b.txt', 'c.txt']:
                    Path(source_dir, name).write_text(f'source_{name}')
                    Path(dest_dir, name).write_text(f'dest_{name}')
                handler = MockOverwriteHandler([OverwriteChoice.NO_ALL])

                copy_files_with_overwrite(
                    ['a.txt', 'b.txt', 'c.txt'], source_dir, dest_dir, handler
                )

                # Only asked once
                self.assertEqual(handler.prompt_count, 1)
                # All files should retain original content
                for name in ['a.txt', 'b.txt', 'c.txt']:
                    self.assertEqual(
                        Path(dest_dir, name).read_text(),
                        f'dest_{name}'
                    )


class TestOverwriteCancel(unittest.TestCase):
    """Test CANCEL response."""

    def test_cancel_aborts_operation(self):
        """CANCEL should abort the operation."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'a.txt').write_text('source_a')
                Path(source_dir, 'b.txt').write_text('source_b')
                Path(dest_dir, 'a.txt').write_text('dest_a')
                handler = MockOverwriteHandler([OverwriteChoice.CANCEL])

                result = copy_files_with_overwrite(
                    ['a.txt', 'b.txt'], source_dir, dest_dir, handler
                )

                self.assertTrue(result.cancelled)


class TestMixedResponses(unittest.TestCase):
    """Test mixed response sequences."""

    def test_mixed_responses(self):
        """Mixed responses should be handled correctly."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                for name in ['a.txt', 'b.txt', 'c.txt']:
                    Path(source_dir, name).write_text(f'source_{name}')
                    Path(dest_dir, name).write_text(f'dest_{name}')
                # yes, no, yes
                handler = MockOverwriteHandler([
                    OverwriteChoice.YES,
                    OverwriteChoice.NO,
                    OverwriteChoice.YES
                ])

                copy_files_with_overwrite(
                    ['a.txt', 'b.txt', 'c.txt'], source_dir, dest_dir, handler
                )

                self.assertEqual(handler.prompt_count, 3)
                # a.txt overwritten, b.txt kept, c.txt overwritten
                self.assertEqual(Path(dest_dir, 'a.txt').read_text(), 'source_a.txt')
                self.assertEqual(Path(dest_dir, 'b.txt').read_text(), 'dest_b.txt')
                self.assertEqual(Path(dest_dir, 'c.txt').read_text(), 'source_c.txt')


class TestMoveWithOverwrite(unittest.TestCase):
    """Test move with overwrite handling."""

    def test_move_with_overwrite_yes(self):
        """Move should also handle overwrite."""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                Path(source_dir, 'file.txt').write_text('source')
                Path(dest_dir, 'file.txt').write_text('dest')
                handler = MockOverwriteHandler([OverwriteChoice.YES])

                move_files_with_overwrite(
                    ['file.txt'], source_dir, dest_dir, handler
                )

                # Source should be gone, dest should have new content
                self.assertFalse(Path(source_dir, 'file.txt').exists())
                self.assertEqual(
                    Path(dest_dir, 'file.txt').read_text(),
                    'source'
                )


class TestOverwriteOlder(unittest.TestCase):
    """Test YES_OLDER response - overwrite only if source is newer."""

    def test_yes_older_overwrites_newer_source(self):
        """YES_OLDER should overwrite when source is newer."""
        import os
        import time

        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create dest file first (older)
                dest_file = Path(dest_dir, 'file.txt')
                dest_file.write_text('old_dest')
                old_time = time.time() - 100  # 100 seconds ago
                os.utime(dest_file, (old_time, old_time))

                # Create source file (newer)
                source_file = Path(source_dir, 'file.txt')
                source_file.write_text('new_source')

                handler = MockOverwriteHandler([OverwriteChoice.YES_OLDER])

                result = copy_files_with_overwrite(
                    ['file.txt'], source_dir, dest_dir, handler
                )

                # Source is newer, should be copied
                self.assertEqual(dest_file.read_text(), 'new_source')
                self.assertEqual(len(result.copied_files), 1)
                self.assertEqual(len(result.skipped_files), 0)

    def test_yes_older_skips_older_source(self):
        """YES_OLDER should skip when source is older than dest."""
        import os
        import time

        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create source file first (older)
                source_file = Path(source_dir, 'file.txt')
                source_file.write_text('old_source')
                old_time = time.time() - 100  # 100 seconds ago
                os.utime(source_file, (old_time, old_time))

                # Create dest file (newer)
                dest_file = Path(dest_dir, 'file.txt')
                dest_file.write_text('new_dest')

                handler = MockOverwriteHandler([OverwriteChoice.YES_OLDER])

                result = copy_files_with_overwrite(
                    ['file.txt'], source_dir, dest_dir, handler
                )

                # Source is older, should be skipped
                self.assertEqual(dest_file.read_text(), 'new_dest')
                self.assertEqual(len(result.copied_files), 0)
                self.assertEqual(len(result.skipped_files), 1)

    def test_yes_older_applies_to_all_remaining(self):
        """YES_OLDER should apply to all remaining conflicts."""
        import os
        import time

        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                old_time = time.time() - 100
                new_time = time.time()

                # a.txt: source newer (should copy)
                Path(source_dir, 'a.txt').write_text('source_a')
                dest_a = Path(dest_dir, 'a.txt')
                dest_a.write_text('dest_a')
                os.utime(dest_a, (old_time, old_time))

                # b.txt: source older (should skip)
                src_b = Path(source_dir, 'b.txt')
                src_b.write_text('source_b')
                os.utime(src_b, (old_time, old_time))
                Path(dest_dir, 'b.txt').write_text('dest_b')

                # c.txt: source newer (should copy)
                Path(source_dir, 'c.txt').write_text('source_c')
                dest_c = Path(dest_dir, 'c.txt')
                dest_c.write_text('dest_c')
                os.utime(dest_c, (old_time, old_time))

                handler = MockOverwriteHandler([OverwriteChoice.YES_OLDER])

                result = copy_files_with_overwrite(
                    ['a.txt', 'b.txt', 'c.txt'], source_dir, dest_dir, handler
                )

                # Only prompted once
                self.assertEqual(handler.prompt_count, 1)
                # a and c copied, b skipped
                self.assertEqual(Path(dest_dir, 'a.txt').read_text(), 'source_a')
                self.assertEqual(Path(dest_dir, 'b.txt').read_text(), 'dest_b')
                self.assertEqual(Path(dest_dir, 'c.txt').read_text(), 'source_c')
                self.assertEqual(len(result.copied_files), 2)
                self.assertEqual(len(result.skipped_files), 1)


if __name__ == '__main__':
    unittest.main()
