"""Test whether attaching to YOUR OWN Chrome bypasses Tesco's bot protection.

Playwright *launching* Chrome is blocked by Akamai (navigator.webdriver=true,
automation flags). But if YOU launch Chrome with a debug port and we merely
*attach* to it, those automation tells are absent and the session is a genuine
human one — which Akamai may accept.

Steps:
  1) Quit Chrome completely (Cmd-Q; make sure no Chrome is running).
  2) Launch Chrome with a debug port and a dedicated profile (single line):
       "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-mealplanner"
  3) In that window, sign in at tesco.com and open the groceries page once
     (clear any prompts) so Akamai validates the real session.
  4) Run:  cd ~/mealplanner && .venv/bin/python -m scripts.tesco_cdp_test
"""

from playwright.sync_api import sync_playwright

CDP_URL = "http://localhost:9222"
TEST_QUERY = "banana"
SEARCH = f"https://www.tesco.com/groceries/en-GB/search?query={TEST_QUERY}"


def main() -> None:
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            print(f"Could not connect to Chrome at {CDP_URL}: {exc}")
            print("Is Chrome running with --remote-debugging-port=9222 ?")
            return

        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            print("navigator.webdriver:", page.evaluate("navigator.webdriver"))
            page.goto(SEARCH, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            body = (page.content() or "").lower()
            denied = "access denied" in body
            products = page.locator('a[href*="/products/"]').count()
            print(f"final url: {page.url}")
            print(f"title: {page.title()[:60]!r}")
            print(f"denied: {denied} | product links: {products} | html len: {len(body)}")
            if not denied and products:
                print("\n✅ SUCCESS — attaching to your Chrome reaches Tesco search.")
                print("   We can wire the basket flow to use this connection.")
            else:
                print("\n❌ Still blocked — Akamai rejects even the attached session.")
        finally:
            page.close()  # close only the tab we opened; leave your browser open


if __name__ == "__main__":
    main()
