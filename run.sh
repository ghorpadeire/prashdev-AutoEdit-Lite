#!/bin/bash

echo ""
echo "============================================================"
echo "  AutoEdit-Lite - AI Video Editor (Mac)"
echo "============================================================"
echo ""
echo "  Enter the path to your video file below."
echo "  (You can drag the file into this terminal window)"
echo ""
read -rp "  Video path: " INPUT

if [ -z "$INPUT" ]; then
    echo ""
    echo "  [ERROR] No input provided. Run again and enter a path."
    exit 1
fi

# Strip any surrounding quotes that appear when dragging files on Mac
INPUT="${INPUT%\'}"
INPUT="${INPUT#\'}"
INPUT="${INPUT%\"}"
INPUT="${INPUT#\"}"

echo ""
echo "  Running with: model=medium, quality=balanced"
echo "  Press Ctrl+C to cancel at any time."
echo ""

python3 main.py --input "$INPUT" --model medium --quality balanced

echo ""
