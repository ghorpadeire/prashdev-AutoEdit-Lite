"""
Tests for analyze.py helper functions.

No Claude API call is made — we test the pure logic functions directly
by feeding them fake data and checking the output.
"""

import json
import pytest
from analyze import _fmt_time, _format_transcript, _estimate_tokens, _parse_and_validate_json


class TestFmtTime:
    def test_zero(self):
        assert _fmt_time(0) == "00:00.0"

    def test_seconds(self):
        assert _fmt_time(5.5) == "00:05.5"

    def test_one_minute(self):
        assert _fmt_time(60) == "01:00.0"

    def test_minutes_and_seconds(self):
        assert _fmt_time(90.3) == "01:30.3"

    def test_large_value(self):
        assert _fmt_time(600) == "10:00.0"


class TestFormatTranscript:
    def test_single_segment(self):
        segments = [{"start": 0.0, "end": 5.0, "text": "Hello world"}]
        result = _format_transcript(segments)
        assert "Hello world" in result
        assert "00:00.0" in result
        assert "00:05.0" in result

    def test_multiple_segments(self):
        segments = [
            {"start": 0.0, "end": 3.0, "text": "First line"},
            {"start": 3.0, "end": 6.0, "text": "Second line"},
        ]
        result = _format_transcript(segments)
        assert "First line" in result
        assert "Second line" in result
        assert result.count("\n") == 1  # two lines separated by one newline

    def test_empty_segments(self):
        assert _format_transcript([]) == ""


class TestEstimateTokens:
    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_four_chars_equals_one_token(self):
        assert _estimate_tokens("abcd") == 1

    def test_longer_text(self):
        text = "a" * 100
        assert _estimate_tokens(text) == 25


class TestParseAndValidateJson:
    VIDEO_DURATION = 120.0

    def _make_raw(self, segments):
        return json.dumps({"segments_to_keep": segments})

    def test_valid_segments(self):
        raw = self._make_raw([{"start": 0.0, "end": 10.0, "reason": "good"}])
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION)
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 10.0

    def test_strips_markdown_fences(self):
        raw = "```json\n" + self._make_raw([{"start": 1.0, "end": 5.0, "reason": "ok"}]) + "\n```"
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION)
        assert len(result) == 1

    def test_rejects_start_greater_than_end(self):
        raw = self._make_raw([{"start": 10.0, "end": 5.0, "reason": "bad"}])
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION)
        assert result == []

    def test_rejects_too_short_segment(self):
        # duration = 0.3s which is below MIN_SEGMENT_DURATION (0.5s)
        raw = self._make_raw([{"start": 1.0, "end": 1.3, "reason": "too short"}])
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION)
        assert result == []

    def test_clamps_segment_beyond_video_duration(self):
        raw = self._make_raw([{"start": 100.0, "end": 150.0, "reason": "past end"}])
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION)
        assert len(result) == 1
        assert result[0]["end"] == self.VIDEO_DURATION

    def test_rejects_segment_starting_past_video(self):
        raw = self._make_raw([{"start": 130.0, "end": 140.0, "reason": "out of bounds"}])
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION)
        assert result == []

    def test_multiple_valid_segments(self):
        raw = self._make_raw([
            {"start": 0.0, "end": 10.0, "reason": "first"},
            {"start": 20.0, "end": 30.0, "reason": "second"},
        ])
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION)
        assert len(result) == 2

    def test_chunk_offset_applied(self):
        # Chunk offset shifts timestamps (used when processing long videos in chunks)
        raw = self._make_raw([{"start": 0.0, "end": 10.0, "reason": "chunk"}])
        result = _parse_and_validate_json(raw, self.VIDEO_DURATION, chunk_start_offset=60.0)
        assert result[0]["start"] == 60.0
        assert result[0]["end"] == 70.0

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            _parse_and_validate_json("not json at all", self.VIDEO_DURATION)
