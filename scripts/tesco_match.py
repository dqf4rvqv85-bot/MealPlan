"""Search Tesco for each shopping-list item and cache candidate products.

Needs your debug Chrome running and signed in (see scripts/tesco_login.py).
Searches every non-pantry item in the current plan that isn't already confirmed,
applying dairy/egg substitutions, and stores the top candidates for the confirm
UI at /tesco/match. Read-only — never touches the basket.

    python -m scripts.tesco_match
"""

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import ProductCandidate, TescoMatch
from app.planning.generate import current_plan
from app.planning.shopping import aggregate
from app.tesco.basket import TescoConnectError, TescoSession
from app.tesco.substitutions import to_search_term


def main() -> None:
    init_db()
    with Session(engine) as s:
        plan = current_plan(s)
        if plan is None:
            print("No meal plan yet — generate one first.")
            return
        lines = [l for l in aggregate(s, plan) if not l.in_pantry]
        confirmed = {
            m.normalized_name
            for m in s.exec(select(TescoMatch).where(TescoMatch.verified == True)).all()  # noqa: E712
        }
        todo = [l for l in lines if l.normalized_name not in confirmed]
        print(f"{len(todo)} of {len(lines)} items to search "
              f"({len(confirmed)} already confirmed).")

        try:
            with TescoSession() as sess:
                for i, line in enumerate(todo, 1):
                    term = to_search_term(line.normalized_name)
                    cands = sess.candidates(term, n=5)
                    # replace any old candidates for this ingredient
                    for old in s.exec(
                        select(ProductCandidate).where(
                            ProductCandidate.normalized_name == line.normalized_name
                        )
                    ).all():
                        s.delete(old)
                    for rank, c in enumerate(cands):
                        s.add(ProductCandidate(
                            normalized_name=line.normalized_name, rank=rank,
                            product_id=c.product_id, title=c.title,
                            url=c.url, price=c.price,
                        ))
                    s.commit()
                    sub = f" (as '{term}')" if term != line.normalized_name else ""
                    top = cands[0].title[:42] if cands else "NO RESULTS"
                    print(f"  [{i}/{len(todo)}] {line.display_name}{sub}: {top}")
        except TescoConnectError as exc:
            print(f"\n{exc}")
            return
    print("\nDone. Review and confirm matches at /tesco/match")


if __name__ == "__main__":
    main()
