import re

# Descriptor words that don't help identify the ingredient for aggregation/search.
_DESCRIPTORS = {
    "fresh", "freshly", "finely", "roughly", "coarsely", "chopped", "diced",
    "sliced", "minced", "grated", "crushed", "ground", "peeled", "cooked",
    "raw", "ripe", "large", "small", "medium", "extra", "organic", "free",
    "range", "skinless", "boneless", "drained", "rinsed", "optional", "to",
    "taste", "for", "garnish", "serving", "plus", "more", "a", "an", "of",
    "good", "quality", "warm", "cold", "hot", "dried", "frozen", "tinned",
    "canned", "whole", "halved", "quartered", "deseeded", "trimmed",
}

_TITLE_WS = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^a-z0-9\s]")


def normalize_title(title: str) -> str:
    """Canonical key for de-duplicating recipes across overlapping batches."""
    return _TITLE_WS.sub(" ", title.strip().lower())


def normalize_name(name: str) -> str:
    """Canonical ingredient key for aggregation and Tesco search.

    Lowercases, strips punctuation and common descriptor words, collapses
    whitespace. Intentionally simple and rule-based; refine later.
    """
    text = _NON_WORD.sub(" ", name.lower())
    tokens = [
        t for t in text.split()
        if t and not t.isdigit() and t not in _DESCRIPTORS
    ]
    return " ".join(tokens).strip() or name.strip().lower()
