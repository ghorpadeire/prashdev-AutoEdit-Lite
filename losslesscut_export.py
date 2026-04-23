"""
losslesscut_export.py

Exports Claude's kept segments as a LosslessCut-compatible CSV/EDL file.

LosslessCut is a free, open-source tool for fast, lossless video trimming.
Unlike FFmpeg re-encoding, LosslessCut cuts at keyframe boundaries — meaning
no quality loss and near-instant exports. The trade-off is ±0.5–1s accuracy
at each cut point, which is invisible on filler/silence cuts.

This module generates a simple CSV file that LosslessCut can import directly
via drag-and-drop (or File → Import Cuts from CSV). The editor gets a ready-made
rough cut without opening Premiere Pro at all.

CSV format (LosslessCut EDL):
    START,END,LABEL
    2.43,18.5,strong hook
    143.1,152.7,clean retake

References:
    https://github.com/mifi/lossless-cut — LosslessCut source & docs
    https://github.com/mifi/lossless-cut/blob/master/src/edlFormats.ts — CSV spec
"""

import csv
from pathlib import Path


def export_losslesscut_csv(
    segments: list[dict],
    output_csv_path: str,
) -> None:
    """
    Write a LosslessCut-compatible CSV file for the given kept segments.

    Each row maps to one kept segment. The LABEL column is populated with
    Claude's editing reason so the editor understands why each segment was kept.

    Parameters
    ----------
    segments : list[dict]
        Kept segments from analyze.py:
        [{"start": float, "end": float, "reason": str}, ...]
    output_csv_path : str
        Destination path for the .csv file.
        Recommended naming: <video_base>_autoedit_cuts.csv

    Returns
    -------
    None
        Writes the file to disk and prints a confirmation message.

    Example
    -------
    >>> export_losslesscut_csv(
    ...     segments=[{"start": 2.43, "end": 18.5, "reason": "strong hook"}],
    ...     output_csv_path="output/video_autoedit_cuts.csv",
    ... )
    LosslessCut CSV saved to: output/video_autoedit_cuts.csv
    → Drag this file into LosslessCut for a lossless rough cut.
    """
    if not segments:
        print("  [WARNING] No segments to export - LosslessCut CSV not written.")
        return

    output_path = Path(output_csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["START", "END", "LABEL"])
        for i, seg in enumerate(segments, start=1):
            # Use Claude's reason as the label; fall back to a timestamp label.
            reason = (seg.get("reason") or "").strip()
            label = reason if reason else f"segment {i} ({seg['start']:.1f}s-{seg['end']:.1f}s)"
            # LosslessCut labels have no hard limit but keep them readable.
            label = label[:100]
            writer.writerow([
                round(seg["start"], 3),
                round(seg["end"], 3),
                label,
            ])

    print(f"  LosslessCut CSV saved to: {output_path}")
    print(f"  -> Drag this file into LosslessCut for an instant lossless rough cut.")
