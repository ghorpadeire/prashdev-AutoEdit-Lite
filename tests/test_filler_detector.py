"""
Tests for filler_detector.py.

All tests use plain Python dicts — no external dependencies, no files on disk.
"""

import pytest
from filler_detector import (
    detect_fillers,
    merge_overlaps,
    apply_removals_to_segments,
    STRONG_FILLERS,
    SENTENCE_START_FILLERS,
    GAP_THRESHOLD_DEFAULT,
    OVERLAP_RATIO,
)


# ── Test helpers ──────────────────────────────────────────────────────────────

def _word(word: str, start: float, end: float, prob: float = 0.99) -> dict:
    return {"word": word, "start": start, "end": end, "probability": prob}


def _seg(text: str, start: float, end: float, words: list[dict] = None) -> dict:
    d = {"start": start, "end": end, "text": text}
    if words is not None:
        d["words"] = words
    return d


# ── Strong filler detection ───────────────────────────────────────────────────

class TestDetectFillersStrongFillers:
    def test_um_detected(self):
        words = [_word("um", 0.0, 0.4), _word("hello.", 0.4, 1.0)]
        segs = [_seg("um hello.", 0.0, 1.0, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:strong" for r in result)

    def test_uh_detected(self):
        words = [_word("uh", 0.0, 0.3), _word("okay.", 0.3, 0.8)]
        segs = [_seg("uh okay.", 0.0, 0.8, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:strong" for r in result)

    def test_hmm_detected(self):
        words = [_word("hmm", 1.0, 1.5), _word("interesting.", 1.5, 2.5)]
        segs = [_seg("hmm interesting.", 1.0, 2.5, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:strong" for r in result)

    def test_filler_timestamps_correct(self):
        words = [_word("um", 2.0, 2.5), _word("hello.", 2.5, 3.0)]
        segs = [_seg("um hello.", 2.0, 3.0, words)]
        result = detect_fillers(segs)
        filler = next(r for r in result if r["reason"] == "filler:strong")
        assert filler["start"] == 2.0
        assert filler["end"] == 2.5

    def test_case_insensitive(self):
        words = [_word("UM", 0.0, 0.4), _word("hello.", 0.4, 1.0)]
        segs = [_seg("UM hello.", 0.0, 1.0, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:strong" for r in result)

    def test_punctuation_stripped_from_token(self):
        # faster-whisper may attach a comma to a filler token
        words = [_word("um,", 0.0, 0.4), _word("hello.", 0.4, 1.0)]
        segs = [_seg("um, hello.", 0.0, 1.0, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:strong" for r in result)

    def test_no_filler_in_clean_speech(self):
        words = [
            _word("The", 0.0, 0.2), _word("sky", 0.2, 0.5),
            _word("is", 0.5, 0.7), _word("blue.", 0.7, 1.0),
        ]
        segs = [_seg("The sky is blue.", 0.0, 1.0, words)]
        result = detect_fillers(segs)
        assert not any(r["reason"] == "filler:strong" for r in result)

    def test_multiple_fillers_in_one_segment(self):
        words = [_word("um", 0.0, 0.3), _word("uh", 0.4, 0.7), _word("hello.", 0.8, 1.5)]
        segs = [_seg("um uh hello.", 0.0, 1.5, words)]
        result = detect_fillers(segs)
        assert sum(1 for r in result if r["reason"] == "filler:strong") == 2

    def test_no_words_key_returns_empty(self):
        segs = [{"start": 0.0, "end": 5.0, "text": "um hello"}]
        assert detect_fillers(segs) == []

    def test_empty_words_list_returns_empty(self):
        segs = [_seg("um hello", 0.0, 5.0, [])]
        assert detect_fillers(segs) == []


# ── Sentence-start filler detection ──────────────────────────────────────────

class TestDetectFillersSentenceStart:
    def test_so_at_very_start_detected(self):
        words = [
            _word("So", 0.0, 0.3), _word("let", 0.3, 0.5),
            _word("me", 0.5, 0.7), _word("begin.", 0.7, 1.2),
        ]
        segs = [_seg("So let me begin.", 0.0, 1.2, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)

    def test_okay_after_eos_detected(self):
        words = [
            _word("Good.", 0.0, 0.5), _word("Okay", 0.5, 0.8),
            _word("moving", 0.8, 1.1), _word("on.", 1.1, 1.5),
        ]
        segs = [_seg("Good. Okay moving on.", 0.0, 1.5, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)

    def test_so_mid_sentence_not_flagged(self):
        words = [
            _word("I", 0.0, 0.2), _word("did", 0.2, 0.4),
            _word("it", 0.4, 0.6), _word("so", 0.6, 0.8),
            _word("quickly.", 0.8, 1.2),
        ]
        segs = [_seg("I did it so quickly.", 0.0, 1.2, words)]
        result = detect_fillers(segs)
        assert not any(r["reason"] == "filler:sentence_start" for r in result)

    def test_right_after_eos_detected(self):
        words = [
            _word("Done.", 0.0, 0.5), _word("Right,", 0.5, 0.8),
            _word("next.", 0.8, 1.2),
        ]
        segs = [_seg("Done. Right, next.", 0.0, 1.2, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)

    def test_well_after_question_detected(self):
        words = [
            _word("Why?", 0.0, 0.5), _word("Well", 0.5, 0.8),
            _word("because.", 0.8, 1.4),
        ]
        segs = [_seg("Why? Well because.", 0.0, 1.4, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)


# ── Gap detection ─────────────────────────────────────────────────────────────

class TestDetectFillersGapDetection:
    def test_gap_above_threshold_detected(self):
        words = [_word("Hello.", 0.0, 0.5), _word("World.", 2.0, 2.8)]
        segs = [_seg("Hello. World.", 0.0, 2.8, words)]
        result = detect_fillers(segs)
        gaps = [r for r in result if r["reason"] == "gap"]
        assert len(gaps) == 1
        assert gaps[0]["start"] == 0.5
        assert gaps[0]["end"] == 2.0

    def test_gap_below_threshold_not_detected(self):
        words = [_word("Hello.", 0.0, 0.5), _word("World.", 1.0, 1.8)]
        segs = [_seg("Hello. World.", 0.0, 1.8, words)]
        result = detect_fillers(segs, gap_threshold=0.8)
        assert not any(r["reason"] == "gap" for r in result)

    def test_gap_exactly_at_threshold_not_detected(self):
        # 1.3 - 0.5 = 0.8 is NOT strictly greater than 0.8
        words = [_word("A.", 0.0, 0.5), _word("B.", 1.3, 2.0)]
        segs = [_seg("A. B.", 0.0, 2.0, words)]
        result = detect_fillers(segs, gap_threshold=0.8)
        assert not any(r["reason"] == "gap" for r in result)

    def test_custom_threshold(self):
        words = [_word("A.", 0.0, 0.5), _word("B.", 0.8, 1.5)]
        segs = [_seg("A. B.", 0.0, 1.5, words)]
        result = detect_fillers(segs, gap_threshold=0.2)
        gaps = [r for r in result if r["reason"] == "gap"]
        assert len(gaps) == 1  # 0.8 - 0.5 = 0.3 > 0.2

    def test_no_gap_before_first_word(self):
        # 3 seconds of silence before first spoken word — must NOT be flagged
        words = [_word("Hello.", 3.0, 3.5), _word("World.", 4.0, 4.5)]
        segs = [_seg("Hello. World.", 3.0, 4.5, words)]
        result = detect_fillers(segs)
        assert not any(r["reason"] == "gap" for r in result)

    def test_multiple_gaps(self):
        words = [
            _word("A.", 0.0, 0.5),
            _word("B.", 2.0, 2.5),
            _word("C.", 5.0, 5.5),
        ]
        segs = [_seg("A. B. C.", 0.0, 5.5, words)]
        result = detect_fillers(segs)
        gaps = [r for r in result if r["reason"] == "gap"]
        assert len(gaps) == 2


# ── False-start detection ─────────────────────────────────────────────────────

class TestDetectFillersFalseStart:
    def _two_utterances(self, u1: list[tuple], u2: list[tuple]) -> list[dict]:
        """Build segment with u1 ending in EOS punct followed by u2."""
        words = []
        for idx, (w, s, e) in enumerate(u1):
            word_str = w + "." if idx == len(u1) - 1 else w
            words.append(_word(word_str, s, e))
        for w, s, e in u2:
            words.append(_word(w, s, e))
        return [_seg("...", words[0]["start"], words[-1]["end"], words)]

    def test_high_jaccard_flagged(self):
        segs = self._two_utterances(
            [("I", 0.0, 0.2), ("want", 0.2, 0.4), ("to", 0.4, 0.6), ("say", 0.6, 0.8), ("something", 0.8, 1.0)],
            [("I", 1.1, 1.3), ("want", 1.3, 1.5), ("to", 1.5, 1.7), ("say", 1.7, 1.9), ("something", 1.9, 2.1), ("important.", 2.1, 2.5)],
        )
        result = detect_fillers(segs)
        assert any(r["reason"] == "false_start" for r in result)

    def test_low_overlap_not_flagged(self):
        segs = self._two_utterances(
            [("I", 0.0, 0.2), ("love", 0.2, 0.5), ("cats", 0.5, 0.8)],
            [("dogs", 1.0, 1.2), ("are", 1.2, 1.4), ("great", 1.4, 1.6), ("pets.", 1.6, 2.0)],
        )
        result = detect_fillers(segs)
        assert not any(r["reason"] == "false_start" for r in result)

    def test_short_utterances_skipped(self):
        # Both utterances < _MIN_UTT_TOKENS (3) — must not be flagged
        segs = self._two_utterances(
            [("Go", 0.0, 0.3), ("now", 0.3, 0.6)],
            [("Go", 0.7, 1.0), ("now.", 1.0, 1.3)],
        )
        result = detect_fillers(segs)
        assert not any(r["reason"] == "false_start" for r in result)

    def test_false_start_timestamps_match_first_utterance(self):
        segs = self._two_utterances(
            [("The", 1.0, 1.2), ("idea", 1.2, 1.5), ("is", 1.5, 1.7), ("simple", 1.7, 2.0)],
            [("The", 2.1, 2.3), ("idea", 2.3, 2.6), ("is", 2.6, 2.8), ("really", 2.8, 3.0), ("simple.", 3.0, 3.4)],
        )
        result = detect_fillers(segs)
        fs = [r for r in result if r["reason"] == "false_start"]
        assert len(fs) >= 1
        assert fs[0]["start"] == 1.0
        assert fs[0]["end"] == 2.0


# ── merge_overlaps ────────────────────────────────────────────────────────────

class TestMergeOverlaps:
    def test_empty(self):
        assert merge_overlaps([]) == []

    def test_single_item_unchanged(self):
        r = [{"start": 1.0, "end": 2.0, "reason": "gap"}]
        assert merge_overlaps(r) == r

    def test_non_overlapping_unchanged(self):
        r = [
            {"start": 1.0, "end": 2.0, "reason": "gap"},
            {"start": 3.0, "end": 4.0, "reason": "filler:strong"},
        ]
        assert merge_overlaps(r) == r

    def test_overlapping_merged(self):
        r = [
            {"start": 1.0, "end": 3.0, "reason": "gap"},
            {"start": 2.0, "end": 4.0, "reason": "filler:strong"},
        ]
        result = merge_overlaps(r)
        assert len(result) == 1
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 4.0

    def test_adjacent_merged(self):
        r = [
            {"start": 1.0, "end": 2.0, "reason": "gap"},
            {"start": 2.0, "end": 3.0, "reason": "filler:strong"},
        ]
        result = merge_overlaps(r)
        assert len(result) == 1
        assert result[0]["end"] == 3.0

    def test_contained_range_merged(self):
        r = [
            {"start": 1.0, "end": 5.0, "reason": "gap"},
            {"start": 2.0, "end": 3.0, "reason": "filler:strong"},
        ]
        result = merge_overlaps(r)
        assert len(result) == 1
        assert result[0]["end"] == 5.0

    def test_three_overlapping_merged_to_one(self):
        r = [
            {"start": 0.0, "end": 2.0, "reason": "a"},
            {"start": 1.5, "end": 3.0, "reason": "b"},
            {"start": 2.8, "end": 4.0, "reason": "c"},
        ]
        result = merge_overlaps(r)
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 4.0

    def test_original_list_not_mutated(self):
        r = [
            {"start": 1.0, "end": 3.0, "reason": "gap"},
            {"start": 2.0, "end": 4.0, "reason": "filler:strong"},
        ]
        r_copy = [dict(x) for x in r]
        merge_overlaps(r)
        assert r == r_copy


# ── apply_removals_to_segments ────────────────────────────────────────────────

class TestApplyRemovalsToSegments:
    def test_empty_removals_returns_all(self):
        segs = [_seg("Hello", 0.0, 5.0), _seg("World", 5.0, 10.0)]
        result = apply_removals_to_segments(segs, [])
        assert len(result) == 2

    def test_no_overlap_keeps_all(self):
        segs = [_seg("Hello", 5.0, 10.0)]
        removals = [{"start": 0.0, "end": 1.0, "reason": "gap"}]
        result = apply_removals_to_segments(segs, removals)
        assert len(result) == 1

    def test_below_60_percent_kept(self):
        # 10s segment, 5.5s overlap = 55% < 60%
        segs = [_seg("Hello", 0.0, 10.0)]
        removals = [{"start": 0.0, "end": 5.5, "reason": "gap"}]
        result = apply_removals_to_segments(segs, removals)
        assert len(result) == 1

    def test_at_60_percent_dropped(self):
        # 10s segment, 6.0s overlap = 60% >= 60%
        segs = [_seg("Hello", 0.0, 10.0)]
        removals = [{"start": 0.0, "end": 6.0, "reason": "gap"}]
        result = apply_removals_to_segments(segs, removals)
        assert len(result) == 0

    def test_additive_overlap_across_multiple_removals(self):
        # 10s segment, 3s + 3s = 6s = 60% >= threshold
        segs = [_seg("Hello", 0.0, 10.0)]
        removals = [
            {"start": 1.0, "end": 4.0, "reason": "filler:strong"},
            {"start": 6.0, "end": 9.0, "reason": "filler:strong"},
        ]
        result = apply_removals_to_segments(segs, removals)
        assert len(result) == 0

    def test_words_key_stripped_from_output(self):
        words = [_word("Hi", 0.0, 0.5)]
        segs = [_seg("Hi", 0.0, 5.0, words)]
        result = apply_removals_to_segments(segs, [])
        assert "words" not in result[0]

    def test_text_and_timestamps_preserved(self):
        segs = [_seg("Good content", 1.0, 6.0)]
        removals = [{"start": 0.0, "end": 0.5, "reason": "gap"}]
        result = apply_removals_to_segments(segs, removals)
        assert result[0]["text"] == "Good content"
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 6.0

    def test_zero_duration_segment_skipped(self):
        segs = [{"start": 2.0, "end": 2.0, "text": ""}]
        result = apply_removals_to_segments(segs, [])
        assert len(result) == 0

    def test_mixed_keep_and_drop(self):
        segs = [
            _seg("Filler heavy", 0.0, 10.0),
            _seg("Clean content", 15.0, 25.0),
        ]
        # 80% of first segment is filler
        removals = [{"start": 0.0, "end": 8.0, "reason": "gap"}]
        result = apply_removals_to_segments(segs, removals)
        assert len(result) == 1
        assert result[0]["text"] == "Clean content"

    def test_extra_keys_preserved(self):
        segs = [{"start": 0.0, "end": 5.0, "text": "Hi", "language": "en"}]
        result = apply_removals_to_segments(segs, [])
        assert result[0].get("language") == "en"


# ── EOS inference ─────────────────────────────────────────────────────────────

class TestEosInference:
    def test_period_triggers_sentence_start_for_next_word(self):
        words = [
            _word("Done.", 0.0, 0.5), _word("Okay", 0.5, 0.8), _word("next.", 0.8, 1.2),
        ]
        segs = [_seg("Done. Okay next.", 0.0, 1.2, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)

    def test_question_mark_triggers_sentence_start(self):
        words = [
            _word("Really?", 0.0, 0.5), _word("Well", 0.5, 0.8), _word("yes.", 0.8, 1.2),
        ]
        segs = [_seg("Really? Well yes.", 0.0, 1.2, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)

    def test_exclamation_triggers_sentence_start(self):
        words = [
            _word("Yes!", 0.0, 0.4), _word("Right", 0.4, 0.7), _word("here.", 0.7, 1.0),
        ]
        segs = [_seg("Yes! Right here.", 0.0, 1.0, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)

    def test_comma_does_not_trigger_sentence_start(self):
        words = [
            _word("Hello,", 0.0, 0.4), _word("so", 0.4, 0.6), _word("anyway.", 0.6, 1.0),
        ]
        segs = [_seg("Hello, so anyway.", 0.0, 1.0, words)]
        result = detect_fillers(segs)
        assert not any(r["reason"] == "filler:sentence_start" for r in result)

    def test_first_word_always_at_sentence_start(self):
        words = [
            _word("So", 0.0, 0.3), _word("here", 0.3, 0.6),
            _word("we", 0.6, 0.8), _word("go.", 0.8, 1.1),
        ]
        segs = [_seg("So here we go.", 0.0, 1.1, words)]
        result = detect_fillers(segs)
        assert any(r["reason"] == "filler:sentence_start" for r in result)


# ── Integration ───────────────────────────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline_mixed_fillers(self):
        words = [
            _word("Um", 0.0, 0.3),
            _word("so", 0.3, 0.5),
            _word("today", 0.5, 0.8),
            _word("I", 0.8, 0.9),
            _word("want", 0.9, 1.1),
            _word("to", 1.1, 1.3),
            _word("talk", 1.3, 1.6),
            _word("about", 1.6, 1.9),
            _word("productivity.", 1.9, 2.5),
            _word("The", 4.0, 4.2),   # gap: 4.0 - 2.5 = 1.5s > 0.8s threshold
            _word("key", 4.2, 4.5),
            _word("is", 4.5, 4.7),
            _word("focus.", 4.7, 5.2),
        ]
        segs = [_seg("Um so today I want to talk about productivity. The key is focus.", 0.0, 5.2, words)]
        raw = detect_fillers(segs)
        merged = merge_overlaps(sorted(raw, key=lambda r: r["start"]))
        kept = apply_removals_to_segments(segs, merged)

        reasons = {r["reason"] for r in raw}
        assert "filler:strong" in reasons   # "Um"
        assert "gap" in reasons             # 1.5s pause between sentences
        # "so" follows "Um" (no EOS punct) so it is NOT at sentence start — correct

        # Segment has mostly clean content (only first 0.5s is filler + gap) — kept
        assert len(kept) == 1

    def test_no_words_key_skips_gracefully(self):
        segs = [
            {"start": 0.0, "end": 5.0, "text": "um hello there"},
            {"start": 5.0, "end": 10.0, "text": "this is good content"},
        ]
        assert detect_fillers(segs) == []
        kept = apply_removals_to_segments(segs, [])
        assert len(kept) == 2

    def test_heavily_fillered_segment_dropped(self):
        words = [
            _word("um", 0.0, 0.5), _word("uh", 0.5, 1.0), _word("ah", 1.0, 1.5),
            _word("hmm", 1.5, 2.0), _word("er", 2.0, 2.5), _word("yeah.", 2.5, 3.0),
        ]
        segs = [_seg("um uh ah hmm er yeah.", 0.0, 3.0, words)]
        raw = detect_fillers(segs)
        merged = merge_overlaps(sorted(raw, key=lambda r: r["start"]))
        kept = apply_removals_to_segments(segs, merged)
        # 5 fillers cover 0.0-2.5 (83% of 3.0s) — dropped
        assert len(kept) == 0

    def test_clean_segment_always_kept(self):
        words = [
            _word("The", 0.0, 0.2), _word("most", 0.2, 0.5),
            _word("important", 0.5, 0.9), _word("thing", 0.9, 1.1),
            _word("is", 1.1, 1.3), _word("consistency.", 1.3, 2.0),
        ]
        segs = [_seg("The most important thing is consistency.", 0.0, 2.0, words)]
        raw = detect_fillers(segs)
        merged = merge_overlaps(sorted(raw, key=lambda r: r["start"]))
        kept = apply_removals_to_segments(segs, merged)
        assert len(kept) == 1
        assert kept[0]["text"] == "The most important thing is consistency."

    def test_multi_segment_words_across_segments(self):
        segs = [
            _seg("um really.", 0.0, 1.0, [_word("um", 0.0, 0.4), _word("really.", 0.4, 1.0)]),
            _seg("The idea is clear.", 1.5, 4.0, [
                _word("The", 1.5, 1.7), _word("idea", 1.7, 2.0),
                _word("is", 2.0, 2.2), _word("clear.", 2.2, 4.0),
            ]),
        ]
        raw = detect_fillers(segs)
        merged = merge_overlaps(sorted(raw, key=lambda r: r["start"]))
        kept = apply_removals_to_segments(segs, merged)
        # First seg: "um" (0.4s) / 1.0s = 40% < 60% → kept
        # Second seg: no fillers → kept
        assert len(kept) == 2
