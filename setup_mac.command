#!/bin/bash
# setup_mac.command
# Double-click this file in Finder to run the full setup.
# It will open Terminal automatically.

# Always run from the folder this script is in
cd "$(dirname "$0")"

clear
echo ""
echo "============================================================"
echo "  AutoEdit-Lite - First Time Setup (Mac)"
echo "============================================================"
echo "  This script installs everything you need."
echo "  It only needs to run ONCE."
echo "============================================================"
echo ""
read -rp "  Press Enter to begin setup..." _

# ── STEP 1: Check Python ──────────────────────────────────────────────────
echo ""
echo "[1/5] Checking Python..."

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    if [ "$MAJOR" -ge 3 ]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo "  [ERROR] Python 3 is not installed."
    echo ""
    echo "  Please:"
    echo "    1. Go to: https://www.python.org/downloads/"
    echo "    2. Download Python 3.10 or newer"
    echo "    3. Install it"
    echo "    4. Double-click setup_mac.command again"
    echo ""
    read -rp "  Press Enter to exit..." _
    exit 1
fi

echo "  OK - Found: $($PYTHON_CMD --version)"

# ── STEP 2: Install Homebrew + FFmpeg ────────────────────────────────────
echo ""
echo "[2/5] Checking FFmpeg..."

if command -v ffmpeg &>/dev/null; then
    echo "  OK - FFmpeg is already installed."
else
    echo "  FFmpeg not found. Installing via Homebrew..."
    echo ""

    if ! command -v brew &>/dev/null; then
        echo "  Homebrew not found. Installing Homebrew first..."
        echo "  (This is a free package manager for Mac — safe and widely used)"
        echo ""
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add brew to PATH for Apple Silicon Macs
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi

        if ! command -v brew &>/dev/null; then
            echo ""
            echo "  [ERROR] Homebrew installation failed."
            echo "  Please install FFmpeg manually: https://ffmpeg.org/download.html"
            read -rp "  Press Enter to exit..." _
            exit 1
        fi
        echo "  OK - Homebrew installed."
    fi

    echo "  Installing FFmpeg..."
    brew install ffmpeg
    if ! command -v ffmpeg &>/dev/null; then
        echo ""
        echo "  [ERROR] FFmpeg installation failed."
        echo "  Try running: brew install ffmpeg"
        read -rp "  Press Enter to exit..." _
        exit 1
    fi
    echo "  OK - FFmpeg installed."
fi

# ── STEP 3: Install Python packages ──────────────────────────────────────
echo ""
echo "[3/5] Installing Python packages..."
echo "  (faster-whisper, anthropic, ffmpeg-python, python-dotenv)"
echo "  Please wait..."
echo ""

$PYTHON_CMD -m pip install --upgrade pip --quiet 2>/dev/null || true
$PYTHON_CMD -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "  [ERROR] Package installation failed."
    echo "  Make sure you have an internet connection and try again."
    read -rp "  Press Enter to exit..." _
    exit 1
fi
echo ""
echo "  OK - All packages installed."

# ── STEP 4: Set up API key ────────────────────────────────────────────────
echo ""
echo "[4/5] Setting up your Anthropic API key..."
echo ""

if [ -f ".env" ]; then
    echo "  Found existing .env file. Skipping creation."
else
    cp .env.example .env
    echo "  Created your .env file."
    echo ""
    echo "  ============================================================"
    echo "  IMPORTANT: You need to add your Anthropic API key."
    echo "  ============================================================"
    echo ""
    echo "  1. A text editor is about to open with your .env file"
    echo "  2. Replace  your_key_here  with your real API key"
    echo "  3. Get your key at: https://console.anthropic.com/"
    echo "  4. Save the file and close the editor"
    echo "  5. Come back here and press Enter to continue"
    echo ""
    read -rp "  Press Enter to open the .env file..." _

    # Open in TextEdit (Mac default) or nano as fallback
    if command -v open &>/dev/null; then
        open -e .env
        echo ""
        echo "  TextEdit has opened with your .env file."
        echo "  Edit it, save (Cmd+S), then close TextEdit."
    else
        nano .env
    fi

    echo ""
    read -rp "  Done editing? Press Enter to continue..." _
fi

# ── STEP 5: Verify setup ──────────────────────────────────────────────────
echo ""
echo "[5/5] Verifying setup..."
$PYTHON_CMD -c "import faster_whisper, anthropic, ffmpeg, dotenv; print('   All packages OK')"

if [ $? -ne 0 ]; then
    echo ""
    echo "  [ERROR] Some packages did not install correctly."
    echo "  Try: pip3 install -r requirements.txt"
    read -rp "  Press Enter to exit..." _
    exit 1
fi

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  SETUP COMPLETE!"
echo "============================================================"
echo ""
echo "  You are ready to use AutoEdit-Lite."
echo ""
echo "  HOW TO USE:"
echo "    - Double-click  run_mac.command  to edit a video"
echo "    - OR open Terminal and run:"
echo "      python3 main.py --input input/video.mp4"
echo ""
echo "  FIRST TIME TIP:"
echo "    Test with a short video (under 2 minutes) first."
echo "    Drop it in the  input/  folder, then run the tool."
echo ""
echo "============================================================"
echo ""
read -rp "  Press Enter to close..." _
