import csv
import io

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import Session

from app.db import get_session
from app.planning.generate import (
    current_plan,
    generate_plan,
    plan_items,
    remove_item,
    set_servings,
    swap_item,
)
from app.planning.pantry import set_in_pantry
from app.planning.shopping import aggregate
from app.templating import templates

router = APIRouter()


_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MEALS = ["Breakfast", "Lunch", "Dinner"]


@router.get("/plan", response_class=HTMLResponse)
def plan_page(request: Request, session: Session = Depends(get_session)):
    plan = current_plan(session)
    rows = plan_items(session, plan) if plan else []
    ndays = (max((it.slot for it, _ in rows), default=-1) // len(_MEALS)) + 1
    grid = [[None] * len(_MEALS) for _ in range(ndays)]
    for item, recipe in rows:
        day, meal = divmod(item.slot, len(_MEALS))
        if 0 <= day < ndays and 0 <= meal < len(_MEALS):
            grid[day][meal] = (item, recipe)
    day_labels = [_DAY_NAMES[i] if i < len(_DAY_NAMES) else f"Day {i + 1}"
                  for i in range(ndays)]
    return templates.TemplateResponse(
        request, "plan.html",
        {"plan": plan, "grid": grid, "meals": _MEALS, "day_labels": day_labels},
    )


@router.post("/plan/generate")
def generate(
    days: int = Form(7),
    servings: int = Form(2),
    session: Session = Depends(get_session),
):
    generate_plan(session, days=max(1, days), servings=max(1, servings))
    return RedirectResponse(url="/plan", status_code=303)


@router.post("/plan/items/{item_id}/swap", response_class=HTMLResponse)
def swap(request: Request, item_id: int, session: Session = Depends(get_session)):
    result = swap_item(session, item_id)
    if result is None:
        return HTMLResponse("", status_code=404)
    item, recipe = result
    return templates.TemplateResponse(
        request, "_plan_cell.html", {"item": item, "recipe": recipe}
    )


@router.post("/plan/items/{item_id}/servings", response_class=HTMLResponse)
def servings(
    item_id: int, servings: int = Form(...), session: Session = Depends(get_session)
):
    set_servings(session, item_id, servings)
    return HTMLResponse("", status_code=204)


@router.post("/plan/items/{item_id}/remove", response_class=HTMLResponse)
def remove(item_id: int, session: Session = Depends(get_session)):
    remove_item(session, item_id)
    return HTMLResponse("")  # empty body replaces the row with nothing


@router.get("/plan/shopping", response_class=HTMLResponse)
def shopping(request: Request, session: Session = Depends(get_session)):
    plan = current_plan(session)
    lines = aggregate(session, plan) if plan else []
    buy = [l for l in lines if not l.in_pantry]
    pantry = [l for l in lines if l.in_pantry]
    return templates.TemplateResponse(
        request, "shopping.html", {"plan": plan, "buy": buy, "pantry": pantry}
    )


@router.post("/pantry/toggle")
def pantry_toggle(
    normalized_name: str = Form(...),
    present: bool = Form(False),
    session: Session = Depends(get_session),
):
    set_in_pantry(session, normalized_name, present)
    return RedirectResponse(url="/plan/shopping", status_code=303)


@router.get("/plan/shopping.csv")
def shopping_csv(session: Session = Depends(get_session)):
    plan = current_plan(session)
    lines = aggregate(session, plan) if plan else []
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["item", "quantity", "used_in"])
    for line in lines:
        if line.in_pantry:
            continue  # already stocked — not part of the shop
        writer.writerow(
            [line.display_name, line.quantity_display, "; ".join(line.used_in)]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=shopping_list.csv"},
    )
