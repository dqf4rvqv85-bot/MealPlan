"""The user's pantry: staples they keep stocked, excluded from the shop list.

Persisted in the PantryItem table and editable per shop (toggle items in/out on
the shopping page). Seeded once with common staples so the first list is already
trimmed; everything is then adjustable.
"""

from sqlmodel import Session, select

from app.models import PantryItem

# Sensible defaults (singularized normalized names) seeded on first use.
DEFAULT_PANTRY = {
    "salt", "black pepper", "pepper", "water", "oil", "olive oil",
    "vegetable oil", "sesame oil", "cooking spray", "baking powder",
    "baking soda", "bicarbonate of soda", "vanilla", "vanilla extract",
    "cinnamon", "turmeric", "cumin", "paprika", "smoked paprika",
    "garlic powder", "onion powder", "chilli powder", "chilli flake",
    "curry powder", "mixed herb", "oregano", "thyme", "ground ginger",
    "nutmeg", "cornflour", "corn starch", "plain flour", "flour",
    "sugar", "brown sugar", "soy sauce", "maple syrup",
}


def ensure_seeded(session: Session) -> None:
    """Populate the pantry with defaults the first time it's empty."""
    if session.exec(select(PantryItem)).first() is None:
        for name in sorted(DEFAULT_PANTRY):
            session.add(PantryItem(normalized_name=name))
        session.commit()


def get_pantry(session: Session) -> set[str]:
    return {p.normalized_name for p in session.exec(select(PantryItem)).all()}


def set_in_pantry(session: Session, normalized_name: str, present: bool) -> None:
    """Add or remove one ingredient from the pantry."""
    existing = session.exec(
        select(PantryItem).where(PantryItem.normalized_name == normalized_name)
    ).first()
    if present and existing is None:
        session.add(PantryItem(normalized_name=normalized_name))
        session.commit()
    elif not present and existing is not None:
        session.delete(existing)
        session.commit()
