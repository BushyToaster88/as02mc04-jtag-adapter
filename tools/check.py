#!/usr/bin/env python3
"""Independent consistency checks.

  check.py sch   compare the netlist KiCad exports from the schematic with design.py
  check.py pcb   compare the pad nets in the board file with design.py, check the
                 physical pin order of the connectors against the card header, and
                 check the silkscreen against JLCPCB's printing limits

Exit status is non-zero if anything disagrees.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpdata

import design as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sym(x):
    return x.value() if isinstance(x, sexpdata.Symbol) else x


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and sym(c[0]) == name]


def expected():
    """{net: set("REF.PIN")} from design.py"""
    return {net: set(pins) for net, pins in D.NETS.items()}


def compare(actual, label):
    exp = expected()
    ok = True
    for net in sorted(set(exp) | set(actual)):
        e = exp.get(net, set())
        a = actual.get(net, set())
        if e != a:
            ok = False
            print(f"MISMATCH {label} net {net}: missing {sorted(e - a)} extra {sorted(a - e)}")
    npins = sum(len(v) for v in actual.values())
    print(f"{label}: {len(actual)} nets, {npins} connected pins, {'matches design.py' if ok else 'DIFFERS from design.py'}")
    return ok


def check_sch():
    path = os.path.join(ROOT, "build", "sch.net")
    data = sexpdata.loads(open(path, encoding="utf-8").read())
    actual = {}
    for net in kids(kids(data, "nets")[0], "net"):
        name = kids(net, "name")[0][1]
        nodes = {f"{kids(n, 'ref')[0][1]}.{kids(n, 'pin')[0][1]}" for n in kids(net, "node")}
        if name.startswith("unconnected-"):
            for n in nodes:
                if n not in D.NO_CONNECT:
                    print(f"MISMATCH schematic: {n} is unconnected but not listed in NO_CONNECT")
                    return False
            continue
        actual[name.lstrip("/")] = nodes
    ok = compare(actual, "schematic netlist")
    comps = {kids(c, "ref")[0][1]: c for c in kids(kids(data, "components")[0], "comp")}
    for ref, c in D.COMPONENTS.items():
        if ref not in comps:
            print(f"MISMATCH schematic: {ref} missing")
            ok = False
            continue
        fp = kids(comps[ref], "footprint")[0][1]
        if fp != c["fp"]:
            print(f"MISMATCH schematic: {ref} footprint {fp} != {c['fp']}")
            ok = False
    extra = set(comps) - set(D.COMPONENTS)
    if extra:
        print("MISMATCH schematic: unexpected components", sorted(extra))
        ok = False
    print(f"schematic components: {len(comps)}")
    return ok


def check_pcb():
    import pcbnew

    path = os.path.join(ROOT, "hw", D.PROJECT + ".kicad_pcb")
    board = pcbnew.LoadBoard(path)
    actual = {}
    refs = set()
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if fp.IsBoardOnly():
            continue            # mechanical only, for example the pull hole
        refs.add(ref)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if not num:
                continue
            net = pad.GetNetname()
            key = f"{ref}.{num}"
            if not net or net.startswith("unconnected-"):
                if key not in D.NO_CONNECT:
                    print(f"MISMATCH board: pad {key} has no net")
                    return False
                continue
            actual.setdefault(net.lstrip("/"), set()).add(key)
    ok = compare(actual, "board pad nets")
    if refs != set(D.COMPONENTS):
        print("MISMATCH board: footprints", sorted(refs ^ set(D.COMPONENTS)))
        ok = False
    return ok


def check_geometry():
    """Physical checks that a netlist comparison cannot see: which way round the
    connectors sit, pad pitch, and where the socket face is relative to the edge."""
    import pcbnew

    path = os.path.join(ROOT, "hw", D.PROJECT + ".kicad_pcb")
    board = pcbnew.LoadBoard(path)
    mmv = pcbnew.ToMM
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    # outline from the centre lines of the Edge.Cuts shapes (the bounding box would include the line width)
    ex, ey = [], []
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            for pt in (d.GetStart(), d.GetEnd()):
                ex.append(mmv(pt.x))
                ey.append(mmv(pt.y))
    left, right, top, bottom = min(ex), max(ex), min(ey), max(ey)
    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        print("GEOMETRY FAIL:", msg)

    def pads(ref):
        return {p.GetNumber(): (mmv(p.GetPosition().x), mmv(p.GetPosition().y), p.GetNetname())
                for p in fps[ref].Pads() if p.GetNumber()}

    # --- J2: seen from the front (KiCad top view), left to right must read like the card's silkscreen
    j2 = pads("J2")
    order = [n for n, _ in sorted(j2.items(), key=lambda kv: kv[1][0])]
    nets = [j2[n][2] for n in order]
    want = ["GND_T", "TDI_T", "TDO_T", "TCK_T", "TMS_T", "VREF_T"]
    if nets != want:
        fail(f"J2 left to right is {nets}, expected {want}")
    if order != ["6", "5", "4", "3", "2", "1"]:
        fail(f"J2 pad numbers left to right are {order}, expected 6..1 (pad n must meet J4 pin n)")
    xs = [j2[n][0] for n in order]
    pitch = [round(b - a, 3) for a, b in zip(xs, xs[1:])]
    if any(abs(d - 2.54) > 0.001 for d in pitch):
        fail(f"J2 pitch {pitch}")
    for n, (silk, net) in D.J4.items():
        if j2[str(n)][2] != net:
            fail(f"J2 pad {n} is on {j2[str(n)][2]} but card pin {n} ({silk}) needs {net}")
    row_y = j2["1"][1]
    face = row_y + 10.05                      # nominal mating face of the socket
    proud = bottom - face                     # positive: board edge beyond the socket face
    if not (0.2 <= proud <= 0.5):
        fail(f"board edge is {proud:.2f} mm beyond the J2 mating face, expected 0.2 to 0.5")
    if fps["J2"].GetLayer() != pcbnew.F_Cu or fps["J1"].GetLayer() != pcbnew.F_Cu:
        fail("J1 and J2 must both be on the front side")

    # --- J1: Xilinx numbering, key slot (odd row) toward the top edge, pin 2 at the right-hand end
    j1 = pads("J1")
    for n, (func, net) in D.HS3.items():
        got = j1[str(n)][2]
        if net is None:
            if not got.startswith("unconnected-"):
                fail(f"J1 pad {n} ({func}) should be unconnected, is on {got}")
        elif got != net:
            fail(f"J1 pad {n} ({func}) is on {got}, expected {net}")
    odd_y = {round(j1[str(n)][1], 3) for n in range(1, 15, 2)}
    even_y = {round(j1[str(n)][1], 3) for n in range(2, 15, 2)}
    if len(odd_y) != 1 or len(even_y) != 1 or not (min(odd_y) < min(even_y)):
        fail("J1 odd (ground, key slot) row must be nearer the top edge than the even (signal) row")
    if not (j1["2"][0] > j1["14"][0]):
        fail("J1 pin 2 must be at the right-hand end")
    if any(abs((j1[str(n)][0] - j1[str(n + 2)][0]) - 2.0) > 0.001 for n in range(2, 13, 2)):
        fail("J1 pitch is not 2.00 mm")
    # the signal order under J1 must match the order at J2, so nothing crosses
    j1_lr = [j1[str(n)][2] for n in (10, 8, 6, 4, 2)]
    if j1_lr != ["TDI_H", "TDO_H", "TCK_H", "TMS_H", "VREF"]:
        fail(f"J1 even row left to right is {j1_lr}")

    # --- every series part really sits between its two nets
    for sig, r in D.SERIES.items():
        rp = pads(r)
        got = {rp["1"][2], rp["2"][2]}
        want2 = {"VREF", "VREF_T"} if sig == "VREF" else {sig + "_H", sig + "_T"}
        if got != want2:
            fail(f"{r} joins {got}, expected {want2}")

    # --- the unlimited 1.8 V net must stay a stub: J2 pad 1 to the limiter and nothing else
    vt = sum(mmv(t.GetLength()) for t in board.GetTracks()
             if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "VREF_T")
    if vt > 3.0:
        fail(f"VREF_T (card 1.8 V ahead of R9) has {vt:.1f} mm of track, expected a stub under 3 mm")
    if "R_1206" not in fps["R9"].GetFPID().GetUniStringLibItemName():
        fail("R9 must be the 1206 high-power part")

    # --- no pour may come within 0.5 mm of the copper ahead of R9 (J2 pad 1, link, R9 pad 1) or of
    # J2 pad 6: a solder bridge from one of those hand-soldered pins to the ground pour would bypass
    # the limiter or the reverse protection. Ground pours are tested against both; the VREF fill only
    # against J2 pad 6 (next to the copper ahead of R9 it is the same rail behind 4.7 ohm).
    err = pcbnew.FromMM(0.0005)

    def near(item, layer, fill, dist):
        ps = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(ps, layer, pcbnew.FromMM(dist), err, pcbnew.ERROR_INSIDE)
        ps.BooleanIntersection(fill)
        return ps.Area() > 0

    guarded = []
    for ref, num in (("J2", "1"), ("R9", "1"), ("J2", "6")):
        for pad in fps[ref].Pads():
            if pad.GetNumber() == num:
                guarded += [(f"{ref} pad {num}", pad, l) for l in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(l)]
    guarded += [("the link from J2 pad 1 to R9", t, t.GetLayer()) for t in board.GetTracks()
                if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "VREF_T"]
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        for l in z.GetLayerSet().Seq():
            fill = z.GetFilledPolysList(l)
            for name, item, il in guarded:
                if il != l or (z.GetNetname() == "VREF" and "pad 6" not in name):
                    continue
                if near(item, l, fill, 0.49):
                    fail(f"the {z.GetNetname()} pour on {board.GetLayerName(l)} comes within 0.5 mm of {name}")

    # --- test holes (bare FPGA pins) must keep clear of the pull hole, which is where fingers go
    hx_, hy_ = mmv(fps["H1"].GetPosition().x), mmv(fps["H1"].GetPosition().y)
    gaps = []
    for n in range(1, 7):
        tx, ty, _ = pads(f"TP{n}")["1"]
        gaps.append(((tx - hx_) ** 2 + (ty - hy_) ** 2) ** 0.5 - 1.5 - 0.85)
    if min(gaps) < 1.5:
        fail(f"a test hole pad is only {min(gaps):.2f} mm from the pull hole, expected at least 1.5")

    print(f"geometry: board {right - left:.2f} x {bottom - top:.2f} mm, J2 row {bottom - row_y:.2f} mm above the bottom edge, "
          f"board edge {proud:.2f} mm past the socket face, unlimited 1.8 V track {vt:.1f} mm, "
          f"pours held 0.5 mm back from J2 pads 1 and 6, "
          f"test holes {min(gaps):.2f} mm from the pull hole: {'OK' if ok else 'FAILED'}")
    return ok


def check_silk():
    """Silkscreen against JLCPCB's printing limits, tested on the exact printed shapes:
    character height and stroke width, and no ink on or too near a pad, a hole, the board
    edge, another legend or a component outline."""
    import math

    import pcbnew

    MIN_H, MIN_T = 1.0, 0.15      # JLCPCB: character height and line width
    EDGE, PAD, HOLE, GAP = 0.5, 0.15, 0.15, 0.15
    OUTL = 0.10                   # component outlines may come this close to a pad (the fab clips them, text must not be clipped)
    LOWER = 0.67                  # height of a lowercase letter body relative to the nominal text height
    path = os.path.join(ROOT, "hw", D.PROJECT + ".kicad_pcb")
    board = pcbnew.LoadBoard(path)
    mm, mmv = pcbnew.FromMM, pcbnew.ToMM
    err = mm(0.005)
    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        print("SILKSCREEN FAIL:", msg)

    def circle(x, y, r):
        ps = pcbnew.SHAPE_POLY_SET()
        ps.NewOutline()
        for i in range(64):
            a = 2 * math.pi * i / 64
            ps.Append(int(x + r * math.cos(a)), int(y + r * math.sin(a)))
        return ps

    def overlap(a, b):
        x = pcbnew.SHAPE_POLY_SET(a)
        x.BooleanIntersection(b)
        return x.Area() / 1e12        # mm2

    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    inner = pcbnew.SHAPE_POLY_SET(outline)
    inner.Deflate(mm(EDGE), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err)

    ntext = nline = 0
    for silk, cu, mask, side in ((pcbnew.F_SilkS, pcbnew.F_Cu, pcbnew.F_Mask, "front"),
                                 (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Mask, "back")):
        # ---- what must stay free of ink on this side (legends keep PAD away, component outlines OUTL)
        keep = []
        keep_outl = []
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                name = f"{fp.GetReference()} pad {pad.GetNumber() or 'hole'}"
                pos = pad.GetPosition()
                d = pad.GetDrillSize().x
                if d > 0:
                    keep.append((name + " hole", circle(pos.x, pos.y, d / 2 + mm(HOLE))))
                    keep_outl.append((name + " hole", circle(pos.x, pos.y, d / 2 + mm(OUTL))))
                if pad.IsOnLayer(mask) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                    ps = pcbnew.SHAPE_POLY_SET()
                    pad.TransformShapeToPolygon(ps, cu, mm(PAD), err, pcbnew.ERROR_OUTSIDE)
                    keep.append((name, ps))
                    ps = pcbnew.SHAPE_POLY_SET()
                    pad.TransformShapeToPolygon(ps, cu, mm(OUTL), err, pcbnew.ERROR_OUTSIDE)
                    keep_outl.append((name, ps))
        for v in board.GetTracks():
            if v.GetClass() == "PCB_VIA":
                pos = v.GetPosition()
                vname = f"via at ({mmv(pos.x) - 100:.2f}, {mmv(pos.y) - 100:.2f})"
                keep.append((vname, circle(pos.x, pos.y, v.GetDrillValue() / 2 + mm(HOLE))))
                keep_outl.append((vname, circle(pos.x, pos.y, v.GetDrillValue() / 2 + mm(OUTL))))
        # ---- component outlines printed on this side
        outlines = []
        strokes = []
        for fp in board.GetFootprints():
            for g in fp.GraphicalItems():
                if g.GetLayer() == silk and g.GetClass() == "PCB_SHAPE":
                    nline += 1
                    if 0 < g.GetWidth() < mm(MIN_T) - 10:
                        fail(f"{side}: outline of {fp.GetReference()} is drawn {mmv(g.GetWidth()):.2f} mm wide")
                    ps = pcbnew.SHAPE_POLY_SET()
                    g.TransformShapeToPolygon(ps, silk, mm(0.1), err, pcbnew.ERROR_OUTSIDE)
                    outlines.append((fp.GetReference() + " outline", ps))
                    exact = pcbnew.SHAPE_POLY_SET()
                    g.TransformShapeToPolygon(exact, silk, 0, err, pcbnew.ERROR_OUTSIDE)
                    strokes.append((f"{side} outline of {fp.GetReference()}", exact))
            for t in list(fp.GetFields()):
                if t.IsVisible() and t.GetLayer() == silk:
                    fail(f"{side}: {fp.GetReference()} shows its {t.GetName()} on the silkscreen")
        # ---- the legends themselves
        legends = []
        for d in board.GetDrawings():
            if d.GetLayer() != silk:
                continue
            ps = pcbnew.SHAPE_POLY_SET()
            if d.GetClass() == "PCB_TEXT":
                ntext += 1
                label = f"{side} text '{d.GetText()}'"
                h, th = mmv(d.GetTextHeight()), mmv(d.GetTextThickness())
                if h < MIN_H - 1e-6:
                    fail(f"{label} is {h:.2f} mm high, minimum {MIN_H}")
                # a lowercase letter prints about 0.67 of the nominal height plus one stroke width
                if any(c.islower() for c in d.GetText()) and LOWER * h + th < MIN_H - 1e-6:
                    fail(f"{label} has lowercase letters that print only {LOWER * h + th:.2f} mm high, minimum {MIN_H}")
                if th < MIN_T - 1e-6:
                    fail(f"{label} has {th:.2f} mm strokes, minimum {MIN_T}")
                if d.IsMirrored() != (side == "back"):
                    fail(f"{label} is mirrored the wrong way for the {side}")
                d.TransformTextToPolySet(ps, 0, err, pcbnew.ERROR_OUTSIDE)
            else:
                label = f"{side} mark at ({mmv(d.GetCenter().x) - 100:.1f}, {mmv(d.GetCenter().y) - 100:.1f})"
                d.TransformShapeToPolygon(ps, silk, 0, err, pcbnew.ERROR_OUTSIDE)
            legends.append((label, ps))
        for label, ps in legends:
            out = pcbnew.SHAPE_POLY_SET(ps)
            out.BooleanSubtract(inner)
            if out.Area() / 1e12 > 1e-6:
                fail(f"{label} comes within {EDGE} mm of the board edge")
            for name, k in keep:
                if overlap(ps, k) > 1e-6:
                    fail(f"{label} is on or within {PAD} mm of {name}")
            for name, o in outlines:
                if overlap(ps, o) > 1e-6:
                    fail(f"{label} touches the {name}")
        for label, ps in strokes:
            out = pcbnew.SHAPE_POLY_SET(ps)
            out.BooleanSubtract(outline)
            if out.Area() / 1e12 > 1e-6:
                fail(f"{label} runs off the board")
            for name, k in keep_outl:
                if overlap(ps, k) > 1e-6:
                    fail(f"{label} is on or within {OUTL} mm of {name}")
        for i, (la, pa) in enumerate(legends):
            grown = pcbnew.SHAPE_POLY_SET(pa)
            grown.Inflate(mm(GAP), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err)
            for lb, pb in legends[i + 1:]:
                if overlap(grown, pb) > 1e-6:
                    fail(f"{la} runs into {lb}")
    print(f"silkscreen: {ntext} texts and {nline} outline strokes checked against {MIN_H} mm height, {MIN_T} mm line, "
          f"{EDGE} mm to the edge, {PAD} mm to pads and holes: {'OK' if ok else 'FAILED'}")
    return ok


def check_labels():
    """The words on the silkscreen must name what they sit beside: each test-hole label against the net
    of its hole (both faces), each pin name on the back against its J2 pad, and the two end labels on the front."""
    import pcbnew

    path = os.path.join(ROOT, "hw", D.PROJECT + ".kicad_pcb")
    board = pcbnew.LoadBoard(path)
    mmv = pcbnew.ToMM
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        print("LABEL FAIL:", msg)

    texts = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() in texts:
            c = d.GetBoundingBox().Centre()
            texts[d.GetLayer()].append((d.GetText(), mmv(c.x), mmv(c.y)))

    def pad(ref, num):
        for p in fps[ref].Pads():
            if p.GetNumber() == str(num):
                return mmv(p.GetPosition().x), mmv(p.GetPosition().y), p.GetNetname()
        raise KeyError(f"{ref}.{num}")

    hole_name = {"GND": "GND", "TDI_T": "TDI", "TDO_T": "TDO", "TCK_T": "TCK", "TMS_T": "TMS", "VREF": "VREF"}
    pin_name = {"VREF_T": "1V8", "TMS_T": "TMS", "TCK_T": "TCK", "TDO_T": "TDO", "TDI_T": "TDI", "GND_T": "GND"}
    names = set(hole_name.values()) | set(pin_name.values())     # every word that names a signal
    n = 0
    for layer, side in ((pcbnew.F_SilkS, "front"), (pcbnew.B_SilkS, "back")):
        # test holes: the label is the text straight above the hole, between it and the top edge
        for i in range(1, 7):
            x, y, net = pad(f"TP{i}", 1)
            near = [t[0] for t in texts[layer] if abs(t[1] - x) < 1.0 and 0.5 < y - t[2] < 2.6]
            want = hole_name[net]
            n += 1
            if near.count(want) != 1 or any(t in names and t != want for t in near):
                fail(f"{side}: test hole TP{i} is on net {net} and should be labelled {want}, found {near}")
    # J2 pin names on the back: the text in the column of each pad, just below it
    for num in range(1, 7):
        x, y, net = pad("J2", num)
        near = [t[0] for t in texts[pcbnew.B_SilkS] if abs(t[1] - x) < 0.6 and 0.9 < t[2] - y < 5.0]
        want = pin_name[net]
        n += 1
        if near.count(want) != 1 or any(t in names and t != want for t in near):
            fail(f"back: J2 pad {num} is on net {net} and should be labelled {want}, found {near}")
    # front: GND beside pad 6 (left end), 1V8 beside pad 1 (right end)
    for num, want, sign in ((6, "GND", -1), (1, "1V8", +1)):
        x, y, net = pad("J2", num)
        near = [t[0] for t in texts[pcbnew.F_SilkS] if abs(t[2] - y) < 0.8 and 0.9 < sign * (t[1] - x) < 4.0]
        n += 1
        if near.count(want) != 1 or pin_name[net] != want or any(t in names and t != want for t in near):
            fail(f"front: J2 pad {num} (net {net}) should have {want} beside it, found {near}")
    # the web address must be there, exactly, on the back
    if [t[0] for t in texts[pcbnew.B_SilkS]].count("www.exulan.com") != 1:
        fail("back: expected exactly one 'www.exulan.com'")
    print(f"labels: {n} labels compared with the nets they sit beside, web address present: {'OK' if ok else 'FAILED'}")
    return ok


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "sch"
    if what == "sch":
        good = check_sch()
    else:
        results = [check_pcb(), check_geometry(), check_silk(), check_labels()]   # run them all, so every problem is listed
        good = all(results)
    sys.exit(0 if good else 1)
