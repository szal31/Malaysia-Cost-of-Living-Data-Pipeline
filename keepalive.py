"""Visit the owner's other Streamlit apps so they don't go to sleep for lack of visitors.

A plain HTTP request isn't a visit to Streamlit (the app only starts a session in a real browser), so this
opens each app in a headless browser and clicks "Yes, get this app back up!" if it has gone to sleep.
Never fails the job: a sleeping or unreachable app is reported, not fatal.

Usage:  pip install playwright && playwright install chromium && python keepalive.py
"""
import re
from contextlib import contextmanager

APPS = ["https://rapidkl-ridership-analysis.streamlit.app/",
        "https://malay-tweet-sentiment-analysis.streamlit.app/",
        "https://malaysia-economic-ai-assistant.streamlit.app/"]
WAKE = re.compile("get this app back up", re.I)


def visit(page, url):
    """Open the app like a visitor; wake it if it's asleep. Returns "woken" or "awake"."""
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)  # a live app never goes network-idle
    page.wait_for_timeout(15_000)  # the sleep page and the app are both drawn by JavaScript
    button = page.get_by_role("button", name=WAKE)
    if button.count():
        button.click()
        page.wait_for_timeout(30_000)  # give it time to start, so the visit counts
        return "woken"
    page.wait_for_timeout(10_000)  # stay long enough for the app's session to open
    return "awake"


@contextmanager
def browser_pages():
    from playwright.sync_api import sync_playwright  # only the GitHub job installs it
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            yield browser.new_page()
        finally:
            browser.close()


def main():
    try:
        with browser_pages() as page:
            for url in APPS:
                try:
                    print(visit(page, url), url)
                except Exception as e:  # one app failing shouldn't skip the others
                    print("unreachable", url, type(e).__name__, str(e)[:200])
    except Exception as e:
        print("keep-alive skipped:", type(e).__name__, e)
    return 0


if __name__ == "__main__":
    main()
