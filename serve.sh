#!/usr/bin/env bash
# Build the site and serve it locally for testing.
# Usage: ./serve.sh [port]   (default port: 8000)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8000}"

uv run build.py
echo "Serving at http://localhost:${PORT} (Ctrl+C to stop)"
python3 -m http.server "${PORT}" -d _site
