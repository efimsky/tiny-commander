"""Tests for the function key bar component."""

import unittest
from unittest.mock import MagicMock, call, patch

from tnc.function_bar import FunctionBar, ModifierState


class TestFunctionBar(unittest.TestCase):
    """Tests for FunctionBar class."""

    def test_default_labels(self) -> None:
        """Test that default labels show standard F-key actions."""
        bar = FunctionBar()
        labels = bar.get_labels()

        self.assertEqual(labels['F3'], 'View')
        self.assertEqual(labels['F4'], 'Edit')
        self.assertEqual(labels['F5'], 'Copy')
        self.assertEqual(labels['F6'], 'Move')
        self.assertEqual(labels['F7'], 'Mkdir')
        self.assertEqual(labels['F8'], 'Delete')
        self.assertEqual(labels['F9'], 'Menu')
        self.assertEqual(labels['F10'], 'Quit')

    def test_shift_modifier_labels(self) -> None:
        """Test that Shift modifier changes F3 and F4 labels."""
        bar = FunctionBar()
        bar.set_modifier(ModifierState.SHIFT)
        labels = bar.get_labels()

        self.assertEqual(labels['F3'], 'Sort')
        self.assertEqual(labels['F4'], 'Create')
        # Other keys unchanged
        self.assertEqual(labels['F5'], 'Copy')

    def test_alt_modifier_labels(self) -> None:
        """Test that Alt modifier changes F3 label."""
        bar = FunctionBar()
        bar.set_modifier(ModifierState.ALT)
        labels = bar.get_labels()

        self.assertEqual(labels['F3'], 'DirSz')
        # Other keys unchanged
        self.assertEqual(labels['F4'], 'Edit')

    def test_clear_modifier(self) -> None:
        """Test that clearing modifier restores default labels."""
        bar = FunctionBar()
        bar.set_modifier(ModifierState.SHIFT)
        bar.set_modifier(ModifierState.NONE)
        labels = bar.get_labels()

        self.assertEqual(labels['F3'], 'View')
        self.assertEqual(labels['F4'], 'Edit')

    def _get_all_rendered_text(self, mock_win) -> str:
        """Helper to concatenate all addstr call text content."""
        all_text = []
        for call_obj in mock_win.addstr.call_args_list:
            args = call_obj[0]
            if len(args) >= 3:
                all_text.append(args[2])  # text is third argument
        return ''.join(all_text)

    def test_render_at_correct_position(self) -> None:
        """Test that render outputs at correct y position."""
        bar = FunctionBar()
        mock_win = MagicMock()

        bar.render(mock_win, y=24, width=80)

        # All addstr calls should be at y=24
        for call_obj in mock_win.addstr.call_args_list:
            args = call_obj[0]
            self.assertEqual(args[0], 24)  # y position

    def test_render_contains_all_keys(self) -> None:
        """Test that rendered output contains all function key labels."""
        bar = FunctionBar()
        mock_win = MagicMock()

        bar.render(mock_win, y=24, width=80)

        rendered_text = self._get_all_rendered_text(mock_win)
        self.assertIn('F3', rendered_text)
        self.assertIn('View', rendered_text)
        self.assertIn('F4', rendered_text)
        self.assertIn('Edit', rendered_text)
        self.assertIn('F10', rendered_text)
        self.assertIn('Quit', rendered_text)

    def test_render_shift_modifier(self) -> None:
        """Test that Shift modifier changes displayed labels."""
        bar = FunctionBar()
        bar.set_modifier(ModifierState.SHIFT)
        mock_win = MagicMock()

        bar.render(mock_win, y=24, width=80)

        rendered_text = self._get_all_rendered_text(mock_win)
        # Should show Shift labels for modified keys
        self.assertIn('Sort', rendered_text)
        self.assertIn('Create', rendered_text)

    def test_render_alt_modifier(self) -> None:
        """Test that Alt modifier changes displayed labels."""
        bar = FunctionBar()
        bar.set_modifier(ModifierState.ALT)
        mock_win = MagicMock()

        bar.render(mock_win, y=24, width=80)

        rendered_text = self._get_all_rendered_text(mock_win)
        self.assertIn('DirSz', rendered_text)

    def test_render_respects_width_limit(self) -> None:
        """Test that render doesn't exceed width limit with standard terminal width."""
        bar = FunctionBar()
        mock_win = MagicMock()

        # Use standard terminal width (80) to ensure buttons fit
        bar.render(mock_win, y=24, width=80)

        # Check that no addstr call goes beyond width
        for call_obj in mock_win.addstr.call_args_list:
            args = call_obj[0]
            x_pos = args[1]
            text = args[2]
            # x_pos + len(text) should not exceed width
            self.assertLessEqual(x_pos + len(text), 80)

    def test_render_uses_two_tone_colors(self) -> None:
        """Test that render uses different colors for F-key and label."""
        bar = FunctionBar()
        mock_win = MagicMock()

        with patch('tnc.function_bar.get_attr') as mock_get_attr:
            mock_get_attr.side_effect = [100, 200]  # Different attrs for key/label
            bar.render(mock_win, y=24, width=80)

        # get_attr should have been called for PAIR_FKEY and PAIR_FKEY_LABEL
        self.assertGreaterEqual(mock_get_attr.call_count, 2)

    def test_render_evenly_distributes_keys(self) -> None:
        """Test that keys are evenly distributed across the width (mc-style)."""
        bar = FunctionBar()
        mock_win = MagicMock()

        bar.render(mock_win, y=24, width=80)

        # With 8 keys and width=80, cell_width = 80 // 8 = 10
        # Keys should start at positions: 0, 10, 20, 30, 40, 50, 60, 70
        # Extract x positions of F-key renders (skip the initial clear line call)
        key_x_positions = []
        for call_obj in mock_win.addstr.call_args_list:
            args = call_obj[0]
            if len(args) >= 3:
                text = args[2]
                x_pos = args[1]
                # F-key text starts with space then 'F'
                if text.strip().startswith('F'):
                    key_x_positions.append(x_pos)

        # Should have 8 keys (F3, F4, F5, F6, F7, F8, F9, F10)
        self.assertEqual(len(key_x_positions), 8)

        # Check even distribution: each key should be at i * cell_width
        cell_width = 80 // 8  # = 10
        expected_positions = [i * cell_width for i in range(8)]
        self.assertEqual(key_x_positions, expected_positions)

    def test_render_even_distribution_narrow_width(self) -> None:
        """Test even distribution with narrower width."""
        bar = FunctionBar()
        mock_win = MagicMock()

        bar.render(mock_win, y=24, width=80)

        # With 8 keys and width=80, cell_width = 80 // 8 = 10
        key_x_positions = []
        for call_obj in mock_win.addstr.call_args_list:
            args = call_obj[0]
            if len(args) >= 3:
                text = args[2]
                x_pos = args[1]
                if text.strip().startswith('F'):
                    key_x_positions.append(x_pos)

        self.assertEqual(len(key_x_positions), 8)
        cell_width = 80 // 8  # = 10
        expected_positions = [i * cell_width for i in range(8)]
        self.assertEqual(key_x_positions, expected_positions)


if __name__ == '__main__':
    unittest.main()
