"""
xml_export.py

Exports Claude's kept segments as a Final Cut Pro 7 XML (XMEML) timeline
that Adobe Premiere Pro can import as a new sequence with all cuts pre-applied.

Uses OpenTimelineIO's otio-fcp-adapter — a battle-tested open-source library
used in professional post-production pipelines — to generate the XML.
"""

import subprocess
from pathlib import Path

import opentimelineio as otio


def _detect_fps(video_path: str) -> float:
    """Read frame rate from video using ffprobe. Falls back to 25.0 on failure."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        raw = result.stdout.strip()
        if "/" in raw:
            num, den = raw.split("/")
            return round(float(num) / float(den), 3)
        return float(raw)
    except Exception:
        return 25.0


def export_premiere_xml(
    input_video_path: str,
    segments: list[dict],
    output_xml_path: str,
) -> None:
    """
    Write a Premiere Pro-importable FCP7 XML timeline to output_xml_path.

    Parameters
    ----------
    input_video_path : str
        Absolute path to the original video file.
    segments : list[dict]
        Kept segments from analyze.py: [{"start": float, "end": float, "reason": str}, ...]
    output_xml_path : str
        Destination path for the .xml file.
    """
    fps = _detect_fps(input_video_path)
    print(f"  Detected frame rate: {fps:.3f} fps")

    timeline = otio.schema.Timeline(name="AutoEdit — Rough Cut")

    video_track = otio.schema.Track(name="Video 1", kind=otio.schema.TrackKind.Video)
    audio_track = otio.schema.Track(name="Audio 1", kind=otio.schema.TrackKind.Audio)
    timeline.tracks.append(video_track)
    timeline.tracks.append(audio_track)

    abs_path = Path(input_video_path).resolve().as_posix()

    # FCP7 adapter requires available_range on the media reference.
    # Use the max segment end time + 1s buffer as the total available duration.
    max_end_sec = max((seg["end"] for seg in segments), default=0.0)
    available_range = otio.opentime.TimeRange(
        start_time=otio.opentime.RationalTime(0, fps),
        duration=otio.opentime.RationalTime(round((max_end_sec + 1.0) * fps), fps),
    )
    media_ref = otio.schema.ExternalReference(
        target_url=abs_path,
        available_range=available_range,
    )

    for seg in segments:
        start_frame = round(seg["start"] * fps)
        end_frame = round(seg["end"] * fps)
        duration_frames = end_frame - start_frame

        if duration_frames <= 0:
            continue

        source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(start_frame, fps),
            duration=otio.opentime.RationalTime(duration_frames, fps),
        )
        label = (seg.get("reason") or f"{seg['start']:.1f}s-{seg['end']:.1f}s")[:50]

        video_track.append(otio.schema.Clip(
            name=label,
            media_reference=media_ref,
            source_range=source_range,
        ))
        audio_track.append(otio.schema.Clip(
            name=label,
            media_reference=media_ref,
            source_range=source_range,
        ))

    output_path = Path(output_xml_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(timeline, str(output_path), adapter_name="fcp_xml")
    print(f"  Premiere XML saved to: {output_path}")
