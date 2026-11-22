"""Real-PTY end-to-end tests for Tiny Commander navigation, search, chrome, resizes, and styles."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import tempfile
import unicodedata
import unittest

from tests.terminal import KeyMap, TerminalDriver, VirtualTerminal


class _E2ETestBase(unittest.TestCase):
    """Shared real-PTY setup, isolation, and screen inspection helpers."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix='tnc_e2e_nav_')
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.work_dir = self.root / 'work'
        self.home_dir = self.root / 'home'
        self.xdg_config_dir = self.home_dir / '.config'
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.xdg_config_dir.mkdir(parents=True, exist_ok=True)

    def make_driver(
        self,
        *,
        rows: int = 24,
        cols: int = 80,
        cwd: Path | str | None = None,
        term: str = 'xterm-256color',
        extra_env: dict[str, str | None] | None = None,
    ) -> TerminalDriver:
        """Create an isolated TerminalDriver with clean HOME/XDG and unset tool env vars."""
        env: dict[str, str | None] = {
            'XDG_CONFIG_HOME': str(self.xdg_config_dir),
            'EDITOR': None,
            'VISUAL': None,
            'PAGER': None,
        }
        if extra_env:
            env.update(extra_env)
        return TerminalDriver(
            rows=rows,
            cols=cols,
            cwd=cwd if cwd is not None else self.work_dir,
            home=self.home_dir,
            term=term,
            env=env,
        )

    def quit_cleanly(self, driver: TerminalDriver) -> None:
        """Send F10 and assert clean exit and terminal state restoration."""
        driver.press('f10')
        rc = driver.wait_exit()
        self.assertEqual(rc, 0)
        self.assertFalse(driver.screen.in_alt_screen)
        self.assertFalse(driver.screen.mouse_tracking)
        self.assertTrue(driver.screen.cursor_visible)

    def panel_header(self, screen: VirtualTerminal, side: str = 'left') -> str:
        """Return the top border/header string for the left or right panel."""
        left_w = screen.cols // 2
        if side == 'left':
            return screen.region(1, 0, 1, left_w)[0]
        return screen.region(1, left_w, 1, screen.cols - left_w)[0]

    def panel_rows(self, screen: VirtualTerminal, side: str = 'left') -> list[str]:
        """Return interior entry lines (between borders) for the requested panel."""
        left_w = screen.cols // 2
        right_w = screen.cols - left_w
        panel_h = screen.rows - 4
        if side == 'left':
            col_start, inner_w = 1, left_w - 2
        else:
            col_start, inner_w = left_w + 1, right_w - 2
        return [line.rstrip() for line in screen.region(2, col_start, panel_h - 2, inner_w)]

    def visible_entry_names(self, screen: VirtualTerminal, side: str = 'left') -> list[str]:
        """Extract visible entry names from panel rows (ignoring empty rows)."""
        names: list[str] = []
        for line in self.panel_rows(screen, side=side):
            stripped = line.strip()
            if not stripped:
                continue
            names.append(stripped.split()[0])
        return names

    def assert_chrome_and_borders(self, screen: VirtualTerminal) -> None:
        """Verify structural integrity, cursor bounds, panel borders, and chrome rows."""
        self.assertEqual(screen.check_integrity(), [])
        self.assertTrue(0 <= screen.cursor_row < screen.rows)
        self.assertTrue(0 <= screen.cursor_col < screen.cols)
        full_text = screen.text()
        self.assertNotIn('Traceback', full_text)
        self.assertNotIn('curses.error', full_text)

        rows, cols = screen.rows, screen.cols
        left_w = cols // 2
        top_panel_row = 1
        bot_panel_row = rows - 4

        # Menu bar and function key bar
        self.assertIn('Left', screen.row_text(0))
        self.assertIn('F10', screen.row_text(rows - 1))
        self.assertIn('F1', screen.row_text(rows - 1))

        # Status bar and command line prompt
        status_row = screen.row_text(rows - 3)
        self.assertTrue('[Left]' in status_row or '[Right]' in status_row, status_row)
        cmdline_row = screen.row_text(rows - 2)
        self.assertIn('>', cmdline_row)
        self.assertEqual(screen.cursor_row, rows - 2)

        # Panel corners and vertical dividers (long path headers can overwrite '┐' with trailing space)
        self.assertEqual(screen.cell(top_panel_row, 0).char, '┌')
        self.assertIn(screen.cell(top_panel_row, left_w - 1).char, ('┐', ' '))
        self.assertEqual(screen.cell(top_panel_row, left_w).char, '┌')
        self.assertIn(screen.cell(top_panel_row, cols - 1).char, ('┐', ' '))

        self.assertEqual(screen.cell(bot_panel_row, 0).char, '└')
        self.assertEqual(screen.cell(bot_panel_row, left_w - 1).char, '┘')
        self.assertEqual(screen.cell(bot_panel_row, left_w).char, '└')
        self.assertEqual(screen.cell(bot_panel_row, cols - 1).char, '┘')

        for r in range(top_panel_row + 1, bot_panel_row):
            for border_col in (0, left_w - 1, left_w, cols - 1):
                self.assertEqual(
                    screen.cell(r, border_col).char,
                    '│',
                    f'Border broken at row={r}, col={border_col}: {screen.row_text(r)!r}',
                )


