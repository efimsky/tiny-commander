"""Tests for chmod dialog."""

import curses
import unittest
from unittest import mock

from tnc.dialog import ChmodDialog, chmod_dialog
from tnc.permissions import TriState


class TestChmodDialogInit(unittest.TestCase):
    """Tests for ChmodDialog initialization."""

    def test_chmod_dialog_init_single_file(self):
        """ChmodDialog initializes with single file mode."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o755)

        self.assertEqual(dialog.file_count, 1)
        # Check that bits are set correctly for 0o755
        self.assertEqual(dialog.get_bit_state('owner_read'), TriState.CHECKED)
        self.assertEqual(dialog.get_bit_state('owner_write'), TriState.CHECKED)
        self.assertEqual(dialog.get_bit_state('owner_exec'), TriState.CHECKED)
        self.assertEqual(dialog.get_bit_state('group_read'), TriState.CHECKED)
        self.assertEqual(dialog.get_bit_state('group_write'), TriState.UNCHECKED)
        self.assertEqual(dialog.get_bit_state('group_exec'), TriState.CHECKED)

    def test_chmod_dialog_init_multiple_files(self):
        """ChmodDialog initializes with tri-state bits for multiple files."""
        # Simulate mixed state
        bit_states = {
            'owner_read': TriState.CHECKED,
            'owner_write': TriState.MIXED,
            'owner_exec': TriState.UNCHECKED,
            'group_read': TriState.CHECKED,
            'group_write': TriState.UNCHECKED,
            'group_exec': TriState.MIXED,
            'other_read': TriState.CHECKED,
            'other_write': TriState.UNCHECKED,
            'other_exec': TriState.UNCHECKED,
            'setuid': TriState.UNCHECKED,
            'setgid': TriState.UNCHECKED,
            'sticky': TriState.UNCHECKED,
        }

        dialog = ChmodDialog(file_count=5, initial_states=bit_states)

        self.assertEqual(dialog.file_count, 5)
        self.assertEqual(dialog.get_bit_state('owner_write'), TriState.MIXED)
        self.assertEqual(dialog.get_bit_state('group_exec'), TriState.MIXED)

    def test_chmod_dialog_has_directory_flag(self):
        """ChmodDialog tracks if any selected item is a directory."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o755, has_directory=True)
        self.assertTrue(dialog.has_directory)

        dialog = ChmodDialog(file_count=1, initial_mode=0o755, has_directory=False)
        self.assertFalse(dialog.has_directory)


class TestChmodDialogNavigation(unittest.TestCase):
    """Tests for ChmodDialog keyboard navigation."""

    def test_navigate_grid_with_arrows(self):
        """Arrow keys navigate the permission grid."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o644)

        # Start at (0, 0) - owner_read
        self.assertEqual(dialog.cursor_row, 0)
        self.assertEqual(dialog.cursor_col, 0)

        # Right arrow
        dialog.handle_key(curses.KEY_RIGHT)
        self.assertEqual(dialog.cursor_col, 1)

        # Down arrow
        dialog.handle_key(curses.KEY_DOWN)
        self.assertEqual(dialog.cursor_row, 1)

        # Left arrow
        dialog.handle_key(curses.KEY_LEFT)
        self.assertEqual(dialog.cursor_col, 0)

        # Up arrow
        dialog.handle_key(curses.KEY_UP)
        self.assertEqual(dialog.cursor_row, 0)

    def test_toggle_checkbox_with_space(self):
        """Space key toggles current checkbox."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o644)

        # owner_read is checked (0o644 has r for owner)
        self.assertEqual(dialog.get_bit_state('owner_read'), TriState.CHECKED)

        # Toggle it off
        dialog.handle_key(ord(' '))
        self.assertEqual(dialog.get_bit_state('owner_read'), TriState.UNCHECKED)

        # Toggle it back on
        dialog.handle_key(ord(' '))
        self.assertEqual(dialog.get_bit_state('owner_read'), TriState.CHECKED)

    def test_toggle_mixed_becomes_checked(self):
        """Toggling MIXED state becomes CHECKED."""
        bit_states = {
            'owner_read': TriState.MIXED,
            'owner_write': TriState.CHECKED,
            'owner_exec': TriState.UNCHECKED,
            'group_read': TriState.CHECKED,
            'group_write': TriState.UNCHECKED,
            'group_exec': TriState.UNCHECKED,
            'other_read': TriState.CHECKED,
            'other_write': TriState.UNCHECKED,
            'other_exec': TriState.UNCHECKED,
            'setuid': TriState.UNCHECKED,
            'setgid': TriState.UNCHECKED,
            'sticky': TriState.UNCHECKED,
        }
        dialog = ChmodDialog(file_count=3, initial_states=bit_states)

        # owner_read is MIXED
        self.assertEqual(dialog.get_bit_state('owner_read'), TriState.MIXED)

        # Toggle it - should become CHECKED
        dialog.handle_key(ord(' '))
        self.assertEqual(dialog.get_bit_state('owner_read'), TriState.CHECKED)

    def test_escape_cancels(self):
        """Escape key returns None (cancel)."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o644)

        result = dialog.handle_key(27)  # Escape

        self.assertIsNone(result)
        self.assertTrue(dialog.cancelled)

    def test_cancel_button_sets_cancelled(self):
        """Cancel button sets cancelled flag."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o644)

        # Navigate to buttons and select Cancel
        dialog.focus_section = 'buttons'
        dialog.button_focus = 1  # Cancel

        result = dialog.handle_key(ord('\n'))

        self.assertIsNone(result)
        self.assertTrue(dialog.cancelled)


