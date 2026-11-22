"""Unit tests for the pure-stdlib VT100/ANSI VirtualTerminal emulator."""

import unittest

from tests.terminal.virtual_terminal import Cell, Style, VirtualTerminal


class TestVirtualTerminalBasics(unittest.TestCase):
    """Test text printing, control characters, wrapping, and cursor movement."""

    def test_initial_grid_and_modes(self) -> None:
        vt = VirtualTerminal(rows=4, cols=10)
        self.assertEqual(vt.rows, 4)
        self.assertEqual(vt.cols, 10)
        self.assertEqual((vt.cursor_row, vt.cursor_col), (0, 0))
        self.assertTrue(vt.cursor_visible)
        self.assertFalse(vt.in_alt_screen)
        self.assertFalse(vt.mouse_tracking)
        self.assertFalse(vt.sgr_mouse)
        self.assertEqual(vt.row_text(0), '')
        self.assertEqual(vt.row_text(0, strip_trailing=False), ' ' * 10)

    def test_basic_text_cr_lf_bs_tab(self) -> None:
        vt = VirtualTerminal(rows=5, cols=20)
        vt.feed('hello\r\nworld!\b?\r\n\tindented')
        self.assertEqual(vt.row_text(0), 'hello')
        self.assertEqual(vt.row_text(1), 'world?')
        self.assertEqual(vt.row_text(2), '        indented')

    def test_delayed_wrap_and_no_autowrap(self) -> None:
        vt = VirtualTerminal(rows=3, cols=5)
        vt.feed('ABCDE')
        self.assertEqual(vt.row_text(0), 'ABCDE')
        # Xenl delayed wrap keeps cursor on last col without prematurely wrapping row
        self.assertEqual((vt.cursor_row, vt.cursor_col), (0, 4))
        vt.feed('F')
        self.assertEqual(vt.row_text(1), 'F')
        self.assertEqual((vt.cursor_row, vt.cursor_col), (1, 1))

        # Disable auto-wrap (?7l): subsequent chars overwrite final column
        vt2 = VirtualTerminal(rows=2, cols=5)
        vt2.feed('\x1b[?7lABCDEFG')
        self.assertFalse(vt2.auto_wrap)
        self.assertEqual(vt2.row_text(0), 'ABCDG')
        self.assertEqual(vt2.row_text(1), '')

    def test_csi_cursor_movements_and_clamping(self) -> None:
        vt = VirtualTerminal(rows=5, cols=10)
        vt.feed('\x1b[3;5H')  # 1-based -> (row=2, col=4)
        self.assertEqual((vt.cursor_row, vt.cursor_col), (2, 4))
        vt.feed('\x1b[2A')  # up 2 -> row 0
        self.assertEqual((vt.cursor_row, vt.cursor_col), (0, 4))
        vt.feed('\x1b[10B')  # down 10 -> clamp row 4
        self.assertEqual((vt.cursor_row, vt.cursor_col), (4, 4))
        vt.feed('\x1b[3C')  # right 3 -> col 7
        self.assertEqual((vt.cursor_row, vt.cursor_col), (4, 7))
        vt.feed('\x1b[20D')  # left 20 -> clamp col 0
        self.assertEqual((vt.cursor_row, vt.cursor_col), (4, 0))
        vt.feed('\x1b[2E')  # doesn't overflow bottom
        self.assertEqual(vt.cursor_row, 4)
        vt.feed('\x1b[8G')  # horizontal absolute col 7 (0-based)
        self.assertEqual(vt.cursor_col, 7)
        vt.feed('\x1b[2d')  # vertical position absolute row 1
        self.assertEqual(vt.cursor_row, 1)
        vt.feed('\x1b[4;9f')  # HVP synonym for CUP
        self.assertEqual((vt.cursor_row, vt.cursor_col), (3, 8))
        vt.feed('\x1b[99;99H')
        self.assertEqual((vt.cursor_row, vt.cursor_col), (4, 9))

    def test_erase_operations_with_bce_style(self) -> None:
        vt = VirtualTerminal(rows=3, cols=6)
        vt.feed('111111\r\n222222\r\n333333')
        vt.feed('\x1b[2;4H\x1b[44m\x1b[K')  # erase to end of line on row 1 from col 3
        self.assertEqual(vt.row_text(1), '222')
        self.assertEqual(vt.cell(1, 4).style.bg, 4)

        vt.feed('\x1b[2;3H\x1b[1K')  # erase from start of line to col 2
        self.assertEqual(vt.row_text(1, strip_trailing=False), '      ')

        vt.feed('\x1b[2;2H\x1b[0J')  # erase from cursor to end of screen
        self.assertEqual(vt.row_text(0), '111111')
        self.assertEqual(vt.row_text(2), '')

        vt.feed('\x1b[1;3H\x1b[1J')  # erase start of screen to cursor
        self.assertEqual(vt.row_text(0), '   111')

        vt.feed('\x1b[49m\x1b[2J')  # erase entire screen
        self.assertEqual(vt.lines(), ['', '', ''])

        vt.feed('\x1b[1;1HABCDEF\x1b[1;2H\x1b[3X')  # erase 3 chars at col 1..3
        self.assertEqual(vt.row_text(0), 'A   EF')


