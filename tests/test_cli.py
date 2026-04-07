"""Tests for CLI argument support."""

from __future__ import annotations

import unittest

from agent_cli.cli import _build_overrides, _build_parser


class CliTest(unittest.TestCase):
    """Covers common CLI flags."""

    def test_parser_accepts_api_key_and_debug(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["--api-key", "secret", "--debug", "doctor"])

        self.assertEqual(args.api_key, "secret")
        self.assertTrue(args.debug)

    def test_build_overrides_includes_api_key_and_debug(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["--api-key", "secret", "--debug", "--model", "m"])

        overrides = _build_overrides(args=args)

        self.assertEqual(overrides["model.api_key"], "secret")
        self.assertEqual(overrides["debug"], True)


if __name__ == "__main__":
    unittest.main()

