#!/usr/bin/env python3
"""Print pads and outline extents of a KiCad footprint: fpinfo.py LIBDIR NAME [...]"""
import sys
import pcbnew


def info(libdir, name):
    fp = pcbnew.FootprintLoad(libdir, name)
    print(f"== {name}  attrs={fp.GetAttributes()}")
    for p in fp.Pads():
        pos = p.GetPosition()
        sz = p.GetSize(pcbnew.F_Cu) if hasattr(p, "GetSize") else None
        try:
            dr = p.GetDrillSize()
            drill = f"drill {pcbnew.ToMM(dr.x):g}x{pcbnew.ToMM(dr.y):g}"
        except Exception:
            drill = ""
        print(f"   pad {p.GetNumber() or '-':>3} at ({pcbnew.ToMM(pos.x):8.3f},{pcbnew.ToMM(pos.y):8.3f}) "
              f"size {pcbnew.ToMM(sz.x):.3f}x{pcbnew.ToMM(sz.y):.3f} {drill} attr={p.GetAttribute()} shape={p.GetShape(pcbnew.F_Cu)}")
    ext = {}
    for g in fp.GraphicalItems():
        layer = g.GetLayerName()
        bb = g.GetBoundingBox()
        e = ext.setdefault(layer, [1e9, 1e9, -1e9, -1e9])
        e[0] = min(e[0], pcbnew.ToMM(bb.GetLeft())); e[1] = min(e[1], pcbnew.ToMM(bb.GetTop()))
        e[2] = max(e[2], pcbnew.ToMM(bb.GetRight())); e[3] = max(e[3], pcbnew.ToMM(bb.GetBottom()))
    for layer, e in ext.items():
        print(f"   {layer:10} x {e[0]:8.3f} .. {e[2]:8.3f}   y {e[1]:8.3f} .. {e[3]:8.3f}")
    for m in fp.Models():
        print("   model", m.m_Filename)


if __name__ == "__main__":
    a = sys.argv[1:]
    for i in range(0, len(a), 2):
        info(a[i], a[i + 1])