class TestE2ENavigationAndHistory(_E2ETestBase):
    """Real-PTY tests for directory navigation, scrolling, history, tab switch, and hidden toggle."""

    def test_subdir_entry_and_dotdot_restores_exited_dir_selection(self) -> None:
        nested = self.work_dir / 'alpha_dir' / 'nested_dir'
        nested.mkdir(parents=True)
        (nested / 'deep_marker.txt').write_text('deep', encoding='utf-8')
        (self.work_dir / 'beta_dir').mkdir()
        (self.work_dir / 'zeta.txt').write_text('z', encoding='utf-8')

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()
            self.assertIn('1 of 4', driver.screen.row_text(21))

            # Enter beta_dir (index 2: .., alpha_dir, beta_dir, zeta.txt)
            driver.press('down', 'down', 'enter')
            driver.wait_until(lambda _s: '/beta_dir' in self.panel_header(driver.screen, 'left'))
            self.assertIn('/beta_dir>', driver.screen.row_text(22))
            self.assertIn('1 of 1', driver.screen.row_text(21))

            # Press Enter on '..' to return to parent and restore cursor onto beta_dir
            driver.press('enter')
            driver.wait_until(lambda _s: '/beta_dir' not in self.panel_header(driver.screen, 'left'))
            driver.wait_for_text('3 of 4', row=21)
            self.assertIsNotNone(
                driver.screen.find_styled_text('beta_dir/', row=4, fg=0, bg=6)
            )

            # Enter two levels deep: alpha_dir -> nested_dir
            driver.press('up', 'enter')
            driver.wait_until(
                lambda s: '/alpha_dir' in self.panel_header(s, 'left')
                and s.contains('nested_dir/')
            )
            driver.press('down', 'enter')
            driver.wait_until(
                lambda s: '/nested_dir' in self.panel_header(s, 'left')
                and s.contains('deep_marker.txt')
            )

            # Navigate back out twice via '..' and verify cursor recalls exited directories
            driver.press('enter')
            driver.wait_until(
                lambda s: '/nested_dir' not in self.panel_header(s, 'left')
                and s.find_styled_text('nested_dir/', row=3, fg=0, bg=6) is not None
            )
            driver.press('home', 'enter')
            driver.wait_until(lambda _s: '/alpha_dir' not in self.panel_header(driver.screen, 'left'))
            driver.wait_for_text('2 of 4', row=21)
            self.assertIsNotNone(
                driver.screen.find_styled_text('alpha_dir/', row=3, fg=0, bg=6)
            )

            self.quit_cleanly(driver)

    def test_long_list_home_end_pgup_pgdn_scrolling(self) -> None:
        for i in range(55):
            (self.work_dir / f'item_{i:02d}.txt').write_text(str(i), encoding='utf-8')

        # 24 rows -> panel_height=20 -> visible_rows=18, total entries = 56 ('..' + 55 files)
        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()
            self.assertIn('1 of 56', driver.screen.row_text(21))
            left_entries = self.visible_entry_names(driver.screen, 'left')
            self.assertEqual(left_entries[0], '../')
            self.assertIn('item_00.txt', left_entries)
            self.assertNotIn('item_54.txt', left_entries)

            # PgDn moves cursor down by visible_rows (18 -> index 18 -> 19 of 56)
            driver.press('pgdn')
            driver.wait_for_text('19 of 56', row=21)
            driver.press('pgdn')
            driver.wait_for_text('37 of 56', row=21)
            scrolled_entries = self.visible_entry_names(driver.screen, 'left')
            self.assertNotIn('../', scrolled_entries)
            self.assertNotIn('item_00.txt', scrolled_entries)
            self.assertIn('item_35.txt', scrolled_entries)

            # End jumps to last entry (56 of 56: item_54.txt)
            driver.press('end')
            driver.wait_for_text('56 of 56', row=21)
            end_entries = self.visible_entry_names(driver.screen, 'left')
            self.assertEqual(end_entries[-1], 'item_54.txt')
            self.assertIsNotNone(
                driver.screen.find_styled_text('item_54.txt', row=19, fg=0, bg=6)
            )

            # PgUp moves up one page (55 - 18 = 37 -> 38 of 56)
            driver.press('pgup')
            driver.wait_for_text('38 of 56', row=21)

            # Home returns to '..' at top
            driver.press('home')
            driver.wait_for_text('1 of 56', row=21)
            top_entries = self.visible_entry_names(driver.screen, 'left')
            self.assertEqual(top_entries[0], '../')
            self.assertIsNotNone(driver.screen.find_styled_text('../', row=2, fg=0, bg=6))

            self.quit_cleanly(driver)

    def test_panel_directory_history_alt_left_right_and_tab_independence(self) -> None:
        (self.work_dir / 'dir_a').mkdir()
        (self.work_dir / 'dir_b').mkdir()
        (self.work_dir / 'dir_c').mkdir()

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()

            # Left panel visits dir_a -> parent -> dir_b
            driver.press('down', 'enter')
            driver.wait_until(lambda _s: '/dir_a' in self.panel_header(driver.screen, 'left'))
            driver.press('enter')
            driver.wait_until(lambda _s: '/dir_a' not in self.panel_header(driver.screen, 'left'))
            driver.press('home', 'down', 'down', 'enter')
            driver.wait_until(lambda _s: '/dir_b' in self.panel_header(driver.screen, 'left'))

            # Alt+Left walks back through Left panel history
            driver.press('alt+left')
            driver.wait_until(lambda _s: '/dir_b' not in self.panel_header(driver.screen, 'left'))
            self.assertNotIn('/dir_b>', driver.screen.row_text(22))

            driver.press('alt+left')
            driver.wait_until(lambda _s: '/dir_a' in self.panel_header(driver.screen, 'left'))
            self.assertIn('/dir_a>', driver.screen.row_text(22))

            # Alt+Right walks forward
            driver.press('alt+right')
            driver.wait_until(lambda _s: '/dir_a' not in self.panel_header(driver.screen, 'left'))
            driver.press('alt+right')
            driver.wait_until(lambda _s: '/dir_b' in self.panel_header(driver.screen, 'left'))

            # Tab switches to Right panel; navigate Right independently into dir_c
            driver.press('tab')
            driver.wait_for_text('[Right]', row=21)
            driver.press('down', 'down', 'down', 'enter')
            driver.wait_until(lambda _s: '/dir_c' in self.panel_header(driver.screen, 'right'))
            self.assertIn('/dir_b', self.panel_header(driver.screen, 'left'))

            # Switch back to Left; Alt+Left affects only Left panel
            driver.press('tab')
            driver.wait_for_text('[Left]', row=21)
            driver.press('alt+left')
            driver.wait_until(lambda _s: '/dir_b' not in self.panel_header(driver.screen, 'left'))
            self.assertIn('/dir_c', self.panel_header(driver.screen, 'right'))

            self.quit_cleanly(driver)

    def test_hidden_files_toggle_per_panel_via_menu(self) -> None:
        (self.work_dir / '.dotdir').mkdir()
        (self.work_dir / '.hidden.txt').write_text('secret', encoding='utf-8')
        (self.work_dir / 'visible.txt').write_text('public', encoding='utf-8')

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()
            self.assertIn('.dotdir/', self.visible_entry_names(driver.screen, 'left'))
            self.assertIn('.hidden.txt', self.visible_entry_names(driver.screen, 'left'))
            self.assertIn('.hidden.txt', self.visible_entry_names(driver.screen, 'right'))

            # Left menu (index 0) -> item 5 ('Toggle hidden')
            driver.press('f9')
            driver.wait_for_text('Toggle hidden')
            driver.press('down', 'down', 'down', 'down', 'down', 'enter')
            driver.wait_until(
                lambda s: not s.contains('Sort by name')
                and '.hidden.txt' not in self.visible_entry_names(s, 'left')
            )
            left_names = self.visible_entry_names(driver.screen, 'left')
            self.assertNotIn('.dotdir/', left_names)
            self.assertIn('../', left_names)
            self.assertIn('visible.txt', left_names)
            # Right panel keeps hidden files visible independently
            self.assertIn('.hidden.txt', self.visible_entry_names(driver.screen, 'right'))

            # Toggle Left hidden files back on
            driver.press('f9')
            driver.wait_for_text('Toggle hidden')
            driver.press('down', 'down', 'down', 'down', 'down', 'enter')
            driver.wait_until(
                lambda s: not s.contains('Sort by name')
                and '.hidden.txt' in self.visible_entry_names(s, 'left')
            )

            # Right menu -> Toggle hidden affects only Right panel
            driver.press('f9')
            driver.wait_for_text('Sort by name')
            driver.press('left', 'down', 'down', 'down', 'down', 'down', 'enter')
            driver.wait_until(
                lambda s: not s.contains('Sort by name')
                and '.hidden.txt' not in self.visible_entry_names(s, 'right')
            )
            self.assertIn('.hidden.txt', self.visible_entry_names(driver.screen, 'left'))

            self.quit_cleanly(driver)


