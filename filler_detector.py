"""
filler_detector.py

O(n) rule-based filler detection over word-level timestamps from faster-whisper.

Detects and tags:
  - Long silences (gaps between spoken words)
  - Strong verbal fillers: um, uh, ah, er, hmm ...
  - Sentence-start soft fillers: so, okay, right ... (only after a sentence boundary)
  - False starts: near-duplicate consecutive utterances (Jaccard + bigram similarity)

apply_removals_to_segments() uses bisect for O(s log r) lookup per segment —
faster than a two-pointer O(s + r) scan when the removal list is short.
"""

import bisect

# ── Tunable constants ─────────────────────────────────────────────────────────

STRONG_FILLERS = frozenset({
    "um", "uh", "ah", "er", "hmm", "hm", "ugh", "mhm", "mm",
})

# Only removed when appearing at the very start of a new sentence
SENTENCE_START_FILLERS = frozenset({
    "so", "okay", "ok", "right", "well", "anyway", "basically", "alright", "now",
})

GAP_THRESHOLD_DEFAULT = 0.8   # silences longer than this (seconds) are flagged
JACCARD_THRESHOLD     = 0.6   # word-set Jaccard for false-start detection
BIGRAM_THRESHOLD      = 0.5   # bigram Jaccard for false-start detection
OVERLAP_RATIO         = 0.60  # drop segment if >= 60% of its duration is filler

_MIN_UTT_TOKENS = 3           # minimum tokens per utterance for false-start check
_EOS_CHARS      = frozenset(".?!")
_PUNCT_STRIP    = str.maketrans("", "", ".,!?;:-'\"")


def _token(word_str: str) -> str:
    """Lowercase, punctuation-stripped token for set/dict operations."""
    return word_str.lower().translate(_PUNCT_STRIP).strip()


def _is_eos(word_str: str) -> bool:
    """True if this word token ends a sentence (faster-whisper attaches punctuation)."""
    return bool(word_str) and word_str[-1:] in _EOS_CHARS


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return {(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)}


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


# ── Core detection ────────────────────────────────────────────────────────────

def detect_fillers(
    word_segments: list[dict],
    gap_threshold: float = GAP_THRESHOLD_DEFAULT,
) -> list[dict]:
    """
    Single O(n) forward pass that detects filler ranges in word-timestamped segments.

    Parameters
    ----------
    word_segments : list[dict]
        Transcript segments each optionally containing a "words" key with per-word
        dicts: {"word": str, "start": float, "end": float, "probability": float}.
    gap_threshold : float
        Silences longer than this (seconds) are tagged "gap".

    Returns
    -------
    list[dict]
        Removal ranges: [{"start": float, "end": float, "reason": str}, ...].
        Not guaranteed to be sorted — call merge_overlaps(sorted(...)) before use.
    """
    all_words: list[dict] = []
    for seg in word_segments:
        all_words.extend(seg.get("words") or [])

    if not all_words:
        return []

    removals: list[dict] = []

    # Forward-pass state
    prev_end = 0.0
    prev_eos = True  # treat the very start of the recording as a sentence boundary

    # Utterance accumulation (sentence-grouped) for false-start detection
    utterances: list[tuple[float, float, list[str]]] = []
    utt_tokens: list[str] = []
    utt_start = float(all_words[0]["start"])
    utt_end   = utt_start

    for i, w in enumerate(all_words):
        tok     = _token(w["word"])
        w_start = float(w["start"])
        w_end   = float(w["end"])

        # 1. Gap detection (checked first so emission order is monotone)
        if i > 0 and (w_start - prev_end) > gap_threshold:
            removals.append({
                "start":  round(prev_end, 3),
                "end":    round(w_start,  3),
                "reason": "gap",
            })

        # 2. Strong filler (always flagged regardless of position)
        if tok in STRONG_FILLERS:
            removals.append({
                "start":  round(w_start, 3),
                "end":    round(w_end,   3),
                "reason": "filler:strong",
            })

        # 3. Sentence-start soft filler (only flagged after an EOS word)
        elif tok in SENTENCE_START_FILLERS and prev_eos:
            removals.append({
                "start":  round(w_start, 3),
                "end":    round(w_end,   3),
                "reason": "filler:sentence_start",
            })

        # 4. Accumulate tokens for utterance grouping (all words, including fillers)
        if tok:
            utt_tokens.append(tok)
            utt_end = w_end

        # 5. Close utterance on EOS punctuation
        if _is_eos(w["word"]) and utt_tokens:
            utterances.append((utt_start, utt_end, utt_tokens))
            utt_tokens = []
            nxt_start  = float(all_words[i + 1]["start"]) if i + 1 < len(all_words) else w_end
            utt_start  = nxt_start
            utt_end    = nxt_start

        prev_end = w_end
        prev_eos = _is_eos(w["word"])

    # Flush trailing utterance (no terminal EOS punctuation)
    if utt_tokens:
        utterances.append((utt_start, utt_end, utt_tokens))

    # 6. False-start detection: O(u) pass over consecutive utterance pairs
    for i in range(len(utterances) - 1):
        u1_start, u1_end, u1_toks = utterances[i]
        _,        _,      u2_toks = utterances[i + 1]

        if len(u1_toks) < _MIN_UTT_TOKENS or len(u2_toks) < _MIN_UTT_TOKENS:
            continue

        u1_set = set(u1_toks)
        u2_set = set(u2_toks)

        if (
            _jaccard(u1_set, u2_set) >= JACCARD_THRESHOLD
            or _jaccard(_bigrams(u1_toks), _bigrams(u2_toks)) >= BIGRAM_THRESHOLD
        ):
            removals.append({
                "start":  round(u1_start, 3),
                "end":    round(u1_end,   3),
                "reason": "false_start",
            })

    return removals


