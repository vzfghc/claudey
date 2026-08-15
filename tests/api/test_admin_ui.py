"""Playwright tests for Claudey admin UI."""

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
    """Navigate to the admin page and wait for it to load."""
    page.goto("http://localhost:8090/admin/")
    page.wait_for_selector(".app-shell")
    return page


def test_custom_provider_buttons_visible(admin_page: Page):
    """Test that custom provider buttons are visible in the UI."""
    # Check that both buttons are visible
    expect(admin_page.locator("#addOpenAIProviderBtn")).to_be_visible()
    expect(admin_page.locator("#addAnthropicProviderBtn")).to_be_visible()


def test_openai_provider_dialog_opens(admin_page: Page):
    """Test that clicking OpenAI button opens the dialog."""
    admin_page.click("#addOpenAIProviderBtn")
    dialog = admin_page.locator(".custom-provider-dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Add OpenAI-compatible Provider")


def test_anthropic_provider_dialog_opens(admin_page: Page):
    """Test that clicking Anthropic button opens the dialog."""
    admin_page.click("#addAnthropicProviderBtn")
    dialog = admin_page.locator(".custom-provider-dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Add Anthropic-compatible Provider")


def test_provider_dialog_form_validation(admin_page: Page):
    """Test form validation in custom provider dialog."""
    admin_page.click("#addOpenAIProviderBtn")
    dialog = admin_page.locator(".custom-provider-dialog")

    # Try to submit empty form
    admin_page.click(".custom-provider-dialog .primary-button")

    # Check that form shows validation errors
    expect(dialog.locator("input:invalid")).to_have_count(2)  # Name and URL required

    # Fill in name but not URL
    admin_page.fill("#providerName", "Test Provider")
    admin_page.click(".custom-provider-dialog .primary-button")
    expect(dialog.locator("input:invalid")).to_have_count(1)  # URL still required

    # Fill in invalid URL
    admin_page.fill("#baseUrl", "not-a-url")
    admin_page.click(".custom-provider-dialog .primary-button")
    expect(dialog.locator("input:invalid")).to_have_count(1)  # URL format invalid


def test_provider_dialog_cancellation(admin_page: Page):
    """Test that dialog can be cancelled."""
    admin_page.click("#addOpenAIProviderBtn")
    dialog = admin_page.locator(".custom-provider-dialog")
    expect(dialog).to_be_visible()

    # Click cancel button
    admin_page.click(".custom-provider-dialog .secondary-button")
    expect(dialog).not_to_be_visible()


def test_model_combobox_typing_replaces_prefilled_value(admin_page: Page):
    """Typing into a model combobox must replace the prefilled value.

    A configured model (or the optional-field default "None") pre-fills the
    combobox input; appending typed characters to it made filtering never
    match ("No matching models" on every query). The input must select its
    value on focus so the first keystroke replaces it.
    """
    admin_page.click('nav[aria-label="Admin views"] >> text=Model Config')
    combobox = admin_page.locator(
        '.model-combobox input[placeholder="Search or enter provider/model"]'
    )
    expect(combobox).to_be_visible()
    combobox.click()
    combobox.press_sequentially("deep")
    # Regression: the pre-filled value must be replaced, not appended to.
    expect(combobox).to_have_value("deep")
    listbox = combobox.locator(
        "xpath=ancestor::div[contains(@class, 'model-combobox')]"
        "//div[contains(@class, 'model-combobox-list')]"
    )
    expect(listbox).to_be_visible()


def test_optional_model_combobox_typing_replaces_none_default(admin_page: Page):
    """Optional model comboboxes default to "None"; typing must replace it."""
    admin_page.click('nav[aria-label="Admin views"] >> text=Model Config')
    combobox = admin_page.locator(
        '.model-combobox input[placeholder="Uses provider default"]'
    ).first
    expect(combobox).to_be_visible()
    combobox.click()
    combobox.press_sequentially("claude")
    expect(combobox).to_have_value("claude")