class TestE2EPanelsMouseAndSort(_E2ETestBase):
    """Real-PTY tests for sort orders, reverse sort, dirs-first, mouse clicks, and panel styles."""

    def test_sort_modes_and_reverse_ordering_via_keys_and_menu(self) -> None:
        dir_a = self.work_dir / 'dir_a'
        dir_b = self.work_dir / 'dir_b'
        dir_a.mkdir()
        dir_b.mkdir()

        # Construct files whose Name, Size, Date, and Extension orders are all distinct:
        #   alpha.zz:   size=100,  mtime=1_000_000 (oldest)
        #   bravo.aa:   size=5000, mtime=1_500_000 (middle)
        #   charlie.mm: size=10,   mtime=2_000_000 (newest)
        f_alpha = self.work_dir / 'alpha.zz'
        f_bravo = self.work_dir / 'bravo.aa'
        f_charlie = self.work_dir / 'charlie.mm'
        f_alpha.write_text('a' * 100, encoding='utf-8')
        f_bravo.write_text('b' * 5000, encoding='utf-8')
        f_charlie.write_text('c' * 10, encoding='utf-8')
        os.utime(dir_a, (1_200_000, 1_200_000))
        os.utime(dir_b, (1_800_000, 1_800_000))
        os.utime(f_alpha, (1_000_000, 1_000_000))
        os.utime(f_bravo, (1_500_000, 1_500_000))
        os.utime(f_charlie, (2_000_000, 2_000_000))

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()

            # Default sort: Name ('vn') with dirs first
            self.assertIn('vn ', self.panel_header(driver.screen, 'left'))
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'left'),
                ['../', 'dir_a/', 'dir_b/', 'alpha.zz', 'bravo.aa', 'charlie.mm'],
            )

            # Shift+F3 -> Size ('vs', largest first; dirs remain before files)
            driver.press('shift+f3')
            driver.wait_until(lambda s: 'vs ' in self.panel_header(s, 'left'))
            size_names = self.visible_entry_names(driver.screen, 'left')
            self.assertEqual(size_names[0], '../')
            self.assertEqual(set(size_names[1:3]), {'dir_a/', 'dir_b/'})
            self.assertEqual(size_names[3:], ['bravo.aa', 'alpha.zz', 'charlie.mm'])

            # Shift+F3 -> Date ('vd', newest first)
            driver.press('shift+f3')
            driver.wait_until(lambda s: 'vd ' in self.panel_header(s, 'left'))
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'left'),
                ['../', 'dir_b/', 'dir_a/', 'charlie.mm', 'bravo.aa', 'alpha.zz'],
            )

            # Shift+F3 -> Extension ('ve', aa < mm < zz)
            driver.press('shift+f3')
            driver.wait_until(lambda s: 've ' in self.panel_header(s, 'left'))
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'left'),
                ['../', 'dir_a/', 'dir_b/', 'bravo.aa', 'charlie.mm', 'alpha.zz'],
            )

            # Shift+F3 -> back to Name ('vn')
            driver.press('shift+f3')
            driver.wait_until(lambda s: 'vn ' in self.panel_header(s, 'left'))

            # Ctrl+F3 -> Reverse Name ('^n'); dirs stay before files!
            driver.press('ctrl+f3')
            driver.wait_until(lambda s: '^n ' in self.panel_header(s, 'left'))
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'left'),
                ['../', 'dir_b/', 'dir_a/', 'charlie.mm', 'bravo.aa', 'alpha.zz'],
            )

            # Right menu -> Sort by size + Reverse sort affects Right panel while Left is active
            driver.click_text('Right', row=0)
            driver.wait_for_text('Sort by name')
            driver.press('down', 'enter')  # Right -> Sort by size
            driver.wait_until(
                lambda s: not s.contains('Sort by name') and 'vs ' in self.panel_header(s, 'right')
            )
            driver.click_text('Right', row=0)
            driver.wait_for_text('Reverse sort')
            driver.press('down', 'down', 'down', 'down', 'enter')  # Right -> Reverse sort
            driver.wait_until(
                lambda s: not s.contains('Sort by name') and '^s ' in self.panel_header(s, 'right')
            )
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'right')[3:],
                ['charlie.mm', 'alpha.zz', 'bravo.aa'],
            )
            self.assertIn('^n ', self.panel_header(driver.screen, 'left'))

            self.quit_cleanly(driver)

    def test_active_vs_inactive_panel_highlight_styles_and_mouse_interaction(self) -> None:
        (self.work_dir / 'sub_one').mkdir()
        (self.work_dir / 'alpha.txt').write_text('alpha', encoding='utf-8')
        (self.work_dir / 'beta.txt').write_text('beta', encoding='utf-8')

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()

            # At startup Left is active (black on cyan), Right is inactive (white on blue bold dir)
            self.assertIsNotNone(driver.screen.find_styled_text('../', row=2, fg=0, bg=6))
            right_col_start = 50
            right_dotdot_styles = driver.screen.styles_for_text('../', row=2, occurrence=1)
            self.assertTrue(right_dotdot_styles)
            self.assertTrue(all(st.fg == 7 and st.bg == 4 and st.bold for st in right_dotdot_styles))

            # Select alpha.txt (row 4) with Insert; alpha.txt becomes yellow (fg=3, bg=4, bold=True)
            driver.press('down', 'down', 'insert')
            driver.wait_for_text('1 selected', row=21)
            alpha_sel = driver.screen.styles_for_text('alpha.txt', row=4, occurrence=0)
            self.assertTrue(all(st.fg == 3 and st.bg == 4 and st.bold for st in alpha_sel))
            # Cursor moved onto beta.txt (row 5)
            self.assertIsNotNone(driver.screen.find_styled_text('beta.txt', row=5, fg=0, bg=6))

            # Move cursor back onto selected alpha.txt -> cursor+selected (fg=3, bg=6, bold=True)
            driver.press('up')
            driver.wait_until(
                lambda s: s.find_styled_text('alpha.txt', row=4, fg=3, bg=6, bold=True) is not None
            )

            # Click on beta.txt in Right panel -> switches active panel to Right,
            # removes cyan cursor highlight from Left, highlights Right beta.txt
            driver.click(right_col_start + 3, 5)
            driver.wait_for_text('[Right]', row=21)
            self.assertTrue(
                any(st.fg == 0 and st.bg == 6 for st in driver.screen.row_styles(5)[right_col_start + 1:right_col_start + 10])
            )
            # Left panel alpha.txt loses bg=6 and shows selected yellow on blue (bg=4)
            left_alpha = driver.screen.styles_for_text('alpha.txt', row=4, occurrence=0)
            self.assertTrue(all(st.fg == 3 and st.bg == 4 and st.bold for st in left_alpha))

            # Double-click sub_one/ in Right panel to enter it
            driver.wait_mouse_settle()
            driver.double_click(right_col_start + 3, 3)
            driver.wait_until(lambda s: '/sub_one' in self.panel_header(s, 'right'))

            self.quit_cleanly(driver)


