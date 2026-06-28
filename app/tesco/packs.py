"""Work out how many Tesco packs to buy for a needed quantity.

Parses the pack size out of a product title (e.g. "... 1kg", "... 400G",
"... 6 Pack", "... 2.272L") and divides the quantity needed by it. Units must
match (count vs grams vs millilitres); on any mismatch or unparseable title we
fall back to 1 pack — the user reviews the basket anyway.
"""

import math
import re

_WEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g)\b", re.I)
_VOLUME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(litres?|liters?|l|ml|cl)\b", re.I)
_PACK_RE = re.compile(r"(\d+)\s*(?:pack|pk|pieces|ct|sachets|cobettes|bags)\b", re.I)
_PACKOF_RE = re.compile(r"pack of\s*(\d+)", re.I)
_MULTI_RE = re.compile(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l|cl)\b", re.I)


def parse_pack_size(title: str) -> tuple[float | None, str | None]:
    """Return (size, dim) with dim in {'count','g','ml'}, or (None, None)."""
    if not title:
        return None, None
    t = title.lower()

    # "6 x 7g" style multipacks -> total in g or ml
    m = _MULTI_RE.search(t)
    if m:
        n, v, u = int(m.group(1)), float(m.group(2)), m.group(3)
        if u in ("g", "kg"):
            return (n * v * (1000 if u == "kg" else 1), "g")
        ml = v * (1000 if u == "l" else 10 if u == "cl" else 1)
        return (n * ml, "ml")

    if "twin pack" in t:
        return (2, "count")
    m = _PACK_RE.search(t) or _PACKOF_RE.search(t)
    if m:
        return (float(m.group(1)), "count")

    m = _WEIGHT_RE.search(t)
    if m:
        v = float(m.group(1))
        return (v * 1000 if m.group(2).lower() == "kg" else v, "g")

    m = _VOLUME_RE.search(t)
    if m:
        v, u = float(m.group(1)), m.group(2).lower()
        ml = v * 1000 if u in ("l", "litre", "litres", "liter", "liters") else (
            v * 10 if u == "cl" else v
        )
        return (ml, "ml")

    return None, None


# map a shopping line's group_unit to a pack dimension
_DIM = {"": "count", "g": "g", "ml": "ml"}


def packs_for(title: str, needs: list[tuple[float | None, str]]) -> int:
    """Packs to buy for `needs` (list of (quantity, group_unit)) of one product."""
    size, dim = parse_pack_size(title or "")
    if not size or size <= 0:
        return 1
    best = 1
    for qty, group_unit in needs:
        if qty is None:
            continue
        if _DIM.get(group_unit) == dim:
            best = max(best, math.ceil(qty / size - 1e-9))
    return max(1, best)
