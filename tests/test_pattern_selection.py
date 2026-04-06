"""Tests for multi-select patterns (+, -, *)."""

import fnmatch
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tnc.panel import Panel


class TestSelectByPattern(unittest.TestCase):
    """Test '+' key - select by pattern."""

    def test_select_by_pattern_wildcard(self):
        """Pattern with * should select matching files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()
            Path(tmpdir, 'image.png').touch()
            Path(tmpdir, 'data.csv').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('*.txt')

            self.assertIn('file1.txt', panel.selected)
            self.assertIn('file2.txt', panel.selected)
            self.assertNotIn('image.png', panel.selected)
            self.assertNotIn('data.csv', panel.selected)

    def test_select_by_pattern_question_mark(self):
        """Pattern with ? should match single character."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()
            Path(tmpdir, 'file10.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('file?.txt')

            self.assertIn('file1.txt', panel.selected)
            self.assertIn('file2.txt', panel.selected)
            self.assertNotIn('file10.txt', panel.selected)

    def test_select_by_pattern_adds_to_existing(self):
        """Selecting by pattern should add to existing selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()
            Path(tmpdir, 'image.png').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.selected.add('file.txt')
            panel.select_by_pattern('*.png')

            self.assertIn('file.txt', panel.selected)
            self.assertIn('image.png', panel.selected)

    def test_empty_pattern_selects_nothing(self):
        """Empty pattern should not select anything."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('')

            self.assertEqual(len(panel.selected), 0)

    def test_dotdot_never_selected_by_pattern(self):
        """'..' should never be selected by any pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('*')

            self.assertNotIn('..', panel.selected)

    def test_dotdot_pattern_does_not_select_dotdot(self):
        """Pattern matching '..' should not select it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('..*')

            self.assertNotIn('..', panel.selected)


class TestDeselectByPattern(unittest.TestCase):
    """Test '-' key - deselect by pattern."""

    def test_deselect_by_pattern(self):
        """Deselect should remove matching files from selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()
            Path(tmpdir, 'image.png').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('*')  # Select all
            panel.deselect_by_pattern('*.txt')

            self.assertNotIn('file1.txt', panel.selected)
            self.assertNotIn('file2.txt', panel.selected)
            self.assertIn('image.png', panel.selected)

    def test_deselect_only_selected_files(self):
        """Deselect should only affect already selected files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()
            Path(tmpdir, 'other.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.selected.add('file.txt')
            panel.deselect_by_pattern('*.txt')

            self.assertEqual(len(panel.selected), 0)

    def test_empty_deselect_pattern_does_nothing(self):
        """Empty deselect pattern should not change selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.selected.add('file.txt')
            panel.deselect_by_pattern('')

            self.assertIn('file.txt', panel.selected)


class TestInvertSelection(unittest.TestCase):
    """Test '*' key - invert selection."""

    def test_invert_selection_empty_to_all(self):
        """Invert with no selection should select all (except '..')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()
            Path(tmpdir, 'image.png').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.invert_selection()

            # All files should be selected (3 files, not '..')
            self.assertEqual(len(panel.selected), 3)
            self.assertIn('file1.txt', panel.selected)
            self.assertIn('file2.txt', panel.selected)
            self.assertIn('image.png', panel.selected)
            self.assertNotIn('..', panel.selected)

    def test_invert_selection_all_to_empty(self):
        """Invert with all selected should deselect all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('*')
            panel.invert_selection()

            self.assertEqual(len(panel.selected), 0)

    def test_invert_selection_partial(self):
        """Invert with partial selection should swap selected/unselected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()
            Path(tmpdir, 'image.png').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_by_pattern('*.txt')
            panel.invert_selection()

            self.assertNotIn('file1.txt', panel.selected)
            self.assertNotIn('file2.txt', panel.selected)
            self.assertIn('image.png', panel.selected)

    def test_invert_never_selects_dotdot(self):
        """Invert should never select '..'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.invert_selection()

            self.assertNotIn('..', panel.selected)


class TestKeyHandlingForPatterns(unittest.TestCase):
    """Test key handling for pattern selection."""

    @mock.patch('curses.has_colors', return_value=False)
    @mock.patch('curses.curs_set')
    def test_asterisk_key_triggers_invert(self, _mock_curs_set, _mock_has_colors):
        """'*' key should call panel.invert_selection()."""
        from tnc.app import App

        mock_stdscr = mock.MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)

        app = App(mock_stdscr)
        app.setup()

        with mock.patch.object(app.active_panel, 'invert_selection') as mock_invert:
            app.handle_key(ord('*'))
            mock_invert.assert_called_once()


class TestSelectAll(unittest.TestCase):
    """Test select_all method."""

    def test_select_all_selects_all_files(self):
        """select_all should select all files and directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file1.txt').touch()
            Path(tmpdir, 'file2.txt').touch()
            Path(tmpdir, 'subdir').mkdir()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_all()

            self.assertIn('file1.txt', panel.selected)
            self.assertIn('file2.txt', panel.selected)
            self.assertIn('subdir', panel.selected)

    def test_select_all_excludes_dotdot(self):
        """select_all should not select '..' entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, 'file.txt').touch()

            panel = Panel(tmpdir, width=40, height=20)
            panel.select_all()

            self.assertNotIn('..', panel.selected)
            self.assertIn('file.txt', panel.selected)

    def test_select_all_on_empty_dir(self):
        """select_all on empty directory should result in empty selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = Panel(tmpdir, width=40, height=20)
            panel.select_all()

            self.assertEqual(len(panel.selected), 0)


if __name__ == '__main__':
    unittest.main()
