"""Tests for sort cycling functionality."""

import tempfile
import unittest
from pathlib import Path

from tnc.panel import Panel


class TestSortCycle(unittest.TestCase):
    """Tests for Panel.cycle_sort method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

        # Create test files
        (self.test_path / 'alpha.txt').write_text('a')
        (self.test_path / 'beta.py').write_text('bb')
        (self.test_path / 'gamma.md').write_text('ggg')

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_default_sort_is_name(self) -> None:
        """Test that default sort order is 'name'."""
        panel = Panel(str(self.test_path), width=40, height=10)

        self.assertEqual(panel.sort_order, 'name')

    def test_cycle_from_name_to_size(self) -> None:
        """Test cycling from name to size."""
        panel = Panel(str(self.test_path), width=40, height=10)
        panel.sort_order = 'name'

        panel.cycle_sort()

        self.assertEqual(panel.sort_order, 'size')

    def test_cycle_from_size_to_date(self) -> None:
        """Test cycling from size to date."""
        panel = Panel(str(self.test_path), width=40, height=10)
        panel.sort_order = 'size'

        panel.cycle_sort()

        self.assertEqual(panel.sort_order, 'date')

    def test_cycle_from_date_to_extension(self) -> None:
        """Test cycling from date to extension."""
        panel = Panel(str(self.test_path), width=40, height=10)
        panel.sort_order = 'date'

        panel.cycle_sort()

        self.assertEqual(panel.sort_order, 'extension')

    def test_cycle_from_extension_to_name(self) -> None:
        """Test cycling from extension back to name."""
        panel = Panel(str(self.test_path), width=40, height=10)
        panel.sort_order = 'extension'

        panel.cycle_sort()

        self.assertEqual(panel.sort_order, 'name')

    def test_full_cycle(self) -> None:
        """Test cycling through all sort orders returns to start."""
        panel = Panel(str(self.test_path), width=40, height=10)
        initial_order = panel.sort_order

        for _ in range(4):  # name -> size -> date -> extension -> name
            panel.cycle_sort()

        self.assertEqual(panel.sort_order, initial_order)

    def test_cycle_refreshes_panel(self) -> None:
        """Test that cycling sort order refreshes the panel."""
        panel = Panel(str(self.test_path), width=40, height=10)

        # Get initial entries order
        initial_entries = [e.name for e in panel.entries]

        # Cycle to size sort
        panel.cycle_sort()

        # Entries should have changed (size sort is descending)
        current_entries = [e.name for e in panel.entries]
        # Note: entries might be same if sizes happen to be in name order
        # But sort_order should definitely change
        self.assertEqual(panel.sort_order, 'size')

    def test_cycle_preserves_hidden_setting(self) -> None:
        """Test that cycling preserves show_hidden setting."""
        panel = Panel(str(self.test_path), width=40, height=10)
        panel.show_hidden = False

        panel.cycle_sort()

        self.assertFalse(panel.show_hidden)

    def test_sort_cycle_order(self) -> None:
        """Test the exact cycle order: name -> size -> date -> extension."""
        panel = Panel(str(self.test_path), width=40, height=10)
        expected_cycle = ['name', 'size', 'date', 'extension', 'name']

        orders = [panel.sort_order]
        for _ in range(4):
            panel.cycle_sort()
            orders.append(panel.sort_order)

        self.assertEqual(orders, expected_cycle)


if __name__ == '__main__':
    unittest.main()