class TestE2EQuickSearch(_E2ETestBase):
    """Real-PTY tests for quick search ('/') filtering, backspace, confirmation, cancel, collisions."""

    def test_quick_search_filter_backspace_enter_confirm_and_esc_cancel(self) -> None:
        for name in ('apple.txt', 'apricot.txt', 'banana.txt', 'cherry.txt'):
            (self.work_dir / name).write_text(name, encoding='utf-8')

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()

            # Start quick search with '/'
            driver.press('/')
            driver.wait_for_text('[Left] /', row=21)

            # Type 'ap' -> filters to apple.txt and apricot.txt, cursor on apple.txt
            driver.type_text('ap')
            driver.wait_for_text('[Left] /ap', row=21)
            filtered = self.visible_entry_names(driver.screen, 'left')
            self.assertEqual(filtered, ['../', 'apple.txt', 'apricot.txt'])

            # Down arrow inside search mode selects apricot.txt, Enter confirms and keeps selection
            driver.press('down', 'enter')
            driver.wait_until(lambda s: '[Left] /' not in s.row_text(21))
            full_names = self.visible_entry_names(driver.screen, 'left')
            self.assertIn('banana.txt', full_names)
            self.assertIn('apricot.txt', driver.screen.row_text(21))
            self.assertIsNotNone(driver.screen.find_styled_text('apricot.txt', row=4, fg=0, bg=6))

            # Start another search, narrow to 'apric', Backspace back to 'ap', then Esc cancels
            driver.press('/')
            driver.wait_for_text('[Left] /', row=21)
            driver.type_text('apric')
            driver.wait_for_text('[Left] /apric', row=21)
            self.assertEqual(self.visible_entry_names(driver.screen, 'left'), ['../', 'apricot.txt'])

            driver.press('backspace', 'backspace', 'backspace')
            driver.wait_until(lambda s: s.row_text(21).rstrip() == '[Left] /ap')
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'left'),
                ['../', 'apple.txt', 'apricot.txt'],
            )

            # Esc cancels search, restores full list and resets cursor to '..'
            driver.press_esc_settled()
            driver.wait_for_text('1 of 5', row=21)
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'left'),
                ['../', 'apple.txt', 'apricot.txt', 'banana.txt', 'cherry.txt'],
            )

            self.quit_cleanly(driver)

    def test_quick_search_no_match_and_empty_backspace_exit(self) -> None:
        (self.work_dir / 'sample.txt').write_text('x', encoding='utf-8')

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()
            driver.press('/')
            driver.type_text('zzz')
            driver.wait_for_text('[Left] /zzz', row=21)
            self.assertEqual(self.visible_entry_names(driver.screen, 'left'), ['../'])
            self.assertEqual(driver.screen.check_integrity(), [])

            # Backspace 3 times to empty query '/', then once more exits search mode
            driver.press('backspace', 'backspace', 'backspace')
            driver.wait_until(lambda s: s.row_text(21).rstrip() == '[Left] /')
            driver.press('backspace')
            driver.wait_until(
                lambda s: '[Left] /' not in s.row_text(21)
                and 'sample.txt' in self.visible_entry_names(s, 'left')
            )
            self.assertEqual(
                self.visible_entry_names(driver.screen, 'left'),
                ['../', 'sample.txt'],
            )

            self.quit_cleanly(driver)

    def test_quick_search_collision_with_command_line_and_tab_switch(self) -> None:
        (self.work_dir / 'apple.txt').write_text('a', encoding='utf-8')
        (self.work_dir / 'banana.txt').write_text('b', encoding='utf-8')

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()

            # When command line has text, '/' must type into command line instead of search
            driver.type_text('cd /tmp')
            driver.wait_for_text('> cd /tmp', row=22)
            self.assertNotIn('[Left] /', driver.screen.row_text(21))
            self.assertIn('banana.txt', self.visible_entry_names(driver.screen, 'left'))

            # Double-Esc clears command line
            driver.press_esc_settled()
            driver.wait_for_text('[Esc] again to clear', row=21)
            driver.press_esc_settled()
            driver.wait_until(lambda s: 'cd /tmp' not in s.row_text(22))

            # Start search then Tab -> switches to Right and restores Left full entries
            driver.press('/')
            driver.type_text('app')
            driver.wait_for_text('[Left] /app', row=21)
            driver.press('tab')
            driver.wait_for_text('[Right]', row=21)
            self.assertIn('banana.txt', self.visible_entry_names(driver.screen, 'left'))

            self.quit_cleanly(driver)


