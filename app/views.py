import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, func, select

from app.db import get_session
from app.models import Ingredient, Recipe
from app.templating import templates

router = APIRouter()


@router.get("/recipes", response_class=HTMLResponse)
def library(request: Request, q: str | None = None, session: Session = Depends(get_session)):
    total = session.exec(select(func.count()).select_from(Recipe)).one()
    stmt = select(Recipe).order_by(Recipe.title)
    if q:
        stmt = stmt.where(Recipe.title.ilike(f"%{q}%"))
    recipes = session.exec(stmt).all()
    return templates.TemplateResponse(
        request,
        "library.html",
        {"recipes": recipes, "total": total, "q": q},
    )


@router.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(request: Request, recipe_id: int, session: Session = Depends(get_session)):
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        return HTMLResponse("<h1>Recipe not found</h1>", status_code=404)
    ingredients = session.exec(
        select(Ingredient).where(Ingredient.recipe_id == recipe_id)
    ).all()
    steps = json.loads(recipe.steps_json or "[]")
    return templates.TemplateResponse(
        request,
        "recipe.html",
        {"recipe": recipe, "ingredients": ingredients, "steps": steps},
    )
