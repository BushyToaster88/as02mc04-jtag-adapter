#!/usr/bin/env python3
"""Generate the project-specific footprints into hw/lib/as02mc04.pretty.

Socket_1x06_P2.54mm_RA_J4order
    An ordinary 1x6 2.54 mm right-angle female socket (body 8.5 mm). The only
    special thing is the pad numbering: pad 1 is at the END THAT MEETS PIN 1 (1V8)
    OF THE CARD HEADER J4, so pad n of J2 always carries the signal of J4 pin n.
    Frame (KiCad, Y down), origin at the centre of the row of solder pins, body and
    mating face toward +Y (the board's bottom edge). Seen from the component side
    with the socket at the bottom, pad 1 is on the RIGHT.
    All six pads are round on purpose: the part maker numbers this socket from the
    other end, so a square "pin 1" pad here would only invite a query at assembly.
    The socket is symmetric, so which end is called pin 1 has no electrical meaning.

TestHole_D1.7mm_Drill1.0mm
    A bare plated hole for a probe or a soldered pin. Carries no part.

PullHole_3.0mm_NPTH
    An unplated hole for a pull loop. Carries no part.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "hw", "lib", "as02mc04.pretty")
MODELS = "${KIPRJMOD}/lib/jlc.3dshapes"

PITCH = 2.54
N = 6
HALF = PITCH * (N - 1) / 2  # 6.35

# Dimensions in millimetres, from the SHOU HAN PM2.54-1x6PWZ-H8.5 drawing (LCSC C54876735):
# body 8.5 x 2.5 x 15.74, mating face 10.0 +/- 0.3 from the hole row, hole 1.02.
SOCKET = dict(
    name="Socket_1x06_P2.54mm_RA_J4order",
    body_y0=1.50, body_y1=10.05, body_half_x=7.87, pad=1.7, drill=1.0,
    model="HDR-TH_PM2.54-1X6PWZ-H8.5.wrl",
)


def line(x1, y1, x2, y2, layer, w):
    return (f'\t(fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f})\n'
            f'\t\t(stroke (width {w}) (type solid)) (layer "{layer}"))')


def rect(x1, y1, x2, y2, layer, w):
    return "\n".join([line(x1, y1, x2, y1, layer, w), line(x2, y1, x2, y2, layer, w),
                      line(x2, y2, x1, y2, layer, w), line(x1, y2, x1, y1, layer, w)])


def socket():
    d = SOCKET
    hx, y0, y1 = d["body_half_x"], d["body_y0"], d["body_y1"]
    items = [rect(-hx, y0, hx, y1, "F.Fab", 0.1)]
    for n in range(N):
        x = HALF - n * PITCH
        items.append(line(x, 0, x, y0, "F.Fab", 0.1))                       # contact tail into the body
        items.append(line(x - 0.6, y1, x - 0.6, y1 - 1.0, "F.Fab", 0.1))    # opening at the mating face
        items.append(line(x + 0.6, y1, x + 0.6, y1 - 1.0, "F.Fab", 0.1))
    # silkscreen: back wall and the two side walls, stopping short of the board edge
    sa, sb = y0 - 0.11, y1 - 0.85
    for sx in (-hx - 0.11, hx + 0.11):
        items.append(line(sx, sa, sx, sb, "F.SilkS", 0.15))
    for a, b in ((-hx - 0.11, -HALF - 1.05), (HALF + 1.05, hx + 0.11)):
        items.append(line(a, sa, b, sa, "F.SilkS", 0.15))
    items.append(rect(-hx - 0.25, -1.1, hx + 0.25, y1 + 0.25, "F.CrtYd", 0.05))
    pads = []
    for n in range(1, N + 1):
        x = HALF - (n - 1) * PITCH          # pad 1 at +6.35, pad 6 at -6.35
        pads.append(f'\t(pad "{n}" thru_hole circle (at {x:.3f} 0) (size {d["pad"]} {d["pad"]}) (drill {d["drill"]})\n'
                    f'\t\t(layers "*.Cu" "*.Mask") (remove_unused_layers no))')
    return f"""(footprint "{d['name']}"
\t(version 20241229)
\t(generator "as02mc04-tools")
\t(layer "F.Cu")
\t(descr "1x6 2.54 mm right-angle female socket, body 8.5 mm (SHOU HAN PM2.54-1x6PWZ-H8.5, LCSC C54876735). Pad 1 mates with pin 1 (1V8) of card header J4. Mating face is 10.05 mm from the solder pin row.")
\t(tags "AS02MC04 J4 JTAG socket 1x06 2.54mm right angle")
\t(property "Reference" "REF**" (at 0 -2.2 0) (layer "F.SilkS")
\t\t(effects (font (size 1 1) (thickness 0.15))))
\t(property "Value" "{d['name']}" (at 0 5.2 0) (layer "F.Fab")
\t\t(effects (font (size 0.8 0.8) (thickness 0.12))))
\t(attr through_hole)
{chr(10).join(items)}
\t(fp_text user "${{REFERENCE}}" (at 0 6.8 0) (layer "F.Fab")
\t\t(effects (font (size 0.8 0.8) (thickness 0.12))))
{chr(10).join(pads)}
\t(model "{MODELS}/{d['model']}"
\t\t(offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
)
"""


def test_hole():
    name = "TestHole_D1.7mm_Drill1.0mm"
    return f"""(footprint "{name}"
\t(version 20241229)
\t(generator "as02mc04-tools")
\t(layer "F.Cu")
\t(descr "Plated test hole, 1.7 mm pad, 1.0 mm drill, for a probe or a soldered 0.64 mm pin. No part is fitted.")
\t(tags "test point hole")
\t(property "Reference" "REF**" (at 0 -1.6 0) (layer "F.Fab")
\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))
\t(property "Value" "{name}" (at 0 1.6 0) (layer "F.Fab")
\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))
\t(attr through_hole exclude_from_pos_files exclude_from_bom)
\t(fp_circle (center 0 0) (end 1.1 0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))
\t(fp_circle (center 0 0) (end 0.85 0) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
\t(pad "1" thru_hole circle (at 0 0) (size 1.7 1.7) (drill 1.0)
\t\t(layers "*.Cu" "*.Mask") (remove_unused_layers no))
)
"""


def pull_hole():
    name = "PullHole_3.0mm_NPTH"
    return f"""(footprint "{name}"
\t(version 20241229)
\t(generator "as02mc04-tools")
\t(layer "F.Cu")
\t(descr "Unplated 3.0 mm hole for a pull loop, so the adapter can be lifted straight off the card header. No part is fitted.")
\t(tags "hole pull loop")
\t(property "Reference" "REF**" (at 0 -2.4 0) (layer "F.Fab")
\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))
\t(property "Value" "{name}" (at 0 2.4 0) (layer "F.Fab")
\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))
\t(attr board_only exclude_from_pos_files exclude_from_bom)
\t(fp_circle (center 0 0) (end 1.9 0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))
\t(fp_circle (center 0 0) (end 1.5 0) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
\t(pad "" np_thru_hole circle (at 0 0) (size 3.0 3.0) (drill 3.0) (layers "*.Cu" "*.Mask"))
)
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".kicad_mod"):
            os.remove(os.path.join(OUT, f))
    for name, text in ((SOCKET["name"], socket()), ("TestHole_D1.7mm_Drill1.0mm", test_hole()),
                       ("PullHole_3.0mm_NPTH", pull_hole())):
        p = os.path.join(OUT, name + ".kicad_mod")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print("wrote", p)


if __name__ == "__main__":
    main()