class TestE2ECommandLineAndChrome(_E2ETestBase):
    """Real-PTY tests for command line editing, Alt+Enter, Esc hints, execution, and help chrome."""

    def test_command_line_editing_esc_clear_and_ctrl_x_hint(self) -> None:
        (self.work_dir / 'dummy.txt').write_text('d', encoding='utf-8')

        # Width >= 100 so full '[Esc] again to clear' and '[Ctrl+X]' hints fit in status bar
        with self.make_driver(rows=30, cols=100) as driver:
            driver.wait_ready()
            cmd_row = 28
            status_row = 27

            driver.type_text('echo abcd')
            driver.wait_for_text('> echo abcd', row=cmd_row)
            end_col = driver.screen.cursor_col
            self.assertEqual(driver.screen.cursor_row, cmd_row)

            # Left arrow moves cursor inside command line; typing inserts mid-string
            driver.press('left', 'left')
            driver.wait_until(lambda s: s.cursor_col == end_col - 2)
            driver.type_text('XY')
            driver.wait_for_text('> echo abXYcd', row=cmd_row)

            # Backspace deletes 'Y', Right skips 'c', Backspace deletes 'c' -> 'echo abXd',
            # Left onto 'X', Delete removes 'X' -> 'echo abd'
            driver.press('backspace', 'right', 'backspace')
            driver.wait_for_text('> echo abXd', row=cmd_row)
            driver.press('left', 'delete')
            driver.wait_for_text('> echo abd', row=cmd_row)

            # First Esc shows '[Esc] again to clear'; second Esc clears command line
            driver.press_esc_settled()
            driver.wait_for_text('[Esc] again to clear', row=status_row)
            self.assertIn('echo abd', driver.screen.row_text(cmd_row))

            driver.press_esc_settled()
            driver.wait_until(
                lambda s: 'echo abd' not in s.row_text(cmd_row)
                and '[Esc] again to clear' not in s.row_text(status_row)
            )

            # Ctrl+X chord displays full '[Ctrl+X] c=chmod o=chown' hint at cols >= 100
            driver.press('ctrl+x')
            driver.wait_for_text('[Ctrl+X] c=chmod o=chown', row=status_row)
            driver.press_esc_settled()
            driver.wait_until(lambda s: '[Ctrl+X]' not in s.row_text(status_row))

            self.quit_cleanly(driver)

    def test_alt_enter_inserts_quoted_filename_and_command_executes(self) -> None:
        (self.work_dir / 'my file.txt').write_text('space', encoding='utf-8')
        (self.work_dir / 'plain.txt').write_text('plain', encoding='utf-8')

        with self.make_driver(rows=24, cols=100) as driver:
            driver.wait_ready()

            # Move cursor to 'my file.txt' and press Alt+Enter
            driver.press('down')
            driver.wait_for_text('my file.txt', row=21)
            driver.type_text('ls ')
            driver.press('alt+enter')
            driver.wait_for_text("ls 'my file.txt'", row=22)

            # Clear via double-Esc, then execute a real shell command creating a file
            driver.press_esc_settled()
            driver.wait_for_text('[Esc] again to clear', row=21)
            driver.press_esc_settled()
            driver.wait_until(lambda s: "ls 'my file.txt'" not in s.row_text(22))

            driver.type_text('touch cmd_created.txt')
            driver.wait_for_text('touch cmd_created.txt', row=22)
            driver.press('enter')
            driver.wait_for_text('[Press any key to continue]')
            driver.wait_stable()
            driver.press('space')
            driver.wait_ready()
            driver.wait_for_text('cmd_created.txt')
            self.assertTrue((self.work_dir / 'cmd_created.txt').is_file())

            self.quit_cleanly(driver)

    def test_command_line_priority_horizontal_scroll_and_f1_help_chrome(self) -> None:
        (self.work_dir / 'alpha.txt').write_text('a', encoding='utf-8')

        with self.make_driver(rows=24, cols=80) as driver:
            driver.wait_ready()

            # Selection modifiers (+, -, *, /) go literally to command line when non-empty
            driver.type_text('echo 1+2-3*4/5')
            driver.wait_for_text('> echo 1+2-3*4/5', row=22)

            # Long input collapses prompt to '> ' and scrolls horizontally around cursor
            driver.type_text(' ' + 'z' * 75)
            driver.wait_until(
                lambda s: s.row_text(22).startswith('> ') and 'zzzzzz' in s.row_text(22)
            )
            self.assertLess(driver.screen.cursor_col, 80)
            self.assertEqual(driver.screen.check_integrity(), [])

            # Clear command line and test F1 help modal chrome
            driver.press_esc_settled()
            driver.press_esc_settled()
            driver.wait_until(lambda s: 'zzzzzz' not in s.row_text(22))

            driver.press('f1')
            driver.wait_for_text('Keyboard Shortcuts')
            driver.press('down')
            driver.wait_stable(0.03)
            driver.press_esc_settled()
            driver.wait_until(lambda s: not s.contains('Keyboard Shortcuts'))

            self.quit_cleanly(driver)


