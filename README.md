# Meal-Plan to Tesco Shopping Workflow

Local web app: a scanned vegan recipe **PDF → weekly meal plan → Tesco basket**.

The recipe source PDF is committed as `recipes.pdf` (292 image-only scanned pages,
so recipe extraction uses Claude vision rather than text parsing).

## Pipeline

```
recipes.pdf ──rasterize──▶ page PNGs ──Claude vision──▶ recipes + ingredients (SQLite)
                                                              │
                                       auto-generate week ◀───┘  (edit / swap meals)
                                                │
                                  aggregate ingredients ──▶ shopping list (web + CSV)
                                                │
                                    Playwright ──▶ tesco.com/groceries basket
```

## Stack

Python 3.11 · FastAPI + Jinja2 + a little HTMX · SQLite (SQLModel) · PyMuPDF ·
Anthropic SDK (`claude-opus-4-8`) · Playwright (Chromium).

## Setup

```bash
uv venv --python 3.11        # or: python -m venv .venv
uv pip install -e .          # or: .venv/bin/pip install -e .
cp .env.example .env         # then fill in keys (see below)
```

`.env` keys:

| Key | Used for |
|-----|----------|
| `ANTHROPIC_API_KEY` | recipe extraction (Claude vision) |
| `TESCO_EMAIL` / `TESCO_PASSWORD` | Tesco login for the basket step |
| `PDF_PATH` | defaults to `recipes.pdf` |
| `DB_PATH` | defaults to `mealplanner.db` |
| `TESCO_STORAGE_STATE` | saved logged-in Tesco session |

## 1. Extract recipes (one-time, cached)

```bash
python -m scripts.ingest --pages 1-12 --estimate   # token/cost sanity-check first
python -m scripts.ingest --pages 1-12              # extract a small range
python -m scripts.ingest                            # full book (resumes; skips done batches)
```

Extraction is idempotent — already-processed page batches are skipped, and rasterized
pages are cached under `page_cache/`, so re-runs are cheap/free.

**No API key handy?** Seed sample recipes to explore the rest of the app:

```bash
python -m scripts.seed_demo
```

## 2. Run the app

```bash
.venv/bin/uvicorn app.main:app --reload
```

- `/recipes` — browse / search the library
- `/plan` — auto-generate a week, swap or remove meals, set servings
- `/plan/shopping` — consolidated shopping list (scaled to servings) + CSV export
- `/tesco/review` — match items to Tesco products and fill the basket

## 3. Tesco basket

```bash
python -m scripts.tesco_login   # one-time, opens a visible browser for CAPTCHA/2FA
```

Then from `/tesco/review`: **Search Tesco for matches** (caches product matches),
review them, and **Add selected to basket**. Defaults to **dry run** — untick it to
add for real. It never proceeds to checkout; confirm pack quantities in the Tesco
basket yourself (recipe amounts in g/ml/tbsp don't map 1:1 to pack sizes).

> The Tesco automation drives a live third-party site; selectors live in
> `app/tesco/basket.py` and may need updating if Tesco changes their markup.

## Notes

- Chromium is provided by the environment; `app/tesco/basket.py` auto-detects the
  pre-installed build, so you don't need `playwright install`.
- `.env`, the SQLite DB, `page_cache/`, and the Tesco session file are git-ignored.
