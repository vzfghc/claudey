"""Playwright tests for the React Claudey admin UI.

These run only when an admin server is live on the loopback (they skip in
clean CI environments). They must stay aligned with the React app under
``src/claudey/api/admin_static/admin-ui``; the selectors below rely on
stable text labels, ids, and ``data-slot`` attributes rather than styling
classes.
"""

import socket
from importlib.util import find_spec

import pytest
from playwright.sync_api import Page, expect

_ADMIN_PORT = 8090


def _admin_server_running() -> bool:
    """Return whether the admin server is listening on the loopback."""
    try:
        with socket.create_connection(("127.0.0.1", _ADMIN_PORT), timeout=0.5):
            return True
    except OSError:
        return False


# The ``page`` fixture is provided by pytest-playwright, which is not part of
# the locked test environment; these live-server checks only run when the
# plugin is available AND the admin server is actually up.
pytestmark = pytest.mark.skipif(
    find_spec("pytest_playwright") is None or not _admin_server_running(),
    reason="requires pytest-playwright and the admin server on 127.0.0.1:8090",
)


@pytest.fixture
def admin_page(page: Page) -> Page:
    """Navigate to the admin page and wait for the app shell to load."""
    page.goto(f"http://localhost:{_ADMIN_PORT}/admin/")
    page.wait_for_selector('nav[aria-label="Admin views"]')
    return page


def _open_custom_provider_dialog(admin_page: Page):
    """Open the custom-provider dialog from the Providers view."""
    admin_page.click('nav[aria-label="Admin views"] >> text=Providers')
    admin_page.click('button:has-text("Custom Provider")')
    dialog = admin_page.locator('[data-slot="dialog-content"]')
    expect(dialog).to_be_visible()
    return dialog


def test_custom_provider_dialog_opens_openai(admin_page: Page):
    """The dialog defaults to OpenAI compatibility."""
    dialog = _open_custom_provider_dialog(admin_page)
    expect(dialog).to_contain_text("Add OpenAI-compatible Provider")
    # Compatibility select defaults to OpenAI-compatible.
    expect(dialog.locator("#providerName")).to_be_visible()
    expect(dialog.locator("#baseUrl")).to_be_visible()


def test_custom_provider_dialog_switches_to_anthropic(admin_page: Page):
    """Switching compatibility updates the dialog title."""
    dialog = _open_custom_provider_dialog(admin_page)
    admin_page.click('[data-slot="dialog-content"] button[role="combobox"]')
    admin_page.click('div[role="option"]:has-text("Anthropic-compatible")')
    expect(dialog).to_contain_text("Add Anthropic-compatible Provider")


def test_custom_provider_dialog_cancel_closes(admin_page: Page):
    """Cancelling closes the dialog."""
    dialog = _open_custom_provider_dialog(admin_page)
    admin_page.click('[data-slot="dialog-content"] button:has-text("Cancel")')
    expect(dialog).not_to_be_visible()


def test_custom_provider_dialog_requires_check_before_add(admin_page: Page):
    """Adding without a successful connection check is refused."""
    dialog = _open_custom_provider_dialog(admin_page)
    add_button = dialog.locator('button:has-text("Add Provider")')
    add_button.click()
    # The dialog stays open and prompts for a connection check first.
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Check the connection")


def test_model_combobox_typing_replaces_prefilled_value(admin_page: Page):
    """Typing into a model combobox must replace the prefilled value.

    A configured model (or the optional-field default "None") pre-fills the
    combobox input; appending typed characters to it made filtering never
    match ("No matching models" on every query). The input must select its
    value on focus so the first keystroke replaces it.
    """
    admin_page.click('nav[aria-label="Admin views"] >> text=Model Config')
    combobox = admin_page.locator(
        'input[placeholder="Search or enter provider/model"]'
    ).first
    expect(combobox).to_be_visible()
    combobox.click()
    combobox.press_sequentially("deep")
    # Regression: the pre-filled value must be replaced, not appended to.
    expect(combobox).to_have_value("deep")
    expect(admin_page.locator('[role="option"]')).not_to_have_count(0)


def test_optional_model_combobox_typing_replaces_none_default(admin_page: Page):
    """Optional model comboboxes default to "None"; typing must replace it."""
    admin_page.click('nav[aria-label="Admin views"] >> text=Model Config')
    combobox = admin_page.locator('input[placeholder="Uses provider default"]').first
    expect(combobox).to_be_visible()
    combobox.click()
    combobox.press_sequentially("claude")
    expect(combobox).to_have_value("claude")
