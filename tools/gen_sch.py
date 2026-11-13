#!/usr/bin/env python3
"""Generate the KiCad schematic from tools/design.py.

Every pin gets a short wire stub and a net label, so the drawing is a faithful
picture of the netlist in design.py. The result is normalised by
`kicad-cli sch upgrade` and then checked with ERC and a netlist comparison
(see tools/check.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design as D
import symlib
from sexp import fmt, q, uid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "hw", D.PROJECT + ".kicad_sch")
ROOT_UUID = uid("sheet-root")

# ref -> (x, y, rotation). 1.27 mm grid.
PLACE = {
    # HS3 side
    "J1": (60.96, 78.74, 0),
    # series resistors
    "R1": (111.76, 66.04, 90),
    "R2": (111.76, 76.2, 90),
    "R3": (111.76, 86.36, 90),
    "R4": (111.76, 96.52, 90),
    # card side
    "J2": (167.64, 73.66, 0),
    # test holes
    "TP1": (203.2, 71.12, 0),
    "TP2": (215.9, 71.12, 0),
    "TP3": (228.6, 71.12, 0),
    "TP4": (241.3, 71.12, 0),
    "TP5": (254.0, 71.12, 0),
    "TP6": (266.7, 71.12, 0),
    # 1.8 V feed
    "R9": (40.64, 144.78, 90),
    "C1": (60.96, 154.94, 0),
    "C2": (73.66, 154.94, 0),
    "R7": (86.36, 154.94, 0),
    # reverse protection (R5 far enough from Q1 that their two gate labels do not overlap)
    "R5": (109.22, 152.4, 90),
    "Q1": (139.7, 152.4, 0),
    "R10": (165.1, 152.4, 0),
    # reversed indicator (D2 far enough from R8 that their labels do not overlap)
    "R8": (193.04, 144.78, 90),
    "D2": (228.6, 144.78, 0),
}

# reference / value text offsets per symbol and rotation: (dx, dy, justify)
TEXT = {
    ("Conn_02x07_Odd_Even", 0): ((1.27, -12.7, None), (1.27, 12.7, None)),
    ("Conn_01x06", 0): ((0, -10.16, None), (0, 12.7, None)),
    ("R", 90): ((0, -2.54, None), (0, 2.54, None)),
    ("R", 0): ((2.54, -1.27, "left"), (2.54, 1.27, "left")),
    ("C", 0): ((3.81, -1.27, "left"), (3.81, 1.27, "left")),
    ("LED", 0): ((0, -3.81, None), (0, 3.81, None)),
    ("AO3400A", 0): ((7.62, -1.27, "left"), (7.62, 1.27, "left")),
    ("TestPoint", 0): ((0, -6.35, None), (0, -4.445, None)),
}

STUB = 2.54
LABEL_ROT = {(1, 0): (0, "left"), (-1, 0): (180, "right"), (0, -1): (90, "left"), (0, 1): (270, "right")}


def effects(size=1.27, justify=None, hide=False):
    j = f" (justify {justify})" if justify else ""
    h = " (hide yes)" if hide else ""
    return f"(effects (font (size {fmt(size)} {fmt(size)})){j}{h})"


def prop(name, value, x, y, rot=0, justify=None, hide=False):
    h = "\n\t\t\t(hide yes)" if hide else ""
    j = f" (justify {justify})" if justify else ""
    return (f'\t\t(property {q(name)} {q(value)}\n\t\t\t(at {fmt(x)} {fmt(y)} {rot}){h}\n'
            f'\t\t\t(effects (font (size 1.27 1.27)){j})\n\t\t)')


def wire(x1, y1, x2, y2, key):
    return (f'\t(wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))\n'
            f'\t\t(stroke (width 0) (type default))\n\t\t(uuid {q(uid("wire-" + key))})\n\t)')


def label(net, x, y, d, key):
    """Global label, so net names carry no sheet prefix (GND rather than /GND)."""
    rot, just = LABEL_ROT[d]
    return (f'\t(global_label {q(net)}\n\t\t(shape passive)\n\t\t(at {fmt(x)} {fmt(y)} {rot})\n'
            f'\t\t(effects (font (size 1.27 1.27)) (justify {just}))\n\t\t(uuid {q(uid("label-" + key))})\n\t)')


def no_connect(x, y, key):
    return f'\t(no_connect (at {fmt(x)} {fmt(y)}) (uuid {q(uid("nc-" + key))}))'


def text(s, x, y, key, size=1.27):
    return (f'\t(text {q(s)}\n\t\t(exclude_from_sim no)\n\t\t(at {fmt(x)} {fmt(y)} 0)\n'
            f'\t\t(effects (font (size {fmt(size)} {fmt(size)})) (justify left bottom))\n\t\t(uuid {q(uid("text-" + key))})\n\t)')


def symbol_instance(ref, lib_id, x, y, rot, value, footprint, fields, pin_numbers, ref_at, val_at, in_bom=True, on_board=True):
    rx, ry, rj = ref_at
    vx, vy, vj = val_at
    lines = [
        "\t(symbol",
        f"\t\t(lib_id {q(lib_id)})",
        f"\t\t(at {fmt(x)} {fmt(y)} {rot})",
        "\t\t(unit 1)",
        "\t\t(exclude_from_sim no)",
        f"\t\t(in_bom {'yes' if in_bom else 'no'})",
        f"\t\t(on_board {'yes' if on_board else 'no'})",
        "\t\t(dnp no)",
        f"\t\t(uuid {q(uid('sym-' + ref))})",
        prop("Reference", ref, x + rx, y + ry, rot, rj),
        prop("Value", value, x + vx, y + vy, rot, vj),
        prop("Footprint", footprint, x, y, 0, None, hide=True),
        prop("Datasheet", "", x, y, 0, None, hide=True),
    ]
    for k, v in fields.items():
        lines.append(prop(k, v, x, y, 0, None, hide=True))
    for n in pin_numbers:
        lines.append(f'\t\t(pin {q(n)} (uuid {q(uid("pin-" + ref + "-" + n))}))')
    lines.append(f'\t\t(instances\n\t\t\t(project {q(D.PROJECT)}\n\t\t\t\t(path {q("/" + ROOT_UUID)}\n'
                 f'\t\t\t\t\t(reference {q(ref)})\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)')
    lines.append("\t)")
    return "\n".join(lines)


def main():
    pin_net = D.pin_net()
    lib_blocks = {}
    body = []

    def lib(lib_id):
        if lib_id not in lib_blocks:
            l, n = lib_id.split(":")
            lib_blocks[lib_id] = symlib.load(l, n)
        return lib_blocks[lib_id]

    used = set()
    for ref, c in D.COMPONENTS.items():
        x, y, rot = PLACE[ref]
        blk = lib(c["sym"])
        pins = symlib.pins(blk)
        name = c["sym"].split(":")[1]
        ref_at, val_at = TEXT[(name, rot)]
        fields = {"Description": c["desc"], "LCSC": c["lcsc"], "MPN": c["mpn"], "Manufacturer": c["mfr"]}
        body.append(symbol_instance(ref, c["sym"], x, y, rot, c["value"], c["fp"], fields,
                                    [p["number"] for p in pins], ref_at, val_at, in_bom=D.fitted(ref)))
        for p in pins:
            key = f"{ref}.{p['number']}"
            px, py = symlib.pin_end(p, x, y, rot)
            if key in D.NO_CONNECT:
                body.append(no_connect(px, py, key))
                used.add(key)
                continue
            net = pin_net.get(key)
            if net is None:
                raise SystemExit(f"pin {key} has no net and is not marked no-connect")
            used.add(key)
            dx, dy = symlib.pin_out_dir(p, rot)
            ex, ey = px + dx * STUB, py + dy * STUB
            body.append(wire(px, py, ex, ey, key))
            body.append(label(net, ex, ey, (dx, dy), key))
    missing = (set(pin_net) | set(D.NO_CONNECT)) - used
    if missing:
        raise SystemExit(f"design.py names pins that do not exist: {sorted(missing)}")

    notes = [
        ("HS3 SIDE: Xilinx 14-pin JTAG header.\nPin 2 is the HS3 buffer supply (VREF).", 38.1, 53.34, "n1"),
        ("SERIES RESISTORS\n(the HS3 already has 100R inside)", 99.06, 53.34, "n2"),
        ("CARD SIDE: J2 plugs straight onto card header J4,\nor takes a 6-way male-to-female jumper cable.\n"
         "J2 pin n meets J4 pin n.", 149.86, 50.8, "n3"),
        ("TEST HOLES (not fitted)\nfor a scope or logic analyzer", 200.66, 53.34, "n4"),
        ("1.8 V FEED: R9 limits what a fault behind it can draw\nfrom the card's 1.8 V rail to 0.38 A. It is a 0.75 W part: a dead short\n"
         "makes it hot, not burnt. Only J2 pin 1, the 2 mm link and R9 pad 1 are ahead of it.",
         33.02, 132.08, "n5"),
        ("REVERSE-INSERTION PROTECTION: Q1 sits in the ground lead.\n"
         "Correct way round: gate sees 1.8 V, Q1 is on.\n"
         "Reversed: gate sees 0 V, body diode blocks, no short.", 111.76, 132.08, "n6"),
        ("REVERSED INDICATOR: sits across the two end pins (behind R9),\n"
         "so it glows only when 1.8 V arrives the wrong way round.\n"
         "Dim by nature (1.8 V). No light does NOT prove correct orientation.", 185.42, 132.08, "n7"),
        ("Card header J4 (AS02MC04, XCKU3P bank 0, 1.8 V ONLY)\n"
         "pin 1  1V8  reference voltage from the card\n"
         "pin 2  TMS\n"
         "pin 3  TCK  (silkscreen on the card says TDK)\n"
         "pin 4  TDO\n"
         "pin 5  TDI\n"
         "pin 6  GND", 200.66, 114.3, "n8"),
    ]
    for s, x, y, k in notes:
        body.append(text(s, x, y, k))

    libs = "\n\t\t".join(b.replace("\n", "\n\t") for b in lib_blocks.values())
    out = f"""(kicad_sch
\t(version 20260306)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid {q(ROOT_UUID)})
\t(paper "A4")
\t(title_block
\t\t(title {q(D.TITLE)})
\t\t(date {q(D.DATE)})
\t\t(rev {q(D.REV)})
\t\t(comment 1 "Card: Alibaba Cloud AS02MC04 (PN YZQT-02337-101), header J4, 1.8 V JTAG")
\t\t(comment 2 "Probe: Digilent JTAG-HS3 rev A, Xilinx 14-pin 2.00 mm header")
\t)
\t(lib_symbols
\t\t{libs}
\t)
{chr(10).join(body)}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", OUT, len(out), "bytes")


if __name__ == "__main__":
    main()
