"""Tests for streaming error handling."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


class _CrLfStreamingResponse:
    def __iter__(self) -> "_CrLfStreamingResponse":
        self._lines = iter(
            [
                b"event: response.created\r\n",
                b'data: {"response":{"id":"resp-1"}}\r\n',
                b"\r\n",
                b"event: response.output_item.done\r\n",
                (
                    b'data: {"item":{"type":"message","role":"assistant","content":'
                    b'[{"type":"output_text","text":"hello"}]}}\r\n'
                ),
                b"\r\n",
                b"event: response.completed\r\n",
                (
                    b'data: {"response":{"id":"resp-1","output":[{"type":"message",'
                    b'"role":"assistant","content":[{"type":"output_text","text":"hello"}]}]}}\r\n'
                ),
                b"\r\n",
            ]
        )
        return self

    def __next__(self) -> bytes:
        return next(self._lines)


class _StreamingResponseWithCommentAndEofFlush:
    def __iter__(self) -> "_StreamingResponseWithCommentAndEofFlush":
        self._lines = iter(
            [
                b": keep-alive\n",
                b"event: response.completed\n",
                b'data: {"response":{"id":"resp-2","output":[]}}',
            ]
        )
        return self

    def __next__(self) -> bytes:
        return next(self._lines)


class _DataOnlyTypedStreamingResponse:
    def __iter__(self) -> "_DataOnlyTypedStreamingResponse":
        self._lines = iter(
            [
                b'data: {"type":"response.created","response":{"id":"resp-3"}}\n',
                b"\n",
                (
                    b'data: {"type":"response.output_item.done","item":{"type":"message","role":"assistant",'
                    b'"content":[{"type":"output_text","text":"hello"}]}}\n'
                ),
                b"\n",
                (
                    b'data: {"type":"response.completed","response":{"id":"resp-3","output":[{"type":"message",'
                    b'"role":"assistant","content":[{"type":"output_text","text":"hello"}]}]}}\n'
                ),
                b"\n",
                b"data: [DONE]\n",
                b"\n",
            ]
        )
        return self

    def __next__(self) -> bytes:
        return next(self._lines)


class _UnrecognizedStreamingResponse:
    def __iter__(self) -> "_UnrecognizedStreamingResponse":
        self._lines = iter(
            [
                b'{"id":"resp-x","output":[]}\n',
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

    def test_parse_streaming_response_accepts_crlf_delimiters(self) -> None:
        parsed = _parse_streaming_response(response=_CrLfStreamingResponse())

        self.assertEqual(parsed.response_id, "resp-1")
        self.assertEqual(parsed.output_items[0]["content"][0]["text"], "hello")

    def test_parse_streaming_response_ignores_comments_and_flushes_at_eof(self) -> None:
        parsed = _parse_streaming_response(response=_StreamingResponseWithCommentAndEofFlush())

        self.assertEqual(parsed.response_id, "resp-2")
        self.assertEqual(parsed.output_items, [])

    def test_parse_streaming_response_accepts_data_only_typed_events(self) -> None:
        parsed = _parse_streaming_response(response=_DataOnlyTypedStreamingResponse())

        self.assertEqual(parsed.response_id, "resp-3")
        self.assertEqual(parsed.output_items[0]["content"][0]["text"], "hello")

    def test_parse_streaming_response_writes_raw_debug_dump_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            debug_path: Path = Path(tmp_dir) / "stream.log"

            with self.assertRaisesRegex(RuntimeError, "stream ended without response.completed"):
                _parse_streaming_response(
                    response=_UnrecognizedStreamingResponse(),
                    debug_output_path=debug_path,
                )

            self.assertEqual(
                debug_path.read_text(encoding="utf-8"),
                '{"id":"resp-x","output":[]}\n',
            )


if __name__ == "__main__":
    unittest.main()
