"""
Tests for helper functions in main.py.

These functions are pure logic — no video file, no FFmpeg, no API needed.
"""

from main import _format_duration


class TestFormatDuration:
    def test_seconds_only(self):
        assert _format_duration(45) == "0:45"

    def test_one_minute(self):
        assert _format_duration(60) == "1:00"

    def test_minutes_and_seconds(self):
        assert _format_duration(90) == "1:30"

    def test_zero(self):
        assert _format_duration(0) == "0:00"

    def test_exactly_one_hour(self):
        assert _format_duration(3600) == "1:00:00"

    def test_hours_minutes_seconds(self):
        assert _format_duration(3661) == "1:01:01"

    def test_long_video(self):
        assert _format_duration(7384) == "2:03:04"

    def test_float_is_truncated(self):
        # float seconds should be truncated, not rounded
        assert _format_duration(90.9) == "1:30"
