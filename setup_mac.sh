#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "======================================"
echo "   DTC Editor - Mac Setup"
echo "======================================"
echo ""

cd "$(dirname "$0")"

# ============================================
# Check Python 3.10+
# ============================================
echo "Checking Python..."

PY=""
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  if python -c 'import sys; sys.exit(0 if sys.version_info[0]==3 else 1)' 2>/dev/null; then
    PY="python"
  fi
fi

if [[ -z "$PY" ]]; then
  echo ""
  echo "ERROR: Python 3 is not installed."
  echo ""
  echo "To fix this:"
  echo "  1. Go to https://www.python.org/downloads/"
  echo "  2. Download and install Python 3.10 or newer"
  echo "  3. Restart Terminal"
  echo "  4. Run this script again"
  echo ""
  exit 1
fi

# Check Python version is 3.10+
PY_VERSION=$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$($PY -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PY -c 'import sys; print(sys.version_info.minor)')

if [[ "$PY_MAJOR" -lt 3 ]] || { [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 10 ]]; }; then
  echo ""
  echo "ERROR: Python $PY_VERSION is too old. You need Python 3.10 or newer."
  echo ""
  echo "To fix this:"
  echo "  1. Go to https://www.python.org/downloads/"
  echo "  2. Download and install Python 3.10 or newer"
  echo "  3. Restart Terminal"
  echo "  4. Run this script again"
  echo ""
  exit 1
fi

echo "  Found Python $PY_VERSION"

# ============================================
# Check/Install Homebrew
# ============================================
echo ""
echo "Checking Homebrew..."

if ! command -v brew >/dev/null 2>&1; then
  echo ""
  echo "WARNING: Homebrew is not installed."
  echo ""
  echo "Vale (style checker) requires Homebrew to install."
  echo "The editor will still work, but style checking will be disabled."
  echo ""
  echo "To install Homebrew later:"
  echo "  1. Go to https://brew.sh"
  echo "  2. Follow the instructions"
  echo "  3. Run this setup script again"
  echo ""
  BREW_AVAILABLE=false
else
  echo "  Homebrew is installed"
  BREW_AVAILABLE=true
fi

# ============================================
# Install Vale via Homebrew
# ============================================
if [[ "$BREW_AVAILABLE" == true ]]; then
  echo ""
  echo "Checking Vale..."

  if command -v vale >/dev/null 2>&1; then
    echo "  Vale is already installed"
  else
    echo "  Installing Vale (style checker)..."
    if brew install vale; then
      echo "  Vale installed successfully"
    else
      echo ""
      echo "WARNING: Vale installation failed."
      echo "The editor will still work, but style checking will be disabled."
      echo ""
    fi
  fi
fi

# ============================================
# Create virtual environment
# ============================================
echo ""
echo "Setting up Python virtual environment..."

if [[ -d ".venv" ]]; then
  echo "  Virtual environment already exists"
else
  echo "  Creating virtual environment..."
  $PY -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# ============================================
# Install Python packages
# ============================================
echo ""
echo "Installing Python packages (this may take a minute)..."

python -m pip install --upgrade pip --quiet
python -m pip install -e . --quiet

echo "  Packages installed successfully"

# ============================================
# Verify installation
# ============================================
echo ""
echo "Verifying installation..."

# Check that key packages are importable
if python -c "import streamlit" 2>/dev/null; then
  echo "  Streamlit: OK"
else
  echo "  ERROR: Streamlit not installed properly"
  exit 1
fi

if python -c "import anthropic" 2>/dev/null; then
  echo "  Anthropic: OK"
else
  echo "  ERROR: Anthropic not installed properly"
  exit 1
fi

if python -c "import docx" 2>/dev/null; then
  echo "  python-docx: OK"
else
  echo "  ERROR: python-docx not installed properly"
  exit 1
fi

if python -c "import dtc_editor" 2>/dev/null; then
  echo "  DTC Editor: OK"
else
  echo "  ERROR: DTC Editor not installed properly"
  exit 1
fi

# ============================================
# Done!
# ============================================
echo ""
echo "======================================"
echo "   Setup complete!"
echo "======================================"
echo ""
echo "To run the editor:"
echo ""
echo "  1. Open Terminal"
echo "  2. Run these commands:"
echo ""
echo "     cd \"$(pwd)\""
echo "     source .venv/bin/activate"
echo "     python3 -m streamlit run app.py"
echo ""
echo "  3. Your browser will open automatically"
echo "  4. Enter your Anthropic API key and upload a document"
echo ""
echo "See RUN_ME_FIRST.md for detailed instructions."
echo ""
