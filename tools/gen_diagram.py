#!/usr/bin/env python3
"""Draw a to-scale side view of the adapter standing on the card header J4.

Output: docs/img/how_it_sits.svg (and .png if ImageMagick is available).
The view looks along the row of J4 pins, so the card's rear edge is on the right.
All dimensions are millimetres; they come from tools/gen_pcb.py and the part drawings.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "img", "how_it_sits.svg")

S = 14.0                      # pixels per millimetre
X0, Z0 = 520, 650             # pixel position of the J4 pin axis at the card surface

# geometry (x: positive toward the card's rear edge and beyond, z: up from the card surface)
BOARD_H = 29.55
EDGE_PROUD = 0.30
J4_BASE = 2.54
PCB_T = 1.6
CONTACT_H = 1.25              # socket contact axis above the adapter's front face
Z_BOT = J4_BASE - EDGE_PROUD
Z_TOP = Z_BOT + BOARD_H
X_FRONT = -CONTACT_H          # adapter front face (points away from the card centre)
X_BACK = X_FRONT - PCB_T
J1_Z = Z_TOP - 9.4
PULL_Z = Z_TOP - 3.5
REAR_EDGE = 4.9


def px(x, z):
    return X0 + x * S, Z0 - z * S


def rect(x0, z0, x1, z1, fill, stroke="#222", sw=1.2, extra=""):
    (ax, ay), (bx, by) = px(x0, z1), px(x1, z0)
    return (f'<rect x="{ax:.1f}" y="{ay:.1f}" width="{bx - ax:.1f}" height="{by - ay:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')


def text(s, x, z, size=17, anchor="start", weight="normal", fill="#111"):
    ax, ay = px(x, z)
    return (f'<text x="{ax:.1f}" y="{ay:.1f}" font-family="DejaVu Sans, Arial, sans-serif" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}" fill="{fill}">{s}</text>')


def leader(x0, z0, x1, z1):
    (ax, ay), (bx, by) = px(x0, z0), px(x1, z1)
    return f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="#555" stroke-width="1"/>'


def arrow(x0, z0, x1, z1, color="#b3261e"):
    (ax, ay), (bx, by) = px(x0, z0), px(x1, z1)
    return (f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{color}" stroke-width="3" '
            f'marker-end="url(#arr)"/>')


def main():
    e = []
    e.append('<defs><marker id="arr" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto">'
             '<path d="M0,0 L10,4 L0,8 z" fill="#b3261e"/></marker></defs>')
    e.append('<rect x="0" y="0" width="1180" height="810" fill="#ffffff"/>')
    e.append(text("Side view, to scale: adapter standing on card header J4", -34.5, 43.3, 22, weight="bold"))

    # card
    e.append(rect(-36, -1.6, REAR_EDGE, 0, "#2e6b3e"))
    e.append(text("FPGA card (component side up)", -35, -3.6, 16))
    e.append(leader(REAR_EDGE, -0.8, REAR_EDGE + 3, -4.5))
    e.append(text("rear edge of the card", REAR_EDGE + 3.3, -5.0, 16))
    # heatsink hint
    e.append(rect(-36, 0, -25, 9.5, "#3a3a3a"))
    e.append(text("heatsink", -34.6, 4.2, 15, fill="#ffffff"))
    # J4
    e.append(rect(-1.27, 0, 1.27, J4_BASE, "#1c1c1c"))
    e.append(rect(-0.32, 0, 0.32, 8.6, "#d4af37", sw=0.6))
    e.append(leader(-1.27, 1.2, -9.5, 3.3))
    e.append(text("J4 on the card", -10, 3.2, 16, anchor="end"))

    # adapter board
    e.append(rect(X_BACK, Z_BOT, X_FRONT, Z_TOP, "#1f5f3a"))
    # socket J2 and its solder tail
    e.append(rect(X_FRONT, J4_BASE, X_FRONT + 2.5, J4_BASE + 8.5, "#555555"))
    e.append(rect(X_BACK - 1.6, J4_BASE + 10.05 - 0.2, X_FRONT + 0.4, J4_BASE + 10.05 + 0.2, "#d4af37", sw=0.6))
    e.append(rect(-0.32, J4_BASE, 0.32, 8.6, "#d4af37", sw=0.6, extra='fill-opacity="0.75"'))
    # J1 shroud
    e.append(rect(X_FRONT, J1_Z - 3.15, X_FRONT + 7.6, J1_Z + 3.15, "#111111"))
    # HS3 pod (approximate size) and USB cable
    e.append(rect(X_FRONT + 3.7, J1_Z - 3.7, X_FRONT + 3.7 + 33, J1_Z + 3.7, "#f0c05a", extra='fill-opacity="0.85"'))
    e.append(text("Digilent HS3", X_FRONT + 13.5, J1_Z - 0.6, 18, weight="bold"))
    e.append(rect(X_FRONT + 36.7, J1_Z - 1.6, X_FRONT + 47, J1_Z + 1.6, "#888888"))
    e.append(text("USB", X_FRONT + 38.4, J1_Z - 0.55, 14, fill="#ffffff"))
    # pull hole marker
    cx, cy = px((X_FRONT + X_BACK) / 2, PULL_Z)
    e.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{1.5 * S:.1f}" fill="#ffffff" stroke="#222" stroke-width="1" fill-opacity="0.5"/>')

    # labels
    e.append(leader(X_FRONT + 1.2, J4_BASE + 5.5, 7.5, 13.2))
    e.append(text("J2 socket (grips the J4 pins)", 7.9, 12.8, 16))
    e.append(leader(X_FRONT + 6.5, J1_Z + 3.15, 9.5, 30.4))
    e.append(text("J1, keyed HS3 header", 9.9, 30.3, 16))
    e.append(leader(X_BACK, 17.0, -9.0, 18.8))
    e.append(text("back face: pin names,", -9.4, 19.6, 16, anchor="end"))
    e.append(text("faces the heatsink", -9.4, 18.0, 16, anchor="end"))
    e.append(leader(X_FRONT, 14.8, 7.5, 16.3))
    e.append(text("front face: all parts, faces away from the card", 7.9, 16.1, 16))
    e.append(leader(X_BACK, PULL_Z, -9.0, 29.3))
    e.append(text("pull hole", -9.4, 29.1, 16, anchor="end"))

    # how to handle it
    xm = (X_FRONT + X_BACK) / 2
    e.append(arrow(xm, Z_TOP + 6.0, xm, Z_TOP + 0.6))
    e.append(text("seat it: press here, straight down", xm - 1.5, Z_TOP + 6.6, 16, anchor="end", fill="#b3261e"))
    e.append(text("remove it: lift straight up, adapter and HS3 together", xm + 2.0, Z_TOP + 4.6, 16, fill="#b3261e"))
    e.append(text("never plug or unplug the HS3 or its USB plug while it is on the card", xm + 2.0, Z_TOP + 2.9, 16, fill="#b3261e"))

    # overall height, drawn on the left so it does not cross the HS3
    xd = -6.2
    (ax, ay), (bx, by) = px(xd, 0), px(xd, Z_TOP)
    e.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#333" stroke-width="1"/>')
    for z in (0, Z_TOP):
        (tx, ty) = px(xd, z)
        e.append(f'<line x1="{tx - 6}" y1="{ty}" x2="{tx + 6}" y2="{ty}" stroke="#333" stroke-width="1"/>')
    (mx, my) = px(xd - 0.5, 9.0)
    e.append(f'<text x="{mx:.1f}" y="{my:.1f}" font-family="DejaVu Sans, Arial, sans-serif" font-size="15" '
             f'text-anchor="middle" transform="rotate(-90 {mx:.1f} {my:.1f})">{Z_TOP:.1f} mm above the card</text>')

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="810" viewBox="0 0 1180 810">\n'
           + "\n".join(e) + "\n</svg>\n")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", OUT)
    try:
        subprocess.run(["magick", "-density", "110", OUT, OUT[:-4] + ".png"], check=True)
        print("wrote", OUT[:-4] + ".png")
    except Exception as ex:  # pragma: no cover
        print("png not written:", ex)


if __name__ == "__main__":
    main()
