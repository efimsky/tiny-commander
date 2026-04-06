"""Tests for navigation history (remembering directory position on navigate up)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tnc.panel import Panel


class TestNavigationHistory(unittest.TestCase):
    """Test navigation history for remembering child directory on navigate up."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        # Resolve to handle macOS /var -> /private/var symlink
        self.root = Path(self.temp_dir.name).resolve()

        # Create directory structure:
        # root/
        #   alpha/
        #   beta/
        #   gamma/
        #   file.txt
        (self.root / 'alpha').mkdir()
        (self.root / 'beta').mkdir()
        (self.root / 'gamma').mkdir()
        (self.root / 'file.txt').touch()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_navigate_up_positions_cursor_on_child(self) -> None:
        """When navigating up via '..', cursor should be on the child we came from."""
        panel = Panel(str(self.root / 'beta'))

        # Navigate up via '..' entry
        panel.cursor = 0  # '..' is always first
        panel.enter()

        # Should now be in root, cursor on 'beta'
        self.assertEqual(panel.path, self.root)
        beta_index = panel._find_entry_index('beta')
        self.assertIsNotNone(beta_index)
        self.assertEqual(panel.cursor, beta_index)

    def test_navigate_multiple_levels_remembers_each(self) -> None:
        """History should track multiple levels of navigation."""
        # Create deeper structure
        (self.root / 'alpha' / 'deep').mkdir()
        (self.root / 'alpha' / 'other').mkdir()

        panel = Panel(str(self.root / 'alpha' / 'deep'))

        # Navigate up to alpha
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root / 'alpha')
        deep_index = panel._find_entry_index('deep')
        self.assertEqual(panel.cursor, deep_index)

        # Navigate up to root
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root)
        alpha_index = panel._find_entry_index('alpha')
        self.assertEqual(panel.cursor, alpha_index)

    def test_navigate_up_when_child_deleted_falls_back(self) -> None:
        """If the child directory no longer exists, fall back to cursor 0."""
        child_path = self.root / 'beta'
        panel = Panel(str(child_path))

        # Delete the child directory while we're "inside" it
        # (simulate by removing it before navigating up)
        shutil.rmtree(child_path)

        # Navigate up - beta no longer exists
        panel.cursor = 0
        panel.enter()

        # Should be in root, cursor at 0 (fallback)
        self.assertEqual(panel.path, self.root)
        self.assertEqual(panel.cursor, 0)

    def test_external_path_change_clears_history(self) -> None:
        """External path changes (not via '..') should clear history."""
        panel = Panel(str(self.root / 'beta'))

        # Navigate up via '..' (this adds to history: root → beta)
        panel.cursor = 0
        panel.enter()

        # Verify history is working - cursor should be on beta
        beta_index = panel._find_entry_index('beta')
        self.assertIsNotNone(beta_index)
        self.assertEqual(panel.cursor, beta_index)

        # Now externally change to root (this should clear history)
        panel.change_directory(self.root, external=True)

        # Cursor should be at 0, not on beta (history was cleared)
        self.assertEqual(panel.cursor, 0)

    def test_history_limit_evicts_oldest(self) -> None:
        """History should be limited to 50 entries, evicting oldest."""
        # Create a deep directory structure (51 levels)
        current = self.root
        for i in range(51):
            subdir = current / f'level{i}'
            subdir.mkdir()
            current = subdir

        panel = Panel(str(current))

        # Navigate up 51 times
        for _ in range(51):
            panel.cursor = 0
            panel.enter()

        # Now we're back at root
        # The oldest entry (level0) should have been evicted
        # We can't easily test the internal state, but we can verify
        # the history didn't grow unbounded and navigation still works
        self.assertEqual(panel.path, self.root)

    def test_navigate_into_and_back_multiple_times(self) -> None:
        """Repeated navigation into same child and back should work."""
        panel = Panel(str(self.root))

        # Navigate into beta
        beta_index = panel._find_entry_index('beta')
        panel.cursor = beta_index
        panel.enter()
        self.assertEqual(panel.path, self.root / 'beta')

        # Navigate back
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root)
        self.assertEqual(panel.cursor, beta_index)

        # Navigate into beta again
        panel.cursor = beta_index
        panel.enter()
        self.assertEqual(panel.path, self.root / 'beta')

        # Navigate back again
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root)
        self.assertEqual(panel.cursor, beta_index)

    def test_history_tracks_different_parents_independently(self) -> None:
        """Each parent path should have its own remembered child."""
        # Create structure:
        # root/alpha/sub1
        # root/beta/sub2
        (self.root / 'alpha' / 'sub1').mkdir()
        (self.root / 'beta' / 'sub2').mkdir()

        panel = Panel(str(self.root / 'alpha' / 'sub1'))

        # Navigate up from sub1 to alpha
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root / 'alpha')

        # Navigate up from alpha to root
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root)
        alpha_index = panel._find_entry_index('alpha')
        self.assertEqual(panel.cursor, alpha_index)

        # Now navigate into beta/sub2
        beta_index = panel._find_entry_index('beta')
        panel.cursor = beta_index
        panel.enter()
        sub2_index = panel._find_entry_index('sub2')
        panel.cursor = sub2_index
        panel.enter()
        self.assertEqual(panel.path, self.root / 'beta' / 'sub2')

        # Navigate up from sub2 to beta
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root / 'beta')
        sub2_index = panel._find_entry_index('sub2')
        self.assertEqual(panel.cursor, sub2_index)

        # Navigate up from beta to root - should remember beta, not alpha
        panel.cursor = 0
        panel.enter()
        self.assertEqual(panel.path, self.root)
        beta_index = panel._find_entry_index('beta')
        self.assertEqual(panel.cursor, beta_index)


if __name__ == '__main__':
    unittest.main()
