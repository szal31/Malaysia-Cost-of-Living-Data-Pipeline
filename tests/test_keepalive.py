import keepalive


class Button:
    def __init__(self, present):
        self.present, self.clicked = present, False

    def count(self):
        return int(self.present)

    def click(self):
        self.clicked = True


class Page:
    def __init__(self, asleep):
        self.button = Button(asleep)

    def goto(self, url, **kw):
        pass

    def get_by_role(self, role, name):
        return self.button

    def wait_for_timeout(self, ms):
        pass


def test_sleeping_app_is_woken():
    page = Page(asleep=True)
    assert keepalive.visit(page, "https://x.streamlit.app/") == "woken"
    assert page.button.clicked


def test_awake_app_is_just_visited():
    page = Page(asleep=False)
    assert keepalive.visit(page, "https://x.streamlit.app/") == "awake"
    assert not page.button.clicked


def test_main_never_raises(monkeypatch):
    def broken():
        raise RuntimeError("no browser")
    monkeypatch.setattr(keepalive, "browser_pages", broken)
    assert keepalive.main() == 0
