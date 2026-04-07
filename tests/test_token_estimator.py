"""Tests for token estimation."""

from __future__ import annotations

import unittest

from agent_cli.token_estimator import estimate_text_tokens


class TokenEstimatorTest(unittest.TestCase):
    """Covers heuristic token estimation."""

    def test_estimate_text_tokens_uses_character_heuristic(self) -> None:
        self.assertEqual(estimate_text_tokens("abcd" * 10), 10)


if __name__ == "__main__":
    unittest.main()

