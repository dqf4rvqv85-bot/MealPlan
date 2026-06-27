"""Aggregate plan ingredients into a consolidated shopping list."""

from collections import Counter
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models import Ingredient, MealPlan, MealPlanItem, Recipe


@dataclass
class ShoppingLine:
    normalized_name: str
    display_name: str
    unit: str | None
    quantity: float | None  # None => "as needed" (no numeric quantities seen)
    used_in: list[str] = field(default_factory=list)

    @property
    def quantity_display(self) -> str:
        if self.quantity is None:
            return "as needed"
        q = round(self.quantity, 2)
        q = int(q) if q == int(q) else q
        return f"{q} {self.unit}".strip() if self.unit else str(q)


def aggregate(session: Session, plan: MealPlan) -> list[ShoppingLine]:
    items = session.exec(
        select(MealPlanItem).where(MealPlanItem.meal_plan_id == plan.id)
    ).all()

    # group key -> accumulator
    qty: dict[tuple[str, str], float | None] = {}
    names: dict[tuple[str, str], Counter] = {}
    used: dict[tuple[str, str], set[str]] = {}

    for item in items:
        recipe = session.get(Recipe, item.recipe_id)
        if recipe is None:
            continue
        factor = (item.servings / recipe.servings) if recipe.servings else 1.0
        ingredients = session.exec(
            select(Ingredient).where(Ingredient.recipe_id == recipe.id)
        ).all()
        for ing in ingredients:
            key = (ing.normalized_name, ing.unit or "")
            names.setdefault(key, Counter())[ing.name] += 1
            used.setdefault(key, set()).add(recipe.title)
            if ing.quantity is not None:
                scaled = ing.quantity * factor
                cur = qty.get(key)
                qty[key] = scaled if cur is None else cur + scaled
            else:
                qty.setdefault(key, None)

    lines: list[ShoppingLine] = []
    for (norm, unit), name_counter in names.items():
        lines.append(
            ShoppingLine(
                normalized_name=norm,
                display_name=name_counter.most_common(1)[0][0],
                unit=unit or None,
                quantity=qty.get((norm, unit)),
                used_in=sorted(used[(norm, unit)]),
            )
        )
    lines.sort(key=lambda x: x.display_name.lower())
    return lines
