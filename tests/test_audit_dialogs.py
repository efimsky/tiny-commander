"""Regression and audit tests for modal/dialog fixes (#96-#106 and hooks)."""

import curses
import stat
import unittest
from unittest import mock

from tnc.dialog import (
    ChmodDialog,
    ChownDialog,
    ConfirmModal,
    ErrorModal,
    HelpModal,
    InputDialog,
    OverwriteModal,
    SelectionDialog,
    SummaryModal,
    draw_modal,
    format_time,
)
from tnc.file_ops import OverwriteChoice
from tnc.modal import Button, ButtonBar, Modal
from tnc.permissions import TriState


def _rendered_rows_by_y(win: mock.MagicMock) -> dict[int, list[tuple[int, str]]]:
    """Collect addstr(y, x, text, ...) calls grouped by row y."""
    rows: dict[int, list[tuple[int, str]]] = {}
    for call in win.addstr.call_args_list:
        args = call[0]
        if len(args) >= 3 and isinstance(args[0], int) and isinstance(args[2], str):
            y, x, text = args[0], args[1], args[2]
            rows.setdefault(y, []).append((x, text))
    return rows


def _rendered_texts(win: mock.MagicMock) -> list[str]:
    """Extract all string arguments passed to win.addstr."""
    texts: list[str] = []
    for call in win.addstr.call_args_list:
        args = call[0]
        if len(args) >= 3 and isinstance(args[2], str):
            texts.append(args[2])
    return texts


class TestErrorModalMultiLine(unittest.TestCase):
    """#96: ErrorModal splits multi-line message and details cleanly."""

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_multiline_message_splits_into_separate_bordered_lines(self, _attr):
        msg = 'Chmod succeeded on 2 of 4 files.\na.txt: Permission denied\nb.txt: Read-only'
        modal = ErrorModal('Error', msg)
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)

        modal.render(win)

        texts = _rendered_texts(win)
        for text in texts:
            self.assertNotIn('\n', text)
        # All full box rows (starting and ending with │, excluding single-char
        # title side borders) should have uniform width == modal._width.
        box_rows = [t for t in texts if t.startswith('│') and t.endswith('│') and len(t) > 1]
        self.assertGreaterEqual(len(box_rows), 4)
        for row in box_rows:
            self.assertEqual(len(row), modal._width)
        joined = '\n'.join(texts)
        self.assertIn('Chmod succeeded on 2 of 4 files.', joined)
        self.assertIn('a.txt: Permission denied', joined)
        self.assertIn('b.txt: Read-only', joined)
        # Width should be based on longest individual line, not total msg length.
        self.assertLess(modal._width, len(msg))

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_multiline_details_and_empty_message(self, _attr):
        modal = ErrorModal('Error', '', details=['first line\nsecond line'])
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)

        modal.render(win)

        texts = _rendered_texts(win)
        for text in texts:
            self.assertNotIn('\n', text)
        joined = '\n'.join(texts)
        self.assertIn('first line', joined)
        self.assertIn('second line', joined)


class TestOverwriteModalButtonLayout(unittest.TestCase):
    """#97: OverwriteModal width >= 64 and ButtonBar prevents overlap."""

    def _make_overwrite(self) -> OverwriteModal:
        return OverwriteModal(
            filename='a.txt',
            source_size=100,
            dest_size=200,
            source_mtime=1705329000.0,
            dest_mtime=1705329000.0,
            current=1,
            total=1,
        )

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_overwrite_modal_width_at_least_64_and_buttons_non_overlapping(self, _attr):
        modal = self._make_overwrite()
        self.assertGreaterEqual(modal._width, 64)

        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        modal.render(win)

        positions = modal.button_bar.button_positions
        self.assertEqual(len(positions), 5)
        for i in range(len(positions) - 1):
            _, cur_end, cur_y, _ = positions[i]
            next_start, _, next_y, _ = positions[i + 1]
            self.assertEqual(cur_y, next_y)
            self.assertLess(
                cur_end, next_start,
                f'Buttons {i} and {i + 1} touch or overlap: {positions}',
            )

    def test_button_bar_prevents_overlap_when_slot_smaller_than_text(self):
        buttons = [
            Button('Yes', 'y', OverwriteChoice.YES),
            Button('No', 'n', OverwriteChoice.NO),
            Button('All', 'a', OverwriteChoice.YES_ALL),
            Button('Skip', 's', OverwriteChoice.NO_ALL),
            Button('Older', 'o', OverwriteChoice.YES_OLDER),
        ]
        bar = ButtonBar(buttons, focused=4)
        win = mock.MagicMock()
        # Total chars of all 5 buttons = 9 + 8 + 9 + 10 + 11 = 47; slot_width = 9 < 11.
        bar.render(win, y=10, x_start=5, total_width=47)

        self.assertEqual(len(bar.button_positions), 5)
        for i, (start, end, y, _val) in enumerate(bar.button_positions):
            self.assertGreaterEqual(start, 5)
            self.assertLessEqual(end, 5 + 47)
            if i > 0:
                prev_end = bar.button_positions[i - 1][1]
                self.assertGreaterEqual(start, prev_end)

    def test_button_bar_narrow_width_never_overlaps_or_overflows(self):
        buttons = [
            Button('AlphaLong', 'a', 1),
            Button('BravoLong', 'b', 2),
        ]
        bar = ButtonBar(buttons, focused=0)
        win = mock.MagicMock()
        bar.render(win, y=5, x_start=10, total_width=20)

        for i, (start, end, _y, _val) in enumerate(bar.button_positions):
            self.assertGreaterEqual(start, 10)
            self.assertLessEqual(end, 30)
            self.assertLess(start, end)
            if i > 0:
                self.assertGreaterEqual(start, bar.button_positions[i - 1][1])


