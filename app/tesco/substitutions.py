"""Map a recipe ingredient to the Tesco SEARCH TERM to use.

The user isn't vegan — they're trying the recipes — so the book's dairy and egg
substitutes are swapped to conventional equivalents before searching Tesco
(plant milk -> milk, vegan yoghurt -> natural yoghurt, ...). Tofu, tempeh, vegan
meat substitutes, nutritional yeast, etc. are searched as written. Matching is
exact on the normalized name (so 'butter bean' and 'peanut butter powder' are
never mistaken for butter). Per-item overrides happen in the confirm UI.
"""

SUBSTITUTIONS = {
    # plant milks -> dairy milk
    "plant milk": "milk",
    "unsweetened plant milk": "milk",
    "unsweetened plant based milk": "milk",
    "plant based milk": "milk",
    "soy milk": "milk",
    "almond milk": "milk",
    "oat milk": "milk",
    "rice milk": "milk",
    # vegan yoghurts -> natural (plain, unsweetened) yoghurt
    "unsweetened vegan yoghurt": "natural yoghurt",
    "vegan unsweetened yoghurt": "natural yoghurt",
    "vegan unsweetened yogurt": "natural yoghurt",
    "plant based yoghurt": "natural yoghurt",
    "vegan soy yogurt": "natural yoghurt",
    "soy yoghurt": "natural yoghurt",
    "vegan yoghurt": "natural yoghurt",
    "vegan yogurt": "natural yoghurt",
    # vegan cheese -> cheese
    "vegan cheese sauce": "cheese sauce",
    "low fat cheese sauce": "cheese sauce",
    "vegan mozzarella": "mozzarella",
    "vegan cheese": "cheese",
    "vegan cheddar": "cheddar",
    "vegan parmesan": "parmesan",
    # vegan chocolate -> chocolate
    "dark vegan chocolate chip": "dark chocolate chips",
    "vegan dark chocolate chip": "dark chocolate chips",
    "vegan chocolate chip": "chocolate chips",
    "vegan dark chocolate": "dark chocolate",
    "dark vegan chocolate": "dark chocolate",
    "vegan chocolate": "chocolate",
    # vegan butter / cream / mayo (not in current data but common)
    "vegan butter": "butter",
    "plant butter": "butter",
    "dairy free butter": "butter",
    "vegan cream": "single cream",
    "plant cream": "single cream",
    "dairy free cream": "single cream",
    "vegan mayo": "mayonnaise",
    "vegan mayonnaise": "mayonnaise",
    # egg replacers -> eggs
    "flax egg": "eggs",
    "chia egg": "eggs",
    "egg replacer": "eggs",
    "egg substitute": "eggs",
    "vegan egg": "eggs",
}


def to_search_term(normalized_name: str) -> str:
    """The Tesco query for an ingredient (conventional swap if applicable)."""
    return SUBSTITUTIONS.get(normalized_name, normalized_name)


def is_substituted(normalized_name: str) -> bool:
    return normalized_name in SUBSTITUTIONS
