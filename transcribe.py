"""
transcribe.py

Extracts audio from the input video and transcribes it locally using
faster-whisper. Returns a list of timed segments with start, end, and text.
Nothing is sent to any external service during this step.
"""

import os
# Force CPU-only mode before ctranslate2/faster-whisper loads.
# Without this, ctranslate2 probes for CUDA at import time on Windows and
# crashes with "cublas64_12.dll not found" on machines without CUDA 12.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _check_ffmpeg() -> None:
    """Raise a clear error if ffmpeg is not found on PATH."""
    if shutil.which("ffmpeg") is None:
        print("\n[ERROR] FFmpeg was not found on your system PATH.")
        print("  Windows: Download from https://github.com/BtbN/FFmpeg-Builds/releases")
        print("           Then add the 'bin' folder to your system PATH.")
        print("  Mac:     Run:  brew install ffmpeg")
        print("  After installing, open a NEW terminal window and try again.\n")
        sys.exit(1)


def _extract_audio(video_path: Path, audio_path: Path) -> None:
    """Use ffmpeg to extract a mono 16kHz WAV from the video — ideal for Whisper."""
    cmd = [
        "ffmpeg",
        "-y",                  # overwrite output if it exists
        "-i", str(video_path),
        "-ac", "1",            # mono channel
        "-ar", "16000",        # 16kHz sample rate (Whisper's preferred rate)
        "-vn",                 # no video stream
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\n[ERROR] FFmpeg failed to extract audio from: {video_path}")
        print(f"  FFmpeg error: {result.stderr[-500:]}")
        sys.exit(1)


def transcribe_video(
    video_path: str,
    model_name: str,
    logs_dir: str = "logs",
) -> list[dict]:
    """
    Transcribe a video file and return a list of timed segments.

    Each segment is a dict:  {"start": float, "end": float, "text": str}

    Parameters
    ----------
    video_path : str
        Path to the input video file.
    model_name : str
        Whisper model size: tiny | base | small | medium | large
    logs_dir : str
        Directory where transcript.json will be saved.

    Returns
    -------
    list[dict]
        Sorted list of transcript segments with start/end times.
    """
    _check_ffmpeg()

    video_path = Path(video_path)
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)

    # Extract audio to a temporary WAV file
    audio_path = logs_path / "_audio_temp.wav"
    print(f"  Extracting audio from: {video_path.name}")
    _extract_audio(video_path, audio_path)

    # Load the faster-whisper model
    # device="cpu" works on all machines; compute_type="int8" is memory-efficient
    print(f"  Loading Whisper model: {model_name}")
    print("  (First run downloads model files — this may take a few minutes)")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("\n[ERROR] faster-whisper is not installed.")
        print("  Run:  pip install faster-whisper\n")
        sys.exit(1)

    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    print("  Transcribing... (this may take a while for long videos)")
    segments_generator, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        language=None,      # auto-detect language
        vad_filter=True,    # skip silent sections automatically
    )

    # Convert the generator to a list of plain dicts
    segments: list[dict] = []
    for seg in segments_generator:
        segments.append({
            "start": round(float(seg.start), 3),
            "end":   round(float(seg.end),   3),
            "text":  seg.text.strip(),
        })

    # Clean up temp audio file
    if audio_path.exists():
        audio_path.unlink()

    # Save to logs
    transcript_log = logs_path / "transcript.json"
    with open(transcript_log, "w", encoding="utf-8") as f:
        json.dump(
            {"model": model_name, "language": info.language, "segments": segments},
            f, indent=2, ensure_ascii=False,
        )

    print(f"  Transcription complete — {len(segments)} segments found")
    print(f"  Saved transcript to: {transcript_log}")
    return segments
