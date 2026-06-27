"""Claude vision extraction of structured recipes from rendered page images."""

import base64
from typing import Optional

import anthropic
from pydantic import BaseModel

from app.config import settings

_EXTRACTION_PROMPT = (
    "These are consecutive scanned pages from a vegan cookbook. "
    "Extract every COMPLETE recipe visible across the images.\n\n"
    "For each recipe return:\n"
    "- title: the recipe name as printed.\n"
    "- servings: the number of servings. In this book it is shown as a row of "
    "small FILLED circles/dots immediately after the word 'Serves' — count the "
    "filled dots and return that integer (e.g. three filled dots = 3, one "
    "filled dot = 1). If a plain number is printed instead, use it. Only use "
    "null if there is no dot indicator and no printed number at all.\n"
    "- meal_type: one of breakfast, lunch, dinner, dessert, snack, side, "
    "drink, sauce, or null if unclear.\n"
    "- nutrition: the per-serving values printed in the small footer line, e.g. "
    "'Calories - 558, Protein - 22.8g, Fat - 80.9g, Carbs - 9.5g'. Return "
    "calories, protein_g, fat_g and carbs_g as plain numbers (grams without the "
    "'g' suffix). Use null for any value not shown.\n"
    "- ingredients: each with:\n"
    "    - raw_text: exactly as printed (keep quantities and notes).\n"
    "    - name: the bare ingredient as you would add it to a supermarket "
    "shopping list — singular, WITHOUT quantities, pack sizes, or preparation "
    "words. Drop anything after a comma and any '(...)' notes. Examples: "
    "'1 medjool date, pitted and diced' -> 'medjool dates'; "
    "'1 cup mango (fresh or frozen), chopped' -> 'mango'; "
    "'1 large pre-baked sweet potato (I used Hannah)' -> 'sweet potato'. "
    "Keep it specific enough to buy (e.g. 'chickpea flour', not 'flour').\n"
    "    - quantity: a number, or null.\n"
    "    - unit: e.g. 'g', 'ml', 'tbsp', 'tsp', 'cup', 'clove', or null.\n"
    "- steps: the method as an ordered list of strings.\n"
    "- continues_past_batch: true ONLY if a recipe clearly begins on these "
    "pages but its method/ingredients continue beyond the LAST image shown.\n\n"
    "Ignore non-recipe pages: table of contents, introductions, full-page "
    "photos with no recipe, and indexes. All recipes are vegan."
)


class ParsedIngredient(BaseModel):
    raw_text: str
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None


class ParsedNutrition(BaseModel):
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None


class ParsedRecipe(BaseModel):
    title: str
    servings: Optional[int] = None
    meal_type: Optional[str] = None
    nutrition: Optional[ParsedNutrition] = None
    ingredients: list[ParsedIngredient]
    steps: list[str]
    continues_past_batch: bool = False


class ExtractedRecipes(BaseModel):
    recipes: list[ParsedRecipe]


def _client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env before extraction."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _content_blocks(images: list[bytes], page_start: int) -> list[dict]:
    blocks: list[dict] = []
    for offset, img in enumerate(images):
        blocks.append({"type": "text", "text": f"Page {page_start + offset + 1}:"})
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(img).decode("ascii"),
                },
            }
        )
    blocks.append({"type": "text", "text": _EXTRACTION_PROMPT})
    return blocks


def extract_batch(
    images: list[bytes], page_start: int, client: anthropic.Anthropic | None = None
) -> ExtractedRecipes:
    """Extract recipes from a batch of page images (page_start is 0-based)."""
    client = client or _client()
    resp = client.messages.parse(
        model=settings.extraction_model,
        max_tokens=8000,
        messages=[{"role": "user", "content": _content_blocks(images, page_start)}],
        output_format=ExtractedRecipes,
    )
    return resp.parsed_output or ExtractedRecipes(recipes=[])


def count_batch_tokens(
    images: list[bytes], page_start: int, client: anthropic.Anthropic | None = None
) -> int:
    """Input-token estimate for one batch (for cost sanity-checks)."""
    client = client or _client()
    resp = client.messages.count_tokens(
        model=settings.extraction_model,
        messages=[{"role": "user", "content": _content_blocks(images, page_start)}],
    )
    return resp.input_tokens
