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
from app.planning.shopping import aggregate
from app.templating import templates

router = APIRouter()


@router.get("/plan", response_class=HTMLResponse)
def plan_page(request: Request, session: Session = Depends(get_session)):
    plan = current_plan(session)
    rows = plan_items(session, plan) if plan else []
    return templates.TemplateResponse(
        request, "plan.html", {"plan": plan, "rows": rows}
    )


@router.post("/plan/generate")
def generate(
    num_meals: int = Form(7),
    servings: int = Form(2),
    session: Session = Depends(get_session),
):
    generate_plan(session, num_meals=max(1, num_meals), servings=max(1, servings))
    return RedirectResponse(url="/plan", status_code=303)


@router.post("/plan/items/{item_id}/swap", response_class=HTMLResponse)
def swap(request: Request, item_id: int, session: Session = Depends(get_session)):
    result = swap_item(session, item_id)
    if result is None:
        return HTMLResponse("", status_code=404)
    item, recipe = result
    return templates.TemplateResponse(
        request, "_plan_row.html", {"item": item, "recipe": recipe}
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
    return templates.TemplateResponse(
        request, "shopping.html", {"plan": plan, "lines": lines}
    )


@router.get("/plan/shopping.csv")
def shopping_csv(session: Session = Depends(get_session)):
    plan = current_plan(session)
    lines = aggregate(session, plan) if plan else []
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["item", "quantity", "unit", "used_in"])
    for line in lines:
        qty = "" if line.quantity is None else round(line.quantity, 2)
        writer.writerow([line.display_name, qty, line.unit or "", "; ".join(line.used_in)])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=shopping_list.csv"},
    )
