from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from app.db import get_session
from app.models import TescoMatch
from app.planning.generate import current_plan
from app.planning.shopping import aggregate
from app.tesco.basket import add_to_basket, search_terms, search_url
from app.templating import templates

router = APIRouter()


def _matches_by_name(session: Session) -> dict[str, TescoMatch]:
    return {m.normalized_name: m for m in session.exec(select(TescoMatch)).all()}


def _review_context(session: Session, request: Request, **extra) -> dict:
    plan = current_plan(session)
    lines = aggregate(session, plan) if plan else []
    lines = [l for l in lines if not l.in_pantry]  # skip staples you already have
    matches = _matches_by_name(session)
    rows = []
    for i, line in enumerate(lines):
        rows.append(
            {
                "i": i,
                "line": line,
                "match": matches.get(line.normalized_name),
                "search_link": search_url(line.display_name),
            }
        )
    return {"request": request, "plan": plan, "rows": rows, **extra}


@router.get("/tesco/review", response_class=HTMLResponse)
def review(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "tesco_review.html", _review_context(session, request)
    )


@router.post("/tesco/search")
async def search(request: Request, session: Session = Depends(get_session)):
    plan = current_plan(session)
    if plan is None:
        return RedirectResponse(url="/plan", status_code=303)
    lines = aggregate(session, plan)
    existing = _matches_by_name(session)
    # only search items we don't already have a cached match for
    todo = [l for l in lines if l.normalized_name not in existing]
    error = None
    try:
        results = await run_in_threadpool(
            search_terms, [l.display_name for l in todo]
        )
        for line, res in zip(todo, results):
            session.add(
                TescoMatch(
                    normalized_name=line.normalized_name,
                    search_term=line.display_name,
                    tesco_product_id=res.product_id,
                    product_url=res.url,
                    product_title=res.title,
                    pack_note=res.price,
                    verified=res.found,
                )
            )
        session.commit()
    except Exception as exc:  # browser/site/login failure — surface it
        error = f"Tesco search failed: {exc}"

    ctx = _review_context(session, request, error=error)
    return templates.TemplateResponse(request, "tesco_review.html", ctx)


@router.post("/tesco/add")
async def add(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    dry_run = form.get("dry_run") == "on"
    included = form.getlist("include")  # list of row indices as strings

    items: list[tuple[str, str, int]] = []
    for idx in included:
        url = form.get(f"url_{idx}")
        term = form.get(f"term_{idx}") or ""
        if not url:
            continue
        try:
            qty = max(1, int(form.get(f"qty_{idx}", "1")))
        except ValueError:
            qty = 1
        items.append((term, url, qty))

    error = None
    results = []
    if not items:
        error = "No matched items selected."
    else:
        try:
            results = await run_in_threadpool(add_to_basket, items, dry_run)
        except Exception as exc:
            error = f"Tesco basket update failed: {exc}"

    ctx = _review_context(session, request, error=error, results=results, was_dry_run=dry_run)
    return templates.TemplateResponse(request, "tesco_review.html", ctx)
