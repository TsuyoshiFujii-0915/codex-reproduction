"""Tests for streaming error handling."""

from __future__ import annotations

import unittest

from agent_cli.model_client import _parse_streaming_response


class _FakeStreamingResponse:
    def __iter__(self) -> "_FakeStreamingResponse":
        self._lines = iter(
            [
                b"event: error\n",
                b'data: {"message":"boom"}\n',
                b"\n",
            ]
        )
        return self

    def __next__(self) -> bytes:
        return next(self._lines)


class StreamingErrorTest(unittest.TestCase):
    """Covers explicit error events in streaming responses."""

    def test_parse_streaming_response_raises_on_error_event(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "boom"):
            _parse_streaming_response(response=_FakeStreamingResponse())


if __name__ == "__main__":
    unittest.main()

