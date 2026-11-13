# Source this before running kicad-cli from the tools: it points KiCad at a
# private config folder that already has the stock library tables, so the
# command-line checks do not depend on (or touch) your personal KiCad setup.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export KICAD_CONFIG_HOME="$HERE/build/kicad_cfg"
mkdir -p "$KICAD_CONFIG_HOME/10.0"
for t in sym-lib-table fp-lib-table; do
  [ -f "$KICAD_CONFIG_HOME/10.0/$t" ] || cp "/usr/share/kicad/template/$t" "$KICAD_CONFIG_HOME/10.0/$t"
done
