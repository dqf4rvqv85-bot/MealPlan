from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import ROOT, settings
from app.db import init_db
from app.routes_plan import router as plan_router
from app.tesco.routes import router as tesco_router
from app.views import router as views_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mealplanner", lifespan=lifespan)
app.include_router(views_router)
app.include_router(plan_router)
app.include_router(tesco_router)


@app.get("/healthz")
def healthz() -> dict:
    pdf = settings.resolve(settings.pdf_path)
    return {
        "status": "ok",
        "db": str(settings.resolve(settings.db_path).relative_to(ROOT)),
        "pdf_present": pdf.exists(),
        "anthropic_key_set": bool(settings.anthropic_api_key),
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (
        "<!doctype html><meta charset=utf-8>"
        "<title>Mealplanner</title>"
        "<body style='font-family:system-ui;max-width:640px;margin:3rem auto;padding:0 1rem'>"
        "<h1>🥗 Mealplanner</h1>"
        "<p>Vegan recipe PDF → weekly meal plan → Tesco basket.</p>"
        "<ul>"
        "<li><a href='/recipes'>Recipe library</a></li>"
        "<li><a href='/plan'>Generate a meal plan</a></li>"
        "</ul>"
        "<p style='color:#666'>No recipes yet? Run "
        "<code>python -m scripts.ingest</code> (needs ANTHROPIC_API_KEY) or "
        "<code>python -m scripts.seed_demo</code> for sample data.</p>"
        "</body>"
    )
