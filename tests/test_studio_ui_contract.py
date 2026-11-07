"""Keep the single-page interface wired to actual controls and mobile layout."""
import re
from html.parser import HTMLParser
from importlib.resources import files


class _Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.labels = set()
        self.controls = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "label" and "for" in attributes:
            self.labels.add(attributes["for"])
        if "aria-controls" in attributes:
            self.controls.add(attributes["aria-controls"])


def test_studio_browser_controls_have_corresponding_markup():
    assets = files("pennovia.studio")
    html = assets.joinpath("index.html").read_text(encoding="utf-8")
    js = assets.joinpath("app.js").read_text(encoding="utf-8")
    css = assets.joinpath("app.css").read_text(encoding="utf-8")

    parser = _Ids()
    parser.feed(html)
    referenced = set(re.findall(r'\$\("([a-z][a-z0-9-]+)"\)', js))
    assert referenced <= parser.ids
    assert parser.labels <= parser.ids
    assert parser.controls <= parser.ids

    # Product flow: all five stages and each original export path remain visible.
    for required in (
        "sources-title", "profile-title", "draft-title", "review-title",
        "export-title", "profile-import", "file-input", "download",
        "wordpress", "drive",
    ):
        assert required in parser.ids

    assert "@media(max-width:800px)" in css
    assert "@media(max-width:490px)" in css
    assert "grid-template-columns:1fr" in css
    assert "__STUDIO_TOKEN__" in html
    assert "textContent =" in js
