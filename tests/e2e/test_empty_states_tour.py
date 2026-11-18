# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright test for the fresh-user empty-state tour (TESTS.md P2).

A brand-new user (no binaries, models, or predictions) walks the main data
pages in sequence. Every page must present its empty state, and the CTA
links must be present and navigate correctly. Individual pages are asserted
in their own modules (``test_binary_pages.py``, ``test_models_page.py``,
``test_predictions_page.py``, ``test_ml_workflow_pages.py``); this tour
guards the whole journey as a single regression.
"""

import re
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestEmptyStatesTour:
    """A fresh user sees a coherent empty state on every data page."""

    def test_fresh_user_empty_states(self, page: Any, server: Any) -> None:
        # Arrange: brand-new user with no data at all.
        register_and_login(page)

        # 1. Status bar: no active tasks for the fresh user.
        expect(
            page.locator("#status-bar-toggle .status-bar-tooltip .tooltip-empty")
        ).to_have_attribute("style", re.compile(r"display:\s*block"))

        # 2. Binary library: empty state with the upload affordance.
        page.goto(f"{BASE_URL}/binary-library")
        empty = page.locator("#binaries-empty")
        expect(empty).to_be_visible(timeout=15000)
        expect(empty).to_contain_text("No binaries uploaded yet")
        expect(page.locator("#upload-box")).to_be_visible()

        # 3. Similarity dashboard: no binaries + no saved computations.
        page.goto(f"{BASE_URL}/similarity-dashboard")
        expect(page.locator("#no-binaries")).to_be_visible(timeout=15000)
        expect(
            page.locator("#no-binaries a[href='/binary-library']")
        ).to_contain_text("Go to Binary Library")
        expect(page.locator("#no-saved")).to_be_visible(timeout=15000)

        # 4. Models: server-rendered empty state; CTA navigates to the
        # create-model page, whose binary select reflects the empty library.
        page.goto(f"{BASE_URL}/getModels")
        models_empty = page.locator(".empty-state-page")
        expect(models_empty).to_be_visible()
        expect(models_empty).to_contain_text("NO MODELS AVAILABLE")
        page.locator(".empty-state-page a[href='/create-model']").click()
        page.wait_for_url(f"{BASE_URL}/create-model")
        expect(page.locator("#binary-select")).to_have_text(
            "NO BINARIES AVAILABLE", timeout=15000
        )

        # 5. Predictions: server-rendered empty state; CTA navigates to the
        # create-prediction page, whose selects reflect the empty library
        # and the absence of models.
        page.goto(f"{BASE_URL}/getPredictions")
        preds_empty = page.locator(".empty-state-page")
        expect(preds_empty).to_be_visible()
        expect(preds_empty).to_contain_text("NO PREDICTIONS AVAILABLE")
        page.locator(".empty-state-page a[href='/create-prediction']").click()
        page.wait_for_url(f"{BASE_URL}/create-prediction")
        expect(page.locator("#binary-select")).to_have_text(
            "NO BINARIES AVAILABLE", timeout=15000
        )
        expect(page.locator("#model-select")).to_have_text(
            "NO MODELS AVAILABLE", timeout=15000
        )

        # 6. Scanner pages: with no targets the select reports that fact and
        # stays disabled (scan button likewise disabled).
        for path in ("/getDangerousFunctions", "/getBehavioralScan"):
            page.goto(f"{BASE_URL}{path}")
            select = page.locator("#scan-target-select")
            expect(select).to_have_value("", timeout=15000)
            expect(select).to_be_disabled(timeout=15000)
            expect(select.locator("option")).to_have_count(1)
            expect(select.locator("option")).to_have_text("No targets available")
            expect(page.locator("#scan-btn")).to_be_disabled()