class TestInputDialogButtonBorder(unittest.TestCase):
    """#98: InputDialog renders side borders on the button row."""

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_button_row_has_left_and_right_borders(self, _attr):
        dialog = InputDialog('Title', 'Enter name:')
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)

        dialog.render(win)

        btn_y = dialog.button_bar.button_positions[0][2]
        rows = _rendered_rows_by_y(win)
        btn_calls = rows[btn_y]
        # The first call on btn_y should be the full empty bordered frame line.
        border_calls = [
            (x, text) for x, text in btn_calls
            if text.startswith('│') and text.endswith('│')
        ]
        self.assertTrue(
            border_calls,
            f'Expected side borders on button row y={btn_y}, saw {btn_calls!r}',
        )


class TestSelectionDialogLayout(unittest.TestCase):
    """#99: SelectionDialog hint width, height, clamping, and custom text scroll."""

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_dimensions_and_rendered_height_match_in_selection_mode(self, _attr):
        dialog = SelectionDialog('Pick', ['a', 'b'], allow_custom=True)
        width, height = dialog.get_dimensions()
        # 2 options + 1 Custom = 3 items -> height = 3 + 6 = 9
        self.assertEqual(height, 9)

        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        dialog.render(win)

        rows = _rendered_rows_by_y(win)
        min_y, max_y = min(rows), max(rows)
        self.assertEqual(max_y - min_y + 1, height)
        # Every row (including 3-part title row and content/border rows) matches width.
        for _y, entries in rows.items():
            self.assertEqual(sum(len(text) for _x, text in entries), width)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_dimensions_and_rendered_height_match_in_custom_mode(self, _attr):
        dialog = SelectionDialog('Pick', ['a'], allow_custom=True)
        dialog.in_custom_input_mode = True
        width, height = dialog.get_dimensions()
        self.assertEqual(height, 8)
        self.assertGreaterEqual(width, len('[Enter] to confirm, [Esc] to cancel') + 4)

        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        dialog.render(win)

        rows = _rendered_rows_by_y(win)
        self.assertEqual(max(rows) - min(rows) + 1, 8)
        for _y, entries in rows.items():
            self.assertEqual(sum(len(text) for _x, text in entries), width)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_narrow_terminal_clamps_width_and_scrolls_long_custom_text(self, _attr):
        dialog = SelectionDialog('Very Long Dialog Title Here', ['a' * 60], allow_custom=True)
        dialog.in_custom_input_mode = True
        dialog.custom_text = 'x' * 80 + 'TAIL'

        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 34)
        dialog.render(win)

        # Clamped width = max(34 - 2, 20) = 32
        rows = _rendered_rows_by_y(win)
        for _y, entries in rows.items():
            for x, _text in entries:
                self.assertGreaterEqual(x, 0)
            self.assertEqual(sum(len(text) for _x, text in entries), 32)
        joined = '\n'.join(_rendered_texts(win))
        self.assertIn('TAIL_', joined)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_small_terminal_clamps_start_coords_non_negative(self, _attr):
        dialog = SelectionDialog('Pick', [f'opt{i}' for i in range(15)])
        win = mock.MagicMock()
        win.getmaxyx.return_value = (10, 25)
        dialog.render(win)

        for call in win.addstr.call_args_list:
            y, x = call[0][0], call[0][1]
            self.assertGreaterEqual(y, 0)
            self.assertGreaterEqual(x, 0)


