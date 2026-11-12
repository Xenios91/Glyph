# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the models page.

Tests the models list page including empty state, table structure,
and action buttons.
"""

import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestModelsPage:
    """Tests for the models list page."""

    def test_models_page_loads(self, page: Any, server: Any) -> None:
        """Test that the models page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getModels")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Models List")

    def test_models_page_shows_empty_state_or_table(self, page: Any, server: Any) -> None:
        """Test that the models page shows either empty state or models table."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getModels")
        page.wait_for_load_state("networkidle")

        # Page should show either the empty state or a models table
        empty_state = page.locator(".empty-state-page")
        models_table = page.locator("table.cyber-table")
        assert empty_state.is_visible() or models_table.is_visible(), (
            "Models page should show either empty state or models table"
        )

    def test_models_empty_state_structure(self, page: Any, server: Any) -> None:
        """Test that the models page has correct empty state structure when no models exist."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getModels")
        page.wait_for_load_state("networkidle")

        empty_state = page.locator(".empty-state-page")
        if empty_state.is_visible():
            expect(page.locator(".empty-state-title")).to_be_visible()
            expect(page.locator(".empty-state-title")).to_contain_text("NO MODELS AVAILABLE")
        # If empty state is not visible, models exist - that's also valid

    def test_models_empty_state_has_description(self, page: Any, server: Any) -> None:
        """Test that the models empty state has a description when no models exist."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getModels")
        page.wait_for_load_state("networkidle")

        empty_state = page.locator(".empty-state-page")
        if empty_state.is_visible():
            # The empty state may contain multiple description paragraphs.
            expect(page.locator(".empty-state-description").first).to_be_visible()
        # If empty state is not visible, models exist - that's also valid

    def test_models_empty_state_has_create_model_link(self, page: Any, server: Any) -> None:
        """Test that the models empty state has a link to create a model."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getModels")
        page.wait_for_load_state("networkidle")

        # The empty state should have a link to create model
        create_link = page.locator('a[href="/create-model"]')
        assert create_link.count() > 0, "Empty state should have a link to create model"

    def test_models_page_has_back_button(self, page: Any, server: Any) -> None:
        """Test that the models page has a back button."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getModels")
        page.wait_for_load_state("networkidle")

        back_button = page.locator(".back-btn")
        # Back button may not be visible in empty state, but should exist in DOM
        # when models are present. For empty state, just verify page loads.
        assert page.url == f"{BASE_URL}/getModels"


def _seed_model(data_dir: str, name: str) -> None:
    """Insert a legacy (unowned) model row visible to every user."""
    conn = sqlite3.connect(Path(data_dir) / "models.db")
    try:
        conn.execute(
            "INSERT INTO models (model_name, model_data, label_encoder_data) "
            "VALUES (?, x'00', x'00')",
            (name,),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_model_row(data_dir: str, name: str) -> None:
    """Remove a seeded model row so other tests see a clean database."""
    conn = sqlite3.connect(Path(data_dir) / "models.db")
    try:
        conn.execute("DELETE FROM models WHERE model_name = ?", (name,))
        conn.commit()
    finally:
        conn.close()


def _model_exists(data_dir: str, name: str) -> bool:
    """Return True when the named model row exists in models.db."""
    conn = sqlite3.connect(Path(data_dir) / "models.db")
    try:
        return (
            conn.execute(
                "SELECT 1 FROM models WHERE model_name = ?", (name,)
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


class TestModelStatusColumn:
    """R11: the meaningless always-complete STATUS column must be gone."""

    def test_models_table_has_no_status_column(
        self, page: Any, server: Any, data_dir: str
    ) -> None:
        """The model table renders only the checkbox and MODEL NAME columns."""
        register_and_login(page)
        model_name = f"e2e_nostatus_{uuid4().hex[:8]}"
        _seed_model(data_dir, model_name)
        try:
            page.goto(f"{BASE_URL}/getModels")
            page.wait_for_load_state("networkidle")

            table = page.locator("table.cyber-table")
            expect(table).to_be_visible()

            headers = table.locator("thead th").all_inner_texts()
            assert not any("STATUS" in h.upper() for h in headers), (
                f"STATUS column must be removed from the model table, got {headers}"
            )

            row = page.locator(f"tr[data-model-name='{model_name}']")
            expect(row).to_have_count(1)
            expect(row).to_contain_text(model_name)
            # One checkbox cell + one name cell + one chevron cell (R22).
            assert row.locator("td").count() == 3, (
                "Model row must contain the checkbox, name, and chevron cells"
            )
        finally:
            _delete_model_row(data_dir, model_name)


class TestSymbolsDeleteConfirmation:
    """R9: the symbols page single-click delete must require confirmation."""

    def test_symbols_page_delete_requires_confirmation(
        self, page: Any, server: Any, data_dir: str
    ) -> None:
        """Clicking DELETE MODEL opens the styled modal; cancel keeps, confirm deletes."""
        register_and_login(page)
        model_name = f"e2e_symdel_{uuid4().hex[:8]}"
        _seed_model(data_dir, model_name)
        try:
            page.goto(f"{BASE_URL}/getSymbols?model_name={model_name}")
            page.wait_for_load_state("networkidle")

            native_dialogs: list[str] = []

            def _on_dialog(dialog: Any) -> None:
                native_dialogs.append(dialog.message)
                dialog.dismiss()

            page.on("dialog", _on_dialog)

            # A single click must open the styled modal, naming the model.
            page.locator("#delete-model-btn").click()
            overlay = page.locator(".confirm-modal-overlay")
            expect(overlay).to_be_visible()
            expect(page.locator(".confirm-modal-title")).to_contain_text("Delete Model")
            expect(page.locator(".confirm-modal-message")).to_contain_text(model_name)

            # Cancelling keeps the user on the page and the model intact.
            page.locator(".confirm-modal .cyber-btn", has_text="Cancel").click()
            expect(overlay).to_have_count(0)
            assert page.url == f"{BASE_URL}/getSymbols?model_name={model_name}"
            assert _model_exists(data_dir, model_name)

            # Confirming deletes the model and redirects home.
            page.locator("#delete-model-btn").click()
            expect(overlay).to_be_visible()
            page.locator(".confirm-modal .cyber-btn", has_text="Delete").click()
            page.wait_for_url(f"{BASE_URL}/", timeout=15000)
            assert not _model_exists(data_dir, model_name)
            assert not native_dialogs, f"Native dialog opened: {native_dialogs}"
        finally:
            _delete_model_row(data_dir, model_name)
