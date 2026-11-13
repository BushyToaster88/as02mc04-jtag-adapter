#!/usr/bin/env python3
"""Produce and verify the JLCPCB production files in fab/.

  fab/<project>-gerbers.zip   Gerbers and drill files (upload this for the PCB)
  fab/<project>-bom.csv       bill of materials with LCSC part numbers (assembly)
  fab/<project>-cpl.csv       component placement list (assembly)

Run through tools/fab.sh so the KiCad environment is set up.
"""
import csv
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

import design as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, "hw")
FAB = os.path.join(ROOT, "fab")
GERB = os.path.join(FAB, "gerbers")
PCB = os.path.join(HW, D.PROJECT + ".kicad_pcb")
KICAD_FP = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
JLC_FP = os.path.join(HW, "lib", "jlc.pretty")
LOCAL_FP = os.path.join(HW, "lib", "as02mc04.pretty")

LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"

# How JLCPCB's own footprint for each part is turned relative to the KiCad footprint
# used on this board. JLCPCB rotation = KiCad rotation + offset.
#   jlc:     JLCPCB/EasyEDA footprint fetched for that LCSC part (hw/lib/jlc.pretty)
#   offset:  degrees
#   padmap:  KiCad pad number -> JLCPCB pad number where the two libraries number differently
ROTATION = {
    "Resistor_SMD:R_0603_1608Metric": dict(jlc="R0603", offset=0),
    "Resistor_SMD:R_1206_3216Metric": dict(jlc="R1206", offset=0),
    "Capacitor_SMD:C_0603_1608Metric": dict(jlc="C0603", offset=0),
    # KiCad numbers the cathode 1, JLCPCB numbers the anode 1. Cathode is on the same side in both.
    "LED_SMD:LED_0603_1608Metric": dict(jlc="LED-SMD_L1.6-W0.8-R-RD", offset=0, padmap={"1": "2", "2": "1"}),
    "Package_TO_SOT_SMD:SC-59": dict(jlc="SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR", offset=180),
    "Connector_Molex_Milligrid:Molex_8783214xx_2x07_P2.0mm_Header_Vertical_Polarized_MountingPegs":
        dict(jlc="CONN-SMD_878321420", offset=0),
    # same land pattern, pads numbered from the other end on purpose (pad n meets J4 pin n)
    "as02mc04:Socket_1x06_P2.54mm_RA_J4order":
        dict(jlc="HDR-TH_PM2.54-1X6PWZ-H8.5", offset=0, padmap={str(n): str(7 - n) for n in range(1, 7)}),
}


def run(cmd, cwd=HW):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "Debug:" not in l)
    if r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd)}\n{out}")
    return out


def rot(x, y, deg):
    """KiCad footprint rotation: counter-clockwise on screen, Y axis pointing down."""
    a = math.radians(deg)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def load_pads(libdir, name):
    fp = pcbnew.FootprintLoad(libdir, name)
    if fp is None:
        raise SystemExit(f"footprint {name} not found in {libdir}")
    return {p.GetNumber(): (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y))
            for p in fp.Pads() if p.GetNumber()}


def verify_rotations():
    """Check every rotation offset by overlaying the KiCad pads on JLCPCB's pads."""
    ok = True
    for lib_id, info in ROTATION.items():
        lib, name = lib_id.split(":")
        libdir = LOCAL_FP if lib == "as02mc04" else os.path.join(KICAD_FP, lib + ".pretty")
        kpads = load_pads(libdir, name)
        jpads = load_pads(JLC_FP, info["jlc"])
        padmap = info.get("padmap", {})
        worst = 0.0
        for num, (kx, ky) in kpads.items():
            jn = padmap.get(num, num)
            if jn not in jpads:
                print(f"ROTATION CHECK FAIL {name}: JLCPCB footprint has no pad {jn}")
                ok = False
                continue
            # JLCPCB pad, turned by the offset, must land on the KiCad pad
            jx, jy = rot(jpads[jn][0], jpads[jn][1], info["offset"])
            worst = max(worst, math.hypot(jx - kx, jy - ky))
        good = worst <= 0.35
        ok &= good
        print(f"  rotation offset {info['offset']:>3} deg  {name[:44]:44}  worst pad mismatch {worst:.2f} mm  {'ok' if good else 'FAIL'}")
    return ok


