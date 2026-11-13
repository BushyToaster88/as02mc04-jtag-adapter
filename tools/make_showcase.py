#!/usr/bin/env python3
"""Render the board from several angles and combine the views into one picture.

Output: docs/img/showcase.png (and the single views in build/showcase/).
Run through tools/render.sh, or directly after sourcing tools/env.sh.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import design as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "hw", D.PROJECT + ".kicad_pcb")
WORK = os.path.join(ROOT, "build", "showcase")
OUT = os.path.join(ROOT, "docs", "img", "showcase.png")
FONT_DIR = "/usr/share/fonts/noto"

# name: (kicad-cli options, width, height)
VIEWS = {
    "front": (["--perspective", "--side", "top", "--rotate", "-40,0,-28", "--zoom", "0.78"], 2400, 2000),
    "back": (["--perspective", "--side", "bottom", "--rotate", "-32,0,-22", "--zoom", "0.78"], 2400, 2000),
    "top": (["--side", "top", "--zoom", "0.85"], 1500, 1800),
    "bottom": (["--side", "bottom", "--zoom", "0.85"], 1500, 1800),
    "edge": (["--side", "front", "--zoom", "0.9"], 2000, 1000),
}


def font(size, bold=False):
    name = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
    path = os.path.join(FONT_DIR, name)
    return ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default()


def render():
    os.makedirs(WORK, exist_ok=True)
    for name, (opts, w, h) in VIEWS.items():
        out = os.path.join(WORK, name + ".png")
        cmd = ["kicad-cli", "pcb", "render", "--quality", "high", "--background", "transparent",
               "-w", str(w), "-h", str(h), "-o", out] + opts + [PCB]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out):
            raise SystemExit(f"render of {name} failed:\n{r.stdout}{r.stderr}")


def view(name):
    """The rendered view, cropped to the board itself (ignoring the faint halo round it)."""
    im = Image.open(os.path.join(WORK, name + ".png")).convert("RGBA")
    solid = im.getchannel("A").point(lambda a: 255 if a > 200 else 0)
    # drop the renderer's faint rectangular halo, keep a soft one-pixel edge on the board itself
    im.putalpha(solid.filter(ImageFilter.GaussianBlur(0.8)))
    box = solid.getbbox()
    if box[0] <= 1 or box[1] <= 1 or box[2] >= im.width - 1 or box[3] >= im.height - 1:
        raise SystemExit(f"the {name} view touches the edge of its render, lower its zoom")
    pad = 30
    box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
    return im.crop(box)


def place(canvas, im, cell, caption, draw):
    """Scale the view into the cell (x, y, w, h), drop a soft shadow under it, caption below."""
    x, y, w, h = cell
    cap_h = 70
    scale = min(w / im.width, (h - cap_h) / im.height)
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    px = x + (w - im.width) // 2
    py = y + (h - cap_h - im.height) // 2
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    mask = im.getchannel("A").point(lambda a: 110 if a > 200 else 0)
    shadow.paste((20, 28, 40, 255), (px + 14, py + 22), mask)
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    canvas.alpha_composite(im, (px, py))
    f = font(34)
    tw = draw.textlength(caption, font=f)
    draw.text((x + (w - tw) / 2, y + h - cap_h + 14), caption, font=f, fill=(70, 78, 92, 255))


def main():
    render()
    W, H = 3600, 2250
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    # soft vertical gradient backdrop
    top, bot = (244, 246, 249), (205, 212, 222)
    grad = Image.new("RGB", (1, H))
    for yy in range(H):
        t = yy / (H - 1)
        grad.putpixel((0, yy), tuple(int(a + (b - a) * t) for a, b in zip(top, bot)))
    canvas.paste(grad.resize((W, H)))
    draw = ImageDraw.Draw(canvas)

    # header
    draw.text((90, 60), "AS02MC04 JTAG adapter", font=font(92, True), fill=(24, 32, 46, 255))
    draw.text((92, 178), "for the Digilent JTAG-HS3", font=font(52), fill=(60, 70, 86, 255))
    info = f"Rev {D.REV}   |   24.0 x 29.55 mm   |   2 layers   |   1.8 V JTAG"
    f = font(40)
    draw.text((W - 90 - draw.textlength(info, font=f), 84), info, font=f, fill=(60, 70, 86, 255))
    f = font(58, True)
    web = "www.exulan.com"
    draw.text((W - 90 - draw.textlength(web, font=f), 150), web, font=f, fill=(20, 90, 60, 255))
    draw.line([(90, 268), (W - 90, 268)], fill=(170, 180, 194, 255), width=3)

    y0 = 300
    body = H - y0 - 40
    place(canvas, view("front"), (60, y0, 1560, body), "Front: HS3 header, limiter resistor, reverse protection, socket for the card", draw)
    place(canvas, view("back"), (1640, y0, 1180, int(body * 0.62)), "Back: pin names and warnings", draw)
    place(canvas, view("edge"), (1640, y0 + int(body * 0.62), 1180, body - int(body * 0.62)),
          "Socket end: plugs onto the card's 6-pin JTAG header", draw)
    place(canvas, view("top"), (2840, y0, 700, body // 2), "Front, straight on", draw)
    place(canvas, view("bottom"), (2840, y0 + body // 2, 700, body - body // 2), "Back, straight on", draw)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    canvas.convert("RGB").save(OUT, optimize=True)
    print("wrote", OUT, canvas.size)


if __name__ == "__main__":
    main()
