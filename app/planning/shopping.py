"""Aggregate plan ingredients into a consolidated, buyable shopping list."""

from collections import Counter
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models import Ingredient, MealPlan, MealPlanItem, Recipe
from app.planning.pantry import ensure_seeded, get_pantry
from app.units import format_amount, group_for


@dataclass
class ShoppingLine:
    normalized_name: str
    display_name: str
    group_unit: str  # canonical bucket: 'g', 'ml', 'cup~', or a discrete unit
    quantity: float | None  # in group_unit; None => "as needed"
    approximate: bool = False  # quantity came from a density/volume estimate
    in_pantry: bool = False  # user already keeps this stocked
    used_in: list[str] = field(default_factory=list)

    @property
    def quantity_display(self) -> str:
        return format_amount(self.group_unit, self.quantity, self.approximate)


def aggregate(session: Session, plan: MealPlan) -> list[ShoppingLine]:
    ensure_seeded(session)
    pantry = get_pantry(session)
    items = session.exec(
        select(MealPlanItem).where(MealPlanItem.meal_plan_id == plan.id)
    ).all()

    # key = (normalized_name, group_unit) -> accumulators
    qty: dict[tuple[str, str], float | None] = {}
    names: dict[tuple[str, str], Counter] = {}
    used: dict[tuple[str, str], set[str]] = {}
    approx: dict[tuple[str, str], bool] = {}

    for item in items:
        recipe = session.get(Recipe, item.recipe_id)
        if recipe is None:
            continue
        factor = (item.servings / recipe.servings) if recipe.servings else 1.0
        ingredients = session.exec(
            select(Ingredient).where(Ingredient.recipe_id == recipe.id)
        ).all()
        for ing in ingredients:
            group_unit, amount, is_approx = group_for(
                ing.normalized_name, ing.quantity, ing.unit
            )
            key = (ing.normalized_name, group_unit)
            names.setdefault(key, Counter())[ing.name] += 1
            used.setdefault(key, set()).add(recipe.title)
            approx[key] = approx.get(key, False) or is_approx
            if amount is not None:
                scaled = amount * factor
                cur = qty.get(key)
                qty[key] = scaled if cur is None else (cur or 0.0) + scaled
            else:
                qty.setdefault(key, None)

    lines: list[ShoppingLine] = []
    for (norm, group_unit), name_counter in names.items():
        lines.append(
            ShoppingLine(
                normalized_name=norm,
                display_name=name_counter.most_common(1)[0][0],
                group_unit=group_unit,
                quantity=qty.get((norm, group_unit)),
                approximate=approx[(norm, group_unit)],
                in_pantry=norm in pantry,
                used_in=sorted(used[(norm, group_unit)]),
            )
        )
    lines.sort(key=lambda x: x.display_name.lower())
    return lines
