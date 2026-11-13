"""Small helpers for KiCad S-expression text.

KiCad files are S-expressions. These helpers work on the text level so that
blocks copied out of the stock libraries keep their exact content.
"""
import uuid

NS = uuid.UUID("6f1d2c4e-8a53-4b57-9d0e-a502c04a1e01")


def uid(key: str) -> str:
    """Deterministic UUID so regenerated files stay stable."""
    return str(uuid.uuid5(NS, key))


def q(s) -> str:
    """Quote a string for an S-expression."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def fmt(v: float) -> str:
    """Format a number the way KiCad does (no trailing zeros)."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def find_block(text: str, start: int) -> int:
    """Return the index just past the ')' that closes the '(' at text[start]."""
    assert text[start] == "("
    depth = 0
    i = start
    in_str = False
    n = len(text)
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise ValueError("unbalanced S-expression")


def children(block: str):
    """Split '(head a b (c ...) (d ...))' into (head_text, [child blocks])."""
    assert block[0] == "(" and block[-1] == ")"
    inner = block[1:-1]
    kids = []
    i = 0
    n = len(inner)
    head_end = None
    in_str = False
    while i < n:
        c = inner[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if c == "(":
            if head_end is None:
                head_end = i
            end = find_block(inner, i)
            kids.append(inner[i:end])
            i = end
            continue
        i += 1
    head = inner if head_end is None else inner[:head_end]
    return head.strip(), kids


def head_of(block: str) -> str:
    """First token of a block, e.g. 'symbol' for '(symbol "R" ...)'."""
    i = 1
    while i < len(block) and block[i] not in " \t\r\n()":
        i += 1
    return block[1:i]


def first_string(block: str) -> str:
    """First quoted string in a block (its name)."""
    a = block.index('"')
    b = a + 1
    while block[b] != '"':
        if block[b] == "\\":
            b += 1
        b += 1
    return block[a + 1:b]
