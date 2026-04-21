#!/bin/bash
# AutoEdit for Premiere Pro — Mac Installer
# Double-click this file to install. It will ask for your password once.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTENSION_SRC="$SCRIPT_DIR/com.autoedit.premiere"
CEP_DIR="$HOME/Library/Application Support/Adobe/CEP/extensions"
EXTENSION_DST="$CEP_DIR/com.autoedit.premiere"
SETTINGS_DIR="$HOME/Library/Application Support/AutoEdit"
BACKEND_PATH="$(dirname "$SCRIPT_DIR")"  # parent = autoedit-lite/

echo ""
echo "================================================================"
echo "  AutoEdit for Premiere Pro — Mac Installer"
echo "================================================================"
echo ""

# ── Step 1: Enable CEP debug mode (allows unsigned extensions) ──────────────
echo "[1/4] Enabling CEP debug mode..."
for ver in 9 10 11 12; do
  defaults write "com.adobe.CSXS.$ver" PlayerDebugMode 1
done
echo "      Done."

# ── Step 2: Copy extension into Adobe's extensions folder ──────────────────
echo "[2/4] Installing extension..."
mkdir -p "$CEP_DIR"
rm -rf "$EXTENSION_DST"
cp -r "$EXTENSION_SRC" "$EXTENSION_DST"
echo "      Installed to: $EXTENSION_DST"

# ── Step 3: Save backend path so the panel knows where main.py is ──────────
echo "[3/4] Saving backend path..."
mkdir -p "$SETTINGS_DIR"
cat > "$SETTINGS_DIR/settings.json" <<EOF
{
  "backendPath": "$BACKEND_PATH",
  "pythonPath": ""
}
EOF
echo "      Saved to: $SETTINGS_DIR/settings.json"

# ── Step 4: Check for Python ────────────────────────────────────────────────
echo "[4/4] Checking Python..."
PYTHON_BIN=""
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -f "$candidate" ]; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "      WARNING: Python 3 not found. Install it from python.org"
else
  echo "      Found: $PYTHON_BIN ($($PYTHON_BIN --version 2>&1))"
  # Write detected python path back to settings
  cat > "$SETTINGS_DIR/settings.json" <<EOF
{
  "backendPath": "$BACKEND_PATH",
  "pythonPath": "$PYTHON_BIN"
}
EOF
fi

echo ""
echo "================================================================"
echo "  INSTALLATION COMPLETE"
echo "================================================================"
echo ""
echo "Next steps:"
echo "  1. Install Python dependencies (run once):"
echo "     cd \"$BACKEND_PATH\""
echo "     pip3 install -r requirements.txt"
echo ""
echo "  2. Copy .env.example to .env and add your ANTHROPIC_API_KEY:"
echo "     cp \"$BACKEND_PATH/.env.example\" \"$BACKEND_PATH/.env\""
echo "     (then edit .env with your key)"
echo ""
echo "  3. Close Premiere Pro if it is open, then relaunch it."
echo ""
echo "  4. In Premiere Pro: Window > Extensions > AutoEdit"
echo ""
read -p "Press Enter to close..."
