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
    # prep/qualifier words seen in this book's ingredient names
    "pre", "baked", "precooked", "prebaked", "pitted", "and", "mashed",
    "softened", "melted", "drizzle", "splash", "pinch", "handful",
}

_TITLE_WS = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^a-z0-9\s]")
# Everything from the first comma or '(' onward is prep detail, not the item.
_AFTER_DETAIL = re.compile(r"[,(].*$", re.S)

# Words ending in 's' that are already singular — never strip their 's'.
_UNCOUNTABLE = {
    "hummus", "molasses", "couscous", "asparagus", "watercress", "cos",
    "swiss", "houmous",
}


def _singularize(word: str) -> str:
    """Best-effort singular of one token, so 'bananas' keys with 'banana'.

    Only used to build the merge key; the human-facing display name keeps the
    ingredient's original wording, so an odd key (e.g. 'oat') is harmless.
    """
    if word in _UNCOUNTABLE or len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"  # berries -> berry
    if word.endswith("oes"):
        return word[:-2]  # tomatoes -> tomato
    if word.endswith(("ss", "us", "is", "os")):
        return word  # glass, hummus, basis
    if word.endswith("s"):
        return word[:-1]  # bananas -> banana, lentils -> lentil
    return word


def normalize_title(title: str) -> str:
    """Canonical key for de-duplicating recipes across overlapping batches."""
    return _TITLE_WS.sub(" ", title.strip().lower())


def normalize_name(name: str) -> str:
    """Canonical ingredient key for aggregation and Tesco search.

    Drops prep detail after a comma or parenthesis, lowercases, strips
    punctuation and common descriptor words, collapses whitespace.
    Intentionally simple and rule-based; refine later.
    """
    base = _AFTER_DETAIL.sub("", name.lower())
    text = _NON_WORD.sub(" ", base)
    tokens = [
        t for t in text.split()
        if t and not t.isdigit() and t not in _DESCRIPTORS
    ]
    if tokens:
        tokens[-1] = _singularize(tokens[-1])  # singularize the head noun
    return " ".join(tokens).strip() or name.strip().lower()
