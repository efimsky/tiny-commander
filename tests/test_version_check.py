"""Tests for Python version checking."""

import sys
import unittest


class TestVersionCheck(unittest.TestCase):
    """Tests for version check functionality."""

    def test_check_python_version_returns_none_for_313(self):
        """Version check passes for Python 3.13+."""
        # Import the check function (uses only 3.0+ compatible syntax)
        from tnc._version_check import check_python_version

        # Simulate Python 3.13
        result = check_python_version((3, 13, 0))
        self.assertIsNone(result)

    def test_check_python_version_returns_none_for_314(self):
        """Version check passes for Python 3.14+."""
        from tnc._version_check import check_python_version

        result = check_python_version((3, 14, 0))
        self.assertIsNone(result)

    def test_check_python_version_returns_error_for_312(self):
        """Version check fails for Python 3.12."""
        from tnc._version_check import check_python_version

        result = check_python_version((3, 12, 5))
        self.assertIsNotNone(result)
        self.assertIn("3.13", result)
        self.assertIn("3.12", result)

    def test_check_python_version_returns_error_for_39(self):
        """Version check fails for Python 3.9."""
        from tnc._version_check import check_python_version

        result = check_python_version((3, 9, 7))
        self.assertIsNotNone(result)
        self.assertIn("3.13", result)
        self.assertIn("3.9", result)

    def test_check_python_version_returns_error_for_python2(self):
        """Version check fails for Python 2.x."""
        from tnc._version_check import check_python_version

        result = check_python_version((2, 7, 18))
        self.assertIsNotNone(result)
        self.assertIn("3.13", result)
        self.assertIn("2.7", result)

    def test_error_message_format(self):
        """Error message has expected format."""
        from tnc._version_check import check_python_version

        result = check_python_version((3, 9, 1))
        self.assertEqual(result, "tnc requires Python 3.13 or later. You have 3.9.")


if __name__ == "__main__":
    unittest.main()
