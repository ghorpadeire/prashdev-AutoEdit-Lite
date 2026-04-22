"""
tests/test_losslesscut_export.py

Unit tests for losslesscut_export.py
"""

import csv
import pytest
from pathlib import Path
from losslesscut_export import export_losslesscut_csv


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_segments():
    return [
        {"start": 2.43,  "end": 18.5,  "reason": "strong hook"},
        {"start": 25.0,  "end": 40.2,  "reason": "clear value proposition"},
        {"start": 143.1, "end": 152.7, "reason": "clean retake"},
    ]


@pytest.fixture
def output_path(tmp_path):
    return str(tmp_path / "output" / "video_autoedit_cuts.csv")


# ── Tests ──────────────────────────────────────────────────────────────────

class TestExportLosslessCutCsv:

    def test_creates_file(self, sample_segments, output_path):
        """File is created at the given path."""
        export_losslesscut_csv(sample_segments, output_path)
        assert Path(output_path).exists()

    def test_creates_parent_dirs(self, sample_segments, tmp_path):
        """Nested parent directories are created automatically."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "cuts.csv")
        export_losslesscut_csv(sample_segments, deep_path)
        assert Path(deep_path).exists()

    def test_header_row(self, sample_segments, output_path):
        """First row is START,END,LABEL."""
        export_losslesscut_csv(sample_segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == ["START", "END", "LABEL"]

    def test_correct_row_count(self, sample_segments, output_path):
        """File has header + one row per segment."""
        export_losslesscut_csv(sample_segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        # header + 3 segments
        assert len(rows) == 4

    def test_timestamps_preserved(self, sample_segments, output_path):
        """START and END columns match segment timestamps."""
        export_losslesscut_csv(sample_segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert float(rows[0]["START"]) == pytest.approx(2.43)
        assert float(rows[0]["END"])   == pytest.approx(18.5)
        assert float(rows[2]["START"]) == pytest.approx(143.1)
        assert float(rows[2]["END"])   == pytest.approx(152.7)

    def test_reason_used_as_label(self, sample_segments, output_path):
        """Claude's reason appears as the LABEL column value."""
        export_losslesscut_csv(sample_segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["LABEL"] == "strong hook"
        assert rows[1]["LABEL"] == "clear value proposition"

    def test_fallback_label_when_no_reason(self, output_path):
        """Segments without a reason get a timestamp-based fallback label."""
        segments = [{"start": 5.0, "end": 10.0, "reason": ""}]
        export_losslesscut_csv(segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["LABEL"] != ""
        assert "5.0" in rows[0]["LABEL"]

    def test_label_truncated_to_100_chars(self, output_path):
        """Labels longer than 100 characters are truncated."""
        long_reason = "x" * 200
        segments = [{"start": 1.0, "end": 2.0, "reason": long_reason}]
        export_losslesscut_csv(segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows[0]["LABEL"]) <= 100

    def test_empty_segments_no_file_written(self, tmp_path):
        """Empty segment list does not create a file."""
        out = str(tmp_path / "cuts.csv")
        export_losslesscut_csv([], out)
        assert not Path(out).exists()

    def test_missing_reason_key(self, output_path):
        """Segments dict without a 'reason' key uses fallback label."""
        segments = [{"start": 3.0, "end": 7.5}]  # no 'reason' key
        export_losslesscut_csv(segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["LABEL"] != ""

    def test_timestamps_rounded_to_3dp(self, output_path):
        """Timestamps are rounded to 3 decimal places."""
        segments = [{"start": 1.123456789, "end": 9.987654321, "reason": "test"}]
        export_losslesscut_csv(segments, output_path)
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # Should be rounded, not a long float string
        assert len(rows[0]["START"].replace(".", "")) <= 6
        assert len(rows[0]["END"].replace(".", "")) <= 6
