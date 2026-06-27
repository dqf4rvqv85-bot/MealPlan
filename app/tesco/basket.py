"""Tesco automation by ATTACHING to a Chrome you launched yourself.

Tesco groceries sits behind Akamai Bot Manager, which blocks Playwright-*launched*
browsers (navigator.webdriver=true) with "Access Denied". The workaround that
works: you launch Chrome yourself with a debug port and a real logged-in session,
and we *attach* over CDP. To Akamai it's an ordinary human browser, so search and
basket actions go through.

Start Chrome once (after fully quitting Chrome), single line:
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-mealplanner"
then sign in to tesco.com in that window.

All site specifics (URL + selectors) live in the constants block — the only place
to edit when Tesco changes their markup. Nothing here ever checks out.
"""

import re
import urllib.parse
from dataclasses import dataclass

from playwright.sync_api import Page, sync_playwright

# --- Connection + site constants (edit here when Tesco changes) --------------
CDP_URL = "http://localhost:9222"  # Chrome launched with --remote-debugging-port
SHOP = "https://www.tesco.com/shop/en-GB"
# Product tiles are <li data-testid="<productId>"> containing a /products/ link;
# each tile has its own "add" button (aria-label like "add 1 <product name>").
PRODUCT_TILE = 'li[data-testid]:has(a[href*="/products/"])'
PRODUCT_LINK = 'a[href*="/products/"]'
ADD_BUTTON_RE = re.compile(r"^\s*add\b", re.I)
PLUS_BUTTON_RE = re.compile(r"increase|add 1|\+", re.I)
_PRICE_RE = re.compile(r"£\s?\d+(?:\.\d{2})?")
# ---------------------------------------------------------------------------


def search_url(term: str) -> str:
    return f"{SHOP}/search?query={urllib.parse.quote(term)}"


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


class TescoConnectError(RuntimeError):
    """Raised when no debug-enabled Chrome is reachable over CDP."""


class TescoSession:
    """Attaches to a user-launched Chrome over CDP. Never launches/closes it."""

    def __init__(self, headless: bool = True):  # headless kept for call-compat
        self._pw = None
        self._browser = None
        self._ctx = None
        self.page: Page | None = None

    def __enter__(self) -> "TescoSession":
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            self._pw.stop()
            raise TescoConnectError(
                f"Couldn't attach to Chrome at {CDP_URL}. Launch Chrome with "
                "--remote-debugging-port=9222 (and a --user-data-dir), sign in to "
                f"Tesco, then retry. ({exc})"
            ) from exc
        self._ctx = (
            self._browser.contexts[0]
            if self._browser.contexts
            else self._browser.new_context()
        )
        self.page = self._ctx.new_page()
        return self

    def __exit__(self, *exc) -> None:
        # Close only the tab we opened; leave the user's browser running.
        try:
            if self.page:
                self.page.close()
        finally:
            if self._pw:
                self._pw.stop()

    def _top_tile(self, term: str):
        self.page.goto(search_url(term), wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_timeout(2500)
        tile = self.page.locator(PRODUCT_TILE).first
        return tile if tile.count() > 0 else None

    def search(self, term: str) -> ProductMatch:
        try:
            tile = self._top_tile(term)
            if tile is None:
                return ProductMatch(term=term, found=False)
            pid = tile.get_attribute("data-testid")
            links = tile.locator(PRODUCT_LINK)
            title = None
            for i in range(min(links.count(), 4)):
                txt = (links.nth(i).inner_text() or "").strip()
                if txt:
                    title = txt
                    break
            href = links.first.get_attribute("href") or ""
            url = href if href.startswith("http") else f"https://www.tesco.com{href}"
            pm = _PRICE_RE.search(tile.inner_text() or "")
            return ProductMatch(
                term=term,
                found=True,
                title=title,
                url=url,
                product_id=pid,
                price=pm.group(0) if pm else None,
            )
        except Exception:  # fragile site — degrade, don't crash
            return ProductMatch(term=term, found=False)

    def add_top_result(self, term: str, quantity: int) -> tuple[bool, str]:
        """Add the top search result to the basket `quantity` times.

        Adds from the search tile (whose 'add' button we know), then uses the
        quantity stepper that appears for any extra units. Never checks out.
        """
        try:
            tile = self._top_tile(term)
            if tile is None:
                return False, "no product found"
            add_btn = tile.get_by_role("button", name=ADD_BUTTON_RE).first
            if add_btn.count() == 0:
                return False, "add button not found"
            add_btn.click()
            self.page.wait_for_timeout(1000)
            for _ in range(max(0, quantity - 1)):
                plus = tile.get_by_role("button", name=PLUS_BUTTON_RE).first
                if plus.count() == 0:
                    break
                plus.click()
                self.page.wait_for_timeout(700)
            return True, f"added x{quantity}"
        except Exception as exc:
            return False, str(exc)


def search_terms(terms: list[str], headless: bool = True) -> list[ProductMatch]:
    out: list[ProductMatch] = []
    with TescoSession() as s:
        for t in terms:
            out.append(s.search(t))
    return out


def add_to_basket(
    items: list[tuple[str, str, int]], dry_run: bool = True, headless: bool = True
) -> list[AddResult]:
    """items = list of (term, product_url, quantity); adds the top match per term."""
    if dry_run:
        return [
            AddResult(term=t, url=u, quantity=q, ok=True, detail="dry-run (not added)")
            for (t, u, q) in items
        ]
    out: list[AddResult] = []
    with TescoSession() as s:
        for term, url, qty in items:
            ok, detail = s.add_top_result(term, qty)
            out.append(AddResult(term, url, qty, ok, detail))
    return out
