#!/usr/bin/env bash
# Regenerate everything from tools/design.py and run all checks.
#   tools/build.sh          schematic + board + ERC + DRC + netlist comparisons
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
. tools/env.sh
PY="$HERE/.venv/bin/python"
P=as02mc04_jtag_hs3
q() { grep -v -E "RuntimeWarning|Debug:" || true; }
mkdir -p build
"$PY" tools/gen_fp.py 2>&1 | q
"$PY" tools/gen_sch.py 2>&1 | q
(cd hw && kicad-cli sch upgrade --force $P.kicad_sch 2>&1 | q | tail -1)
(cd hw && kicad-cli sch erc --severity-all --format report -o ../build/erc.rpt $P.kicad_sch 2>&1 | q | head -1)
(cd hw && kicad-cli sch export netlist -o ../build/sch.net $P.kicad_sch 2>&1 | q | tail -1)
"$PY" tools/check.py sch 2>&1 | q
"$PY" tools/gen_pcb.py 2>&1 | q
(cd hw && kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --save-board --format report -o ../build/drc.rpt $P.kicad_pcb 2>&1 | q | tail -4)
"$PY" tools/check.py pcb 2>&1 | q
echo "--- DRC summary"; grep -E "^\[" build/drc.rpt | sed 's/\]:.*/]/' | sort | uniq -c || true
