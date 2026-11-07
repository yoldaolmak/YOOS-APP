"""Real Chromium smoke tests of the existing local Studio interface."""
import os
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from pennovia.studio import server  # noqa: E402


SAMPLE = (
    "A useful travel article gives the reader enough detail to choose a route. "
    "When I walk around a new neighborhood, I note practical things such as "
    "connections, crowds, closing times and what the streets actually feel like. "
    "Some routes need more time than a standard itinerary allows. I prefer "
    "a thoughtful pause to a list of places that cannot realistically be seen. "
) * 3

DRAFT = (
    "Walking through a city requires some judgment about distance and timing. "
    "A useful plan can be simple, but it should still explain why the route "
    "is comfortable and what the traveler will encounter along the way. "
    "There is no need to invent a personal experience or unsupported advice. "
) * 9


@contextmanager
def local_studio():
    local = server.make_server(0)
    runner = threading.Thread(target=local.serve_forever, daemon=True)
    runner.start()
    try:
        yield f"http://127.0.0.1:{local.server_address[1]}"
    finally:
        local.shutdown()
        runner.join(timeout=5)
        local.server_close()


def test_real_chromium_full_studio_flow_and_mobile_layout(monkeypatch, tmp_path):
    from pennovia.voice import generator
    from pennovia.exporter import writer

    calls = []
    monkeypatch.setattr(server, "read_url", lambda url: SAMPLE)

    def synthetic_generate(profile, content_type, topic, backend, **options):
        calls.append(("generate", content_type, topic, backend))
        return DRAFT

    def synthetic_wordpress(content, title, publish=False):
        calls.append(("wordpress", title, publish))
        return "https://example.org/?p=123"

    monkeypatch.setattr(generator, "generate", synthetic_generate)
    monkeypatch.setattr(writer, "save_wordpress", synthetic_wordpress)

    with local_studio() as address, playwright.sync_playwright() as browser_engine:
        browser = browser_engine.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900},
                                accept_downloads=True)
        failures = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.goto(address, wait_until="networkidle")

        assert page.title().startswith("Pennovia Studio")
        page.locator("#url-input").fill("https://example.org/first-story")
        page.locator("#add-urls").click()
        page.get_by_role("tab", name="Paste").click()
        page.locator("#paste-input").fill(SAMPLE)
        page.locator("#add-text").click()
        page.get_by_role("tab", name="Files").click()
        page.locator("#file-input").set_input_files({
            "name": "sample.txt",
            "mimeType": "text/plain",
            "buffer": SAMPLE.encode("utf-8"),
        })
        page.locator("#source-list .source-item").nth(2).wait_for()
        assert page.locator("#source-list .source-item").count() == 3

        page.locator("#analyze").click()
        page.get_by_text("Profile ready", exact=True).wait_for()
        assert page.locator("#metric-texts").inner_text() == "3 writing samples"

        with page.expect_download() as profile_download:
            page.locator("#profile-save").click()
        profile = profile_download.value
        assert profile.suggested_filename == "pennovia-voice.json"
        profile_bytes = Path(profile.path()).read_bytes()
        assert b'"schema_version": 1' in profile_bytes

        page.locator("#topic").fill("Walkable neighborhoods")
        page.locator("#content-type").select_option("travel_guide")
        page.locator("#generate").click()
        page.locator("#draft").wait_for(state="visible")
        page.wait_for_function("(expected) => document.querySelector('#draft').value === expected", DRAFT)
        assert calls[0] == ("generate", "travel_guide", "Walkable neighborhoods", "ollama")

        page.locator("#draft").fill(DRAFT + "\n\nExtra editorial note.")
        page.locator("#review").click()
        page.locator("#review-results").wait_for(state="visible")
        assert page.locator("#review-score").inner_text().isdigit()

        page.locator("#export-format").select_option("txt")
        with page.expect_download() as text_download:
            page.locator("#download").click()
        text_file = text_download.value
        assert text_file.suggested_filename == "pennovia-draft.txt"
        assert Path(text_file.path()).read_text(encoding="utf-8").endswith("Extra editorial note.")

        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#wordpress").click()
        page.wait_for_function(
            "() => document.querySelector('#notice').textContent.includes('WordPress draft created')"
        )
        assert calls[-1] == ("wordpress", "Walkable neighborhoods", False)

        shots = Path(os.environ.get("RUNNER_TEMP", str(tmp_path))) / "studio-screenshots"
        shots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shots / "desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(shots / "mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
        assert page.locator("#draft").is_visible()
        assert not failures

        # Imported JSON must work after a reload (in-memory state is deliberately ephemeral).
        page.reload(wait_until="networkidle")
        assert page.locator("#profile-state").inner_text() == "Not analyzed"
        page.locator("#profile-import").set_input_files({
            "name": "voice.json",
            "mimeType": "application/json",
            "buffer": profile_bytes,
        })
        page.get_by_text("Profile ready", exact=True).wait_for()
        assert page.locator("#generate").is_disabled()  # topic was reset on reload
        assert not failures
        browser.close()
