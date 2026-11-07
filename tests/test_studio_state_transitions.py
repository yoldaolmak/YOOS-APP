"""Real browser regression coverage for the implicit Studio state transitions."""
import threading

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from pennovia.exporter import writer
from pennovia.studio import server
from pennovia.voice import generator
from tests.test_studio_browser import DRAFT, SAMPLE, local_studio


def _ready(page):
    page.get_by_role("tab", name="Paste").click()
    page.locator("#paste-input").fill(SAMPLE)
    page.locator("#add-text").click()
    page.locator("#analyze").click()
    page.get_by_text("Profile ready", exact=True).wait_for()
    assert page.locator("#metric-texts").inner_text() == "1 writing samples"


def test_source_and_settings_changes_invalidate_profile_without_deleting_draft():
    with local_studio() as base, playwright.sync_playwright() as engine:
        browser = engine.chromium.launch()
        page = browser.new_page(accept_downloads=True)
        page.goto(base)
        _ready(page)

        page.locator("#draft").fill(DRAFT)
        page.locator("#review").click()
        page.locator("#review-results").wait_for(state="visible")
        page.locator("#paste-input").fill(SAMPLE + " One more sentence.")
        page.locator("#add-text").click()
        assert page.locator("#profile-state").inner_text() == "Reanalysis needed"
        assert page.locator("#profile-results").is_hidden()
        assert page.locator("#review-results").is_hidden()
        assert page.locator("#draft").input_value() == DRAFT
        for button in ("generate", "review", "download", "wordpress", "drive", "profile-save"):
            assert page.locator("#" + button).is_disabled()

        page.locator("#analyze").click()
        page.get_by_text("Profile ready", exact=True).wait_for()
        assert page.locator("#metric-texts").inner_text() == "2 writing samples"
        page.locator("#author").fill("Different author")
        assert page.locator("#profile-state").inner_text() == "Reanalysis needed"
        page.locator("#analyze").click()
        page.get_by_text("Profile ready", exact=True).wait_for()
        page.locator("#language").select_option("tr")
        assert page.locator("#profile-state").inner_text() == "Reanalysis needed"
        page.locator("#analyze").click()
        page.get_by_text("Profile ready", exact=True).wait_for()

        with page.expect_download() as download_info:
            page.locator("#profile-save").click()
        profile_bytes = open(download_info.value.path(), "rb").read()
        page.locator("#profile-import").set_input_files({
            "name": "profile.json", "mimeType": "application/json",
            "buffer": profile_bytes,
        })
        page.get_by_text("Profile ready", exact=True).wait_for()
        assert page.locator("#source-list .source-item").count() == 0
        assert page.locator("#analyze").is_disabled()
        assert page.locator("#draft").input_value() == DRAFT
        assert page.locator("#review-results").is_hidden()
        browser.close()


def test_generation_and_review_lock_all_editor_inputs_while_request_is_active(monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def delayed_generate(*args, **kwargs):
        entered.set()
        if not release.wait(timeout=15):
            raise RuntimeError("synthetic generation timeout")
        return DRAFT

    monkeypatch.setattr(generator, "generate", delayed_generate)
    try:
        with local_studio() as base, playwright.sync_playwright() as engine:
            browser = engine.chromium.launch()
            page = browser.new_page()
            page.goto(base)
            _ready(page)
            page.locator("#topic").fill("An unfamiliar place")

            page.locator("#draft").fill("An existing draft I want to preserve.")
            page.once("dialog", lambda dialog: dialog.dismiss())
            page.locator("#generate").click()
            assert not entered.is_set()
            assert page.locator("#draft").input_value() == "An existing draft I want to preserve."

            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("#generate").click()
            assert entered.wait(timeout=8)
            for field in (
                "draft", "paste-input", "url-input", "author", "language",
                "profile-import", "file-input", "topic", "backend", "model",
                "export-format", "export-title-input",
            ):
                assert page.locator("#" + field).is_disabled(), field
            assert page.locator("#add-text").is_disabled()
            assert page.get_by_role("tab", name="Paste").is_disabled()
            assert page.locator(".source-remove").first.is_disabled()
            release.set()
            page.wait_for_function(
                "(expected) => document.querySelector('#draft').value === expected",
                arg=DRAFT,
            )
            assert page.locator("#draft").is_enabled()
            assert page.locator("#review-results").is_visible()
            browser.close()
    finally:
        release.set()


def test_uncertain_remote_submission_requires_explicit_retry_confirmation(monkeypatch):
    calls = []

    def maybe_wp(content, title, publish=False):
        calls.append((content, title, publish))
        if len(calls) == 1:
            raise writer.RemoteOutcomeUnknown("WordPress outcome is unknown")
        return "https://example.org/draft-2"

    monkeypatch.setattr(writer, "save_wordpress", maybe_wp)
    with local_studio() as base, playwright.sync_playwright() as engine:
        browser = engine.chromium.launch()
        page = browser.new_page()
        page.goto(base)
        _ready(page)
        page.locator("#draft").fill(DRAFT)
        page.locator("#export-title-input").fill("Example")
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#wordpress").click()
        page.wait_for_function(
            "() => document.querySelector('#notice').textContent.includes('outcome is unknown')"
        )
        assert len(calls) == 1

        # A blind repeat is blocked unless the author first acknowledges the
        # uncertain outcome and checks the remote destination.
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.locator("#wordpress").click()
        assert len(calls) == 1

        dialogs = []
        def accept(dialog):
            dialogs.append(dialog.message)
            dialog.accept()
        page.on("dialog", accept)
        page.locator("#wordpress").click()
        page.wait_for_function(
            "() => document.querySelector('#notice').textContent.includes('WordPress draft created')"
        )
        assert len(calls) == 2
        assert len(dialogs) == 2
        assert "may have succeeded" in dialogs[0]
        assert all(call[2] is False for call in calls)

        page.remove_listener("dialog", accept)
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.locator("#wordpress").click()
        assert len(calls) == 2
        browser.close()
