"""Tests for the main App class - curses initialization and cleanup."""

import unittest
from unittest import mock

from tnc.app import App, run_app


def create_mock_stdscr(rows: int = 24, cols: int = 80) -> mock.MagicMock:
    """Create a mock curses stdscr object with specified dimensions."""
    mock_stdscr = mock.MagicMock()
    mock_stdscr.getmaxyx.return_value = (rows, cols)
    mock_stdscr.getch.return_value = ord('y')
    return mock_stdscr


class TestCursesInitialization(unittest.TestCase):
    """Test that curses is initialized properly."""

    def test_app_uses_curses_wrapper(self):
        """App should use curses.wrapper for safe setup/teardown."""
        with mock.patch('curses.wrapper') as mock_wrapper:
            mock_wrapper.return_value = 0
            exit_code = run_app()
            mock_wrapper.assert_called_once()
            self.assertEqual(exit_code, 0)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_app_hides_cursor(self, mock_curs_set, _mock_has_colors):
        """App should hide the cursor during operation."""
        app = App(create_mock_stdscr())
        app.setup()
        mock_curs_set.assert_called_with(0)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_app_enables_keypad(self, _mock_curs_set, _mock_has_colors):
        """App should enable keypad mode for function keys."""
        mock_stdscr = create_mock_stdscr()
        app = App(mock_stdscr)
        app.setup()
        mock_stdscr.keypad.assert_called_with(True)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_cleanup_restores_cursor(self, mock_curs_set, _mock_has_colors):
        """App should restore cursor on cleanup."""
        app = App(create_mock_stdscr())
        app.setup()
        app.cleanup()
        self.assertEqual(mock_curs_set.call_args_list[-1], mock.call(1))

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('curses.doupdate')
    def test_cleanup_on_exception(self, _mock_doupdate, mock_curs_set, _mock_has_colors):
        """Terminal should be restored even if exception occurs."""
        mock_stdscr = create_mock_stdscr()
        mock_stdscr.getch.side_effect = RuntimeError("test")

        app = App(mock_stdscr)
        app.setup()
        try:
            app.run()
        except RuntimeError:
            pass
        finally:
            app.cleanup()

        self.assertEqual(mock_curs_set.call_args_list[-1], mock.call(1))


class TestCursesCleanQuit(unittest.TestCase):
    """Test that app quits cleanly."""

    def test_quit_returns_zero_exit_code(self):
        """Normal quit should return exit code 0."""
        with mock.patch('curses.wrapper') as mock_wrapper:
            mock_wrapper.return_value = 0
            exit_code = run_app()
            self.assertEqual(exit_code, 0)


class TestActionHandlers(unittest.TestCase):
    """Test action handler dictionary pattern."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_action_handlers_dict_exists(self, _mock_curs_set, _mock_has_colors):
        """App should have _action_handlers dictionary after setup."""
        app = App(create_mock_stdscr())
        app.setup()
        self.assertTrue(hasattr(app, '_action_handlers'))
        self.assertIsInstance(app._action_handlers, dict)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_action_handlers_contains_copy(self, _mock_curs_set, _mock_has_colors):
        """Action handlers should contain COPY action."""
        from tnc.app import Action
        app = App(create_mock_stdscr())
        app.setup()
        self.assertIn(Action.COPY, app._action_handlers)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_action_handlers_contains_move(self, _mock_curs_set, _mock_has_colors):
        """Action handlers should contain MOVE action."""
        from tnc.app import Action
        app = App(create_mock_stdscr())
        app.setup()
        self.assertIn(Action.MOVE, app._action_handlers)

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_action_handlers_contains_all_sort_actions(self, _mock_curs_set, _mock_has_colors):
        """Action handlers should contain all sort actions."""
        from tnc.app import Action
        app = App(create_mock_stdscr())
        app.setup()
        sort_actions = [
            Action.SORT_NAME_LEFT, Action.SORT_SIZE_LEFT,
            Action.SORT_DATE_LEFT, Action.SORT_EXT_LEFT,
            Action.SORT_NAME_RIGHT, Action.SORT_SIZE_RIGHT,
            Action.SORT_DATE_RIGHT, Action.SORT_EXT_RIGHT,
            Action.REVERSE_SORT_LEFT, Action.REVERSE_SORT_RIGHT,
        ]
        for action in sort_actions:
            self.assertIn(action, app._action_handlers, f"Missing handler for {action}")

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_action_handlers_are_callable(self, _mock_curs_set, _mock_has_colors):
        """All action handlers should be callable."""
        app = App(create_mock_stdscr())
        app.setup()
        for action, handler in app._action_handlers.items():
            self.assertTrue(callable(handler), f"Handler for {action} is not callable")

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_action_handlers_excludes_quit_and_none(self, _mock_curs_set, _mock_has_colors):
        """QUIT and NONE should not be in action handlers (handled specially)."""
        from tnc.app import Action
        app = App(create_mock_stdscr())
        app.setup()
        self.assertNotIn(Action.QUIT, app._action_handlers)
        self.assertNotIn(Action.NONE, app._action_handlers)


class TestShowError(unittest.TestCase):
    """Test _show_error method uses modal dialog."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    @mock.patch('tnc.app.show_error_dialog')
    def test_show_error_uses_modal_dialog(self, mock_error_dialog, _mock_curs_set, _mock_has_colors):
        """_show_error should use show_error_dialog for modal display."""
        mock_stdscr = create_mock_stdscr()
        app = App(mock_stdscr)
        app.setup()

        app._show_error("Something went wrong")

        mock_error_dialog.assert_called_once()
        # Verify the call includes the error message
        call_args = mock_error_dialog.call_args
        self.assertEqual(call_args[0][1], "Error")  # title
        self.assertEqual(call_args[0][2], "Something went wrong")  # message


if __name__ == '__main__':
    unittest.main()
