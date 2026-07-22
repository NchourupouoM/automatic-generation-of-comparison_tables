#!/usr/bin/env bash
# Rebuild app/static/tailwind.css from the markup. Requires Node.
# Usage: bash tools/build_css.sh
set -euo pipefail
cd "$(dirname "$0")/.."
npx --yes tailwindcss@3 -c tools/tailwind.config.js -i tools/tailwind.input.css \
  -o app/static/tailwind.css --minify
echo "Wrote app/static/tailwind.css"