# ── Merge overlapping removal ranges ─────────────────────────────────────────

def merge_overlaps(removals: list[dict]) -> list[dict]:
    """
    O(m) merge of sorted removal ranges into non-overlapping spans.

    Precondition: removals is sorted by "start".
    """
    if not removals:
        return []
    merged = [dict(removals[0])]
    for r in removals[1:]:
        cur = merged[-1]
        if r["start"] <= cur["end"]:
            cur["end"] = max(cur["end"], r["end"])
        else:
            merged.append(dict(r))
    return merged


# ── Apply removals to transcript segments ─────────────────────────────────────

def apply_removals_to_segments(
    transcript_segments: list[dict],
    removals: list[dict],
) -> list[dict]:
    """
    O(s log r) segment filter using bisect on removal end-times.

    For each transcript segment, binary-searches the removal list to find
    the first range whose end > seg.start, then linearly scans forward to
    accumulate total overlap. Drops any segment where filler overlap covers
    >= OVERLAP_RATIO of its duration.

    Parameters
    ----------
    transcript_segments : list[dict]
        Segments with at minimum "start", "end", "text" keys.
        "words" key is stripped from output (not needed downstream).
    removals : list[dict]
        Sorted, non-overlapping removal ranges from merge_overlaps().

    Returns
    -------
    list[dict]
        Filtered segments with {"start", "end", "text"} keys.
    """
    if not removals:
        return [
            {k: v for k, v in seg.items() if k != "words"}
            for seg in transcript_segments
            if float(seg["end"]) - float(seg["start"]) > 0
        ]

    # Build sorted end-time index once — O(r)
    removal_ends = [r["end"] for r in removals]

    kept: list[dict] = []
    for seg in transcript_segments:
        seg_start = float(seg["start"])
        seg_end   = float(seg["end"])
        duration  = seg_end - seg_start
        if duration <= 0:
            continue

        # Jump past removals that end before this segment starts — O(log r)
        idx = bisect.bisect_right(removal_ends, seg_start)

        overlap = 0.0
        j = idx
        while j < len(removals) and removals[j]["start"] < seg_end:
            r = removals[j]
            o = min(r["end"], seg_end) - max(r["start"], seg_start)
            if o > 0:
                overlap += o
            j += 1

        if overlap / duration < OVERLAP_RATIO:
            kept.append({k: v for k, v in seg.items() if k != "words"})

    return kept
