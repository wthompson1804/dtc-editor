# DTC Editor

AI-powered document editor that transforms technical documents using Claude AI.

## What it does

- Rewrites verbose technical prose into clear, concise language
- Enforces DTC style guidelines automatically
- Preserves document structure, formatting, and technical accuracy
- Generates a redline document showing all changes
- Provides a detailed change log

## Output files

For each document you process, you'll get:

1. **Clean document** (`.clean.docx`) - Your edited document
2. **Redline document** (`.redline.docx`) - Shows all changes with track changes
3. **Change log** (`.review.md`) - Detailed list of every edit made

## Requirements

- **Mac** (macOS 10.15 or later)
- **Python 3.10+**
- **Homebrew** (for installing Vale)
- **Anthropic API key** (for Claude AI)

## Setup

**See [RUN_ME_FIRST.md](RUN_ME_FIRST.md) for complete step-by-step instructions.**

Quick version:

```bash
# 1. Run the setup script (one time only)
./setup_mac.sh

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Start the web app
python3 -m streamlit run app.py
```

## Usage

1. Open the app in your browser (starts automatically at http://localhost:8501)
2. Enter your Anthropic API key
3. Upload a Word document (.docx)
4. Click "Process Document"
5. Download your edited files

## API Costs

This tool uses Claude AI via the Anthropic API. You'll be charged based on usage.
See https://www.anthropic.com/pricing for current rates.

A typical 10-page document costs approximately $0.10-0.50 to process.

## Support

For setup help, see the troubleshooting section in [RUN_ME_FIRST.md](RUN_ME_FIRST.md).
