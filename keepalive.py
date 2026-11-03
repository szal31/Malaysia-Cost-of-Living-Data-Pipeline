"""Visit the owner's other Streamlit apps so they don't go to sleep for lack of visitors.

Never fails the job: a sleeping or unreachable app is reported, not fatal.

Usage:  python keepalive.py
"""
import requests

APPS = ["https://rapidkl-ridership-analysis.streamlit.app/",
        "https://malay-tweet-sentiment-analysis.streamlit.app/",
        "https://malaysia-economic-ai-assistant.streamlit.app/"]


def ping(url):
    """(HTTP status, whether Streamlit served its "gone to sleep" page)."""
    r = requests.get(url, timeout=60)
    return r.status_code, "gone to sleep" in r.text.lower()


def main():
    for url in APPS:
        try:
            code, asleep = ping(url)
            print(f"{code} {'ASLEEP' if asleep else 'awake'} {url}")
        except requests.RequestException as e:
            print(f"unreachable {url}: {e}")
    return 0


if __name__ == "__main__":
    main()
