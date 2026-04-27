"""
analyze.py

Sends the transcript to Claude and gets back a structured list of segments
to keep. Handles retries, validation, chunking for long videos, and logging.
"""

import json
import os
import sys
import time
from pathlib import Path

# ── Model configuration ────────────────────────────────────────────────────
MODEL = "claude-opus-4-7"
MAX_TOKENS = 4096

# Approximate token budget for the transcript portion of the prompt.
# claude-opus-4-7 has a 200k context window but we keep chunks modest
# to ensure response quality stays high.
MAX_TRANSCRIPT_TOKENS = 15_000
CHARS_PER_TOKEN = 4            # rough approximation
CHUNK_DURATION_SECONDS = 600   # 10-minute windows when chunking
MAX_SEGMENT_DURATION = 120.0   # seconds
MIN_SEGMENT_DURATION = 0.5     # seconds


def _load_prompt_template(prompts_dir: str = "prompts") -> str:
    template_path = Path(prompts_dir) / "editor_prompt.txt"
    if not template_path.exists():
        print(f"\n[ERROR] Prompt file not found: {template_path}")
        print("  Make sure the 'prompts/editor_prompt.txt' file exists.\n")
        sys.exit(1)
    return template_path.read_text(encoding="utf-8")


def _format_transcript(segments: list[dict]) -> str:
    """Convert segment list into a readable transcript string for Claude."""
    lines = []
    for seg in segments:
        start = _fmt_time(seg["start"])
        end = _fmt_time(seg["end"])
        lines.append(f"[{start} - {end}] {seg['text']}")
    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    """Format seconds as MM:SS.s (e.g. 02:34.7)."""
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:04.1f}"


def _estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _call_claude(
    client,
    prompt: str,
    extra_prefix: str = "",
) -> str:
    """Send a single request to Claude and return the raw text response."""
    full_prompt = extra_prefix + prompt if extra_prefix else prompt
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": full_prompt}],
    )
    return message.content[0].text


def _call_claude_with_cache(
    client,
    full_prompt: str,
    transcript_str: str,
    extra_prefix: str = "",
) -> str:
    """
    Send prompt with cache_control on the static instruction portion.

    The static instruction template (everything before the transcript) is marked
    ephemeral so Anthropic caches it across calls in the same session. Subsequent
    chunks of the same video are billed at ~10% for the template portion.

    Falls back to _call_claude() if the transcript can't be located in the prompt.
    """
    try:
        split_idx = full_prompt.index(transcript_str)
        static_part = (extra_prefix + full_prompt[:split_idx]).strip()
        dynamic_part = full_prompt[split_idx:]
    except ValueError:
        return _call_claude(client, full_prompt, extra_prefix)

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": static_part, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic_part},
        ]}],
    )
    return message.content[0].text


def _parse_and_validate_json(
    raw: str,
    video_duration: float,
    chunk_start_offset: float = 0.0,
) -> list[dict]:
    """
    Parse Claude's JSON response and validate every segment.

    Returns only segments that pass all validation rules.
    Applies chunk_start_offset to convert chunk-relative timestamps to
    absolute timestamps when processing long-video chunks.
    """
    # Strip any accidental markdown fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)   # raises json.JSONDecodeError on bad JSON

    raw_segments = data.get("segments_to_keep", [])
    validated: list[dict] = []
    prev_end = -1.0

    for seg in raw_segments:
        start = float(seg["start"]) + chunk_start_offset
        end = float(seg["end"]) + chunk_start_offset
        reason = seg.get("reason", "")

        # Rule: start < end
        if start >= end:
            continue

        # Rule: minimum duration
        if (end - start) < MIN_SEGMENT_DURATION:
            continue

        # Rule: maximum duration
        if (end - start) > MAX_SEGMENT_DURATION:
            end = start + MAX_SEGMENT_DURATION

        # Rule: within video duration
        if start >= video_duration:
            continue
        end = min(end, video_duration)

        # Rule: chronological, no overlap
        if start < prev_end:
            start = prev_end
        if start >= end:
            continue

        validated.append({"start": round(start, 3), "end": round(end, 3), "reason": reason})
        prev_end = end

    return validated


_PLATFORM_CONTEXT = {
    "reels": (
        "Instagram Reels: Hook the viewer in the first 3 seconds — open with the strongest, "
        "most surprising or relatable statement. Pacing should feel snappy. Subtitles are "
        "essential (most viewers watch without sound). End on an emotion, a revelation, or "
        "a clear takeaway. Avoid slow build-ups."
    ),
    "tiktok": (
        "TikTok: Immediate value is non-negotiable — the first 2 seconds must give the viewer "
        "a reason to stay. High energy, direct address, and frequent re-engagement moments "
        "(questions, surprising facts). End with a satisfying conclusion or cliffhanger."
    ),
    "shorts": (
        "YouTube Shorts: Viewers skew educational and value clarity. Open with the question "
        "or problem, deliver the answer step by step, close with a memorable summary. Pacing "
        "can be slightly slower than Reels/TikTok but still faster than long-form."
    ),
    "general": (
        "General / Premiere edit: Focus on storytelling clarity and pacing. No platform-specific "
        "constraints — prioritise coherence and engagement over speed."
    ),
}

