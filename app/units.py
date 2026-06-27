"""Consolidate recipe ingredient amounts into buyable quantities.

Recipe measures in this book are a mix of US volume (cup/tbsp/tsp), mass (g/kg),
and discrete counts (clove, tin, head, ...). For a shopping list we want one line
per ingredient, in a unit you can actually buy:

- mass units            -> grams (kg if large)
- known dry staples in volume -> grams via a per-cup density table (approx)
- known liquids in volume     -> millilitres (litres if large)
- other volume (fresh veg)    -> kept as a cooking volume (cups/tbsp), approximate
- discrete units              -> left as-is, summed per unit

Densities are approximate and only cover common staples; conversions derived
from them are flagged approximate so the UI can mark them.
"""

# millilitres per US volume unit
_VOLUME_ML = {
    "tsp": 5.0, "teaspoon": 5.0, "teaspoons": 5.0,
    "tbsp": 15.0, "tablespoon": 15.0, "tablespoons": 15.0,
    "cup": 240.0, "cups": 240.0,
    "ml": 1.0, "l": 1000.0, "litre": 1000.0, "liter": 1000.0,
}

# grams per mass unit
_MASS_G = {
    "g": 1.0, "gram": 1.0, "grams": 1.0,
    "kg": 1000.0, "oz": 28.35, "lb": 453.6, "pound": 453.6,
}

# Approximate grams per US cup for common dry staples (singularized names).
CUP_GRAMS = {
    "oat": 90, "oat flour": 120, "flour": 120, "plain flour": 120,
    "chickpea flour": 120, "self raising flour": 120, "wholemeal flour": 120,
    "rice": 185, "basmati rice": 185, "sushi rice": 185, "white rice": 185,
    "brown rice": 185, "quinoa": 170,
    "red lentil": 200, "lentil": 200, "green lentil": 200,
    "sugar": 200, "brown sugar": 220, "caster sugar": 200, "icing sugar": 120,
    "chickpea": 240, "black bean": 240, "kidney bean": 240, "butter bean": 240,
    "cashew": 130, "almond": 140, "peanut": 145, "walnut": 120,
    "nutritional yeast": 60, "cacao powder": 100, "cocoa powder": 100,
    "peanut butter powder": 60, "desiccated coconut": 80, "chia seed": 170,
    "blueberry": 150, "strawberry": 150, "raspberry": 125, "mixed berry": 150,
    "sweetcorn": 165, "corn": 165, "pea": 145,
}

# Cup/spoon-measured ingredients that are really liquids -> buy by ml.
LIQUID_NAMES = {
    "water", "plant milk", "unsweetened plant milk", "soy milk", "almond milk",
    "oat milk", "coconut milk", "orange juice", "juice", "apple juice",
    "vegetable stock", "stock", "vegetable broth", "broth", "plant cream",
    "soy sauce", "tamari", "maple syrup", "agave", "agave syrup", "oil",
    "olive oil", "vegetable oil", "sesame oil", "vinegar", "apple cider vinegar",
    "rice vinegar", "lemon juice", "lime juice", "passata", "vegan yoghurt",
    "unsweetened vegan yoghurt", "yoghurt", "plant yoghurt",
}


def _num(x: float) -> str:
    """Trim a float for display: 4 -> '4', 2.5 -> '2.5', 0.33 -> '0.33'."""
    r = round(x, 2)
    return str(int(r)) if r == int(r) else str(r)


def group_for(name: str, quantity: float | None, unit: str | None):
    """Map one ingredient amount to (group_unit, quantity_in_group, approximate).

    `group_unit` is the canonical bucket we accumulate the ingredient in
    ('g', 'ml', a cooking-volume bucket 'cup~', or a discrete unit string).
    Ingredients with the same (name, group_unit) sum together.
    """
    u = (unit or "").lower().strip()

    if quantity is None:
        return (u, None, False)  # unquantified -> "as needed", keyed by raw unit

    if u in _MASS_G:
        return ("g", quantity * _MASS_G[u], False)

    if u in _VOLUME_ML:
        ml = quantity * _VOLUME_ML[u]
        grams_per_cup = CUP_GRAMS.get(name)
        if grams_per_cup:                       # dry staple -> buyable grams
            return ("g", ml * grams_per_cup / 240.0, True)
        if name in LIQUID_NAMES:                # liquid -> buyable ml
            return ("ml", ml, False)
        return ("cup~", ml, True)               # fresh/unknown -> keep volume

    # discrete / non-convertible units (clove, tin, head, sheet, none, ...)
    return (u, quantity, False)


def format_amount(group_unit: str, quantity: float | None, approximate: bool) -> str:
    """Human-readable buyable quantity for a consolidated shopping line."""
    if quantity is None:
        return "as needed"
    pre = "~" if approximate else ""

    if group_unit == "g":
        if quantity >= 1000:
            return f"{pre}{_num(quantity / 1000)} kg"
        return f"{pre}{_num(round(quantity))} g"

    if group_unit == "ml":
        if quantity >= 1000:
            return f"{pre}{_num(quantity / 1000)} L"
        return f"{pre}{_num(round(quantity))} ml"

    if group_unit == "cup~":  # fresh/unknown volume -> show in cooking units
        if quantity >= 120:
            return f"{pre}{_num(quantity / 240)} cups"
        if quantity >= 10:
            return f"{pre}{_num(quantity / 15)} tbsp"
        return f"{pre}{_num(quantity / 5)} tsp"

    # discrete unit
    return f"{_num(quantity)} {group_unit}".strip()
