import requests

import keepalive


class Resp:
    status_code = 200

    def __init__(self, text):
        self.text = text


def test_ping_detects_sleep_page(monkeypatch):
    monkeypatch.setattr(keepalive.requests, "get", lambda url, **kw: Resp("Zzzz... This app has gone to sleep"))
    assert keepalive.ping("https://x.streamlit.app/") == (200, True)


def test_main_never_raises(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(keepalive.requests, "get", boom)
    assert keepalive.main() == 0
