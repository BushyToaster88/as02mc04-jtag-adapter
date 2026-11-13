#!/usr/bin/env python3
"""Make a printable 1:1 gauge for checking the pin pitch of both connectors:
the card header J4 (1x6) and the plug of the Digilent HS3 (2x7).

Output: docs/pitch_gauge.svg and docs/pitch_gauge.pdf (A4, real millimetres).
Print at 100 % ("actual size", no "fit to page"), check the 100 mm bar with a ruler,
then hold each connector against its rows of marks.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "docs", "pitch_gauge.svg")
PDF = os.path.join(ROOT, "docs", "pitch_gauge.pdf")

W, H = 210.0, 297.0          # A4, millimetres
FONT = "DejaVu Sans, Arial, sans-serif"


def t(s, x, y, size=3.6, anchor="start", weight="normal", fill="#000"):
    return (f'<text x="{x:.3f}" y="{y:.3f}" font-family="{FONT}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}" fill="{fill}">{s}</text>')


def line(x1, y1, x2, y2, w=0.2, color="#000", dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{color}" stroke-width="{w}"{d}/>'


def dim(x0, x1, y, label, e):
    e.append(line(x0, y, x1, y, 0.15))
    e.append(line(x0, y - 1, x0, y + 1, 0.15))
    e.append(line(x1, y - 1, x1, y + 1, 0.15))
    e.append(t(label, x1 + 2.5, y + 1.2, 3.2))


def comb(x0, y, pitch, pin, title, note, left, right, e):
    """One row of six square marks (the card's pins seen end on)."""
    span = 5 * pitch
    e.append(t(title, x0, y - 11.5, 4.4, weight="bold"))
    e.append(t(note, x0, y - 7.2, 3.3))
    for i in range(6):
        x = x0 + i * pitch
        e.append(f'<rect x="{x - pin / 2:.3f}" y="{y - pin / 2:.3f}" width="{pin}" height="{pin}" fill="#000"/>')
        e.append(line(x, y - 4.2, x, y + 4.2, 0.1))
    e.append(t(left, x0 - 1.5, y + 7.4, 2.8, anchor="end"))
    e.append(t(right, x0 + span + 1.5, y + 7.4, 2.8))
    e.append(line(x0 - 12, y, x0 + span + 12, y, 0.1, "#888", "1.2 0.8"))
    e.append(t("optional: cut along the dashed line and hold the paper edge against the pins",
               x0 + span + 14, y + 1.1, 2.8, fill="#555"))
    dim(x0, x0 + span, y + 11.5, f"{span:.2f} mm between the centres of the two end pins", e)


def grid(x0, y, pitch, hole, title, note, e, outline=None):
    """Two rows of seven round marks (the holes in the HS3 plug)."""
    span = 6 * pitch
    e.append(t(title, x0, y - 10.5, 4.4, weight="bold"))
    e.append(t(note, x0, y - 6.2, 3.3))
    if outline:
        ow, oh = outline
        cx, cy = x0 + span / 2, y + pitch / 2
        e.append(f'<rect x="{cx - ow / 2:.3f}" y="{cy - oh / 2:.3f}" width="{ow}" height="{oh}" fill="none" '
                 f'stroke="#888" stroke-width="0.15" stroke-dasharray="1 0.6"/>')
    for r in range(2):
        for i in range(7):
            x, yy = x0 + i * pitch, y + r * pitch
            e.append(f'<circle cx="{x:.3f}" cy="{yy:.3f}" r="{hole / 2}" fill="#000"/>')
    for i in (0, 6):
        e.append(line(x0 + i * pitch, y - 3.2, x0 + i * pitch, y + pitch + 3.2, 0.1))
    dim(x0, x0 + span, y + pitch + 7.0, f"{span:.2f} mm between the first and last hole of a row, "
                                         f"rows {pitch:.2f} mm apart", e)


def main():
    e = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff"/>']
    e.append(t("Pin pitch gauge: card header J4 and the Digilent HS3 plug", 18, 20, 6.0, weight="bold"))
    e.append(t("Print at 100 % (actual size). Do not use fit to page.", 18, 27, 4.2))

    # ---- calibration bar
    y = 43
    e.append(t("Step 1. Check the print scale: this bar must measure exactly 100 mm.", 18, y - 6.5, 4.0, weight="bold"))
    e.append(line(18, y, 118, y, 0.3))
    for i in range(0, 101, 10):
        h = 3.0 if i % 50 == 0 else 1.8
        e.append(line(18 + i, y - h, 18 + i, y + h, 0.25))
        e.append(t(str(i), 18 + i, y + 7.2, 2.8, anchor="middle"))
    e.append(t("If it is not 100 mm the printer rescaled the page. Reprint before trusting the marks below.", 18, y + 12.5, 3.3))

    # ---- card header J4
    e.append(t("Step 2. Card header J4 (six pins in a row). Lay the pins on each row. Only one row will match.",
               18, 68, 4.0, weight="bold"))
    comb(38, 92, 2.54, 0.64, "Row A: 2.54 mm pitch",
         "What the adapter is built for. All six pins should sit on the six black squares.", "GND end", "1V8 end", e)
    comb(38, 126, 2.00, 0.50, "Row B: 2.00 mm pitch",
         "If the pins match this row instead, stop: the adapter's socket will not fit. Do not order.",
         "GND end", "1V8 end", e)

    # ---- HS3 plug
    e.append(t("Step 3. HS3 plug (two rows of seven holes). Hold the end of the HS3 against each pattern.",
               18, 152, 4.0, weight="bold"))
    grid(38, 174, 2.00, 0.7, "Pattern C: 2.00 mm pitch",
         "What the adapter is built for. All fourteen holes should sit on the fourteen dots.", e,
         outline=(16.65, 6.30))
    e.append(t("dashed box: outside of the adapter's header, 16.65 x 6.30 mm. The HS3 plug goes inside it.",
               38, 189.5, 2.8, fill="#555"))
    grid(38, 210, 2.54, 0.9, "Pattern D: 2.54 mm pitch",
         "If the holes match this pattern instead, stop: this is not the Xilinx 2 mm plug. Do not order.", e)

    # ---- without a printer
    y = 235
    e.append(t("Without a printer", 18, y, 4.4, weight="bold"))
    rows = [
        ("Card header J4, centre of pin 1 to centre of pin 6", "12.70 mm = correct", "10.00 mm = wrong"),
        ("Card header J4, outside faces of the two end pins (calipers)", "13.3 mm = correct", "10.5 mm = wrong"),
        ("HS3 plug, centre of the first hole to centre of the seventh in a row", "12.00 mm = correct", "15.24 mm = wrong"),
        ("HS3 plug, centre of one row to centre of the other", "2.00 mm = correct", "2.54 mm = wrong"),
    ]
    for i, (what, good, bad) in enumerate(rows):
        yy = y + 7 + i * 5.6
        e.append(t(what, 18, yy, 3.3))
        e.append(t(good, 128, yy, 3.3, weight="bold"))
        e.append(t(bad, 166, yy, 3.3))
    e.append(t("Fit test for J4: a standard 0.1 inch jumper wire housing is 2.54 mm wide. Six side by side, or one 1x6 housing,",
               18, y + 31.5, 3.3))
    e.append(t("should slide onto all six pins without spreading apart or bending a pin.", 18, y + 36.3, 3.3))
    e.append(t("The pin at the 1V8 end of J4 is slightly bent on some cards. Straighten it gently before measuring.",
               18, y + 43.5, 3.3))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">\n'
           + "\n".join(e) + "\n</svg>\n")
    with open(SVG, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", SVG)
    subprocess.run(["inkscape", SVG, "--export-type=pdf", f"--export-filename={PDF}"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote", PDF)
    # the numbers quoted on the sheet
    print(f"J4  2.54 pitch: centre span {5 * 2.54:.2f} mm, outside faces {5 * 2.54 + 0.64:.2f} mm")
    print(f"J4  2.00 pitch: centre span {5 * 2.00:.2f} mm, outside faces {5 * 2.00 + 0.50:.2f} mm")
    print(f"HS3 2.00 pitch: row span {6 * 2.00:.2f} mm;  2.54 pitch: row span {6 * 2.54:.2f} mm")


if __name__ == "__main__":
    main()
