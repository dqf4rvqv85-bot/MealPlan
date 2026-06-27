from fastapi.templating import Jinja2Templates

from app.config import ROOT

templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))
