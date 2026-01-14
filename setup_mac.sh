#!/usr/bin/env bash
set -euo pipefail

echo "=== DTC Editor Pilot: macOS setup ==="
echo ""
cd "$(dirname "$0")"

# Find Python 3
PY=""
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  if python -c 'import sys; sys.exit(0 if sys.version_info[0]==3 else 1)' >/dev/null 2>&1; then
    PY="python"
  fi
fi

if [[ -z "$PY" ]]; then
  echo "ERROR: Python 3 is not installed."
  echo "Install Python 3 from https://www.python.org/downloads/ and re-run."
  exit 1
fi

echo "Using Python: $($PY --version)"
echo ""

# Create venv
if [[ ! -d ".venv" ]]; then
  echo "Creating virtual environment (.venv)..."
  $PY -m venv .venv
else
  echo "Virtual environment already exists (.venv)."
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo ""
echo "Upgrading pip..."
python -m pip install --upgrade pip >/dev/null

echo ""
echo "Installing the DTC Editor package..."
python -m pip install -e .

# Optional: Vale (only if brew exists)
echo ""
if command -v brew >/dev/null 2>&1; then
  if command -v vale >/dev/null 2>&1; then
    echo "Vale is already installed."
  else
    echo "Installing Vale via Homebrew (optional)..."
    brew install vale || echo "WARNING: Vale install failed. You can still run without Vale."
  fi
else
  echo "Homebrew not found; skipping Vale install (optional)."
fi

# Create .env if missing (pilot defaults)
if [[ ! -f ".env" ]]; then
  echo ""
  echo "Creating .env (pilot defaults)..."
  cat > .env << 'EOF'
# Pilot defaults
# This vNext2 build runs rule-based edits locally (no LLM/API required).
# If you later add an LLM step, you can add keys here.

# Optional: Vale config if you install Vale and add rules later
# VALE_INI_PATH=rules/vale/.vale.ini
EOF
else
  echo ""
  echo ".env already exists. Leaving it unchanged."
fi

# Create double-click runner
echo ""
echo "Creating run_editor.command (double-click runner)..."
cat > run_editor.command << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Remove Gatekeeper quarantine if present (best effort)
xattr -d com.apple.quarantine "$0" 2>/dev/null || true

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "DTC Editor Pilot"
echo "----------------"
echo "Step 1) Drag a .docx file onto this window"
echo "Step 2) Press Enter"
echo ""

read -r DOCX_PATH

if [[ ! -f "$DOCX_PATH" ]]; then
  echo ""
  echo "ERROR: File not found:"
  echo "  $DOCX_PATH"
  echo ""
  echo "Press Enter to close."
  read -r
  exit 1
fi

OUT_DIR="dtc_out"
mkdir -p "$OUT_DIR"

echo ""
echo "Running editor..."
echo "Input : $DOCX_PATH"
echo "Output: $OUT_DIR"
echo ""

# Run the editor (creates clean + redline + changelog files)
python -m dtc_editor.cli "$DOCX_PATH" --out "$OUT_DIR" --mode safe

echo ""
echo "DONE."
echo "Open this folder to get your files:"
echo "  $OUT_DIR"
echo ""
echo "Press Enter to close."
read -r
EOF

chmod +x run_editor.command
xattr -d com.apple.quarantine run_editor.command 2>/dev/null || true

echo ""
echo "=== Setup complete ==="
echo ""
echo "NEXT:"
echo "  1) Double-click: run_editor.command"
echo "  2) Drag your .docx into the window and press Enter"
echo "  3) Get outputs in: dtc_out/"
