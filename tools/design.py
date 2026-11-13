"""Single source of truth for the AS02MC04 JTAG to HS3 adapter.

Both the schematic generator and the board generator read this file, and the
checker compares what KiCad exports against it.

Revision C of the circuit (after two design reviews):
  * one card-side connector (J2). It plugs straight onto card header J4, or takes
    a 6-way male-to-female jumper cable.
  * R9 limits what a fault behind it can draw from the card's 1.8 V rail to about
    0.38 A. It is a 0.75 W part, so a dead short (0.69 W) makes it hot instead of
    burning it out: a thermal model (not a measurement) gives roughly 105 to 145 C
    at room temperature against a limit of 155 C, and more at the top of the rail
    tolerance or in a warm case. Only J2 pin 1, the 2 mm link and R9's own input
    pad are ahead of it. Every other piece of 1.8 V copper is behind the limiter.
  * The ground pour is held 0.5 mm back from J2 pin 1 (and the link) and from J2
    pin 6, the two hand-soldered pins where a solder bridge to the pour would
    bypass R9 or Q1.
  * R7 is 10k rather than 100k. With the socket reversed and only half seated,
    the few microamps the LED passes lift Q1's gate; 10k leaves it about 0.1 V
    lower than 100k did, so at worst Q1 passes a small current until the socket
    is fully on.
  * Q1 sits in the ground lead and blocks a reversed 6-pin connection.
  * D2 glows (dimly, it only has 1.8 V) when the 6-pin connection is reversed.
  * TP1..TP6 are unpopulated holes for a scope or logic analyzer.
"""

PROJECT = "as02mc04_jtag_hs3"
TITLE = "AS02MC04 JTAG adapter for Digilent JTAG-HS3"
REV = "C"
DATE = "2026-11-11"

R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
TP_FP = "as02mc04:TestHole_D1.7mm_Drill1.0mm"


def _r(value, lcsc, mpn, desc):
    return dict(sym="Device:R", value=value, fp=R0603, lcsc=lcsc, mpn=mpn, mfr="UNI-ROYAL", desc=desc)


def _tp(value, desc):
    # unpopulated plated hole: not in the BOM, not in the placement file
    return dict(sym="Connector:TestPoint", value=value, fp=TP_FP, lcsc="", mpn="", mfr="", desc=desc, fit=False)


# ref -> component description
#   sym:   KiCad library symbol
#   fp:    KiCad footprint (library:name)
#   lcsc:  JLCPCB / LCSC part number used for assembly
#   fit:   False for footprints that carry no part
COMPONENTS = {
    "J1": dict(sym="Connector_Generic:Conn_02x07_Odd_Even", value="HS3 2x7 2.00mm",
               fp="Connector_Molex_Milligrid:Molex_8783214xx_2x07_P2.0mm_Header_Vertical_Polarized_MountingPegs",
               lcsc="C492354", mpn="87832-1420", mfr="Molex",
               desc="Xilinx 14-pin JTAG header, shrouded and keyed, mates with Digilent JTAG-HS3"),
    "J2": dict(sym="Connector_Generic:Conn_01x06", value="J4 socket 1x6 2.54mm RA",
               fp="as02mc04:Socket_1x06_P2.54mm_RA_J4order",
               lcsc="C54876735", mpn="PM2.54-1x6PWZ-H8.5", mfr="SHOU HAN",
               desc="Right-angle female socket, plugs straight onto card header J4 (pin n meets J4 pin n)"),
    "R1": _r("22R", "C23345", "0603WAF220JT5E", "TMS series resistor"),
    "R2": _r("22R", "C23345", "0603WAF220JT5E", "TCK series resistor"),
    "R3": _r("22R", "C23345", "0603WAF220JT5E", "TDO series resistor"),
    "R4": _r("22R", "C23345", "0603WAF220JT5E", "TDI series resistor"),
    "R5": _r("1k", "C21190", "0603WAF1001T5E", "Q1 gate resistor"),
    "R7": _r("10k", "C25804", "0603WAF1002T5E", "VREF bleeder, also holds Q1's gate low when nothing drives VREF"),
    "R8": _r("33R", "C23140", "0603WAF330JT5E", "D2 current limit"),
    "R9": dict(sym="Device:R", value="4R7 0.75W", fp=R1206, lcsc="C313986", mpn="CRCW12064R70FKEAHP", mfr="Vishay",
               desc="Limits fault and inrush current from the card's 1.8 V rail to 0.38 A. "
                    "High-power 1206, rated 0.75 W; a dead short puts 0.69 W into it, so it runs hot"),
    "R10": _r("1M", "C22935", "0603WAF1004T5E", "Bleeds static between adapter ground and card ground"),
    "C1": dict(sym="Device:C", value="1uF", fp=C0603, lcsc="C15849",
               mpn="CL10A105KB8NNNC", mfr="Samsung", desc="VREF decoupling"),
    "C2": dict(sym="Device:C", value="100nF", fp=C0603, lcsc="C14663",
               mpn="CC0603KRX7R9BB104", mfr="YAGEO", desc="VREF decoupling"),
    "D2": dict(sym="Device:LED", value="RED REVERSED", fp="LED_SMD:LED_0603_1608Metric", lcsc="C2286",
               mpn="KT-0603R", mfr="Hubei KENTO",
               desc="Glows when the 6-pin connection to the card is reversed"),
    "Q1": dict(sym="Transistor_FET:AO3400A", value="DMN1019USN", fp="Package_TO_SOT_SMD:SC-59", lcsc="C145103",
               mpn="DMN1019USN-7", mfr="Diodes Incorporated",
               desc="Reverse-insertion protection in the ground lead, fully on at 1.5 V gate drive"),
    "TP1": _tp("GND", "Adapter ground for a scope or logic analyzer"),
    "TP2": _tp("TDI", "TDI at the card connector"),
    "TP3": _tp("TDO", "TDO at the card connector"),
    "TP4": _tp("TCK", "TCK at the card connector"),
    "TP5": _tp("TMS", "TMS at the card connector"),
    "TP6": _tp("VREF", "HS3 reference voltage (card 1V8 after R9)"),
}

