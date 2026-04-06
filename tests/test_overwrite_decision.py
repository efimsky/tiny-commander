"""Tests for overwrite decision logic extraction."""

import unittest

from tnc.file_ops import (
    OverwriteChoice,
    OverwriteState,
    get_overwrite_decision,
    apply_overwrite_choice,
)


class TestOverwriteState(unittest.TestCase):
    """Tests for OverwriteState dataclass."""

    def test_default_state(self):
        """Default state has all flags False."""
        state = OverwriteState()
        self.assertFalse(state.overwrite_all)
        self.assertFalse(state.skip_all)
        self.assertFalse(state.overwrite_older)

    def test_state_with_overwrite_all(self):
        """Can create state with overwrite_all=True."""
        state = OverwriteState(overwrite_all=True)
        self.assertTrue(state.overwrite_all)
        self.assertFalse(state.skip_all)

    def test_state_with_skip_all(self):
        """Can create state with skip_all=True."""
        state = OverwriteState(skip_all=True)
        self.assertTrue(state.skip_all)
        self.assertFalse(state.overwrite_all)

    def test_state_with_overwrite_older(self):
        """Can create state with overwrite_older=True."""
        state = OverwriteState(overwrite_older=True)
        self.assertTrue(state.overwrite_older)


class TestGetOverwriteDecision(unittest.TestCase):
    """Tests for get_overwrite_decision function."""

    def test_skip_all_returns_skip(self):
        """When skip_all is True, decision is 'skip'."""
        state = OverwriteState(skip_all=True)
        decision = get_overwrite_decision(state, source_mtime=100, dest_mtime=50)
        self.assertEqual(decision, 'skip')

    def test_overwrite_all_returns_proceed(self):
        """When overwrite_all is True, decision is 'proceed'."""
        state = OverwriteState(overwrite_all=True)
        decision = get_overwrite_decision(state, source_mtime=100, dest_mtime=50)
        self.assertEqual(decision, 'proceed')

    def test_overwrite_older_source_newer_returns_proceed(self):
        """When overwrite_older and source is newer, decision is 'proceed'."""
        state = OverwriteState(overwrite_older=True)
        decision = get_overwrite_decision(state, source_mtime=100, dest_mtime=50)
        self.assertEqual(decision, 'proceed')

    def test_overwrite_older_source_older_returns_skip(self):
        """When overwrite_older and source is older, decision is 'skip'."""
        state = OverwriteState(overwrite_older=True)
        decision = get_overwrite_decision(state, source_mtime=50, dest_mtime=100)
        self.assertEqual(decision, 'skip')

    def test_overwrite_older_same_mtime_returns_skip(self):
        """When overwrite_older and mtimes are equal, decision is 'skip'."""
        state = OverwriteState(overwrite_older=True)
        decision = get_overwrite_decision(state, source_mtime=100, dest_mtime=100)
        self.assertEqual(decision, 'skip')

    def test_default_state_returns_prompt(self):
        """When no flags set, decision is 'prompt'."""
        state = OverwriteState()
        decision = get_overwrite_decision(state, source_mtime=100, dest_mtime=50)
        self.assertEqual(decision, 'prompt')

    def test_skip_all_takes_precedence_over_overwrite_all(self):
        """skip_all takes precedence when both are set (shouldn't happen)."""
        state = OverwriteState(skip_all=True, overwrite_all=True)
        decision = get_overwrite_decision(state, source_mtime=100, dest_mtime=50)
        self.assertEqual(decision, 'skip')


class TestApplyOverwriteChoice(unittest.TestCase):
    """Tests for apply_overwrite_choice function."""

    def test_yes_returns_proceed_unchanged_state(self):
        """YES choice returns 'proceed' with unchanged state."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.YES, state, source_mtime=100, dest_mtime=50
        )
        self.assertEqual(action, 'proceed')
        self.assertEqual(new_state, state)

    def test_no_returns_skip_unchanged_state(self):
        """NO choice returns 'skip' with unchanged state."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.NO, state, source_mtime=100, dest_mtime=50
        )
        self.assertEqual(action, 'skip')
        self.assertEqual(new_state, state)

    def test_cancel_returns_cancel_unchanged_state(self):
        """CANCEL choice returns 'cancel' with unchanged state."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.CANCEL, state, source_mtime=100, dest_mtime=50
        )
        self.assertEqual(action, 'cancel')
        self.assertEqual(new_state, state)

    def test_yes_all_returns_proceed_sets_overwrite_all(self):
        """YES_ALL returns 'proceed' and sets overwrite_all."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.YES_ALL, state, source_mtime=100, dest_mtime=50
        )
        self.assertEqual(action, 'proceed')
        self.assertTrue(new_state.overwrite_all)
        self.assertFalse(new_state.skip_all)

    def test_no_all_returns_skip_sets_skip_all(self):
        """NO_ALL returns 'skip' and sets skip_all."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.NO_ALL, state, source_mtime=100, dest_mtime=50
        )
        self.assertEqual(action, 'skip')
        self.assertTrue(new_state.skip_all)
        self.assertFalse(new_state.overwrite_all)

    def test_yes_older_source_newer_returns_proceed(self):
        """YES_OLDER with newer source returns 'proceed'."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.YES_OLDER, state, source_mtime=100, dest_mtime=50
        )
        self.assertEqual(action, 'proceed')
        self.assertTrue(new_state.overwrite_older)

    def test_yes_older_source_older_returns_skip(self):
        """YES_OLDER with older source returns 'skip'."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.YES_OLDER, state, source_mtime=50, dest_mtime=100
        )
        self.assertEqual(action, 'skip')
        self.assertTrue(new_state.overwrite_older)

    def test_yes_older_same_mtime_returns_skip(self):
        """YES_OLDER with same mtime returns 'skip'."""
        state = OverwriteState()
        action, new_state = apply_overwrite_choice(
            OverwriteChoice.YES_OLDER, state, source_mtime=100, dest_mtime=100
        )
        self.assertEqual(action, 'skip')
        self.assertTrue(new_state.overwrite_older)


if __name__ == '__main__':
    unittest.main()
