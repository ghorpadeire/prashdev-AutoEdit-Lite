"""
captions.py

Generates a .srt subtitle file from the kept segments.

How it works:
  1. For each kept segment, find all Whisper transcript segments that fall
     inside it (by time overlap).
  2. Re-timestamp them relative to the edited video's timeline.
  3. Write out in standard SRT format.
"""

from pathlib import Path


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format: HH:MM:SS,mmm"""
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    secs = total_s % 60
    total_m = total_s // 60
    mins = total_m % 60
    hours = total_m // 60
    return f"{hours:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def generate_srt(
    transcript_segments: list[dict],
    kept_segments: list[dict],
    output_path: str,
) -> None:
    """
    Generate a .srt subtitle file for the edited video.

    Parameters
    ----------
    transcript_segments : list[dict]
        Original Whisper segments: [{"start", "end", "text"}, ...]
    kept_segments : list[dict]
        Segments kept by Claude: [{"start", "end", "reason"}, ...]
    output_path : str
        Path of the output .srt file (e.g. "output/edited.srt")
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    srt_entries: list[tuple[float, float, str]] = []

    # Running time offset: as we include each kept segment, we accumulate
    # how much total video time has been placed before the current segment.
    output_time_offset = 0.0

    for kept in kept_segments:
        seg_start = kept["start"]
        seg_end = kept["end"]
        seg_duration = seg_end - seg_start

        # Find all transcript lines that START within this kept segment.
        # Requiring t["start"] >= seg_start (with 0.1s grace) prevents
        # text from cut footage bleeding into the first subtitle entry.
        matching: list[dict] = []
        for t in transcript_segments:
            overlap_start = max(t["start"], seg_start)
            overlap_end = min(t["end"], seg_end)
            if t["start"] >= seg_start - 0.1 and overlap_end > overlap_start and t["text"].strip():
                matching.append(t)

        if not matching:
            # No transcript text for this segment — advance time and skip
            output_time_offset += seg_duration
            continue

        # Re-timestamp each matching transcript line relative to output timeline
        for t in matching:
            # Clamp to the kept segment boundaries
            clamped_start = max(t["start"], seg_start)
            clamped_end = min(t["end"], seg_end)

            # Convert to output video time
            out_start = output_time_offset + (clamped_start - seg_start)
            out_end = output_time_offset + (clamped_end - seg_start)

            if out_end > out_start:
                srt_entries.append((out_start, out_end, t["text"].strip()))

        output_time_offset += seg_duration

    # Write SRT file
    lines = []
    for index, (start, end, text) in enumerate(srt_entries, start=1):
        lines.append(str(index))
        lines.append(f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}")
        lines.append(text)
        lines.append("")   # blank line between entries

    srt_content = "\n".join(lines)
    output_path.write_text(srt_content, encoding="utf-8")
    print(f"  Subtitles saved to: {output_path}")
