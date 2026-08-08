#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
    echo "[error] .env file not found. Copy .env.example to .env first:"
    echo "    cp .env.example .env"
    exit 1
fi

# Load .env (skip blank lines and comments)
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${1:-}" ]; then
    echo "Usage: ./run.sh \"<brief>\" \"<path-to-csv>\""
    echo "Example: ./run.sh \"Find why Q4 sales dropped.\" tests/sample_data/sales.csv"
    exit 1
fi

if [ -z "${2:-}" ]; then
    echo "Usage: ./run.sh \"<brief>\" \"<path-to-csv>\""
    exit 1
fi

python -m agent.main --brief "$1" --csv "$2"
