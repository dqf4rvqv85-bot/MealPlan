"""Auto-generate a weekly meal plan and support per-meal edits."""

import random

from sqlmodel import Session, select

from app.models import MealPlan, MealPlanItem, Recipe


def _all_recipe_ids(session: Session) -> list[int]:
    return list(session.exec(select(Recipe.id)).all())


def current_plan(session: Session) -> MealPlan | None:
    return session.exec(
        select(MealPlan).order_by(MealPlan.created_at.desc())
    ).first()


def generate_plan(
    session: Session, num_meals: int = 7, servings: int = 2, name: str = "Weekly plan"
) -> MealPlan:
    """Create a new plan of up to `num_meals` distinct recipes."""
    ids = _all_recipe_ids(session)
    chosen = random.sample(ids, min(num_meals, len(ids))) if ids else []

    plan = MealPlan(name=name)
    session.add(plan)
    session.flush()
    for slot, rid in enumerate(chosen):
        session.add(
            MealPlanItem(
                meal_plan_id=plan.id, recipe_id=rid, slot=slot, servings=servings
            )
        )
    session.commit()
    session.refresh(plan)
    return plan


def plan_items(session: Session, plan: MealPlan) -> list[tuple[MealPlanItem, Recipe]]:
    items = session.exec(
        select(MealPlanItem)
        .where(MealPlanItem.meal_plan_id == plan.id)
        .order_by(MealPlanItem.slot)
    ).all()
    out: list[tuple[MealPlanItem, Recipe]] = []
    for item in items:
        recipe = session.get(Recipe, item.recipe_id)
        if recipe is not None:
            out.append((item, recipe))
    return out


def swap_item(session: Session, item_id: int) -> tuple[MealPlanItem, Recipe] | None:
    """Replace an item's recipe with a random one not already in the plan."""
    item = session.get(MealPlanItem, item_id)
    if item is None:
        return None
    used = {
        i.recipe_id
        for i in session.exec(
            select(MealPlanItem).where(MealPlanItem.meal_plan_id == item.meal_plan_id)
        ).all()
    }
    candidates = [rid for rid in _all_recipe_ids(session) if rid not in used]
    if candidates:
        item.recipe_id = random.choice(candidates)
        session.add(item)
        session.commit()
        session.refresh(item)
    return item, session.get(Recipe, item.recipe_id)


def set_servings(session: Session, item_id: int, servings: int) -> None:
    item = session.get(MealPlanItem, item_id)
    if item is not None:
        item.servings = max(1, servings)
        session.add(item)
        session.commit()


def remove_item(session: Session, item_id: int) -> int | None:
    """Remove an item; returns the plan id it belonged to."""
    item = session.get(MealPlanItem, item_id)
    if item is None:
        return None
    plan_id = item.meal_plan_id
    session.delete(item)
    session.commit()
    return plan_id
