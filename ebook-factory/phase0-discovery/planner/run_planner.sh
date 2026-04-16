#!/bin/bash
# Planner Runner — Topic selection from LEARNING.md

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Defaults
DRY_RUN="false"
CONFIG="$SCRIPT_DIR/config.yaml"
LEARNING_MD=""
OUTPUT=""

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --learning)
            LEARNING_MD="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run      Don't write to topic_plan.md, just simulate"
            echo "  --config PATH  Config file (default: config.yaml)"
            echo "  --learning PATH  LEARNING.md path"
            echo "  --output PATH  Output topic_plan.md path"
            echo "  --help         Show this message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set environment vars
export PLANNER_CONFIG="$CONFIG"
export DRY_RUN="$DRY_RUN"
[ -n "$LEARNING_MD" ] && export LEARNING_MD_PATH="$LEARNING_MD"
[ -n "$OUTPUT" ] && export OUTPUT_PATH="$OUTPUT"

echo "╔══════════════════════════════════════╗"
echo "║   📊 Planner Agent — Starting       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Run planner
python3 orchestrator.py

echo ""
echo "✅ Planner complete"
