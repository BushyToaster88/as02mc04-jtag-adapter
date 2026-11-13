"""Thin helpers over KiCad's pcbnew Python API (KiCad 10) for building a board from a script."""
import math
import os

import pcbnew

mm = pcbnew.FromMM
to_mm = pcbnew.ToMM

FP_DIR = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
LAYER = {
    "F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu,
    "F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS,
    "F.Mask": pcbnew.F_Mask, "B.Mask": pcbnew.B_Mask,
    "F.Paste": pcbnew.F_Paste, "B.Paste": pcbnew.B_Paste,
    "F.Fab": pcbnew.F_Fab, "B.Fab": pcbnew.B_Fab,
    "F.CrtYd": pcbnew.F_CrtYd, "B.CrtYd": pcbnew.B_CrtYd,
    "Edge.Cuts": pcbnew.Edge_Cuts, "Dwgs.User": pcbnew.Dwgs_User, "Cmts.User": pcbnew.Cmts_User,
}


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


class Board:
    """A board under construction. All coordinates are millimetres in KiCad's frame (Y down)."""

    def __init__(self, path, origin=(100.0, 100.0)):
        if os.path.exists(path):
            os.remove(path)
        self.path = path
        self.b = pcbnew.NewBoard(path)
        self.ox, self.oy = origin
        self.nets = {}
        self.fps = {}

    # coordinates: user gives board-local (x right, y down from the top-left corner of the outline)
    def pt(self, x, y):
        return P(self.ox + x, self.oy + y)

    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def footprint(self, ref, lib_id, x, y, rot=0.0, value="", libdir=None, fields=None):
        lib, name = lib_id.split(":")
        d = libdir or os.path.join(FP_DIR, lib + ".pretty")
        fp = pcbnew.FootprintLoad(d, name)
        if fp is None:
            raise RuntimeError(f"footprint {lib_id} not found in {d}")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(value)
        self.b.Add(fp)
        fp.SetPosition(self.pt(x, y))
        fp.SetOrientationDegrees(rot)
        for k, v in (fields or {}).items():
            fp.SetField(k, v)
            f = fp.GetField(k)
            if f is not None:
                f.SetVisible(False)
        self.fps[ref] = fp
        return fp

    def pad(self, ref, num):
        for p in self.fps[ref].Pads():
            if p.GetNumber() == str(num):
                return p
        raise KeyError(f"{ref}.{num}")

    def pad_xy(self, ref, num):
        """Pad centre in board-local millimetres."""
        pos = self.pad(ref, num).GetPosition()
        return to_mm(pos.x) - self.ox, to_mm(pos.y) - self.oy

    def assign(self, ref, num, netname):
        for p in self.fps[ref].Pads():
            if p.GetNumber() == str(num):
                p.SetNet(self.net(netname))

    def track(self, netname, pts, width=0.25, layer="F.Cu"):
        out = []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
                continue
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(self.pt(x1, y1))
            t.SetEnd(self.pt(x2, y2))
            t.SetWidth(mm(width))
            t.SetLayer(LAYER[layer])
            t.SetNet(self.net(netname))
            self.b.Add(t)
            out.append(t)
        return out

    def via(self, netname, x, y, dia=0.6, drill=0.3):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(self.pt(x, y))
        v.SetDrill(mm(drill))
        v.SetWidth(pcbnew.F_Cu, mm(dia))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.net(netname))
        self.b.Add(v)
        return v

    def zone(self, netname, layer, poly, clearance=0.25, min_width=0.25, thermal=True, priority=0, name=""):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(LAYER[layer])
        z.SetNet(self.net(netname))
        o = z.Outline()
        o.NewOutline()
        for x, y in poly:
            o.Append(mm(self.ox + x), mm(self.oy + y))
        z.SetMinThickness(mm(min_width))
        z.SetLocalClearance(mm(clearance))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
        z.SetThermalReliefGap(mm(0.25))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(priority)
        if name:
            z.SetZoneName(name)
        self.b.Add(z)
        return z

    def keepout(self, layer, poly, name="", tracks=True, vias=True, pads=False, copper=True, footprints=False):
        z = pcbnew.ZONE(self.b)
        z.SetIsRuleArea(True)
        z.SetLayer(LAYER[layer])
        o = z.Outline()
        o.NewOutline()
        for x, y in poly:
            o.Append(mm(self.ox + x), mm(self.oy + y))
        z.SetDoNotAllowTracks(tracks)
        z.SetDoNotAllowVias(vias)
        z.SetDoNotAllowPads(pads)
        z.SetDoNotAllowZoneFills(copper)
        z.SetDoNotAllowFootprints(footprints)
        if name:
            z.SetZoneName(name)
        self.b.Add(z)
        return z

    def line(self, x1, y1, x2, y2, layer="Edge.Cuts", width=0.1):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(self.pt(x1, y1))
        s.SetEnd(self.pt(x2, y2))
        s.SetLayer(LAYER[layer])
        s.SetWidth(mm(width))
        self.b.Add(s)
        return s

    def arc(self, cx, cy, r, a0, a1, layer="Edge.Cuts", width=0.1):
        """Arc centred (cx, cy) from angle a0 to a1 (degrees, KiCad frame: 0 = +x, 90 = +y which is down)."""
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        am = (a0 + a1) / 2.0
        pt = lambda a: self.pt(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
        s.SetArcGeometry(pt(a0), pt(am), pt(a1))
        s.SetLayer(LAYER[layer])
        s.SetWidth(mm(width))
        self.b.Add(s)
        return s

    def circle(self, cx, cy, r, layer, width=0.12, fill=False):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_CIRCLE)
        s.SetCenter(self.pt(cx, cy))
        s.SetEnd(self.pt(cx + r, cy))
        s.SetLayer(LAYER[layer])
        s.SetWidth(mm(width))
        if fill:
            s.SetFilled(True)
        self.b.Add(s)
        return s

    def poly(self, pts, layer, width=0.0, fill=True):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_POLY)
        s.SetPolyPoints([self.pt(x, y) for x, y in pts])
        s.SetLayer(LAYER[layer])
        s.SetWidth(mm(width))
        s.SetFilled(fill)
        self.b.Add(s)
        return s

    def rounded_outline(self, w, h, r, layer="Edge.Cuts", width=0.1):
        self.line(r, 0, w - r, 0, layer, width)
        self.line(w, r, w, h - r, layer, width)
        self.line(w - r, h, r, h, layer, width)
        self.line(0, h - r, 0, r, layer, width)
        self.arc(r, r, r, 180, 270, layer, width)
        self.arc(w - r, r, r, 270, 360, layer, width)
        self.arc(w - r, h - r, r, 0, 90, layer, width)
        self.arc(r, h - r, r, 90, 180, layer, width)

    def text(self, s, x, y, layer="F.SilkS", size=1.0, thickness=0.15, rot=0.0, justify="center", mirror=None, bold=False,
             width=None):
        """size is the character height. width (default: same as size) can be made smaller for a condensed label."""
        t = pcbnew.PCB_TEXT(self.b)
        t.SetText(s)
        t.SetPosition(self.pt(x, y))
        t.SetLayer(LAYER[layer])
        t.SetTextSize(pcbnew.VECTOR2I(mm(size if width is None else width), mm(size)))
        t.SetTextThickness(mm(thickness))
        t.SetTextAngleDegrees(rot)
        if bold:
            t.SetBold(True)
        hj = {"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "center": pcbnew.GR_TEXT_H_ALIGN_CENTER,
              "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT}[justify]
        t.SetHorizJustify(hj)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        back = layer.startswith("B.") if mirror is None else mirror
        t.SetMirrored(back)
        self.b.Add(t)
        return t

    def fill_zones(self):
        pcbnew.ZONE_FILLER(self.b).Fill(self.b.Zones())

    def save(self):
        pcbnew.SaveBoard(self.path, self.b)
