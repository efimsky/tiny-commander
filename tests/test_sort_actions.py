"""Tests for sort action handling in App class."""

import tempfile
import unittest
from unittest import mock

from tests.helpers import create_mock_stdscr
from tnc.app import Action, App, _SORT_ACTIONS


def _patch_curses(func):
    """Decorator to patch curses functions for tests."""
    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    return wrapper


class TestSortActionsMapping(unittest.TestCase):
    """Test the _SORT_ACTIONS mapping."""

    def test_sort_actions_mapping_exists(self):
        """_SORT_ACTIONS mapping should exist and contain all sort actions."""
        self.assertIsInstance(_SORT_ACTIONS, dict)
        self.assertEqual(len(_SORT_ACTIONS), 10)

    def test_sort_actions_contains_left_panel_sorts(self):
        """Mapping should contain all left panel sort actions."""
        self.assertIn(Action.SORT_NAME_LEFT, _SORT_ACTIONS)
        self.assertIn(Action.SORT_SIZE_LEFT, _SORT_ACTIONS)
        self.assertIn(Action.SORT_DATE_LEFT, _SORT_ACTIONS)
        self.assertIn(Action.SORT_EXT_LEFT, _SORT_ACTIONS)
        self.assertIn(Action.REVERSE_SORT_LEFT, _SORT_ACTIONS)

    def test_sort_actions_contains_right_panel_sorts(self):
        """Mapping should contain all right panel sort actions."""
        self.assertIn(Action.SORT_NAME_RIGHT, _SORT_ACTIONS)
        self.assertIn(Action.SORT_SIZE_RIGHT, _SORT_ACTIONS)
        self.assertIn(Action.SORT_DATE_RIGHT, _SORT_ACTIONS)
        self.assertIn(Action.SORT_EXT_RIGHT, _SORT_ACTIONS)
        self.assertIn(Action.REVERSE_SORT_RIGHT, _SORT_ACTIONS)

    def test_sort_actions_left_panel_values(self):
        """Left panel actions should map to 'left_panel'."""
        for action in [Action.SORT_NAME_LEFT, Action.SORT_SIZE_LEFT,
                       Action.SORT_DATE_LEFT, Action.SORT_EXT_LEFT,
                       Action.REVERSE_SORT_LEFT]:
            panel_attr, _ = _SORT_ACTIONS[action]
            self.assertEqual(panel_attr, 'left_panel')

    def test_sort_actions_right_panel_values(self):
        """Right panel actions should map to 'right_panel'."""
        for action in [Action.SORT_NAME_RIGHT, Action.SORT_SIZE_RIGHT,
                       Action.SORT_DATE_RIGHT, Action.SORT_EXT_RIGHT,
                       Action.REVERSE_SORT_RIGHT]:
            panel_attr, _ = _SORT_ACTIONS[action]
            self.assertEqual(panel_attr, 'right_panel')

    def test_sort_actions_reverse_has_none_sort_type(self):
        """Reverse sort actions should have None as sort_type."""
        _, sort_type = _SORT_ACTIONS[Action.REVERSE_SORT_LEFT]
        self.assertIsNone(sort_type)
        _, sort_type = _SORT_ACTIONS[Action.REVERSE_SORT_RIGHT]
        self.assertIsNone(sort_type)


class TestHandleSortAction(unittest.TestCase):
    """Test App._handle_sort_action method."""

    @_patch_curses
    def test_handle_sort_action_left_panel_name(self, *_):
        """_handle_sort_action should call left_panel.sort_by('name')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.left_panel.sort_by = mock.MagicMock()

                app._handle_sort_action(Action.SORT_NAME_LEFT)

                app.left_panel.sort_by.assert_called_once_with('name')

    @_patch_curses
    def test_handle_sort_action_right_panel_size(self, *_):
        """_handle_sort_action should call right_panel.sort_by('size')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.right_panel.sort_by = mock.MagicMock()

                app._handle_sort_action(Action.SORT_SIZE_RIGHT)

                app.right_panel.sort_by.assert_called_once_with('size')

    @_patch_curses
    def test_handle_sort_action_reverse_left(self, *_):
        """_handle_sort_action should call left_panel.toggle_sort_reverse()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.left_panel.toggle_sort_reverse = mock.MagicMock()

                app._handle_sort_action(Action.REVERSE_SORT_LEFT)

                app.left_panel.toggle_sort_reverse.assert_called_once()

    @_patch_curses
    def test_handle_sort_action_reverse_right(self, *_):
        """_handle_sort_action should call right_panel.toggle_sort_reverse()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch('os.getcwd', return_value=tmpdir):
                app = App(create_mock_stdscr())
                app.setup()
                app.right_panel.toggle_sort_reverse = mock.MagicMock()

                app._handle_sort_action(Action.REVERSE_SORT_RIGHT)

                app.right_panel.toggle_sort_reverse.assert_called_once()


if __name__ == '__main__':
    unittest.main()
