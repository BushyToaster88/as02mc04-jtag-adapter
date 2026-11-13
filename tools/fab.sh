#!/usr/bin/env bash
# Export and verify the JLCPCB production files into fab/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"; . tools/env.sh
"$HERE/.venv/bin/python" tools/make_fab.py 2>&1 | grep -v -E "RuntimeWarning|Debug:"
