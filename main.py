"""
main.py

AutoEdit-Lite — AI-powered automatic video rough-cut tool.

Usage:
  python main.py --input input/video.mp4
  python main.py --input input/video.mp4 --model medium --quality balanced
  python main.py --input input/video.mp4 --mode premiere
  python main.py --input input/video.mp4 --dry-run
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


# ── Supported input formats ────────────────────────────────────────────────
VALID_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}

# ── Defaults ──────────────────────────────────────────────────────────────
DEFAULT_MODEL = "medium"
DEFAULT_QUALITY = "balanced"
DEFAULT_OUTPUT = "output/edited.mp4"
DEFAULT_MODE = "ffmpeg"


def _get_video_duration_seconds(path: Path) -> float:
    """Use ffprobe to get the video duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _format_duration(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    for d in ["input", "output", "logs", "prompts"]:
        Path(d).mkdir(parents=True, exist_ok=True)


def _validate_input(input_path: Path) -> None:
    """Exit with a clear error if the input file is invalid."""
    if not input_path.exists():
        print(f"\n[ERROR] Input file not found: {input_path}")
        print("  Make sure the file exists and the path is correct.\n")
        sys.exit(1)
    if not input_path.is_file():
        print(f"\n[ERROR] Input path is not a file: {input_path}\n")
        sys.exit(1)
    if input_path.suffix.lower() not in VALID_EXTENSIONS:
        print(f"\n[ERROR] Unsupported file format: {input_path.suffix}")
        print(f"  Supported formats: {', '.join(sorted(VALID_EXTENSIONS))}\n")
        sys.exit(1)


def _check_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("\n[ERROR] FFmpeg or ffprobe was not found on your PATH.")
        print("  Windows: https://github.com/BtbN/FFmpeg-Builds/releases")
        print("           Download, unzip, and add the 'bin' folder to your PATH.")
        print("  Mac:     brew install ffmpeg")
        print("  Then open a NEW terminal and try again.\n")
        sys.exit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="autoedit-lite",
        description="AutoEdit-Lite: AI-powered automatic video rough-cut tool",
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to your input video (e.g. input/video.mp4)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size. Larger = more accurate but slower. (default: medium)",
    )
    parser.add_argument(
        "--quality", default=DEFAULT_QUALITY,
        choices=["light", "balanced", "aggressive"],
        help="How aggressively Claude edits. (default: balanced)",
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Output video path. (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--mode", default=DEFAULT_MODE,
        choices=["ffmpeg", "premiere"],
        help=(
            "Output mode. 'ffmpeg' cuts the video locally (default). "
            "'premiere' exports an FCP7 XML timeline for Premiere Pro instead."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Transcribe and get Claude's plan, but do NOT cut the video.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # ── Startup checks ─────────────────────────────────────────────────────
    _ensure_dirs()
    _check_ffmpeg_available()
    _validate_input(input_path)

    print()
    print("=" * 60)
    print("  AutoEdit-Lite")
    print("=" * 60)
    print(f"  Input   : {input_path}")
    print(f"  Model   : {args.model}")
    print(f"  Quality : {args.quality}")
    if args.dry_run:
        print("  Mode    : DRY RUN (no video cutting)")
    elif args.mode == "premiere":
        premiere_xml_path = output_path.with_suffix(".xml")
        print(f"  Mode    : PREMIERE (FCP7 XML export)")
        print(f"  Output  : {premiere_xml_path}")
    else:
        print(f"  Output  : {output_path}")
    print("=" * 60)
    print()

    # ── Step 1: Get original video duration ───────────────────────────────
    original_duration = _get_video_duration_seconds(input_path)
    if original_duration <= 0:
        print("[ERROR] Could not read video duration. Is the file valid?")
        sys.exit(1)

    # ── Step 2: Transcribe ─────────────────────────────────────────────────
    print("[1/4] Transcribing audio...")
    from transcribe import transcribe_video
    transcript_segments = transcribe_video(
        video_path=str(input_path),
        model_name=args.model,
        logs_dir="logs",
    )

    if not transcript_segments:
        print("[ERROR] Transcription returned no segments. Is there speech in the video?")
        sys.exit(1)

    print(f"  Found {len(transcript_segments)} transcript segment(s).")
    print()

    # ── Step 3: Analyze with Claude ────────────────────────────────────────
    print("[2/4] Asking Claude for editing decisions...")
    from analyze import analyze_transcript
    kept_segments = analyze_transcript(
        segments=transcript_segments,
        quality_mode=args.quality,
        video_duration=original_duration,
        logs_dir="logs",
        prompts_dir="prompts",
    )

    if not kept_segments:
        print("[WARNING] Claude returned no segments to keep.")
        print("  Check logs/claude_raw.txt to see what Claude said.")
        if not args.dry_run:
            print("  No output video created.")
        sys.exit(0)

    kept_duration = sum(s["end"] - s["start"] for s in kept_segments)
    print(f"  Claude selected {len(kept_segments)} segment(s) to keep.")
    print()

    # ── Step 4a: Output (skip in dry-run; choose ffmpeg or premiere mode) ───
    if args.dry_run:
        print("[3/4] Skipping video cut (--dry-run mode).")
        print()
        print("[4/4] Skipping subtitle generation (--dry-run mode).")
        print()
    elif args.mode == "premiere":
        premiere_xml_path = output_path.with_suffix(".xml")
        print("[3/4] Exporting Premiere Pro XML timeline...")
        from xml_export import export_premiere_xml
        export_premiere_xml(
            input_video_path=str(input_path),
            segments=kept_segments,
            output_xml_path=str(premiere_xml_path),
        )
        print()

        srt_path = output_path.with_suffix(".srt")
        print("[4/4] Generating subtitles...")
        from captions import generate_srt
        generate_srt(
            transcript_segments=transcript_segments,
            kept_segments=kept_segments,
            output_path=str(srt_path),
        )
        print()
    else:
        print("[3/4] Cutting and stitching video...")
        from editor import cut_video
        actual_output_duration = cut_video(
            input_path=str(input_path),
            segments=kept_segments,
            output_path=str(output_path),
            dry_run=False,
        )
        print()

        # ── Step 4b: Generate subtitles ────────────────────────────────────
        srt_path = output_path.with_suffix(".srt")
        print("[4/4] Generating subtitles...")
        from captions import generate_srt
        generate_srt(
            transcript_segments=transcript_segments,
            kept_segments=kept_segments,
            output_path=str(srt_path),
        )
        print()

    # ── Final summary ──────────────────────────────────────────────────────
    print("=" * 60)
    print("  DONE")
    print("=" * 60)

    original_fmt = _format_duration(original_duration)
    kept_fmt = _format_duration(kept_duration)
    reduction_pct = (1.0 - kept_duration / original_duration) * 100 if original_duration > 0 else 0.0

    print(f"  Original duration : {original_fmt}")
    print(f"  Edited duration   : {kept_fmt}")
    print(f"  Reduction         : {reduction_pct:.0f}% shorter")
    print(f"  Segments kept     : {len(kept_segments)}")
    print()

    if args.dry_run:
        print("  (Dry run — no output files written)")
    elif args.mode == "premiere":
        print(f"  Premiere XML  : {output_path.with_suffix('.xml')}")
        print(f"  Subtitles     : {output_path.with_suffix('.srt')}")
        print()
        print("  Import into Premiere: File -> Import -> select the .xml file")
    else:
        print(f"  Output video  : {output_path}")
        print(f"  Subtitles     : {output_path.with_suffix('.srt')}")

    print(f"  Debug logs    : logs/")
    print("=" * 60)
    print()

    print(f"Reduced {original_fmt} -> {kept_fmt} ({reduction_pct:.0f}% shorter)")


if __name__ == "__main__":
    main()