_PLATFORM_LABELS = {
    "reels": "Instagram Reels",
    "tiktok": "TikTok",
    "shorts": "YouTube Shorts",
    "general": "General",
}


def _analyze_chunk(
    client,
    segments: list[dict],
    quality_mode: str,
    video_duration: float,
    prompt_template: str,
    chunk_start_offset: float,
    logs_dir: Path,
    chunk_index: int,
    target_duration: int = 90,
    aspect_ratio: str = "16:9",
    platform: str = "general",
) -> list[dict]:
    """Run one Claude request for a single transcript chunk. Retries up to 3 times."""
    # Rule-based filler pre-filter: strip obvious fillers before sending to Claude.
    # Only runs when faster-whisper word timestamps are present; skips silently otherwise.
    has_word_data = any("words" in seg and seg["words"] for seg in segments)
    if has_word_data:
        try:
            from filler_detector import detect_fillers, merge_overlaps, apply_removals_to_segments
            raw_removals = detect_fillers(segments)
            merged_removals = merge_overlaps(sorted(raw_removals, key=lambda r: r["start"]))
            filtered = apply_removals_to_segments(segments, merged_removals)
            removed = len(segments) - len(filtered)
            if removed:
                print(
                    f"  Rule-based pre-filter: removed {removed} filler segment(s) "
                    f"({len(merged_removals)} filler range(s) detected)"
                )
            segments = filtered
        except Exception as e:
            print(f"  [WARNING] Filler pre-filter failed: {e} - sending full transcript to Claude")

    transcript_str = _format_transcript(segments)

    platform_label = _PLATFORM_LABELS.get(platform, "General")
    platform_context = _PLATFORM_CONTEXT.get(platform, _PLATFORM_CONTEXT["general"])
    min_duration = max(10, round(target_duration * 0.85))
    max_duration = round(target_duration * 1.1)

    prompt = prompt_template.replace("{quality_mode}", quality_mode.upper() + " MODE")
    prompt = prompt.replace("{transcript}", transcript_str)
    prompt = prompt.replace("{target_duration}", str(target_duration))
    prompt = prompt.replace("{min_duration}", str(min_duration))
    prompt = prompt.replace("{max_duration}", str(max_duration))
    prompt = prompt.replace("{aspect_ratio}", aspect_ratio)
    prompt = prompt.replace("{platform_label}", platform_label)
    prompt = prompt.replace("{platform_context}", platform_context)

    raw_response = ""
    extra_prefix = ""

    for attempt in range(1, 4):
        try:
            raw_response = _call_claude_with_cache(client, prompt, transcript_str, extra_prefix=extra_prefix)

            # Save raw response for debugging (overwritten each attempt)
            raw_log = logs_dir / f"claude_raw_chunk{chunk_index}.txt"
            raw_log.write_text(raw_response, encoding="utf-8")

            validated = _parse_and_validate_json(raw_response, video_duration, chunk_start_offset)

            # Enforce duration budget — trim from the end if Claude overran
            min_duration = max(10, round(target_duration * 0.85))
            max_duration = round(target_duration * 1.1)
            total = sum(s["end"] - s["start"] for s in validated)
            if total > max_duration and validated:
                while validated and total > max_duration:
                    removed = validated.pop()
                    total -= (removed["end"] - removed["start"])
                print(f"  [Duration enforcement] Trimmed to {total:.1f}s (target: {target_duration}s, max: {max_duration}s)")

            # Save clean JSON
            clean_log = logs_dir / f"claude_clean_chunk{chunk_index}.json"
            with open(clean_log, "w", encoding="utf-8") as f:
                json.dump(validated, f, indent=2)

            return validated

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"  [Attempt {attempt}/3] Claude returned invalid JSON: {exc}")
            if attempt < 3:
                extra_prefix = "Your previous response was invalid JSON. Return ONLY valid JSON. "
                time.sleep(1)
            else:
                print("  [WARNING] All 3 attempts failed. No segments kept for this chunk.")
                fail_log = logs_dir / f"claude_raw_chunk{chunk_index}_failed.txt"
                fail_log.write_text(raw_response, encoding="utf-8")
                return []


