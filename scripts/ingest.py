"""One-time (idempotent) recipe extraction CLI.

Examples:
    python -m scripts.ingest --pages 1-12          # extract a small range
    python -m scripts.ingest --pages 1-12 --estimate   # token/cost estimate only
    python -m scripts.ingest                        # full book (resumes; skips done batches)
"""

import argparse

from app.db import init_db
from app.extraction.pipeline import run_extraction


def _parse_pages(value: str | None) -> tuple[int, int | None]:
    if not value:
        return 1, None
    if "-" in value:
        lo, hi = value.split("-", 1)
        return int(lo), int(hi)
    n = int(value)
    return n, n


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract recipes from the cookbook PDF.")
    ap.add_argument("--pages", help="1-based page range, e.g. '1-12' or '5'")
    ap.add_argument("--limit-batches", type=int, default=None)
    ap.add_argument(
        "--estimate",
        action="store_true",
        help="Only count input tokens (no extraction / no DB writes).",
    )
    args = ap.parse_args()

    init_db()
    page_from, page_to = _parse_pages(args.pages)
    summary = run_extraction(
        page_from=page_from,
        page_to=page_to,
        limit_batches=args.limit_batches,
        estimate_only=args.estimate,
    )

    print(f"batches processed: {summary.batches_processed}")
    print(f"batches skipped (already done): {summary.batches_skipped}")
    if args.estimate:
        toks = summary.estimated_input_tokens
        # claude-opus-4-8 input is $5 / 1M tokens
        print(f"estimated input tokens: {toks:,}")
        print(f"  ~= ${toks / 1_000_000 * 5:.2f} input (output billed separately)")
    else:
        print(f"recipes added: {summary.recipes_added}")
    for note in summary.notes:
        print(f"note: {note}")


if __name__ == "__main__":
    main()