class TestDrawModalTruncationAndClamping(unittest.TestCase):
    """#100: _clamp_modal_width, frame truncation, and clamped ButtonBar width."""

    def test_clamp_modal_width_helper(self):
        from tnc.dialog import _clamp_modal_width

        self.assertEqual(_clamp_modal_width(30, 80), 30)
        self.assertEqual(_clamp_modal_width(100, 40), 38)
        self.assertEqual(_clamp_modal_width(50, 15), 20)

    def test_render_dialog_frame_truncates_title_and_content(self):
        from tnc.dialog import _render_dialog_frame

        frame = _render_dialog_frame(20, 'T' * 50)
        self.assertEqual(len(frame['title_content']), 18)
        line = frame['content_line']('C' * 50)
        self.assertEqual(len(line), 20)
        self.assertTrue(line.startswith('│ '))
        self.assertTrue(line.endswith(' │'))

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_draw_modal_returns_tuple_and_truncates_long_lines(self, _attr):
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 30)
        pos = draw_modal(win, 'A' * 60, ['B' * 60], width=50)
        self.assertIsInstance(pos, tuple)
        self.assertEqual(len(pos), 2)
        # Clamped width on 30-col terminal is 28.
        for text in _rendered_texts(win):
            self.assertLessEqual(len(text), 28)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_modals_pass_clamped_width_to_button_bar(self, _attr):
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 30)
        # Clamped modal width on 30 cols = 28 -> total_width = 24
        modals = [
            ConfirmModal('T', 'M' * 50),
            OverwriteModal('f.txt', 1, 1, 1000.0, 1000.0, 1, 1),
            ErrorModal('Err', 'M' * 50),
            HelpModal(),
        ]
        for modal in modals:
            with self.subTest(modal=type(modal).__name__):
                with mock.patch.object(
                    modal.button_bar, 'render', wraps=modal.button_bar.render
                ) as spy_render:
                    modal.render(win)
                    spy_render.assert_called_once()
                    self.assertEqual(spy_render.call_args.kwargs['total_width'], 24)


class TestHelpModalScrolling(unittest.TestCase):
    """#101: HelpModal scrolls cleanly on 24-row terminals."""

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_24_row_terminal_fits_with_ok_button_and_scroll_hint(self, _attr):
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)

        modal.render(win)

        rows = _rendered_rows_by_y(win)
        min_y, max_y = min(rows), max(rows)
        self.assertGreaterEqual(min_y, 0)
        self.assertLess(max_y, 24)
        self.assertLessEqual(max_y - min_y + 1, 22)

        self.assertEqual(len(modal.button_bar.button_positions), 1)
        btn_y = modal.button_bar.button_positions[0][2]
        self.assertLess(btn_y, max_y)
        joined = '\n'.join(_rendered_texts(win))
        self.assertIn('scroll', joined.lower())
        self.assertGreater(modal._max_scroll, 0)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_scroll_keys_scroll_without_dismissing_and_reveal_bottom(self, _attr):
        modal = HelpModal()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)

        modal.render(win)
        self.assertEqual(modal._scroll_offset, 0)
        max_scroll = modal._max_scroll

        modal.handle_key(curses.KEY_DOWN)
        self.assertFalse(modal._done)
        self.assertEqual(modal._scroll_offset, 1)

        modal.handle_key(curses.KEY_UP)
        self.assertFalse(modal._done)
        self.assertEqual(modal._scroll_offset, 0)

        modal.handle_key(curses.KEY_NPAGE)
        self.assertFalse(modal._done)
        self.assertGreater(modal._scroll_offset, 0)

        modal.handle_key(curses.KEY_PPAGE)
        self.assertFalse(modal._done)
        self.assertEqual(modal._scroll_offset, 0)

        modal.handle_key(curses.KEY_END)
        self.assertFalse(modal._done)
        self.assertEqual(modal._scroll_offset, max_scroll)

        win.reset_mock()
        modal.render(win)
        self.assertIn('Alt+O', '\n'.join(_rendered_texts(win)))

        modal.handle_key(curses.KEY_HOME)
        self.assertFalse(modal._done)
        self.assertEqual(modal._scroll_offset, 0)

        # Non-scroll key dismisses.
        modal.handle_key(ord('q'))
        self.assertTrue(modal._done)