class TestChmodDialogResult(unittest.TestCase):
    """Tests for ChmodDialog result calculation."""

    def test_get_result_mode(self):
        """get_result_mode returns computed mode from current state."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o755)

        # Initial mode should be 0o755
        self.assertEqual(dialog.get_result_mode(), 0o755)

        # Turn off owner execute
        dialog.set_bit_state('owner_exec', TriState.UNCHECKED)
        self.assertEqual(dialog.get_result_mode(), 0o655)

    def test_get_result_mode_ignores_mixed(self):
        """get_result_mode treats MIXED as unchanged (not set in result)."""
        bit_states = {
            'owner_read': TriState.CHECKED,
            'owner_write': TriState.MIXED,  # Will not contribute to mode
            'owner_exec': TriState.UNCHECKED,
            'group_read': TriState.CHECKED,
            'group_write': TriState.UNCHECKED,
            'group_exec': TriState.UNCHECKED,
            'other_read': TriState.CHECKED,
            'other_write': TriState.UNCHECKED,
            'other_exec': TriState.UNCHECKED,
            'setuid': TriState.UNCHECKED,
            'setgid': TriState.UNCHECKED,
            'sticky': TriState.UNCHECKED,
        }
        dialog = ChmodDialog(file_count=3, initial_states=bit_states)

        # Mixed bits should not be included in result mode
        # Only CHECKED bits contribute: owner_read, group_read, other_read = 0o444
        mode = dialog.get_result_mode()
        self.assertEqual(mode, 0o444)

    def test_get_octal_preview(self):
        """get_octal_preview returns formatted octal string."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o755)
        self.assertEqual(dialog.get_octal_preview(), '0755')

        dialog = ChmodDialog(file_count=1, initial_mode=0o4755)
        self.assertEqual(dialog.get_octal_preview(), '4755')


class TestChmodDialogRecursive(unittest.TestCase):
    """Tests for recursive checkbox."""

    def test_recursive_checkbox_available_for_directory(self):
        """Recursive checkbox is available when directory is selected."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o755, has_directory=True)
        self.assertTrue(dialog.has_directory)
        self.assertFalse(dialog.recursive)  # Off by default

    def test_toggle_recursive(self):
        """Can toggle recursive option."""
        dialog = ChmodDialog(file_count=1, initial_mode=0o755, has_directory=True)

        dialog.toggle_recursive()
        self.assertTrue(dialog.recursive)

        dialog.toggle_recursive()
        self.assertFalse(dialog.recursive)


if __name__ == '__main__':
    unittest.main()
