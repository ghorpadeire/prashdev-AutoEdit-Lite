#!/bin/bash
# run_mac.command
# Double-click this file in Finder to edit a video.
# Terminal opens automatically.

cd "$(dirname "$0")"

clear
echo ""
echo "============================================================"
echo "  AutoEdit-Lite - AI Video Editor (Mac)"
echo "============================================================"
echo ""

# ── Quick sanity checks ───────────────────────────────────────────────────
PYTHON_CMD=""
if command -v python3 &>/dev/null; then PYTHON_CMD="python3"
elif command -v python &>/dev/null; then PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "  [ERROR] Python not found. Please run setup_mac.command first."
    read -rp "  Press Enter to exit..." _; exit 1
fi

if ! command -v ffmpeg &>/dev/null; then
    echo "  [ERROR] FFmpeg not found. Please run setup_mac.command first."
    read -rp "  Press Enter to exit..." _; exit 1
fi

if [ ! -f ".env" ]; then
    echo "  [ERROR] .env file not found. Please run setup_mac.command first."
    read -rp "  Press Enter to exit..." _; exit 1
fi

if ! $PYTHON_CMD -c "import faster_whisper" &>/dev/null; then
    echo "  [ERROR] Python packages not installed. Please run setup_mac.command first."
    read -rp "  Press Enter to exit..." _; exit 1
fi

# ── Choose video file ─────────────────────────────────────────────────────
echo "  Drag your video file into this Terminal window and press Enter,"
echo "  OR type the full path to your video file."
echo ""
echo "  Example:  /Users/yourname/Desktop/interview.mp4"
echo ""
read -rp "  Video path: " INPUT

# Strip surrounding quotes (added automatically when dragging on Mac)
INPUT="${INPUT%\'}"
INPUT="${INPUT#\'}"
INPUT="${INPUT%\"}"
INPUT="${INPUT#\"}"
# Trim whitespace
INPUT="$(echo "$INPUT" | xargs)"

if [ -z "$INPUT" ]; then
    echo ""
    echo "  [ERROR] No file entered. Please run again."
    read -rp "  Press Enter to exit..." _; exit 1
fi

if [ ! -f "$INPUT" ]; then
    echo ""
    echo "  [ERROR] File not found: $INPUT"
    echo "  Check the path and try again."
    read -rp "  Press Enter to exit..." _; exit 1
fi

# ── Choose quality mode ───────────────────────────────────────────────────
echo ""
echo "  Choose editing quality:"
echo "    1 = light      (removes obvious mistakes only)"
echo "    2 = balanced   (removes mistakes + filler words)  [RECOMMENDED]"
echo "    3 = aggressive (tightest possible edit)"
echo ""
read -rp "  Enter 1, 2, or 3 (press Enter for default 'balanced'): " QCHOICE

case "$QCHOICE" in
    1) QUALITY="light" ;;
    3) QUALITY="aggressive" ;;
    *) QUALITY="balanced" ;;
esac

# ── Choose Whisper model ──────────────────────────────────────────────────
echo ""
echo "  Choose transcription speed:"
echo "    1 = base    (faster, good enough for clear audio)"
echo "    2 = medium  (slower, more accurate)             [RECOMMENDED]"
echo "    3 = large   (slowest, most accurate, needs 8GB+ RAM)"
echo ""
read -rp "  Enter 1, 2, or 3 (press Enter for 'medium'): " MCHOICE

case "$MCHOICE" in
    1) MODEL="base" ;;
    3) MODEL="large" ;;
    *) MODEL="medium" ;;
esac

# ── Confirm and run ───────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Settings"
echo "  File    : $(basename "$INPUT")"
echo "  Quality : $QUALITY"
echo "  Model   : $MODEL"
echo "  Output  : output/edited.mp4"
echo "============================================================"
echo ""
read -rp "  Press Enter to start editing... (Ctrl+C to cancel)" _
echo ""

$PYTHON_CMD main.py --input "$INPUT" --model "$MODEL" --quality "$QUALITY" --output output/edited.mp4

EXIT_CODE=$?
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "  Finished! Your edited video is in the output/ folder."
    echo "  Opening the output folder..."
    open output/ 2>/dev/null || true
else
    echo "  Something went wrong. Check the messages above for details."
    echo "  Debug logs are in the  logs/  folder."
fi

echo ""
read -rp "  Press Enter to close..." _
