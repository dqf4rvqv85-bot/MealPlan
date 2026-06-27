"""Insert a handful of sample vegan recipes for development / UI testing.

Lets you exercise the meal-plan and shopping flows without running the paid
PDF extraction. Idempotent: skips recipes whose title already exists.

    python -m scripts.seed_demo
"""

import json

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Ingredient, Recipe
from app.normalize import normalize_name, normalize_title

DEMO = [
    {
        "title": "Spicy Chickpea Curry",
        "servings": 4,
        "meal_type": "dinner",
        "ingredients": [
            ("2 tbsp olive oil", "olive oil", 2, "tbsp"),
            ("1 onion, diced", "onion", 1, None),
            ("3 cloves garlic, crushed", "garlic", 3, "clove"),
            ("2 tins chickpeas, drained", "chickpeas", 2, "tin"),
            ("1 tin chopped tomatoes", "chopped tomatoes", 1, "tin"),
            ("2 tbsp curry powder", "curry powder", 2, "tbsp"),
            ("200 ml coconut milk", "coconut milk", 200, "ml"),
        ],
        "steps": ["Fry onion and garlic in oil.", "Add spices, chickpeas, tomatoes.",
                  "Stir in coconut milk and simmer 20 minutes."],
    },
    {
        "title": "Lentil Bolognese",
        "servings": 4,
        "meal_type": "dinner",
        "ingredients": [
            ("1 tbsp olive oil", "olive oil", 1, "tbsp"),
            ("1 onion, finely chopped", "onion", 1, None),
            ("2 carrots, diced", "carrot", 2, None),
            ("250 g red lentils", "red lentils", 250, "g"),
            ("1 tin chopped tomatoes", "chopped tomatoes", 1, "tin"),
            ("300 g spaghetti", "spaghetti", 300, "g"),
        ],
        "steps": ["Soften onion and carrot.", "Add lentils and tomatoes, simmer.",
                  "Serve over cooked spaghetti."],
    },
    {
        "title": "Overnight Oats",
        "servings": 2,
        "meal_type": "breakfast",
        "ingredients": [
            ("100 g rolled oats", "rolled oats", 100, "g"),
            ("250 ml oat milk", "oat milk", 250, "ml"),
            ("2 tbsp maple syrup", "maple syrup", 2, "tbsp"),
            ("100 g blueberries", "blueberries", 100, "g"),
        ],
        "steps": ["Combine oats, milk and syrup.", "Chill overnight.",
                  "Top with blueberries."],
    },
    {
        "title": "Roasted Veg Traybake",
        "servings": 4,
        "meal_type": "dinner",
        "ingredients": [
            ("3 tbsp olive oil", "olive oil", 3, "tbsp"),
            ("2 peppers, sliced", "pepper", 2, None),
            ("1 aubergine, cubed", "aubergine", 1, None),
            ("2 courgettes, sliced", "courgette", 2, None),
            ("1 tin chickpeas, drained", "chickpeas", 1, "tin"),
        ],
        "steps": ["Toss veg with oil.", "Roast at 200C for 35 minutes."],
    },
    {
        "title": "Hummus & Flatbread",
        "servings": 2,
        "meal_type": "lunch",
        "ingredients": [
            ("1 tin chickpeas, drained", "chickpeas", 1, "tin"),
            ("2 tbsp tahini", "tahini", 2, "tbsp"),
            ("1 lemon, juiced", "lemon", 1, None),
            ("2 flatbreads", "flatbread", 2, None),
        ],
        "steps": ["Blend chickpeas, tahini and lemon.", "Serve with flatbread."],
    },
    {
        "title": "Tofu Stir Fry",
        "servings": 3,
        "meal_type": "dinner",
        "ingredients": [
            ("400 g firm tofu, cubed", "tofu", 400, "g"),
            ("2 tbsp soy sauce", "soy sauce", 2, "tbsp"),
            ("1 pepper, sliced", "pepper", 1, None),
            ("200 g rice", "rice", 200, "g"),
        ],
        "steps": ["Fry tofu until golden.", "Add veg and soy sauce.",
                  "Serve with rice."],
    },
    {
        "title": "Banana Pancakes",
        "servings": 2,
        "meal_type": "breakfast",
        "ingredients": [
            ("2 bananas, mashed", "banana", 2, None),
            ("150 g plain flour", "plain flour", 150, "g"),
            ("250 ml oat milk", "oat milk", 250, "ml"),
            ("1 tbsp maple syrup", "maple syrup", 1, "tbsp"),
        ],
        "steps": ["Whisk into a batter.", "Fry small pancakes until bubbling."],
    },
    {
        "title": "Minestrone Soup",
        "servings": 4,
        "meal_type": "lunch",
        "ingredients": [
            ("1 tbsp olive oil", "olive oil", 1, "tbsp"),
            ("1 onion, diced", "onion", 1, None),
            ("2 carrots, diced", "carrot", 2, None),
            ("1 tin chopped tomatoes", "chopped tomatoes", 1, "tin"),
            ("1 tin cannellini beans", "cannellini beans", 1, "tin"),
            ("100 g pasta", "pasta", 100, "g"),
        ],
        "steps": ["Soften veg.", "Add tomatoes, beans, stock and pasta, simmer."],
    },
]


def main() -> None:
    init_db()
    added = 0
    with Session(engine) as session:
        existing = {
            normalize_title(t) for t in session.exec(select(Recipe.title)).all()
        }
        for d in DEMO:
            if normalize_title(d["title"]) in existing:
                continue
            recipe = Recipe(
                title=d["title"],
                servings=d["servings"],
                meal_type=d["meal_type"],
                steps_json=json.dumps(d["steps"]),
                raw_json="{}",
            )
            session.add(recipe)
            session.flush()
            for raw, name, qty, unit in d["ingredients"]:
                session.add(
                    Ingredient(
                        recipe_id=recipe.id,
                        raw_text=raw,
                        name=name,
                        normalized_name=normalize_name(name),
                        quantity=qty,
                        unit=unit,
                    )
                )
            added += 1
        session.commit()
    print(f"seeded {added} demo recipes")


if __name__ == "__main__":
    main()