class TestE2ELiveResizes(_E2ETestBase):
    """Real-PTY tests for live SIGWINCH resizing across shrink, expand, and odd-width layouts."""

    def test_live_resize_shrink_expand_odd_width_matrix(self) -> None:
        (self.work_dir / 'subdir').mkdir()
        for i in range(10):
            (self.work_dir / f'file_{i:02d}.txt').write_text('content', encoding='utf-8')

        matrix = [
            (24, 80),
            (18, 60),
            (14, 45),
            (30, 81),  # Odd width: left=40, right=41
            (40, 120),
        ]

        with self.make_driver(rows=36, cols=100) as driver:
            driver.wait_ready()
            self.assert_chrome_and_borders(driver.screen)
            # At cols=100 (panel_width=50 >= 50), mtime column ':' is visible
            self.assertIn(':', driver.screen.row_text(3))

            for rows, cols in matrix:
                driver.resize_and_wait(
                    rows,
                    cols,
                    predicate=lambda s, r=rows: s.find_text('F10', row=r - 1) is not None,
                )
                self.assert_chrome_and_borders(driver.screen)

                if cols == 80:
                    # panel_width=40 < 50 hides mtime column
                    left_row3 = self.panel_rows(driver.screen, 'left')[1]
                    self.assertNotIn(':', left_row3)
                elif cols == 120:
                    self.assertIn(':', self.panel_rows(driver.screen, 'left')[1])

            self.quit_cleanly(driver)

    def test_resize_preserves_scroll_position_and_navigation_state(self) -> None:
        for i in range(45):
            (self.work_dir / f'entry_{i:02d}.txt').write_text('x', encoding='utf-8')

        with self.make_driver(rows=36, cols=100) as driver:
            driver.wait_ready()
            driver.press('end')
            driver.wait_for_text('46 of 46', row=33)
            driver.press('up', 'up', 'up', 'up', 'up')
            driver.wait_for_text('41 of 46', row=33)
            driver.wait_for_text('entry_39.txt')

            # Shrink below scroll position; _adjust_scroll must keep cursor entry visible
            driver.resize_and_wait(
                18,
                60,
                predicate=lambda s: s.find_text('F10', row=17) is not None,
            )
            self.assert_chrome_and_borders(driver.screen)
            self.assertIn('41 of 46', driver.screen.row_text(15))
            self.assertIsNotNone(driver.screen.find_styled_text('entry_39.txt', fg=0, bg=6))

            # Resize through odd width and expand back
            driver.resize_and_wait(
                30,
                81,
                predicate=lambda s: s.find_text('F10', row=29) is not None,
            )
            self.assert_chrome_and_borders(driver.screen)
            self.assertIsNotNone(driver.screen.find_styled_text('entry_39.txt', fg=0, bg=6))

            driver.resize_and_wait(
                40,
                120,
                predicate=lambda s: s.find_text('F10', row=39) is not None,
            )
            self.assert_chrome_and_borders(driver.screen)
            self.assertIn('41 of 46', driver.screen.row_text(37))
            self.assertIsNotNone(driver.screen.find_styled_text('entry_39.txt', fg=0, bg=6))

            self.quit_cleanly(driver)


