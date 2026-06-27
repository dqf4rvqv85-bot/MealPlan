"""Orchestrates rasterize -> Claude vision -> persist, idempotently."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session, select

from app.config import ROOT, settings
from app.db import engine
from app.extraction.extract import (
    ParsedRecipe,
    count_batch_tokens,
    extract_batch,
)
from app.extraction.rasterize import page_count, render_page_cached
from app.models import ExtractionLog, Ingredient, Recipe
from app.normalize import normalize_name, normalize_title

CACHE_DIR = ROOT / "page_cache"


def build_batches(start: int, stop: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """Return [start, end) 0-based page windows with `overlap` shared pages."""
    step = max(1, size - overlap)
    batches: list[tuple[int, int]] = []
    i = start
    while i < stop:
        end = min(i + size, stop)
        batches.append((i, end))
        if end >= stop:
            break
        i += step
    return batches


@dataclass
class IngestSummary:
    batches_processed: int = 0
    batches_skipped: int = 0
    recipes_added: int = 0
    estimated_input_tokens: int = 0
    notes: list[str] = field(default_factory=list)


def _persist_recipe(
    session: Session, parsed: ParsedRecipe, page_start: int, page_end: int
) -> None:
    recipe = Recipe(
        title=parsed.title.strip(),
        servings=parsed.servings,
        meal_type=parsed.meal_type,
        source_page_start=page_start + 1,  # store 1-based for humans
        source_page_end=page_end,
        steps_json=json.dumps(parsed.steps),
        raw_json=parsed.model_dump_json(),
    )
    session.add(recipe)
    session.flush()  # assign recipe.id
    for ing in parsed.ingredients:
        session.add(
            Ingredient(
                recipe_id=recipe.id,
                raw_text=ing.raw_text,
                name=ing.name,
                normalized_name=normalize_name(ing.name),
                quantity=ing.quantity,
                unit=ing.unit,
            )
        )


def run_extraction(
    page_from: int = 1,
    page_to: int | None = None,
    limit_batches: int | None = None,
    estimate_only: bool = False,
) -> IngestSummary:
    """Extract recipes from pages [page_from, page_to] (1-based, inclusive)."""
    pdf_path = settings.resolve(settings.pdf_path)
    total = page_count(pdf_path)
    start0 = max(0, page_from - 1)
    stop0 = total if page_to is None else min(total, page_to)
    batches = build_batches(
        start0, stop0, settings.extraction_batch_size, settings.extraction_overlap
    )
    if limit_batches is not None:
        batches = batches[:limit_batches]

    summary = IngestSummary()
    with Session(engine) as session:
        seen_titles: set[str] = {
            normalize_title(t)
            for t in session.exec(select(Recipe.title)).all()
        }

        for idx, (b_start, b_end) in enumerate(batches):
            is_last = idx == len(batches) - 1

            already = session.exec(
                select(ExtractionLog).where(
                    ExtractionLog.page_start == b_start,
                    ExtractionLog.page_end == b_end,
                )
            ).first()
            if already is not None and not estimate_only:
                summary.batches_skipped += 1
                continue

            images = [
                render_page_cached(pdf_path, p, CACHE_DIR)
                for p in range(b_start, b_end)
            ]

            if estimate_only:
                summary.estimated_input_tokens += count_batch_tokens(images, b_start)
                summary.batches_processed += 1
                continue

            result = extract_batch(images, b_start)
            added_here = 0
            for parsed in result.recipes:
                if parsed.continues_past_batch and not is_last:
                    continue  # captured fully by the next overlapping batch
                key = normalize_title(parsed.title)
                if not key or key in seen_titles:
                    continue
                seen_titles.add(key)
                _persist_recipe(session, parsed, b_start, b_end)
                added_here += 1

            session.add(
                ExtractionLog(
                    page_start=b_start, page_end=b_end, recipes_found=added_here
                )
            )
            session.commit()
            summary.recipes_added += added_here
            summary.batches_processed += 1

    return summary
