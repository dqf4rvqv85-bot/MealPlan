from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from app.db import get_session
from app.models import ProductCandidate, TescoMatch
from app.planning.generate import current_plan
from app.planning.shopping import aggregate
from app.tesco.basket import TescoConnectError, TescoSession, search_url
from app.tesco.packs import packs_for
from app.tesco.substitutions import to_search_term
from app.templating import templates

router = APIRouter()


def _needs_by_name(lines) -> dict[str, list]:
    out: dict[str, list] = {}
    for line in lines:
        out.setdefault(line.normalized_name, []).append((line.quantity, line.group_unit))
    return out


def _confirmed_matches(session: Session) -> dict[str, TescoMatch]:
    return {
        m.normalized_name: m
        for m in session.exec(
            select(TescoMatch).where(TescoMatch.verified == True)  # noqa: E712
        ).all()
    }


def _buy_lines(session: Session):
    plan = current_plan(session)
    lines = aggregate(session, plan) if plan else []
    return plan, [l for l in lines if not l.in_pantry]


def _match_context(session: Session, request: Request, **extra) -> dict:
    plan, lines = _buy_lines(session)
    confirmed = _confirmed_matches(session)
    needs = _needs_by_name(lines)
    rows = []
    for line in lines:
        cands = session.exec(
            select(ProductCandidate)
            .where(ProductCandidate.normalized_name == line.normalized_name)
            .order_by(ProductCandidate.rank)
        ).all()
        term = to_search_term(line.normalized_name)
        match = confirmed.get(line.normalized_name)
        packs = (
            packs_for(match.product_title or "", needs.get(line.normalized_name, []))
            if match else 1
        )
        rows.append(
            {
                "line": line,
                "candidates": cands,
                "confirmed": match,
                "packs": packs,
                "search_term": term,
                "search_link": search_url(term),
                "substituted": term != line.normalized_name,
            }
        )
    have_candidates = any(r["candidates"] for r in rows)
    unmatched = [r for r in rows if not r["confirmed"]]
    return {
        "request": request,
        "plan": plan,
        "rows": rows,
        "unmatched": unmatched,
        "n_confirmed": sum(1 for r in rows if r["confirmed"]),
        "have_candidates": have_candidates,
        **extra,
    }


@router.get("/tesco/match", response_class=HTMLResponse)
def match(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "tesco_match.html", _match_context(session, request)
    )


@router.get("/tesco/review", response_class=HTMLResponse)
def review(request: Request, session: Session = Depends(get_session)):
    """Manual fallback: a checklist with per-item Tesco search links."""
    _, lines = _buy_lines(session)
    plan = current_plan(session)
    rows = [{"line": l, "search_link": search_url(to_search_term(l.normalized_name))}
            for l in lines]
    return templates.TemplateResponse(
        request, "tesco_review.html", {"request": request, "plan": plan, "rows": rows}
    )


@router.post("/tesco/match/confirm")
async def confirm(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    for key, value in form.multi_items():
        if not key.startswith("pick::"):
            continue
        name = key[len("pick::"):]
        existing = session.exec(
            select(TescoMatch).where(TescoMatch.normalized_name == name)
        ).first()
        if not value:  # "skip" — drop any existing match
            if existing:
                session.delete(existing)
            continue
        cand = session.exec(
            select(ProductCandidate).where(
                ProductCandidate.normalized_name == name,
                ProductCandidate.product_id == value,
            )
        ).first()
        term = to_search_term(name)
        match = existing or TescoMatch(normalized_name=name)
        match.search_term = term
        match.tesco_product_id = value
        match.product_url = cand.url if cand else None
        match.product_title = cand.title if cand else None
        match.pack_note = cand.price if cand else None
        match.verified = True
        session.add(match)
    session.commit()
    return RedirectResponse(url="/tesco/match", status_code=303)


@router.post("/tesco/add")
async def add(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    dry_run = form.get("dry_run") == "on"
    _, lines = _buy_lines(session)
    names = {l.normalized_name for l in lines}
    needs = _needs_by_name(lines)
    matches = [
        m
        for m in _confirmed_matches(session).values()
        if m.normalized_name in names and m.tesco_product_id
    ]
    # how many packs of each to add
    plan_packs = [
        (m, packs_for(m.product_title or "", needs.get(m.normalized_name, [])))
        for m in matches
    ]

    error = None
    results = []
    if not matches:
        error = "No confirmed matches to add — pick products and Save first."
    elif dry_run:
        results = [
            {"title": m.product_title or m.normalized_name, "ok": True,
             "detail": f"dry-run — would add {packs} pack(s)"}
            for m, packs in plan_packs
        ]
    else:
        def _run():
            out = []
            with TescoSession() as s:
                for m, packs in plan_packs:
                    ok, detail = s.add_chosen(
                        m.search_term or to_search_term(m.normalized_name),
                        m.tesco_product_id, packs,
                    )
                    out.append({"title": m.product_title or m.normalized_name,
                                "ok": ok, "detail": detail})
            return out

        try:
            results = await run_in_threadpool(_run)
        except TescoConnectError as exc:
            error = str(exc)
        except Exception as exc:  # pragma: no cover - live site failure
            error = f"Tesco basket update failed: {exc}"

    add_failed = [r["title"] for r in results if not r["ok"]]
    ctx = _match_context(session, request, error=error, results=results,
                         was_dry_run=dry_run, add_failed=add_failed)
    return templates.TemplateResponse(request, "tesco_match.html", ctx)