class TestE2EVisualStylesThemesAndEdgeCases(_E2ETestBase):
    """Real-PTY tests for TERM color/monochrome/dumb fallbacks, Unicode, and deep paths."""

    def test_xterm_256color_themes_and_file_type_styles(self) -> None:
        (self.work_dir / '.dot_hidden').write_text('h', encoding='utf-8')
        (self.work_dir / 'a_dir').mkdir()
        exe = self.work_dir / 'run_me.sh'
        exe.write_text('#!/bin/sh\necho ok\n', encoding='utf-8')
        exe.chmod(0o755)
        target = self.work_dir / 'plain.txt'
        target.write_text('p', encoding='utf-8')
        (self.work_dir / 'link_ok.txt').symlink_to(target)
        (self.work_dir / 'link_bad.txt').symlink_to(self.work_dir / 'missing_target')

        with self.make_driver(rows=24, cols=100, term='xterm-256color') as driver:
            driver.wait_ready()

            # Classic theme: blue panel bg=4, active cursor fg=0 bg=6, distinct file type colors
            self.assertEqual(driver.screen.style_at(15, 2).bg, 4)
            self.assertIsNotNone(driver.screen.find_styled_text('../', row=2, fg=0, bg=6))
            self.assertIsNotNone(driver.screen.find_styled_text('a_dir/', row=3, fg=7, bg=4, bold=True))
            self.assertIsNotNone(driver.screen.find_styled_text('.dot_hidden', row=4, fg=6, bg=4))
            self.assertIsNotNone(driver.screen.find_styled_text('link_bad.txt', row=5, fg=1, bg=4))
            self.assertIsNotNone(driver.screen.find_styled_text('link_ok.txt', row=6, fg=5, bg=4))
            self.assertIsNotNone(driver.screen.find_styled_text('*run_me.sh', row=8, fg=2, bg=4, bold=True))

            # Toggle Options -> Classic colors to switch to Modern transparent theme
            driver.press('f9')
            driver.wait_for_text('Sort by name')
            driver.press('right', 'right', 'right')
            driver.wait_for_text('Classic colors')
            driver.press('down', 'down', 'enter')
            driver.wait_until(lambda s: s.style_at(15, 2).bg is None)
            self.assertIsNotNone(driver.screen.find_styled_text('../', row=2, fg=7, bg=6))
            self.assertIsNotNone(
                driver.screen.find_styled_text('a_dir/', row=3, fg=4, bg=None, bold=True)
            )

            self.quit_cleanly(driver)

    def test_monochrome_xterm_r6_and_dumb_term_fallbacks(self) -> None:
        (self.work_dir / 'folder').mkdir()
        (self.work_dir / 'item.txt').write_text('item', encoding='utf-8')

        # TERM=xterm-r6: monochrome fallback (reverse cursor/bars, bold dirs/selected)
        self.assertFalse(KeyMap('xterm-r6').supports_colors)
        with self.make_driver(rows=24, cols=80, term='xterm-r6') as driver:
            driver.wait_ready()
            self.assert_chrome_and_borders(driver.screen)

            self.assertIsNotNone(
                driver.screen.find_styled_text('../', row=2, fg=None, bg=None, reverse=True)
            )
            self.assertIsNotNone(
                driver.screen.find_styled_text('folder/', row=3, fg=None, bg=None, bold=True, reverse=False)
            )

            # Select item.txt and move cursor back to folder/ to verify bold selected style
            driver.press('down', 'down', 'insert', 'up')
            driver.wait_until(
                lambda s: '1 selected' in s.row_text(21)
                and s.find_styled_text('folder/', row=3, fg=None, bg=None, reverse=True) is not None
            )
            self.assertIsNotNone(
                driver.screen.find_styled_text('item.txt', row=4, fg=None, bg=None, bold=True)
            )
            self.assertTrue(
                all(st.reverse for st in driver.screen.styles_for_text('[Left]', row=21))
            )

            self.quit_cleanly(driver)

        # TERM=dumb: no alt-screen or cursor addressing, starts cleanly without crash
        self.assertFalse(KeyMap('dumb').supports_colors)
        with self.make_driver(rows=24, cols=80, term='dumb') as driver:
            driver.wait_until(
                lambda s: driver.is_alive() and s.contains('F10'),
                description='TERM=dumb initial render',
            )
            driver.wait_stable(0.05)
            self.assertTrue(driver.is_alive())
            self.assertEqual(driver.screen.check_integrity(), [])
            self.assertNotIn('Traceback', driver.screen.text())
            self.assertNotIn('curses.error', driver.screen.text())
            driver.send_signal(signal.SIGINT)
            rc = driver.wait_exit()
            self.assertNotEqual(rc, 1)

    def test_unicode_cjk_combining_nfd_and_long_filename_truncation(self) -> None:
        cjk_name = '中文.txt'
        nfd_name = unicodedata.normalize('NFD', 'café_nfd.txt')
        long_name = 'long_' + 'x' * 65 + '.log'
        (self.work_dir / cjk_name).write_text('cjk', encoding='utf-8')
        (self.work_dir / nfd_name).write_text('nfd', encoding='utf-8')
        (self.work_dir / long_name).write_text('long', encoding='utf-8')

        for rows, cols in ((24, 80), (30, 100)):
            with self.make_driver(rows=rows, cols=cols) as driver:
                driver.wait_ready()
                self.assert_chrome_and_borders(driver.screen)

                cjk_pos = driver.screen.find_text('中文.txt')
                self.assertIsNotNone(cjk_pos)
                cjk_col, cjk_row = cjk_pos
                self.assertTrue(driver.screen.cell(cjk_row, cjk_col + 1).is_continuation)
                self.assertTrue(driver.screen.cell(cjk_row, cjk_col + 3).is_continuation)

                self.assertTrue(driver.screen.contains(nfd_name))
                self.assertTrue(driver.screen.contains('long_' + 'x' * 10))
                self.assertTrue(driver.screen.contains('...'))

                # Move cursor to CJK entry and insert via Alt+Enter into command line
                driver.press('end')
                driver.wait_for_text('4 of 4', row=rows - 3)
                driver.press('alt+enter')
                driver.wait_for_text('中文.txt', row=rows - 2)
                self.assert_chrome_and_borders(driver.screen)

                self.quit_cleanly(driver)

    def test_deep_nested_paths_truncation_and_navigation(self) -> None:
        deep = self.work_dir
        for i in range(1, 13):
            deep = deep / f'lvl_{i:02d}'
        deep.mkdir(parents=True)
        (deep / 'leaf_marker.txt').write_text('leaf', encoding='utf-8')

        start_dir = deep.parent.parent  # lvl_10
        with self.make_driver(rows=24, cols=80, cwd=start_dir) as driver:
            driver.wait_ready()
            self.assert_chrome_and_borders(driver.screen)

            # Long nested path header and prompt truncate from left with '...'
            left_hdr = self.panel_header(driver.screen, 'left')
            self.assertIn('vn ...', left_hdr)
            self.assertIn('/lvl_10', left_hdr)
            self.assertIn('...', driver.screen.row_text(22))

            # Descend into lvl_11 -> lvl_12
            driver.press('down', 'enter')
            driver.wait_until(
                lambda s: '/lvl_11' in self.panel_header(s, 'left')
                and s.contains('lvl_12/')
            )
            driver.press('down', 'enter')
            driver.wait_until(
                lambda s: '/lvl_12' in self.panel_header(s, 'left')
                and s.contains('leaf_marker.txt')
            )
            self.assert_chrome_and_borders(driver.screen)

            # Navigate back via '..' and verify cursor recalls lvl_12
            driver.press('enter')
            driver.wait_until(
                lambda s: '/lvl_11' in self.panel_header(s, 'left')
                and s.find_styled_text('lvl_12/', row=3, fg=0, bg=6) is not None
            )
            self.assert_chrome_and_borders(driver.screen)

            self.quit_cleanly(driver)


if __name__ == '__main__':
    unittest.main()