class TestChmodDialogFixes(unittest.TestCase):
    """#102: ChmodDialog hit-target coords, directory height, clamping/truncation."""

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_grid_and_special_left_edge_click_targets(self, _attr):
        d = ChmodDialog(file_count=1, initial_mode=0o644)
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        d.render(win)

        width, _ = d.get_dimensions()
        start_x = (80 - width) // 2

        # Grid col 0 left edge is start_x + 12 (previously 13).
        grid_0_0 = next(t for t in d._click_targets if t[3] == 'grid:0:0')
        self.assertEqual(grid_0_0[0], start_x + 12)
        self.assertEqual(grid_0_0[1], start_x + 17)

        # Special col 0..2 left edge is start_x + 14 + col * 15 (previously 12).
        for col in range(3):
            spec = next(t for t in d._click_targets if t[3] == f'special:{col}')
            self.assertEqual(spec[0], start_x + 14 + col * 15)
            self.assertEqual(spec[1], start_x + 19 + col * 15)

        # Clicking the exact '[' char of special:0 (start_x + 15) toggles setuid.
        before = d.get_bit_state('setuid')
        d.handle_click(start_x + 15, spec[2], curses.BUTTON1_CLICKED)
        self.assertNotEqual(d.get_bit_state('setuid'), before)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_directory_height_matches_rendered_rows_and_truncates_filename(self, _attr):
        d = ChmodDialog(file_count=1, initial_mode=0o755, has_directory=True, filename='x' * 100)
        width, height = d.get_dimensions()
        self.assertEqual(height, 16)

        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        d.render(win)

        rows = _rendered_rows_by_y(win)
        self.assertEqual(max(rows) - min(rows) + 1, height)
        for text in _rendered_texts(win):
            self.assertEqual(len(text), width)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_small_terminal_clamps_start_coords(self, _attr):
        d = ChmodDialog(file_count=1, initial_mode=0o755, has_directory=True)
        win = mock.MagicMock()
        win.getmaxyx.return_value = (10, 40)
        d.render(win)

        for call in win.addstr.call_args_list:
            y, x = call[0][0], call[0][1]
            self.assertGreaterEqual(y, 0)
            self.assertGreaterEqual(x, 0)


class TestChownDialogAutocompleteViewport(unittest.TestCase):
    """#104: ChownDialog 5-row scrolling window, fixed height, single lookup."""

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_scrolling_window_highlights_item_beyond_fifth(self, _attr):
        users = [f'user{i:02d}' for i in range(10)]
        d = ChownDialog(
            file_count=1,
            current_owner='user',
            current_group='staff',
            users=users,
            groups=['staff'],
        )
        for _ in range(7):
            d.handle_key(curses.KEY_DOWN)
        self.assertEqual(d.autocomplete_index, 6)

        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        d.render(win)

        joined = '\n'.join(_rendered_texts(win))
        self.assertIn('> user06', joined)
        self.assertIn('  user02', joined)
        self.assertNotIn('user00', joined)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_fixed_height_repaints_all_rows_and_calls_suggestions_once(self, _attr):
        users = [f'user{i:02d}' for i in range(8)]
        d = ChownDialog(
            file_count=1,
            current_owner='user',
            current_group='staff',
            users=users,
            groups=['staff'],
            filename='y' * 100,
        )
        _, h_many = d.get_dimensions()
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)

        with mock.patch.object(
            d, 'get_autocomplete_suggestions', wraps=d.get_autocomplete_suggestions
        ) as spy_sug:
            d.render(win)
            self.assertEqual(spy_sug.call_count, 1)

        rows_many = set(_rendered_rows_by_y(win).keys())
        self.assertEqual(len(rows_many), h_many)

        # Shrink suggestions to 0 and verify exact same rows are repainted cleanly.
        d.owner_input = 'nomatch'
        _, h_none = d.get_dimensions()
        self.assertEqual(h_many, h_none)

        win.reset_mock()
        d.render(win)
        rows_none = set(_rendered_rows_by_y(win).keys())
        self.assertEqual(rows_many, rows_none)
        for text in _rendered_texts(win):
            self.assertEqual(len(text), 60)

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_small_terminal_clamps_start_coords(self, _attr):
        d = ChownDialog(file_count=1, current_owner='a', current_group='b', users=['a'], groups=['b'])
        win = mock.MagicMock()
        win.getmaxyx.return_value = (10, 40)
        d.render(win)

        for call in win.addstr.call_args_list:
            y, x = call[0][0], call[0][1]
            self.assertGreaterEqual(y, 0)
            self.assertGreaterEqual(x, 0)


