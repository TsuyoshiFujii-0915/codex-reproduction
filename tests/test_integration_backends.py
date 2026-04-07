"""Optional integration tests for real backends."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.model_client import ResponsesModelClient


class BackendIntegrationTest(unittest.TestCase):
    """Covers real backend requests when env vars are configured."""

    def test_lmstudio_or_compatible_backend(self) -> None:
        base_url = os.environ.get("AGENT_TEST_BASE_URL")
        model = os.environ.get("AGENT_TEST_MODEL")
        if base_url is None or model is None:
            self.skipTest("AGENT_TEST_BASE_URL and AGENT_TEST_MODEL are required")
        client = ResponsesModelClient(base_url=base_url, api_key="", timeout_seconds=30)
        response = client.create_response(
            {
                "model": model,
                "instructions": "Return short text.",
                "tools": [],
                "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "ping"}]}],
                "stream": False,
                "store": False,
                "parallel_tool_calls": False,
            }
        )
        self.assertIsInstance(response.output_items, list)

    def test_openai_backend(self) -> None:
        base_url = os.environ.get("AGENT_TEST_OPENAI_BASE_URL")
        model = os.environ.get("AGENT_TEST_OPENAI_MODEL")
        api_key = os.environ.get("OPENAI_API_KEY")
        if base_url is None or model is None or api_key is None:
            self.skipTest("AGENT_TEST_OPENAI_BASE_URL, AGENT_TEST_OPENAI_MODEL, and OPENAI_API_KEY are required")
        client = ResponsesModelClient(base_url=base_url, api_key=api_key, timeout_seconds=30)
        response = client.create_response(
            {
                "model": model,
                "instructions": "Return short text.",
                "tools": [],
                "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "ping"}]}],
                "stream": False,
                "store": False,
                "parallel_tool_calls": False,
            }
        )
        self.assertIsInstance(response.output_items, list)


if __name__ == "__main__":
    unittest.main()
