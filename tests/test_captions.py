"""
Tests for captions.py.

We feed fake transcript + kept segments and verify the .srt file content.
No video file needed — just plain Python dicts and a temp file.
"""

import pytest
from pathlib import Path
from captions import _seconds_to_srt_time, generate_srt


class TestSecondsToSrtTime:
    def test_zero(self):
        assert _seconds_to_srt_time(0) == "00:00:00,000"

    def test_milliseconds(self):
        assert _seconds_to_srt_time(0.5) == "00:00:00,500"

    def test_one_minute(self):
        assert _seconds_to_srt_time(60) == "00:01:00,000"

    def test_one_hour(self):
        assert _seconds_to_srt_time(3600) == "01:00:00,000"

    def test_complex(self):
        assert _seconds_to_srt_time(3723.456) == "01:02:03,456"


class TestGenerateSrt:
    def test_basic_output(self, tmp_path):
        transcript = [{"start": 0.0, "end": 5.0, "text": "Hello world"}]
        kept = [{"start": 0.0, "end": 5.0, "reason": "good"}]
        out = tmp_path / "test.srt"

        generate_srt(transcript, kept, str(out))

        content = out.read_text()
        assert "Hello world" in content
        assert "00:00:00,000 --> 00:00:05,000" in content

    def test_srt_index_starts_at_one(self, tmp_path):
        transcript = [{"start": 0.0, "end": 3.0, "text": "First"}]
        kept = [{"start": 0.0, "end": 3.0, "reason": "good"}]
        out = tmp_path / "test.srt"

        generate_srt(transcript, kept, str(out))

        lines = out.read_text().strip().split("\n")
        assert lines[0] == "1"

    def test_empty_kept_segments(self, tmp_path):
        transcript = [{"start": 0.0, "end": 5.0, "text": "Hello"}]
        out = tmp_path / "empty.srt"

        generate_srt(transcript, [], str(out))

        assert out.read_text() == ""

    def test_timestamps_reset_for_edited_video(self, tmp_path):
        # Original video: keep segment starting at 30s
        # In the edited video this segment starts at 0s
        transcript = [{"start": 30.0, "end": 35.0, "text": "Kept part"}]
        kept = [{"start": 30.0, "end": 35.0, "reason": "good"}]
        out = tmp_path / "test.srt"

        generate_srt(transcript, kept, str(out))

        content = out.read_text()
        # Output timestamps should start at 00:00:00,000 not 00:00:30,000
        assert "00:00:00,000 --> 00:00:05,000" in content

    def test_skips_empty_text(self, tmp_path):
        transcript = [
            {"start": 0.0, "end": 3.0, "text": "   "},   # whitespace only
            {"start": 3.0, "end": 6.0, "text": "Real text"},
        ]
        kept = [{"start": 0.0, "end": 6.0, "reason": "good"}]
        out = tmp_path / "test.srt"

        generate_srt(transcript, kept, str(out))

        content = out.read_text()
        assert "Real text" in content
        # Only one subtitle entry (index "1" appears once at the start)
        assert content.count("\n1\n") == 0  # no second entry
        assert content.startswith("1\n")    # first and only entry
