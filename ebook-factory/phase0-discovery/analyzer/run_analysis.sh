#!/bin/bash
#
# KDP Analysis Runner
# Parses Amazon KDP reports, calculates metrics, and writes to LEARNING.md
#
# Usage:
#   ./run_analysis.sh              # Use config.yaml defaults
#   ./run_analysis.sh --kdp-dir /path/to/downloads
#   ./run_analysis.sh --learning /path/to/LEARNING.md
#   ./run_analysis.sh --dry-run    # Don't write to LEARNING.md
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
KDP_DIR=""
LEARNING_PATH=""
DRY_RUN=false
CONFIG_PATH=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --kdp-dir)
            KDP_DIR="$2"
            shift 2
            ;;
        --learning)
            LEARNING_PATH="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--kdp-dir DIR] [--learning PATH] [--dry-run] [--config CONFIG]" >&2
            exit 1
            ;;
    esac
done

# Activate virtual environment if available
VENV_ACTIVATE=""
if [ -f "hermes-agent/venv/bin/activate" ]; then
    VENV_ACTIVATE="hermes-agent/venv/bin/activate"
elif [ -f "venv/bin/activate" ]; then
    VENV_ACTIVATE="venv/bin/activate"
fi

# Export environment variables for Python
export KDP_DIR
export LEARNING_PATH
export DRY_RUN
export CONFIG_PATH

# Run Python orchestrator directly
python3 "$SCRIPT_DIR/orchestrator.py"