class TestModalResizeAndTimeout(unittest.TestCase):
    """#105: Modal.show() ignores -1 and erases/re-renders on KEY_RESIZE."""

    def test_show_ignores_minus_one_and_handles_key_resize(self):
        class SpyModal(Modal):
            def __init__(self):
                super().__init__()
                self.renders = 0
                self.keys: list[int] = []

            def render(self, win):
                self.renders += 1

            def handle_key(self, key: int):
                self.keys.append(key)
                if key == 27:
                    self.set_result('done')

        m = SpyModal()
        win = mock.MagicMock()
        win.getch.side_effect = [-1, curses.KEY_RESIZE, 27]

        result = m.show(win)

        self.assertEqual(result, 'done')
        self.assertEqual(m.renders, 3)
        self.assertEqual(m.keys, [27])
        win.erase.assert_called_once()

    @mock.patch('tnc.dialog.get_attr', return_value=0)
    def test_error_modal_does_not_dismiss_on_resize_or_timeout(self, _attr):
        m = ErrorModal('Error', 'Message')
        win = mock.MagicMock()
        win.getmaxyx.return_value = (24, 80)
        win.erase.side_effect = curses.error('ignore')
        win.getch.side_effect = [-1, curses.KEY_RESIZE, ord('q')]

        m.show(win)

        self.assertEqual(win.getch.call_count, 3)


class TestFormatTimeCorruptMtime(unittest.TestCase):
    """#106: format_time returns placeholder on corrupt mtimes."""

    def test_corrupt_mtimes_return_placeholder(self):
        for bad in (1e20, -1e20, float('nan'), float('inf')):
            with self.subTest(bad=bad):
                self.assertEqual(format_time(bad), '????-??-?? ??:??')

    def test_overwrite_modal_with_corrupt_mtime(self):
        modal = OverwriteModal('f.txt', 10, 20, 1e20, -1e20, 1, 1)
        self.assertIn('????-??-?? ??:??', modal.source_info)
        self.assertIn('????-??-?? ??:??', modal.dest_info)


class TestCompatibilityHooks(unittest.TestCase):
    """Hooks for #90 (Modal.button_translator) and #103 (ChmodDialog.get_mode_masks)."""

    def test_modal_button_translator_default_none_and_translates_clicks(self):
        self.assertIsNone(Modal.button_translator)

        class ClickSpy(Modal):
            def __init__(self):
                super().__init__()
                self.clicks: list[tuple[int, int, int]] = []

            def render(self, win):
                pass

            def handle_key(self, key: int):
                if key == 27:
                    self.set_result('esc')

            def handle_click(self, x: int, y: int, button_state: int):
                self.clicks.append((x, y, button_state))

        def swap_1_and_3(state: int) -> int:
            if state == curses.BUTTON3_CLICKED:
                return curses.BUTTON1_CLICKED
            return state

        win = mock.MagicMock()
        win.getch.side_effect = [curses.KEY_MOUSE, 27]

        # Test class-level plain function assignment (also tests descriptor safety).
        with mock.patch.object(Modal, 'button_translator', swap_1_and_3), \
             mock.patch('curses.getmouse', return_value=(0, 3, 4, 0, curses.BUTTON3_CLICKED)):
            m = ClickSpy()
            m.show(win)
            self.assertEqual(m.clicks, [(3, 4, curses.BUTTON1_CLICKED)])

    def test_chmod_dialog_get_mode_masks(self):
        d = ChmodDialog(file_count=1, initial_mode=0o755)
        set_mask, clear_mask = d.get_mode_masks()
        self.assertEqual(set_mask, 0o755)
        self.assertEqual(clear_mask, 0o7777 & ~0o755)

        bit_states = {
            'owner_read': TriState.CHECKED,
            'owner_write': TriState.MIXED,
            'owner_exec': TriState.UNCHECKED,
            'group_read': TriState.CHECKED,
            'group_write': TriState.UNCHECKED,
            'group_exec': TriState.MIXED,
            'other_read': TriState.UNCHECKED,
            'other_write': TriState.UNCHECKED,
            'other_exec': TriState.UNCHECKED,
            'setuid': TriState.MIXED,
            'setgid': TriState.UNCHECKED,
            'sticky': TriState.CHECKED,
        }
        d_mixed = ChmodDialog(file_count=3, initial_states=bit_states)
        set_m, clear_m = d_mixed.get_mode_masks()
        self.assertEqual(set_m, stat.S_IRUSR | stat.S_IRGRP | stat.S_ISVTX)
        self.assertEqual(
            clear_m,
            stat.S_IXUSR | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH | stat.S_ISGID,
        )
        # Mixed bits appear in neither mask.
        mixed_bits = stat.S_IWUSR | stat.S_IXGRP | stat.S_ISUID
        self.assertEqual(set_m & mixed_bits, 0)
        self.assertEqual(clear_m & mixed_bits, 0)
        # Existing get_result_mode() remains unchanged.
        self.assertEqual(d_mixed.get_result_mode(), 0o1440)


if __name__ == '__main__':
    unittest.main()
