#!/usr/bin/env bash
# Plot the board layers and 3D views into docs/ for inspection.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"; . tools/env.sh
P=as02mc04_jtag_hs3
q() { grep -v -E "Debug:" || true; }
mkdir -p build/svg docs/img
cd hw
for spec in "front:F.Cu,F.SilkS,F.Mask,Edge.Cuts" "back:B.Cu,B.SilkS,Edge.Cuts" "assembly:F.Fab,F.CrtYd,Edge.Cuts"; do
  name=${spec%%:*}; layers=${spec#*:}
  mirror=""; [ "$name" = back ] && mirror="--mirror"     # the back is drawn as seen from the back
  kicad-cli pcb export svg --mode-single $mirror -o ../build/svg/$name.svg --layers "$layers" --page-size-mode 2 --exclude-drawing-sheet $P.kicad_pcb 2>&1 | q | tail -1
  magick -density 1400 ../build/svg/$name.svg -background white -flatten ../docs/img/layout_$name.png
done
kicad-cli sch export pdf -o ../docs/schematic.pdf $P.kicad_sch 2>&1 | q | tail -1
kicad-cli sch export svg -o ../build/sch_svg $P.kicad_sch 2>&1 | q | tail -1
magick -density 160 ../build/sch_svg/$P.svg -background white -flatten ../docs/img/schematic.png
R="kicad-cli pcb render --quality high --perspective --background opaque"
$R -w 1800 -h 1500 --side top    --rotate '-40,0,-28'  --zoom 0.82 -o ../docs/img/render_front.png $P.kicad_pcb 2>&1 | q | tail -1
$R -w 1800 -h 1500 --side top    --rotate '-58,0,152'  --zoom 0.82 -o ../docs/img/render_front_top_edge.png $P.kicad_pcb 2>&1 | q | tail -1
$R -w 1800 -h 1500 --side bottom --rotate '-32,0,-22'  --zoom 0.82 -o ../docs/img/render_back.png  $P.kicad_pcb 2>&1 | q | tail -1
kicad-cli pcb render --quality high --background opaque -w 1500 -h 1800 --side top --zoom 0.9 -o ../docs/img/render_top.png $P.kicad_pcb 2>&1 | q | tail -1
kicad-cli pcb render --quality high --background opaque -w 1800 -h 900 --side front --zoom 0.9 -o ../docs/img/render_socket_end.png $P.kicad_pcb 2>&1 | q | tail -1
cd "$HERE"
"$HERE/.venv/bin/python" tools/make_showcase.py 2>&1 | q | tail -1
