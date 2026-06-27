"""Playwright automation for tesco.com/groceries.

This is the deliberately-fragile part of the app: it drives a real browser
against a third-party site whose DOM changes without notice. Design choices to
contain that:
  * All site URLs and CSS selectors live in the constants block below — when
    Tesco changes their markup, this is the only place to edit.
  * Every interaction is wrapped so a miss degrades to "not found" rather than
    crashing the request.
  * Nothing here ever proceeds to checkout. The highest-impact action is adding
    items to the basket, and only when explicitly requested (dry_run=False).

Login note: Tesco login can present CAPTCHA / 2FA. Do a one-time interactive
login with `save_login(headless=False)` to persist a browser session to
settings.tesco_storage_state; subsequent search/add runs reuse it headlessly.
"""

import glob
import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from app.config import settings

# --- Site constants (edit here when Tesco changes their markup) --------------
GROCERIES = "https://www.tesco.com/groceries/en-GB"
LOGIN_URL = "https://www.tesco.com/account/login/en-GB"

# Candidate selectors tried in order; the first that matches wins.
PRODUCT_TILE_SELECTORS = [
    '[data-testid="product-tile"]',
    'li[data-auto="product-tile"]',
    'div.product-list--list-item',
]
PRODUCT_LINK_SELECTOR = 'a[href*="/products/"]'
PRICE_SELECTORS = ['[data-auto="price-value"]', 'p.price-per-sellable-unit', '.price']
_PRODUCT_ID_RE = re.compile(r"/products/(\d+)")
# ---------------------------------------------------------------------------


def search_url(term: str) -> str:
    return f"{GROCERIES}/search?query={urllib.parse.quote(term)}"


def chromium_executable() -> str | None:
    """Locate a pre-installed Chromium when the bundled build is absent.

    Returns None to let Playwright resolve its own browser (matched versions).
    """
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if base:
        matches = sorted(glob.glob(os.path.join(base, "chromium-*/chrome-linux/chrome")))
        if matches:
            return matches[-1]
    return None


@dataclass
class ProductMatch:
    term: str
    found: bool
    title: str | None = None
    url: str | None = None
    product_id: str | None = None
    price: str | None = None


@dataclass
class AddResult:
    term: str
    url: str | None
    quantity: int
    ok: bool
    detail: str


class TescoSession:
    """Context manager wrapping a Playwright browser + Tesco session."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self._browser = None
        self._ctx = None
        self.page: Page | None = None

    def __enter__(self) -> "TescoSession":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless, executable_path=chromium_executable()
        )
        state = settings.resolve(settings.tesco_storage_state)
        self._ctx = self._browser.new_context(
            storage_state=str(state) if state.exists() else None
        )
        self.page = self._ctx.new_page()
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def save_state(self) -> None:
        state = settings.resolve(settings.tesco_storage_state)
        self._ctx.storage_state(path=str(state))

    def login(self) -> None:
        """Fill the login form from settings and persist the session."""
        if not (settings.tesco_email and settings.tesco_password):
            raise RuntimeError("TESCO_EMAIL / TESCO_PASSWORD not set in .env")
        self.page.goto(LOGIN_URL, wait_until="domcontentloaded")
        self.page.fill('input[type="email"], #email', settings.tesco_email)
        self.page.fill('input[type="password"], #password', settings.tesco_password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state("networkidle")
        self.save_state()

    def search(self, term: str) -> ProductMatch:
        try:
            self.page.goto(search_url(term), wait_until="domcontentloaded")
            tile = None
            for sel in PRODUCT_TILE_SELECTORS:
                loc = self.page.locator(sel).first
                if loc.count() > 0:
                    tile = loc
                    break
            if tile is None:
                return ProductMatch(term=term, found=False)
            link = tile.locator(PRODUCT_LINK_SELECTOR).first
            href = link.get_attribute("href") or ""
            url = href if href.startswith("http") else f"https://www.tesco.com{href}"
            title = (link.inner_text() or "").strip() or None
            m = _PRODUCT_ID_RE.search(url)
            price = None
            for psel in PRICE_SELECTORS:
                p = tile.locator(psel).first
                if p.count() > 0:
                    price = (p.inner_text() or "").strip()
                    break
            return ProductMatch(
                term=term,
                found=True,
                title=title,
                url=url,
                product_id=m.group(1) if m else None,
                price=price,
            )
        except Exception:  # fragile site — degrade, don't crash
            return ProductMatch(term=term, found=False)

    def add(self, product_url: str, quantity: int) -> bool:
        """Add a product to the basket `quantity` times. Never checks out."""
        self.page.goto(product_url, wait_until="domcontentloaded")
        add_btn = self.page.get_by_role("button", name=re.compile("add", re.I)).first
        if add_btn.count() == 0:
            return False
        for _ in range(max(1, quantity)):
            add_btn.click()
            self.page.wait_for_timeout(400)
        return True


def search_terms(terms: list[str], headless: bool = True) -> list[ProductMatch]:
    results: list[ProductMatch] = []
    with TescoSession(headless=headless) as s:
        for t in terms:
            results.append(s.search(t))
    return results


def add_to_basket(
    items: list[tuple[str, str, int]], dry_run: bool = True, headless: bool = True
) -> list[AddResult]:
    """items = list of (term, product_url, quantity)."""
    if dry_run:
        return [
            AddResult(term=t, url=u, quantity=q, ok=True, detail="dry-run (not added)")
            for (t, u, q) in items
        ]
    out: list[AddResult] = []
    with TescoSession(headless=headless) as s:
        for term, url, qty in items:
            try:
                ok = s.add(url, qty)
                out.append(
                    AddResult(term, url, qty, ok, "added" if ok else "add button not found")
                )
            except Exception as exc:
                out.append(AddResult(term, url, qty, False, str(exc)))
    return out


def save_login(headless: bool = False) -> None:
    """One-time interactive login helper (run headed to clear CAPTCHA/2FA)."""
    with TescoSession(headless=headless) as s:
        s.login()