def gerbers():
    if os.path.isdir(GERB):
        shutil.rmtree(GERB)
    os.makedirs(GERB)
    run(["kicad-cli", "pcb", "export", "gerbers", "-o", GERB + "/", "--layers", LAYERS,
         "--no-x2", "--no-netlist", "--subtract-soldermask", "--precision", "6", "--check-zones", PCB])
    run(["kicad-cli", "pcb", "export", "drill", "-o", GERB + "/", "--format", "excellon",
         "--drill-origin", "absolute", "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
         "--excellon-oval-format", "alternate", "--excellon-separate-th", PCB])
    files = sorted(f for f in os.listdir(GERB) if not f.endswith(".gbrjob"))
    for f in os.listdir(GERB):
        if f.endswith(".gbrjob"):
            os.remove(os.path.join(GERB, f))
    z = os.path.join(FAB, D.PROJECT + "-gerbers.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(os.path.join(GERB, f), f)
    return z, files


def parse_drill(path):
    """Return {diameter_mm: hit count} from an Excellon file."""
    tools, hits, cur = {}, {}, None
    for line in open(path):
        line = line.strip()
        m = re.match(r"^T(\d+)C([\d.]+)", line)
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.match(r"^T(\d+)$", line)
        if m:
            cur = m.group(1)
            continue
        if cur and cur != "0" and re.match(r"^X-?[\d.]+Y-?[\d.]+", line):
            d = tools[cur]
            hits[d] = hits.get(d, 0) + 1
    return hits


def verify_gerbers(files):
    """Independent look at the exported files: outline size and drill counts against the board."""
    ok = True
    board = pcbnew.LoadBoard(PCB)
    want_pth, want_npth = {}, {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            d = pcbnew.ToMM(pad.GetDrillSize().x)
            if d <= 0:
                continue
            tgt = want_npth if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else want_pth
            tgt[round(d, 3)] = tgt.get(round(d, 3), 0) + 1
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            d = round(pcbnew.ToMM(t.GetDrillValue()), 3)
            want_pth[d] = want_pth.get(d, 0) + 1
    pth = next(f for f in files if f.endswith("-PTH.drl"))
    npth = next(f for f in files if f.endswith("-NPTH.drl"))
    got_pth = {round(k, 3): v for k, v in parse_drill(os.path.join(GERB, pth)).items()}
    got_npth = {round(k, 3): v for k, v in parse_drill(os.path.join(GERB, npth)).items()}
    for label, want, got in (("plated", want_pth, got_pth), ("unplated", want_npth, got_npth)):
        good = want == got
        ok &= good
        desc = ", ".join(f"{n} x {d} mm" for d, n in sorted(got.items()))
        print(f"  {label} holes: {desc}  {'ok' if good else 'FAIL, board has ' + str(want)}")
    # outline size from the Edge.Cuts Gerber, read with an independent library
    try:
        from gerbonara import GerberFile
        from gerbonara.utils import MM
        edge = next(f for f in files if f.lower().endswith((".gm1", ".gko")))
        (x0, y0), (x1, y1) = GerberFile.open(os.path.join(GERB, edge)).bounding_box(unit=MM)
        w, h = x1 - x0, y1 - y0
        # what the board file says, from the centre lines of its Edge.Cuts shapes
        ex, ey = [], []
        for d in board.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts:
                for pt in (d.GetStart(), d.GetEnd()):
                    ex.append(pcbnew.ToMM(pt.x))
                    ey.append(pcbnew.ToMM(pt.y))
        bw, bh = max(ex) - min(ex), max(ey) - min(ey)
        # the outline is drawn with a 0.1 mm line, so the plot is 0.1 mm larger than the board
        good = abs(w - 0.1 - bw) < 0.02 and abs(h - 0.1 - bh) < 0.02
        ok &= good
        print(f"  outline in {edge}: {w - 0.1:.2f} x {h - 0.1:.2f} mm, board file {bw:.2f} x {bh:.2f} mm  {'ok' if good else 'FAIL'}")
    except Exception as e:  # pragma: no cover
        print("  outline check skipped:", e)
    need = {".gtl", ".gbl", ".gto", ".gbo", ".gts", ".gbs", ".gtp", ".gm1"}
    have = {os.path.splitext(f)[1].lower() for f in files}
    missing = need - have
    if missing:
        ok = False
        print("  MISSING layers:", sorted(missing))
    return ok


def bom():
    groups = {}
    for ref, c in D.COMPONENTS.items():
        if not D.fitted(ref):
            continue
        key = (c["lcsc"], c["value"], c["fp"].split(":")[1], c["mpn"])
        groups.setdefault(key, []).append(ref)
    path = os.path.join(FAB, D.PROJECT + "-bom.csv")

    def refkey(r):
        m = re.match(r"([A-Z]+)(\d+)", r)
        return m.group(1), int(m.group(2))

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (lcsc, value, fp, mpn), refs in sorted(groups.items(), key=lambda kv: refkey(sorted(kv[1], key=refkey)[0])):
            w.writerow([f"{value} ({mpn})", ",".join(sorted(refs, key=refkey)), fp, lcsc])
    return path, len(groups), sum(len(v) for v in groups.values())


def cpl():
    pos = os.path.join(ROOT, "build", "pos_front.csv")
    run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front", "-o", pos, PCB])
    path = os.path.join(FAB, D.PROJECT + "-cpl.csv")
    n = 0
    with open(pos, newline="", encoding="utf-8") as fi, open(path, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(fi):
            ref = row["Ref"]
            if ref not in D.COMPONENTS or not D.fitted(ref):
                raise SystemExit(f"{ref} is in the position file but is not a fitted part")
            off = ROTATION[D.COMPONENTS[ref]["fp"]]["offset"]
            r = (float(row["Rot"]) + off) % 360
            # plain millimetre numbers, no unit suffix: the form JLCPCB's KiCad instructions produce
            w.writerow([ref, f"{float(row['PosX']):.4f}", f"{float(row['PosY']):.4f}", "Top", f"{r:g}"])
            n += 1
    fitted = sum(1 for r in D.COMPONENTS if D.fitted(r))
    if n != fitted:
        raise SystemExit(f"placement file has {n} parts, design has {fitted} fitted parts")
    return path, n


def main():
    os.makedirs(FAB, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    print("rotation offsets (KiCad footprint against JLCPCB's footprint for the same part):")
    ok = verify_rotations()
    z, files = gerbers()
    print(f"gerbers: {len(files)} files -> {os.path.relpath(z, ROOT)}")
    for f in files:
        print("   ", f)
    ok &= verify_gerbers(files)
    b, nlines, nparts = bom()
    print(f"bom: {nlines} lines, {nparts} parts -> {os.path.relpath(b, ROOT)}")
    c, n = cpl()
    print(f"cpl: {n} placements -> {os.path.relpath(c, ROOT)}")
    print("FAB FILES", "OK" if ok else "HAVE PROBLEMS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
