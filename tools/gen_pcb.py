#!/usr/bin/env python3
"""Generate the KiCad board from tools/design.py.

Run with KiCad's Python (the project .venv sees pcbnew). Coordinates are
millimetres in the board frame: origin at the top-left corner of the outline,
X to the right, Y down, looking at the component (front) side.

Front view of the finished adapter:

      top edge:  pull hole in the middle, three test holes either side of it
      J1         Digilent HS3 plugs in here (key slot toward the top edge)
      R1..R4     series resistors, R9 (the 1.8 V limiter) at their right-hand end
      J2         socket, opening on the BOTTOM edge, plugs onto card header J4

   left to right at J2:  GND  TDI  TDO  TCK  TMS  1V8   (pad 6 ... pad 1)

When the adapter is plugged onto the card it stands upright on J4, this front
face points away from the card (off the card's rear edge) and so does the HS3.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew

import design as D
from pcbgen import Board, mm
from sexp import uid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "hw", D.PROJECT + ".kicad_pcb")
LOCAL_FP = os.path.join(ROOT, "hw", "lib", "as02mc04.pretty")
MODELS = "${KIPRJMOD}/lib/jlc.3dshapes"

# ------------------------------------------------------------------ geometry
W = 24.0
J1_X, J1_Y = 11.6, 9.4          # HS3 header centre
R_Y = 15.4                      # series resistor row
J2_X, J2_Y = 12.0, 19.2         # row of J2 solder pins
SOCKET_FACE = 10.05             # J2 mating face, measured from its solder pin row
EDGE_PROUD = 0.30               # the board edge stands this far past the socket face
H = round(J2_Y + SOCKET_FACE + EDGE_PROUD, 2)   # 29.55
RADIUS = 1.0
CHAMFER = 2.0                   # bottom-right corner, marks the 1V8 end
TP_Y = 3.0
# test holes: two groups of three at 2.54 mm pitch, kept well away from the pull hole
TP_X = (2.72, 5.26, 7.80, 16.20, 18.74, 21.28)
PULL = (12.0, 3.5, 1.5)         # pull hole: x, y, radius
LED_X = 2.9                     # column of R8 and D2, left of the socket

PLACE = {
    #  ref: (x, y, rotation)
    "J1": (J1_X, J1_Y, 180),
    "J2": (J2_X, J2_Y, 0),
    "R1": (15.70, R_Y, 270),    # TMS  pad 1 (HS3 side) up, pad 2 (card side) down
    "R2": (13.45, R_Y, 270),    # TCK
    "R3": (11.20, R_Y, 270),    # TDO
    "R4": (8.95, R_Y, 270),     # TDI
    "Q1": (5.65, 15.5, 270),    # drain down toward J2 pad 6, gate top right, source top left
    "R10": (2.80, 15.5, 90),    # pad 1 (GND_T) down, pad 2 (GND) up
    "R5": (1.20, 15.5, 90),     # pad 1 (VREF) down, pad 2 (gate) up
    "R9": (18.35, 15.77, 90),   # 1206. pad 1 (VREF_T) down, right above J2 pad 1; pad 2 (VREF) up
    "C2": (21.0, 14.6, 0),      # pad 1 (VREF) left, pad 2 (GND) right
    "C1": (21.0, 16.2, 0),
    "R7": (22.2, 11.6, 90),     # pad 1 (VREF) down, pad 2 (GND) up
    "R8": (LED_X, J2_Y + 2.0, 270),   # pad 1 (GND_T) up, pad 2 down to D2 anode
    "D2": (LED_X, J2_Y + 5.1, 90),    # anode up, cathode down
    "TP1": (TP_X[0], TP_Y, 0),  # GND
    "TP2": (TP_X[1], TP_Y, 0),  # TDI
    "TP3": (TP_X[2], TP_Y, 0),  # TDO
    "TP4": (TP_X[3], TP_Y, 0),  # TCK
    "TP5": (TP_X[4], TP_Y, 0),  # TMS
    "TP6": (TP_X[5], TP_Y, 0),  # VREF
}

# 3D models: project-local copies of the JLCPCB part models. (file, rotation about Z)
MODEL = {
    "Resistor_SMD:R_0603_1608Metric": ("R0603.wrl", 90),
    "Resistor_SMD:R_1206_3216Metric": ("R1206_L3.2-W1.6-H0.6.wrl", 0),
    "Capacitor_SMD:C_0603_1608Metric": ("C0603_L1.6-W0.8-H0.8.wrl", 0),
    "LED_SMD:LED_0603_1608Metric": ("LED0603_L1.6-W0.8-H0.6.wrl", 0),
    "Package_TO_SOT_SMD:SC-59": ("SOT-23-3L_L2.9-W1.6-H1.1-LS2.8-P0.95.wrl", 90),
    "Connector_Molex_Milligrid:Molex_8783214xx_2x07_P2.0mm_Header_Vertical_Polarized_MountingPegs":
        ("CONN-SMD_878321420.wrl", 0),
}

SIG_W = 0.25
PWR_W = 0.4
GND_W = 0.5
EDGE_CLEARANCE = 0.5

# JLCPCB silkscreen minimums: 0.15 mm line, 1.0 mm character height
SILK_LINE = 0.15
SILK_TEXT = 1.0


def set_model(fp, lib_id):
    if lib_id not in MODEL:
        return
    name, rz = MODEL[lib_id]
    fp.Models().clear()
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = f"{MODELS}/{name}"
    m.m_Rotation = pcbnew.VECTOR3D(0, 0, rz)
    fp.Add3DModel(m)


def thicken_silk(fp):
    """Library footprints draw their silkscreen outline with 0.12 mm lines. Bring them up to the minimum.
    Only the width changes, so every footprint still matches its library copy."""
    for g in fp.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and g.GetClass() == "PCB_SHAPE":
            if 0 < g.GetWidth() < mm(SILK_LINE):
                g.SetWidth(mm(SILK_LINE))


def outline(b):
    r, c = RADIUS, CHAMFER
    b.line(r, 0, W - r, 0)
    b.arc(W - r, r, r, 270, 360)
    b.line(W, r, W, H - c)
    b.line(W, H - c, W - c, H)                 # chamfer at the 1V8 end
    b.line(W - c, H, r, H)
    b.arc(r, H - r, r, 90, 180)
    b.line(0, H - r, 0, r)
    b.arc(r, r, r, 180, 270)


def build():
    b = Board(OUT)
    board = b.b

    # ---- design rules (JLCPCB standard 2-layer process, with margin)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_MinClearance = mm(0.2)
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_ViasMinAnnularWidth = mm(0.13)
    ds.m_CopperEdgeClearance = mm(EDGE_CLEARANCE)
    ds.m_HoleClearance = mm(0.25)
    ds.m_HoleToHoleMin = mm(0.5)
    ds.m_SilkClearance = mm(0.0)
    ds.m_MinSilkTextHeight = mm(SILK_TEXT)
    ds.m_MinSilkTextThickness = mm(SILK_LINE)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(0.2))
    nc.SetTrackWidth(mm(SIG_W))
    nc.SetViaDiameter(mm(0.6))
    nc.SetViaDrill(mm(0.3))

    tb = board.GetTitleBlock()
    tb.SetTitle(D.TITLE)
    tb.SetRevision(D.REV)
    tb.SetDate(D.DATE)

    outline(b)

    # ---- footprints
    pin_net = D.pin_net()
    for ref, c in D.COMPONENTS.items():
        if ref not in PLACE:
            raise SystemExit(f"{ref} has no placement")
        x, y, rot = PLACE[ref]
        lib_id = c["fp"]
        libdir = LOCAL_FP if lib_id.startswith("as02mc04:") else None
        fields = {"Description": c["desc"], "LCSC": c["lcsc"], "MPN": c["mpn"], "Manufacturer": c["mfr"]}
        fp = b.footprint(ref, lib_id, x, y, rot, value=c["value"], libdir=libdir, fields=fields)
        fp.SetPath(pcbnew.KIID_PATH("/" + uid("sym-" + ref)))
        set_model(fp, lib_id)
        thicken_silk(fp)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if not num:
                continue
            key = f"{ref}.{num}"
            if key in pin_net:
                pad.SetNet(b.net(pin_net[key]))
            elif key in D.NO_CONNECT:
                # same name the schematic gives a deliberately unconnected pin
                pad.SetNet(b.net(f"unconnected-({ref}-Pin_{num}-Pad{num})"))
            else:
                raise SystemExit(f"pad {key} has no net")

    # pull hole: a board-only footprint (no schematic symbol, no part)
    hole = b.footprint("H1", "as02mc04:PullHole_3.0mm_NPTH", PULL[0], PULL[1], 0, value="PULL", libdir=LOCAL_FP)
    hole.Reference().SetVisible(False)
    hole.Value().SetVisible(False)

    p = b.pad_xy  # pad centre in board millimetres

    def tr(net, pts, w=SIG_W, layer="F.Cu"):
        b.track(net, pts, w, layer)

    def dogleg(a, c, yk):
        """a -> straight down to yk -> 45 degrees across -> straight down to c."""
        (x0, y0), (x1, y1) = a, c
        return [(x0, y0), (x0, yk), (x1, yk + abs(x1 - x0)), (x1, y1)]

    # ---- HS3 side: J1 even pads down to the series resistors
    for jpin, r, net in ((4, "R1", "TMS_H"), (6, "R2", "TCK_H"), (8, "R3", "TDO_H"), (10, "R4", "TDI_H")):
        tr(net, dogleg(p("J1", jpin), p(r, 1), 13.25))

    # ---- card side: resistors down to J2
    for r, jpin, net in (("R1", 2, "TMS_T"), ("R2", 3, "TCK_T"), ("R3", 4, "TDO_T"), ("R4", 5, "TDI_T")):
        tr(net, dogleg(p(r, 2), p("J2", jpin), 16.9))

    # ---- 1.8 V: J2 pad 1 -> R9 -> HS3 pin 2, decoupling, bleeder, test hole.
    # The unlimited net VREF_T is only this one short, wide link. The wide copper on both
    # ends of R9 also carries its heat away if it ever has to sit in a short circuit.
    x1, y1 = p("J2", 1)
    tr("VREF_T", [(x1, y1), p("R9", 1)], 1.2)
    r9x, r9y = p("R9", 2)
    j1x, j1y = p("J1", 2)
    tr("VREF", [(r9x, r9y), (j1x, r9y - (r9x - j1x)), (j1x, j1y)], 0.8)
    c2x, c2y = p("C2", 1)
    c1x, c1y = p("C1", 1)
    tr("VREF", [(r9x, r9y), (c2x - (c2y - r9y), r9y), (c2x, c2y)], PWR_W)
    tr("VREF", [(c2x, c2y), (c1x, c1y)], PWR_W)
    # spine up the right-hand margin to the bleeder and the VREF test hole
    xs = 21.0
    r7x, r7y = p("R7", 1)
    tpx, tpy = p("TP6", 1)
    ya = tpy + 2.0
    tr("VREF", [(c2x, c2y), (c2x, 13.9), (xs, 13.9 - (xs - c2x)), (xs, ya), (tpx, ya - abs(tpx - xs)), (tpx, tpy)])
    tr("VREF", [(xs, r7y), (r7x, r7y)])

    # ground side of C1, C2 and R7
    g2x, g2y = p("C2", 2)
    g1x, g1y = p("C1", 2)
    gvx, gvy = 22.85, 15.4
    b.via("GND", gvx, gvy)
    tr("GND", [(g2x, g2y), (g1x, g1y)], PWR_W)
    tr("GND", [(g2x, gvy), (gvx, gvy)], PWR_W)
    r7gx, r7gy = p("R7", 2)
    b.via("GND", r7gx, r7gy - 1.3)
    tr("GND", [(r7gx, r7gy), (r7gx, r7gy - 1.3)])

    # ---- Q1 in the ground lead, with its gate resistor and the 1 M bleed across it
    dx, dy = p("Q1", 3)
    sx, sy = p("Q1", 2)
    gx, gy = p("Q1", 1)
    x6, y6 = p("J2", 6)
    tr("GND_T", [(dx, dy), (x6, y6)], GND_W)
    r10ax, r10ay = p("R10", 1)
    tr("GND_T", [(r10ax, r10ay), (r10ax, 17.25), (x6, 17.25)])
    svx = sx - 0.9
    b.via("GND", svx, sy)
    tr("GND", [(sx, sy), (svx, sy)], GND_W)
    r10bx, r10by = p("R10", 2)
    tr("GND", [(svx, sy), (r10bx + 0.3, r10by - 0.1), (r10bx, r10by)])
    r5x, r5y = p("R5", 2)
    yg = 13.4
    tr("Q1_G", [(r5x, r5y), (r5x, yg + 0.35), (r5x + 0.35, yg), (gx - 0.35, yg), (gx, yg + 0.35), (gx, gy)])

    # ---- limited 1.8 V (VREF, behind R9) round the bottom, under the socket body, to the gate
    # resistor and the LED cathode. Nothing on this lane can draw more than R9 lets through.
    r5ax, r5ay = p("R5", 1)
    yb = H - 0.8
    tr("VREF", [(c1x, c1y), (c1x, yb - 0.5), (c1x - 0.5, yb), (r5ax + 0.5, yb), (r5ax, yb - 0.5), (r5ax, r5ay)])
    kx, ky = p("D2", 1)
    tr("VREF", [(kx, ky), (kx, yb)])

    # ---- reversed indicator: J2 pad 6 -> R8 -> D2 -> limited 1.8 V
    ax, ay = p("R8", 1)
    tr("GND_T", [(x6, y6), (ax + (ay - y6), y6), (ax, ay)])
    tr("D2_A", [p("R8", 2), p("D2", 2)])

    # ---- test holes: four signals on the back, straight up under J1
    PEG_R = J1_X + 5.0                     # unplated locating hole of J1, right-hand one
    y_end = TP_Y + 1.6                     # where the 45 degree run meets the column of its test hole

    def feed(net, jpin, tp, lane=None):
        x0, y0 = p("J2", jpin)
        xt, yt = p(tp, 1)
        pts = [(x0, y0)]
        xa = x0
        if lane is not None:               # step sideways first, to pass clear of the peg hole
            d = abs(lane - x0)
            y_lane = J1_Y + 3.6
            pts += [(x0, y_lane + d), (lane, y_lane)]
            xa = lane
        pts += [(xa, y_end + abs(xt - xa)), (xt, y_end), (xt, yt)]
        tr(net, pts, SIG_W, "B.Cu")

    feed("TDI_T", 5, "TP2")
    feed("TDO_T", 4, "TP3")
    feed("TCK_T", 3, "TP4")
    feed("TMS_T", 2, "TP5", lane=PEG_R + 1.15)

    # ---- ground vias: under J1 between its pad rows (return path right beside the signals), plus stitching
    for vx in (9.46, 12.0, 14.54):
        b.via("GND", vx, J1_Y)
    ys = J2_Y + 4.7                        # between the columns of the pin names printed on the back
    for vx, vy in ((1.5, 6.5), (1.5, 11.0), (22.7, 6.5), (6.92, ys), (12.0, ys), (17.08, ys),
                   (0.9, 2.2), (23.1, 2.2), (22.3, J2_Y + 1.7), (22.3, J2_Y + 5.2)):
        b.via("GND", vx, vy)

    # ---- ground pours on both layers, held back from the board edge
    m_ = EDGE_CLEARANCE
    poly = [(m_, m_), (W - m_, m_), (W - m_, H - m_), (m_, H - m_)]
    b.zone("GND", "F.Cu", poly, clearance=0.25, min_width=0.25, name="GND_F")
    b.zone("GND", "B.Cu", poly, clearance=0.25, min_width=0.25, name="GND_B")

    # ---- solid VREF fill on R9's output side, round C1/C2 and up the spine to the VREF test hole.
    # It is behind R9, so it adds no unprotected copper, and it wins over the ground pour (higher
    # priority). It takes some heat off R9's output pad in a short circuit; a thermal model says the
    # overall effect on R9's temperature is small, so do not count on it as a heat sink.
    xl, yt, yr = 16.6, 12.9, r9y + 2.05              # left edge, top edge (meets J1 pad 2), lower edge beside R9
    spine = [(xl, yt), (xs - 0.45, yt), (xs - 0.45, tpy + 0.6), (xs + 0.45, tpy + 0.6), (xs + 0.45, c2y - 0.8),
             ((c2x + g2x) / 2, c2y - 0.8), ((c2x + g2x) / 2, c1y + 0.7),
             (c1x - 0.6, c1y + 0.7), (c1x - 0.6, yr), (xl, yr)]
    b.zone("VREF", "F.Cu", spine, clearance=0.25, min_width=0.25, thermal=False, priority=1, name="VREF_HEAT")

    # ---- keep every pour 0.5 mm away from the two hand-soldered socket pins where a solder bridge to
    # the pour would defeat a protection: J2 pad 1 with its link and R9 pad 1 (a bridge there bypasses
    # the limiter R9), and J2 pad 6 (a bridge there bypasses the reverse-protection transistor Q1).
    r9ax, r9ay = p("R9", 1)
    k = 0.5

    def square(x, y, r):
        return [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)]

    b.keepout("F.Cu", [(x1 - 0.875 - k, r9ay - 0.6025 - k), (x1 + 0.875 + k, r9ay - 0.6025 - k),
                       (x1 + 0.875 + k, y1 + 0.85 + k), (x1 - 0.875 - k, y1 + 0.85 + k)],
              name="VREF_T_clear_F", tracks=False, vias=False, copper=True)
    b.keepout("B.Cu", square(x1, y1, 0.85 + k), name="VREF_T_clear_B", tracks=False, vias=False, copper=True)
    b.keepout("F.Cu", square(x6, y6, 0.85 + k), name="GND_T_clear_F", tracks=False, vias=False, copper=True)
    b.keepout("B.Cu", square(x6, y6, 0.85 + k), name="GND_T_clear_B", tracks=False, vias=False, copper=True)

    silkscreen(b)
    b.fill_zones()
    b.save()
    print("wrote", OUT, f"({W} x {H} mm)")


def silkscreen(b):
    """Front and back legends. Every character is at least 1.0 mm high with 0.15 mm strokes
    (JLCPCB's minimums); tools/check.py verifies that and that nothing prints over a pad, a hole or an edge.
    Lowercase letters are only two thirds as tall as capitals, so 1.0 mm text is written in capitals and
    the one lowercase line (the web address) is 1.4 mm."""
    names = {6: "GND", 5: "TDI", 4: "TDO", 3: "TCK", 2: "TMS", 1: "1V8"}
    tps = {"TP1": "GND", "TP2": "TDI", "TP3": "TDO", "TP4": "TCK", "TP5": "TMS", "TP6": "VREF"}
    t = SILK_LINE
    y_tp = 1.2                                   # label row between the top edge and the test holes

    def tp_labels(layer):
        for ref, name in tps.items():
            x, _ = b.pad_xy(ref, 1)
            if name == "VREF":
                x += 0.15                        # four letters: sit a little toward the free end
            b.text(name, x, y_tp, layer, size=1.0, width=0.7, thickness=t)

    # ---------------- front
    tp_labels("F.SilkS")
    b.text("PULL", PULL[0], y_tp, "F.SilkS", size=1.0, width=0.8, thickness=t)
    b.text("HS3", 1.35, J1_Y - 0.6, "F.SilkS", size=1.0, thickness=t, rot=90)
    # key slot marker: the HS3 key rib goes on this (top) side of J1
    b.poly([(J1_X - 1.25, J1_Y - 4.15), (J1_X + 1.25, J1_Y - 4.15), (J1_X + 1.25, J1_Y - 3.75), (J1_X - 1.25, J1_Y - 3.75)],
           "F.SilkS")
    # which end of the socket is which, printed right beside the two end pins
    b.text("GND", 3.15, J2_Y - 0.2, "F.SilkS", size=1.0, width=0.8, thickness=t)
    b.text("1V8", 21.05, J2_Y - 0.2, "F.SilkS", size=1.0, thickness=t)
    # beside the red LED
    b.text("REVERSED", 1.2, J2_Y + 3.55, "F.SilkS", size=1.0, width=0.7, thickness=t, rot=90)

    # ---------------- back (text is mirrored so it reads correctly from the back)
    tp_labels("B.SilkS")
    for pin, name in names.items():
        x, _ = b.pad_xy("J2", pin)
        b.text(name, x, J2_Y + 2.8, "B.SilkS", size=1.0, thickness=t, rot=90)
    cx = W / 2
    b.text("AS02MC04 JTAG", cx, 6.0, "B.SilkS", size=1.2, thickness=0.2)
    b.text("FOR DIGILENT HS3", cx, 7.8, "B.SilkS", size=1.0, thickness=t)
    b.text("www.exulan.com", cx, 11.3, "B.SilkS", size=1.4, thickness=0.2)
    b.text("1.8 V ONLY", cx, 13.4, "B.SilkS", size=1.2, thickness=0.2)
    b.text("TAKE THIS OFF THE CARD TO", cx, 15.4, "B.SilkS", size=1.0, width=0.85, thickness=t)
    b.text("PLUG OR UNPLUG THE HS3", cx, 16.9, "B.SilkS", size=1.0, width=0.85, thickness=t)
    b.text("THIS SIDE FACES HEATSINK", cx, J2_Y + 6.3, "B.SilkS", size=1.0, width=0.9, thickness=t)
    b.text(f"REV {D.REV}  {D.DATE}", cx, J2_Y + 8.4, "B.SilkS", size=1.0, width=0.9, thickness=t)


if __name__ == "__main__":
    build()
