"""Tests for CLI argument support."""

from __future__ import annotations

import unittest

from agent_cli.cli import _build_overrides, _parse_args


class CliTest(unittest.TestCase):
    """Covers common CLI flags."""

    def test_parser_accepts_api_key_and_debug(self) -> None:
        args = _parse_args(["--api-key", "secret", "--debug", "doctor"])

        self.assertEqual(args.api_key, "secret")
        self.assertTrue(args.debug)
        self.assertEqual(args.command, "doctor")

    def test_build_overrides_includes_api_key_and_debug(self) -> None:
        args = _parse_args(["--api-key", "secret", "--debug", "--model", "m"])

        overrides = _build_overrides(args=args)

        self.assertEqual(overrides["model.api_key"], "secret")
        self.assertEqual(overrides["debug"], True)

    def test_parse_args_accepts_config_init(self) -> None:
        args = _parse_args(["config", "init"])

        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "init")

    def test_parse_args_treats_non_command_as_prompt(self) -> None:
        args = _parse_args(["README を要約して"])

        self.assertIsNone(args.command)
        self.assertEqual(args.prompt, "README を要約して")


if __name__ == "__main__":
    unittest.main()
