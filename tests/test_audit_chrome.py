"""Regression tests for terminal chrome UI audit fixes (#111, #112, #113)."""

import curses
import unittest
from unittest import mock

from tnc.colors import (
    PAIR_BROKEN_LINK,
    PAIR_CMDLINE,
    PAIR_DIRECTORY,
    PAIR_EXECUTABLE,
    PAIR_HIDDEN,
    PAIR_PANEL,
    PAIR_SELECTED,
    PAIR_STATUS,
    PAIR_SYMLINK,
    ColorManager,
)
from tnc.command_line import CommandLine
from tnc.function_bar import FunctionBar, ModifierState


class TestCommandLineHorizontalScrolling(unittest.TestCase):
    """Tests for issue #113: CommandLine horizontal scrolling & single display pass."""

    def test_compute_display_returns_text_and_cursor_tuple(self) -> None:
        """_compute_display should return (display_text, cursor_screen_x)."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'ls -la'
        cmdline.cursor_pos = 6

        result = cmdline._compute_display(80)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        display, cursor_x = result
        self.assertEqual(display, '/tmp> ls -la')
        self.assertEqual(cursor_x, len('/tmp> ') + 6)

    def test_long_input_collapses_prompt_and_scrolls_to_cursor_tail(self) -> None:
        """Input exceeding width collapses prompt to '> ' and scrolls around cursor."""
        cmdline = CommandLine('/very/long/directory/path/that/exceeds/width')
        cmdline.input_text = 'echo ' + 'a' * 60
        cmdline.cursor_pos = len(cmdline.input_text)

        display, cursor_x = cmdline._compute_display(width=30)

        self.assertTrue(display.startswith('> '))
        self.assertLessEqual(len(display), 30)
        self.assertEqual(display, '> ' + 'a' * 27)
        self.assertEqual(cursor_x, 29)
        self.assertEqual(cmdline.get_display_text(30), display)
        self.assertEqual(cmdline.get_cursor_screen_pos(30), cursor_x)

    def test_long_input_cursor_in_middle_stays_visible(self) -> None:
        """Moving cursor left/home inside long input shifts visible window."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = '0123456789abcdefghijABCDEFGHIJ'
        width = 20  # prompt '> ' (2) + max_input_width (17) + 1

        cmdline.cursor_pos = 0
        display, cursor_x = cmdline._compute_display(width)
        self.assertEqual(display, '> 0123456789abcdefg')
        self.assertEqual(cursor_x, 2)

        cmdline.cursor_pos = 5
        display, cursor_x = cmdline._compute_display(width)
        self.assertEqual(display, '> 0123456789abcdefg')
        self.assertEqual(cursor_x, 7)
        self.assertEqual(display[cursor_x], '5')

        cmdline.cursor_pos = 22
        display, cursor_x = cmdline._compute_display(width)
        self.assertEqual(display, '> 56789abcdefghijAB')
        self.assertEqual(cursor_x, 19)

    def test_narrow_and_non_positive_widths_guarded(self) -> None:
        """Widths <= 1 must return safe bounded values and render cleanly."""
        cmdline = CommandLine('/home/user')
        cmdline.input_text = 'ls -la'
        cmdline.cursor_pos = 4

        for width in (-5, 0, 1):
            display, cursor_x = cmdline._compute_display(width)
            self.assertEqual((display, cursor_x), ('', 0))

            mock_win = mock.MagicMock()
            returned_x = cmdline.render(mock_win, y=22, width=width)
            self.assertEqual(returned_x, 0)
            for call_obj in mock_win.addstr.call_args_list:
                text = call_obj[0][2]
                self.assertLessEqual(len(text), max(0, width))

    def test_render_computes_display_once(self) -> None:
        """render() should invoke _compute_display only once per render pass."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'echo hello'
        cmdline.cursor_pos = 10
        mock_win = mock.MagicMock()

        with mock.patch.object(
            cmdline, '_compute_display', wraps=cmdline._compute_display
        ) as spy_compute:
            cursor_x = cmdline.render(mock_win, y=22, width=80)

        spy_compute.assert_called_once_with(80)
        self.assertEqual(cursor_x, len('/tmp> echo hello'))


class TestFunctionBarLayoutAndClipping(unittest.TestCase):
    """Tests for issue #112: FunctionBar 80-col overlap & narrow width < 10."""

    def _capture_button_draws(
        self, bar: FunctionBar, width: int
    ) -> list[tuple[int, str]]:
        """Render FunctionBar and return (x, text) draws excluding full-line clear."""
        draws: list[tuple[int, str]] = []
        win = mock.MagicMock()

        def fake_addstr(_y: int, x: int, text: str, *_args, **_kwargs) -> None:
            draws.append((x, text))

        win.addstr.side_effect = fake_addstr
        bar.render(win, y=24, width=width)
        return [(x, t) for x, t in draws if not (x == 0 and len(t) == width)]

    def test_80_col_f8_clips_within_cell_and_never_overlaps_f9(self) -> None:
        """At width=80 (cell_width=8), F8 renders ' F8'+'Delet' in cols 56..63."""
        bar = FunctionBar()
        draws = self._capture_button_draws(bar, width=80)

        f8_draws = [(x, t) for x, t in draws if 56 <= x < 64]
        self.assertEqual(f8_draws, [(56, ' F8'), (59, 'Delet')])
        for x, text in draws:
            if x < 64:
                self.assertLessEqual(
                    x + len(text), 64, f'Button at x={x} ({text!r}) bled into F9 cell'
                )

    def test_80_col_all_modifiers_never_overlap_cells(self) -> None:
        """Across all modifier states at width=80, every button stays within its cell."""
        for mod in (ModifierState.NONE, ModifierState.SHIFT, ModifierState.ALT):
            bar = FunctionBar()
            bar.set_modifier(mod)
            draws = self._capture_button_draws(bar, width=80)
            for x, text in draws:
                cell_idx = x // 8
                cell_end = (cell_idx + 1) * 8
                self.assertLessEqual(
                    x + len(text),
                    cell_end,
                    f'Modifier {mod}: draw {(x, text)!r} exceeded cell end {cell_end}',
                )

    def test_width_30_clips_f10_within_width(self) -> None:
        """At width=30, no addstr call may write past column 30."""
        bar = FunctionBar()
        draws = self._capture_button_draws(bar, width=30)

        for x, text in draws:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(
                x + len(text), 30, f'Draw {(x, text)!r} exceeded width 30'
            )

    def test_width_less_than_ten_has_no_empty_regions_or_pileup(self) -> None:
        """Widths 1..9 must never create zero-width (0,0) regions or pile at col 0."""
        for width in (1, 5, 9):
            bar = FunctionBar()
            draws = self._capture_button_draws(bar, width=width)

            for start_x, end_x, _action in bar.button_positions:
                self.assertLess(start_x, end_x)
                self.assertGreaterEqual(start_x, 0)
                self.assertLessEqual(end_x, width)

            starts = [start_x for start_x, _, _ in bar.button_positions]
            self.assertEqual(len(starts), len(set(starts)))

            occupied: set[int] = set()
            for x, text in draws:
                self.assertLessEqual(x + len(text), width)
                cols = set(range(x, x + len(text)))
                self.assertFalse(
                    occupied & cols,
                    f'Overlapping button renders at width={width}: {draws!r}',
                )
                occupied |= cols

    def test_non_positive_width_guarded(self) -> None:
        """Widths <= 0 should clear button_positions and avoid rendering."""
        for width in (0, -4):
            bar = FunctionBar()
            win = mock.MagicMock()
            bar.render(win, y=24, width=width)
            self.assertEqual(bar.button_positions, [])
            win.addstr.assert_not_called()

    def test_backwards_compatible_members_preserved(self) -> None:
        """ModifierState, set_modifier, _get_key_number, and click feedback work."""
        bar = FunctionBar()
        bar.set_modifier(ModifierState.SHIFT)
        self.assertEqual(bar.get_labels()['F3'], 'Sort')
        self.assertEqual(bar._get_key_number('F10'), '10')
        bar.show_click_feedback('F5')
        self.assertEqual(bar.highlight_button, 'F5')
        bar.clear_click_feedback()
        self.assertIsNone(bar.highlight_button)


