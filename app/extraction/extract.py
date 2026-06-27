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
    "- servings: integer number of servings, or null if not stated.\n"
    "- meal_type: one of breakfast, lunch, dinner, dessert, snack, side, "
    "drink, sauce, or null if unclear.\n"
    "- ingredients: each with raw_text (exactly as printed), name (the cleaned "
    "ingredient, e.g. 'plain flour'), quantity (a number, or null), and unit "
    "(e.g. 'g', 'ml', 'tbsp', 'tsp', 'clove', or null).\n"
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


class ParsedRecipe(BaseModel):
    title: str
    servings: Optional[int] = None
    meal_type: Optional[str] = None
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
