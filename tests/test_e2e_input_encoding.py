"""Unit tests for KeyMap and MouseEncoder input encoding."""

import unittest

from tests.terminal.input_encoding import KeyMap, MouseButton, MouseEncoder


class TestKeyMap(unittest.TestCase):
    """Test keyboard sequence synthesis across terminfo and xterm fallback."""

    def setUp(self) -> None:
        self.km = KeyMap('xterm-256color')

    def test_basic_navigation_and_editing_keys(self) -> None:
        self.assertIn(self.km.encode('enter'), (b'\r', b'\n'))
        self.assertEqual(self.km.encode('enter'), b'\r')
        self.assertEqual(self.km.encode('lf'), b'\n')
        self.assertEqual(self.km.encode('tab'), b'\t')
        self.assertEqual(self.km.encode('esc'), b'\x1b')
        self.assertEqual(self.km.encode('space'), b' ')

        for name in ('up', 'down', 'left', 'right', 'home', 'end', 'pgup', 'pgdn', 'insert', 'delete', 'backspace'):
            seq = self.km.encode(name)
            self.assertIsInstance(seq, bytes)
            self.assertGreater(len(seq), 0)

    def test_case_insensitive_and_single_chars(self) -> None:
        self.assertEqual(self.km.encode('UP'), self.km.encode('up'))
        self.assertEqual(self.km.encode('a'), b'a')
        self.assertEqual(self.km.encode('/'), b'/')
        self.assertEqual(self.km.encode('ф'), 'ф'.encode('utf-8'))

    def test_function_keys_and_modifiers(self) -> None:
        for n in range(1, 13):
            self.assertGreater(len(self.km.encode(f'f{n}')), 1)
        self.assertEqual(self.km.encode('f10'), b'\x1b[21~')
        self.assertEqual(self.km.encode('shift+f3'), b'\x1b[1;2R')
        self.assertEqual(self.km.encode('shift+f4'), b'\x1b[1;2S')
        self.assertEqual(self.km.encode('ctrl+f3'), b'\x1b[1;5R')
        self.assertEqual(self.km.encode('alt+f3'), b'\x1b[1;3R')

    def test_alt_and_ctrl_chords_and_sequences(self) -> None:
        self.assertEqual(self.km.encode('alt+enter'), b'\x1b\r')
        self.assertEqual(self.km.encode('alt+o'), b'\x1bo')
        self.assertEqual(self.km.encode('alt+left'), b'\x1b' + self.km.encode('left'))
        self.assertEqual(self.km.encode('alt+right'), b'\x1b' + self.km.encode('right'))
        self.assertEqual(self.km.encode('ctrl+x'), b'\x18')
        self.assertEqual(self.km.encode('ctrl+c'), b'\x03')
        self.assertEqual(self.km.encode_sequence('ctrl+x', 'c'), b'\x18c')

    def test_unknown_key_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.km.encode('nonexistent_key')
        with self.assertRaises(KeyError):
            self.km.encode('hyper+f1')


class TestMouseEncoder(unittest.TestCase):
    """Test X10 and SGR mouse protocol byte sequences."""

    def test_x10_press_release_click_and_wheel(self) -> None:
        self.assertEqual(MouseEncoder.x10_press(MouseButton.LEFT, 0, 0), b'\x1b[M !!')
        self.assertEqual(MouseEncoder.x10_press(MouseButton.RIGHT, 9, 4), b'\x1b[M"*%')
        self.assertEqual(MouseEncoder.x10_release(9, 4), b'\x1b[M#*%')
        self.assertEqual(
            MouseEncoder.x10_click(MouseButton.LEFT, 5, 2),
            b'\x1b[M &#\x1b[M#&#',
        )
        self.assertEqual(MouseEncoder.x10_wheel('up', 10, 10), bytes([0x1b, ord('['), ord('M'), 96, 43, 43]))
        self.assertEqual(MouseEncoder.x10_wheel('down', 10, 10), bytes([0x1b, ord('['), ord('M'), 97, 43, 43]))

    def test_x10_coordinate_bounds(self) -> None:
        with self.assertRaises(ValueError):
            MouseEncoder.x10_press(MouseButton.LEFT, -1, 0)
        with self.assertRaises(ValueError):
            MouseEncoder.x10_press(MouseButton.LEFT, 223, 0)
        with self.assertRaises(ValueError):
            MouseEncoder.x10_press(MouseButton.LEFT, 0, 223)

    def test_sgr_encoding_supports_wide_coordinates(self) -> None:
        self.assertEqual(MouseEncoder.sgr_press(MouseButton.LEFT, 300, 100), b'\x1b[<0;301;101M')
        self.assertEqual(MouseEncoder.sgr_release(MouseButton.LEFT, 300, 100), b'\x1b[<0;301;101m')
        self.assertEqual(
            MouseEncoder.sgr_click(MouseButton.RIGHT, 10, 5),
            b'\x1b[<2;11;6M\x1b[<2;11;6m',
        )
        self.assertEqual(MouseEncoder.sgr_wheel('up', 5, 5), b'\x1b[<64;6;6M')
        self.assertEqual(MouseEncoder.sgr_wheel('down', 5, 5), b'\x1b[<65;6;6M')


if __name__ == '__main__':
    unittest.main()