def analyze_transcript(
    segments: list[dict],
    quality_mode: str,
    video_duration: float,
    target_duration: int = 90,
    aspect_ratio: str = "16:9",
    platform: str = "general",
    logs_dir: str = "logs",
    prompts_dir: str = "prompts",
) -> list[dict]:
    """
    Send the transcript to Claude and return a validated list of segments to keep.

    Parameters
    ----------
    segments : list[dict]
        Output from transcribe_video(): list of {"start", "end", "text"} dicts.
    quality_mode : str
        "light" | "balanced" | "aggressive"
    video_duration : float
        Total duration of the input video in seconds.
    target_duration : int
        Target length of the final cut in seconds (default: 90).
    aspect_ratio : str
        Output aspect ratio, e.g. "9:16" or "16:9" (default: "16:9").
    platform : str
        Target platform: "reels", "tiktok", "shorts", or "general" (default: "general").
    logs_dir : str
        Directory for saving debug logs.
    prompts_dir : str
        Directory containing editor_prompt.txt.

    Returns
    -------
    list[dict]
        Validated, chronological list of {"start", "end", "reason"} dicts.
    """
    from anthropic import Anthropic
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_key_here":
        print("\n[ERROR] ANTHROPIC_API_KEY is not set.")
        print("  1. Copy .env.example to .env")
        print("  2. Replace 'your_key_here' with your real key from https://console.anthropic.com/")
        print("  3. Save the file and run again.\n")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    prompt_template = _load_prompt_template(prompts_dir)

    # ── Decide whether to chunk ────────────────────────────────────────────
    full_transcript = _format_transcript(segments)
    estimated_tokens = _estimate_tokens(full_transcript)

    if estimated_tokens > MAX_TRANSCRIPT_TOKENS:
        print(f"  Transcript is large (~{estimated_tokens:,} tokens). Chunking into 10-minute windows.")
        if video_duration > 1800:
            print("  [NOTE] Video is over 30 minutes - processing will take longer and cost a little more.")
        kept_segments = _analyze_in_chunks(
            client, segments, quality_mode, video_duration,
            prompt_template, logs_path,
            target_duration=target_duration, aspect_ratio=aspect_ratio, platform=platform,
        )
    else:
        print(f"  Transcript size: ~{estimated_tokens:,} tokens - sending in one request.")
        kept_segments = _analyze_chunk(
            client, segments, quality_mode, video_duration,
            prompt_template, chunk_start_offset=0.0,
            logs_dir=logs_path, chunk_index=0,
            target_duration=target_duration, aspect_ratio=aspect_ratio, platform=platform,
        )

    # Merge the main raw/clean logs from chunk 0 into the standard names
    # so main.py can always reference logs/claude_raw.txt and logs/claude_clean.json
    _merge_logs(logs_path)

    # Save final validated segments
    final_log = logs_path / "final_segments.json"
    with open(final_log, "w", encoding="utf-8") as f:
        json.dump(kept_segments, f, indent=2)
    print(f"  Saved final segments to: {final_log}")

    return kept_segments


def _analyze_in_chunks(
    client,
    segments: list[dict],
    quality_mode: str,
    video_duration: float,
    prompt_template: str,
    logs_path: Path,
    target_duration: int = 90,
    aspect_ratio: str = "16:9",
    platform: str = "general",
) -> list[dict]:
    """Split segments into 10-minute chunks and process each separately."""
    chunks: list[tuple[float, list[dict]]] = []
    current_chunk: list[dict] = []
    chunk_start = 0.0

    for seg in segments:
        if seg["start"] >= chunk_start + CHUNK_DURATION_SECONDS and current_chunk:
            chunks.append((chunk_start, current_chunk))
            chunk_start = seg["start"]
            current_chunk = []
        current_chunk.append(seg)

    if current_chunk:
        chunks.append((chunk_start, current_chunk))

    print(f"  Split into {len(chunks)} chunk(s) of up to 10 minutes each.")

    all_kept: list[dict] = []
    for i, (chunk_offset, chunk_segs) in enumerate(chunks):
        print(f"  Processing chunk {i + 1}/{len(chunks)} (starting at {_fmt_time(chunk_offset)})...")
        relative_segs = [
            {**s, "start": s["start"] - chunk_offset, "end": s["end"] - chunk_offset}
            for s in chunk_segs
        ]
        kept = _analyze_chunk(
            client, relative_segs, quality_mode, video_duration,
            prompt_template, chunk_start_offset=chunk_offset,
            logs_dir=logs_path, chunk_index=i,
            target_duration=target_duration, aspect_ratio=aspect_ratio, platform=platform,
        )
        all_kept.extend(kept)

    return all_kept


def _merge_logs(logs_path: Path) -> None:
    """Copy chunk 0 logs to the canonical log filenames."""
    raw_chunk = logs_path / "claude_raw_chunk0.txt"
    clean_chunk = logs_path / "claude_clean_chunk0.json"
    if raw_chunk.exists():
        (logs_path / "claude_raw.txt").write_text(raw_chunk.read_text(encoding="utf-8"), encoding="utf-8")
    if clean_chunk.exists():
        (logs_path / "claude_clean.json").write_text(clean_chunk.read_text(encoding="utf-8"), encoding="utf-8")
