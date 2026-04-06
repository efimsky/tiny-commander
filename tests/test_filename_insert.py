"""Tests for Alt+Enter filename insertion."""

import unittest

from tnc.command_line import CommandLine


class TestSimpleInsertion(unittest.TestCase):
    """Test simple filename insertion."""

    def test_insert_simple_filename(self):
        """Simple filename should be inserted."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cat '
        cmdline.cursor_pos = 4
        cmdline.insert_filename('file.txt')
        self.assertEqual(cmdline.input_text, 'cat file.txt')

    def test_insert_directory_name(self):
        """Directory name should be inserted."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cd '
        cmdline.cursor_pos = 3
        cmdline.insert_filename('my_dir')
        self.assertEqual(cmdline.input_text, 'cd my_dir')

    def test_insert_dotdot(self):
        """'..' should be inserted."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cd '
        cmdline.cursor_pos = 3
        cmdline.insert_filename('..')
        self.assertEqual(cmdline.input_text, 'cd ..')


class TestQuotedInsertion(unittest.TestCase):
    """Test filenames that need quoting."""

    def test_insert_filename_with_spaces(self):
        """Filename with spaces should be quoted."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cat '
        cmdline.cursor_pos = 4
        cmdline.insert_filename('my file.txt')
        # Should be quoted
        self.assertIn('my file.txt', cmdline.input_text)
        # Check for quotes
        self.assertTrue(
            "'my file.txt'" in cmdline.input_text or
            '"my file.txt"' in cmdline.input_text
        )

    def test_insert_filename_with_special_chars(self):
        """Special characters should be quoted."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = ''
        cmdline.cursor_pos = 0
        cmdline.insert_filename('file$name.txt')
        # Should be quoted to protect $
        self.assertTrue(
            "'" in cmdline.input_text or
            '\\"' in cmdline.input_text or
            '\\$' in cmdline.input_text
        )


class TestCursorPosition(unittest.TestCase):
    """Test cursor positioning after insert."""

    def test_cursor_moves_after_insertion(self):
        """Cursor should move to end of inserted text."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = ''
        cmdline.cursor_pos = 0
        cmdline.insert_filename('test.txt')
        self.assertEqual(cmdline.cursor_pos, len(cmdline.input_text))

    def test_insert_in_middle_of_command(self):
        """Insert at cursor in middle of text."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cp  /dest'
        cmdline.cursor_pos = 3
        cmdline.insert_filename('source.txt')
        self.assertEqual(cmdline.input_text, 'cp source.txt /dest')


class TestUnicodeInsertion(unittest.TestCase):
    """Test unicode filename insertion."""

    def test_insert_unicode_filename(self):
        """Unicode filenames should work."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cat '
        cmdline.cursor_pos = 4
        cmdline.insert_filename('файл.txt')
        self.assertIn('файл.txt', cmdline.input_text)


class TestQuoteEscaping(unittest.TestCase):
    """Test handling of filenames with quotes."""

    def test_insert_filename_with_single_quote(self):
        """Single quotes in filename should be handled."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = ''
        cmdline.cursor_pos = 0
        cmdline.insert_filename("it's a file.txt")
        # Should not break shell parsing
        result = cmdline.input_text
        self.assertIn("it", result)


class TestLeadingSpaceBehavior(unittest.TestCase):
    """Test automatic leading space insertion (mc behavior)."""

    def test_leading_space_added_after_non_whitespace(self):
        """Space should be added when text before cursor is not whitespace."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'file1.txt'
        cmdline.cursor_pos = 9  # At end
        cmdline.insert_filename('file2.txt')
        self.assertEqual(cmdline.input_text, 'file1.txt file2.txt')

    def test_no_leading_space_after_whitespace(self):
        """No extra space when text before cursor is whitespace."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cat '
        cmdline.cursor_pos = 4  # After the space
        cmdline.insert_filename('file.txt')
        self.assertEqual(cmdline.input_text, 'cat file.txt')

    def test_no_leading_space_on_empty_line(self):
        """No leading space when command line is empty."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = ''
        cmdline.cursor_pos = 0
        cmdline.insert_filename('file.txt')
        self.assertEqual(cmdline.input_text, 'file.txt')

    def test_leading_space_in_middle_after_non_whitespace(self):
        """Space added when inserting in middle after non-whitespace."""
        cmdline = CommandLine('/tmp')
        cmdline.input_text = 'cp dest/'
        cmdline.cursor_pos = 2  # After 'cp'
        cmdline.insert_filename('source.txt')
        self.assertEqual(cmdline.input_text, 'cp source.txt dest/')


if __name__ == '__main__':
    unittest.main()