class TestVirtualTerminalEditingScrollAndStyles(unittest.TestCase):
    """Test scroll regions, insert/delete, SGR attributes, DEC modes, and UTF-8."""

    def test_scroll_regions_reverse_index_insert_delete_repeat(self) -> None:
        vt = VirtualTerminal(rows=4, cols=6)
        vt.feed('\x1b[1;1Hrow0\r\nrow1\r\nrow2\r\nrow3')
        # Restrict scroll region to rows 1..2 (1-based 2..3)
        vt.feed('\x1b[2;3r')
        vt.feed('\x1b[3;1H\n')  # scroll up inside region
        self.assertEqual(vt.row_text(0), 'row0')
        self.assertEqual(vt.row_text(1), 'row2')
        self.assertEqual(vt.row_text(2), '')
        self.assertEqual(vt.row_text(3), 'row3')

        # Reverse index at top of region pushes down
        vt.feed('\x1b[2;1H\x1bM')
        self.assertEqual(vt.row_text(1), '')
        self.assertEqual(vt.row_text(2), 'row2')

        # Reset region, test S / T, L / M, @ / P, b
        vt.feed('\x1b[r\x1b[2J')
        vt.feed('\x1b[1;1HA\x1b[4b')  # REP -> AAAAA
        self.assertEqual(vt.row_text(0), 'AAAAA')
        vt.feed('\x1b[1;3H\x1b[1@Z')  # insert 1 blank then Z -> AAZAAA -> AA\ZAA
        self.assertEqual(vt.row_text(0), 'AAZAAA')
        vt.feed('\x1b[1;3H\x1b[2P')  # delete 2 chars -> AAAA
        self.assertEqual(vt.row_text(0), 'AAAA')

        vt.feed('\x1b[2;1HlineB\r\nlineC')
        vt.feed('\x1b[2;1H\x1b[1LNEW')  # insert line at row 1
        self.assertEqual(vt.lines(), ['AAAA', 'NEW', 'lineB', 'lineC'])
        vt.feed('\x1b[2;1H\x1b[1M')  # delete line at row 1
        self.assertEqual(vt.lines(), ['AAAA', 'lineB', 'lineC', ''])

    def test_sgr_attributes_and_colors(self) -> None:
        vt = VirtualTerminal(rows=2, cols=10)
        vt.feed('\x1b[1;2;3;4;7;31;46mA')
        s = vt.cell(0, 0).style
        self.assertTrue(s.bold)
        self.assertTrue(s.dim)
        self.assertTrue(s.italic)
        self.assertTrue(s.underline)
        self.assertTrue(s.reverse)
        self.assertEqual(s.fg, 1)
        self.assertEqual(s.bg, 6)

        vt.feed('\x1b[22;23;24;27;92;104mB')
        s2 = vt.cell(0, 1).style
        self.assertFalse(s2.bold)
        self.assertFalse(s2.dim)
        self.assertFalse(s2.italic)
        self.assertFalse(s2.underline)
        self.assertFalse(s2.reverse)
        self.assertEqual(s2.fg, 10)
        self.assertEqual(s2.bg, 12)

        vt.feed('\x1b[38;5;208;48;2;10;20;30mC')
        s3 = vt.cell(0, 2).style
        self.assertEqual(s3.fg, 208)
        self.assertEqual(s3.bg, (10, 20, 30))

        vt.feed('\x1b[39;49mD\x1b[mE')
        self.assertIsNone(vt.cell(0, 3).style.fg)
        self.assertIsNone(vt.cell(0, 3).style.bg)
        self.assertEqual(vt.cell(0, 4).style, Style())

    def test_private_dec_modes_and_alt_screen(self) -> None:
        vt = VirtualTerminal(rows=3, cols=12)
        vt.feed('main line')
        vt.feed('\x1b[?1049h\x1b[?1000;1006h\x1b[?25l\x1b[?1h')
        self.assertTrue(vt.in_alt_screen)
        self.assertTrue(vt.mouse_tracking)
        self.assertTrue(vt.sgr_mouse)
        self.assertFalse(vt.cursor_visible)
        self.assertTrue(vt.app_cursor_keys)
        self.assertEqual(vt.row_text(0), '')

        vt.feed('alt content')
        self.assertEqual(vt.row_text(0), 'alt content')

        vt.feed('\x1b[?1l\x1b[?25h\x1b[?1000;1006l\x1b[?1049l')
        self.assertFalse(vt.in_alt_screen)
        self.assertFalse(vt.mouse_tracking)
        self.assertFalse(vt.sgr_mouse)
        self.assertTrue(vt.cursor_visible)
        self.assertFalse(vt.app_cursor_keys)
        self.assertEqual(vt.row_text(0), 'main line')

    def test_line_drawing_charset_osc_and_chunked_utf8_cjk(self) -> None:
        vt = VirtualTerminal(rows=3, cols=20)
        # OSC title ignored cleanly (both BEL and ST terminators)
        vt.feed(b'\x1b]0;Window Title\x07\x1b]2;Other\x1b\\')
        # DEC special graphics box corners + horizontal line, then switch back to ASCII
        vt.feed(b'\x1b(0lqqk\x1b(B hello')
        self.assertEqual(vt.row_text(0), '┌──┐ hello')

        # Split UTF-8 bytes & CSI sequence 1 byte at a time
        chunked = '\r\nпапка 日本'.encode('utf-8') + b'\x1b[3;1H\x1b[32mok'
        for i in range(len(chunked)):
            vt.feed(chunked[i:i + 1])

        self.assertEqual(vt.row_text(1), 'папка 日本')
        # Verify wide CJK char occupies 2 columns (index 6 and 7)
        idx_ri = vt.find_text('日', row=1)
        self.assertEqual(idx_ri, (6, 1))
        self.assertTrue(vt.cell(1, 7).is_continuation)
        self.assertEqual(vt.find_text('本', row=1), (8, 1))
        self.assertEqual(vt.row_text(2), 'ok')
        self.assertEqual(vt.cell(2, 0).style.fg, 2)

        # Overwriting second half of wide char clears its first half
        vt.feed('\x1b[2;8HX')
        self.assertEqual(vt.cell(1, 6), Cell(char=' '))
        self.assertEqual(vt.cell(1, 7).char, 'X')

    def test_resize_find_region_and_screenshot(self) -> None:
        vt = VirtualTerminal(rows=3, cols=16)
        vt.feed('F1Help   F1Help\r\nsecond row\r\nF10Quit')
        self.assertEqual(vt.find_text('F1Help'), (0, 0))
        self.assertEqual(vt.find_text('F1Help', occurrence=1), (9, 0))
        self.assertEqual(vt.find_text('Quit', row=2), (3, 2))
        self.assertIsNone(vt.find_text('Missing'))
        self.assertEqual(vt.find_all('F1Help'), [(0, 0), (9, 0)])
        self.assertEqual(vt.region(1, 2, 2, 4), ['cond', '0Qui'])
        self.assertTrue(vt.contains('F10Quit'))

        vt.resize(5, 10)
        self.assertEqual((vt.rows, vt.cols), (5, 10))
        self.assertEqual(vt.row_text(0), 'F1Help   F')
        self.assertEqual(vt.row_text(2), 'F10Quit')
        self.assertEqual(vt.row_text(4), '')

        shot = vt.screenshot(with_ruler=True)
        self.assertIn('F10Quit', shot)
        self.assertIn('0:', shot)
        self.assertIn('cursor=', shot)

    def test_style_queries_csi_guards_combining_and_integrity(self) -> None:
        vt = VirtualTerminal(rows=3, cols=24)
        # Private CSI sequences with '>', '<', '=' prefixes must not print garbage
        vt.feed('\x1b[>0;10;0c\x1b[<u\x1b[=0u')
        # Styled ASCII + combining mark + styled CJK wide characters
        vt.feed('\x1b[32;1mFile\x1b[m ')
        vt.feed('\x1b[7;34m日\x1b[me\u0301 ')
        vt.feed('\x1b[31mFile\x1b[m')

        self.assertEqual(vt.check_integrity(), [])
        self.assertEqual(vt.row_text(0), 'File 日e\u0301 File')
        self.assertEqual(len(vt.row_styles(0)), 24)
        self.assertEqual(len(vt.region_styles(0, 0, 1, 4)[0]), 4)

        self.assertTrue(vt.style_at(0, 0).matches(fg=2, bold=True))
        self.assertFalse(vt.style_at(0, 0).matches(reverse=True))

        # Distinguish differently styled occurrences of 'File' and wide CJK text
        self.assertEqual(vt.find_styled_text('File', fg=2, bold=True), (0, 0))
        self.assertEqual(vt.find_styled_text('File', fg=1), (9, 0))
        self.assertIsNone(vt.find_styled_text('File', reverse=True))

        # Column 5 holds '日', col 6 is its continuation cell
        cjk_styles = vt.styles_for_text('日', row=0)
        self.assertIsNotNone(cjk_styles)
        assert cjk_styles is not None
        self.assertEqual(len(cjk_styles), 1)
        self.assertTrue(cjk_styles[0].matches(reverse=True, fg=4))
        self.assertEqual(vt.find_styled_text('日', reverse=True, fg=4), (5, 0))

        # Corrupting a continuation cell intentionally must be reported by check_integrity()
        vt._active.grid[0][6] = Cell(char='X')
        errs = vt.check_integrity()
        self.assertTrue(any('continuation' in e.lower() for e in errs))


if __name__ == '__main__':
    unittest.main()
