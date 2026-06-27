"""One-time interactive Tesco login; persists the session for later headless runs.

Run this once (it opens a visible browser so you can clear any CAPTCHA / 2FA):

    python -m scripts.tesco_login

Requires TESCO_EMAIL / TESCO_PASSWORD in .env. The session is saved to the path
in TESCO_STORAGE_STATE so the app's search / basket steps can run headlessly.
"""

from app.tesco.basket import save_login


def main() -> None:
    save_login(headless=False)
    print("Tesco session saved.")


if __name__ == "__main__":
    main()
