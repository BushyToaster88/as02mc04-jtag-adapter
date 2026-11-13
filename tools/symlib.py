"""Load symbols from the stock KiCad symbol libraries and flatten derived ones.

A schematic embeds a flattened copy of every library symbol it uses. Derived
symbols (those with an "extends" clause) take their graphics and pins from the
parent and their properties from the child.
"""
import math
import os
import re
from functools import lru_cache

from sexp import children, find_block, first_string, head_of

SYMBOL_DIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")


@lru_cache(maxsize=None)
def _lib_text(lib: str) -> str:
    with open(os.path.join(SYMBOL_DIR, lib + ".kicad_sym"), encoding="utf-8") as f:
        return f.read()


def _raw_symbol(lib: str, name: str) -> str:
    text = _lib_text(lib)
    m = re.search(r'\n\t\(symbol "' + re.escape(name) + r'"\s', text)
    if not m:
        raise KeyError(f"{lib}:{name} not found")
    start = m.start() + 2
    return text[start:find_block(text, start)]


def load(lib: str, name: str) -> str:
    """Return the flattened symbol block named 'lib:name' ready for lib_symbols."""
    raw = _raw_symbol(lib, name)
    _, kids = children(raw)
    ext = [k for k in kids if head_of(k) == "extends"]
    if ext:
        parent = first_string(ext[0])
        praw = _raw_symbol(lib, parent)
        _, pkids = children(praw)
        own_props = [k for k in kids if head_of(k) == "property"]
        own_names = {first_string(k) for k in own_props}
        out = []
        for k in pkids:
            h = head_of(k)
            if h == "property":
                if first_string(k) not in own_names:
                    out.append(k)
            elif h == "symbol":
                out.append(k.replace(f'(symbol "{parent}_', f'(symbol "{name}_', 1))
            elif h == "extends":
                raise ValueError("multi-level extends not handled")
            else:
                out.append(k)
        # child properties go where the parent's properties were
        idx = next((i for i, k in enumerate(out) if head_of(k) in ("property", "symbol")), len(out))
        kids = out[:idx] + own_props + out[idx:]
    body = "\n\t\t".join(kids)
    return f'(symbol "{lib}:{name}"\n\t\t{body}\n\t)'


def pins(symbol_block: str):
    """Return [dict(number, name, x, y, angle, length, etype, unit)] for a flattened symbol."""
    res = []
    _, kids = children(symbol_block)
    for k in kids:
        if head_of(k) != "symbol":
            continue
        sub = first_string(k)
        m = re.search(r"_(\d+)_(\d+)$", sub)
        unit = int(m.group(1)) if m else 0
        _, skids = children(k)
        for p in skids:
            if head_of(p) != "pin":
                continue
            head, pk = children(p)
            etype = head.split()[1]
            at = next(x for x in pk if head_of(x) == "at")
            nums = at[1:-1].split()[1:]
            x, y = float(nums[0]), float(nums[1])
            ang = float(nums[2]) if len(nums) > 2 else 0.0
            length = float(next(x for x in pk if head_of(x) == "length")[1:-1].split()[1])
            name = first_string(next(x for x in pk if head_of(x) == "name"))
            number = first_string(next(x for x in pk if head_of(x) == "number"))
            res.append(dict(number=number, name=name, x=x, y=y, angle=ang, length=length, etype=etype, unit=unit))
    return res


def pin_end(pin, sx, sy, rot=0):
    """Schematic coordinates of a pin's connection point for a symbol placed at
    (sx, sy) with rotation rot (degrees, counter-clockwise on screen).

    Library symbols have Y up, the schematic sheet has Y down.
    """
    a = math.radians(rot)
    x = pin["x"] * math.cos(a) - pin["y"] * math.sin(a)
    y = pin["x"] * math.sin(a) + pin["y"] * math.cos(a)
    return round(sx + x, 4), round(sy - y, 4)


def pin_out_dir(pin, rot=0):
    """Unit vector (schematic coordinates) pointing away from the symbol body."""
    a = math.radians(pin["angle"] + 180 + rot)
    return round(math.cos(a)), round(-math.sin(a))