class TestColorManagerInitErrors(unittest.TestCase):
    """Tests for issue #111: ColorManager.init_colors curses.error handling."""

    @mock.patch('curses.init_pair')
    @mock.patch('curses.use_default_colors')
    @mock.patch('curses.start_color', side_effect=curses.error('start_color failed'))
    @mock.patch('curses.has_colors', return_value=True)
    def test_start_color_failure_returns_false_and_disables_colors(
        self, _mock_has, _mock_start, mock_default, mock_init_pair
    ) -> None:
        """If curses.start_color() raises curses.error, return False cleanly."""
        manager = ColorManager()

        result = manager.init_colors()

        self.assertFalse(result)
        self.assertFalse(manager.colors_enabled)
        mock_default.assert_not_called()
        mock_init_pair.assert_not_called()

    @mock.patch('curses.init_pair')
    @mock.patch(
        'curses.use_default_colors', side_effect=curses.error('no default colors')
    )
    @mock.patch('curses.start_color')
    @mock.patch('curses.has_colors', return_value=True)
    def test_use_default_colors_failure_classic_theme_maps_minus_one(
        self, _mock_has, _mock_start, _mock_default, mock_init_pair
    ) -> None:
        """If use_default_colors() fails, classic theme maps -1 to WHITE/BLACK."""
        manager = ColorManager(classic_theme=True)

        result = manager.init_colors()

        self.assertTrue(result)
        self.assertTrue(manager.colors_enabled)
        calls_by_pair = {call.args[0]: call.args[1:] for call in mock_init_pair.call_args_list}
        for pair, (fg, bg) in calls_by_pair.items():
            self.assertNotEqual(fg, -1, f'Pair {pair} kept fg=-1')
            self.assertNotEqual(bg, -1, f'Pair {pair} kept bg=-1')
        self.assertEqual(
            calls_by_pair[PAIR_CMDLINE], (curses.COLOR_WHITE, curses.COLOR_BLACK)
        )

    @mock.patch('curses.init_pair')
    @mock.patch(
        'curses.use_default_colors', side_effect=curses.error('no default colors')
    )
    @mock.patch('curses.start_color')
    @mock.patch('curses.has_colors', return_value=True)
    def test_use_default_colors_failure_modern_theme_maps_minus_one(
        self, _mock_has, _mock_start, _mock_default, mock_init_pair
    ) -> None:
        """If use_default_colors() fails, modern theme maps -1 to WHITE/BLACK."""
        manager = ColorManager(classic_theme=False)

        result = manager.init_colors()

        self.assertTrue(result)
        self.assertTrue(manager.colors_enabled)
        calls_by_pair = {call.args[0]: call.args[1:] for call in mock_init_pair.call_args_list}
        for pair, (fg, bg) in calls_by_pair.items():
            self.assertNotEqual(fg, -1, f'Pair {pair} kept fg=-1')
            self.assertNotEqual(bg, -1, f'Pair {pair} kept bg=-1')
        self.assertEqual(
            calls_by_pair[PAIR_PANEL], (curses.COLOR_WHITE, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_DIRECTORY], (curses.COLOR_BLUE, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_SELECTED], (curses.COLOR_YELLOW, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_EXECUTABLE], (curses.COLOR_GREEN, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_SYMLINK], (curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_BROKEN_LINK], (curses.COLOR_RED, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_HIDDEN], (curses.COLOR_CYAN, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_STATUS], (curses.COLOR_WHITE, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_CMDLINE], (curses.COLOR_WHITE, curses.COLOR_BLACK)
        )

    @mock.patch('curses.init_pair')
    @mock.patch(
        'curses.use_default_colors', side_effect=curses.error('no default colors')
    )
    @mock.patch('curses.start_color')
    @mock.patch('curses.has_colors', return_value=True)
    def test_theme_toggle_after_use_default_colors_failure_still_maps_minus_one(
        self, _mock_has, _mock_start, _mock_default, mock_init_pair
    ) -> None:
        """Toggling to modern theme later must preserve the fallback mapping."""
        manager = ColorManager(classic_theme=True)
        self.assertTrue(manager.init_colors())

        mock_init_pair.reset_mock()
        manager.set_classic_theme(False)

        calls_by_pair = {call.args[0]: call.args[1:] for call in mock_init_pair.call_args_list}
        self.assertEqual(
            calls_by_pair[PAIR_PANEL], (curses.COLOR_WHITE, curses.COLOR_BLACK)
        )
        self.assertEqual(
            calls_by_pair[PAIR_DIRECTORY], (curses.COLOR_BLUE, curses.COLOR_BLACK)
        )


if __name__ == '__main__':
    unittest.main()
