"""Check the app can attach to your logged-in Chrome over CDP.

Tesco blocks Playwright-launched browsers, so we attach to a Chrome YOU launch.
Start it once (after fully quitting Chrome), single line:

  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-mealplanner"

then sign in to tesco.com in that window, and run:

  python -m scripts.tesco_login
"""

from app.tesco.basket import SHOP, TescoConnectError, TescoSession


def main() -> None:
    try:
        with TescoSession() as s:
            s.page.goto(SHOP, wait_until="domcontentloaded", timeout=30000)
            s.page.wait_for_timeout(2000)
            title = s.page.title()
            denied = "access denied" in (s.page.content() or "").lower()
            print(f"Connected to your Chrome. Page title: {title[:60]!r}")
            print("Access Denied" if denied else "Tesco loads fine — you're good to go.")
    except TescoConnectError as exc:
        print(exc)


if __name__ == "__main__":
    main()
