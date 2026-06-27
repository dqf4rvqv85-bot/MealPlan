from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    servings: Optional[int] = None
    meal_type: Optional[str] = None
    source_page_start: Optional[int] = None
    source_page_end: Optional[int] = None
    # Per-serving nutrition from the recipe footer (for calorie-aware planning).
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    steps_json: str = "[]"  # JSON-encoded list[str]
    raw_json: str = "{}"  # full model output for re-parsing

    ingredients: list["Ingredient"] = Relationship(
        back_populates="recipe",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Ingredient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    raw_text: str
    name: str
    normalized_name: str = Field(index=True)
    quantity: Optional[float] = None
    unit: Optional[str] = None

    recipe: Optional[Recipe] = Relationship(back_populates="ingredients")


class MealPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = "Weekly plan"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    items: list["MealPlanItem"] = Relationship(
        back_populates="plan",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class MealPlanItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    meal_plan_id: int = Field(foreign_key="mealplan.id", index=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    slot: int = 0  # 0..N-1, e.g. day index
    servings: int = 2

    plan: Optional[MealPlan] = Relationship(back_populates="items")


class TescoMatch(SQLModel, table=True):
    """Cache of confirmed ingredient -> Tesco product mappings."""

    id: Optional[int] = Field(default=None, primary_key=True)
    normalized_name: str = Field(index=True, unique=True)
    search_term: str
    tesco_product_id: Optional[str] = None
    product_url: Optional[str] = None
    product_title: Optional[str] = None
    pack_note: Optional[str] = None
    verified: bool = False


class ExtractionLog(SQLModel, table=True):
    """Tracks which PDF page ranges have already been extracted (idempotency)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    page_start: int = Field(index=True)
    page_end: int
    recipes_found: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