# net -> list of "REF.PIN"
NETS = {
    # card 1.8 V exactly as it arrives on J4 pin 1. Nothing but the limiter is on this net.
    "VREF_T": ["J2.1", "R9.1"],
    # the same rail behind the 4.7 ohm limiter: feeds the HS3 buffers, the gate of Q1 and the cathode of D2
    "VREF": ["R9.2", "J1.2", "C1.1", "C2.1", "R7.1", "TP6.1", "R5.1", "D2.1"],
    "GND": ["J1.1", "J1.3", "J1.5", "J1.7", "J1.9", "J1.11", "J1.13",
            "C1.2", "C2.2", "R7.2", "Q1.2", "R10.2", "TP1.1"],
    # card ground exactly as it arrives on J4 pin 6, ahead of Q1
    "GND_T": ["J2.6", "Q1.3", "R8.1", "R10.1"],
    "Q1_G": ["R5.2", "Q1.1"],
    "D2_A": ["R8.2", "D2.2"],
    "TMS_H": ["J1.4", "R1.1"],
    "TCK_H": ["J1.6", "R2.1"],
    "TDO_H": ["J1.8", "R3.1"],
    "TDI_H": ["J1.10", "R4.1"],
    "TMS_T": ["R1.2", "J2.2", "TP5.1"],
    "TCK_T": ["R2.2", "J2.3", "TP4.1"],
    "TDO_T": ["R3.2", "J2.4", "TP3.1"],
    "TDI_T": ["R4.2", "J2.5", "TP2.1"],
}

# pins deliberately left unconnected
NO_CONNECT = ["J1.12", "J1.14"]

# Card header J4, for documentation and checks: pin -> (silk label on the card, adapter net)
J4 = {
    1: ("1V8", "VREF_T"),
    2: ("TMS", "TMS_T"),
    3: ("TDK", "TCK_T"),
    4: ("TDO", "TDO_T"),
    5: ("TDI", "TDI_T"),
    6: ("GND", "GND_T"),
}

# Digilent JTAG-HS3 / Xilinx 14-pin header: pin -> (function, adapter net)
HS3 = {
    1: ("GND", "GND"), 2: ("VREF", "VREF"), 3: ("GND", "GND"), 4: ("TMS", "TMS_H"),
    5: ("GND", "GND"), 6: ("TCK", "TCK_H"), 7: ("GND", "GND"), 8: ("TDO", "TDO_H"),
    9: ("GND", "GND"), 10: ("TDI", "TDI_H"), 11: ("GND", "GND"), 12: ("NC", None),
    13: ("GND", "GND"), 14: ("SRST", None),
}

# which series resistor joins each HS3-side net to its card-side net
SERIES = {"TMS": "R1", "TCK": "R2", "TDO": "R3", "TDI": "R4", "VREF": "R9"}


def fitted(ref):
    return COMPONENTS[ref].get("fit", True)


def pin_net():
    """Return {"REF.PIN": net} and check that no pin is used twice."""
    m = {}
    for net, pins in NETS.items():
        for p in pins:
            assert p not in m, f"{p} is in both {m[p]} and {net}"
            assert p.split(".")[0] in COMPONENTS, f"{p} names an unknown component"
            m[p] = net
    for p in NO_CONNECT:
        assert p not in m, f"{p} is marked no-connect but is on {m[p]}"
    return m
