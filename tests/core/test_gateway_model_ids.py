import pytest

from claudey.core.gateway_model_ids import strip_context_window_suffix


@pytest.mark.parametrize("suffix", ["1m", "5m", "128k", "200k"])
def test_strips_context_window_suffix(suffix):
    assert (
        strip_context_window_suffix(f"deepseek-v4-flash[{suffix}]")
        == "deepseek-v4-flash"
    )


def test_returns_input_unchanged_when_no_suffix():
    assert strip_context_window_suffix("deepseek-v4-flash") == "deepseek-v4-flash"


def test_returns_empty_string_unchanged():
    assert strip_context_window_suffix("") == ""


def test_is_case_sensitive():
    assert (
        strip_context_window_suffix("deepseek-v4-flash[1M]") == "deepseek-v4-flash[1M]"
    )


def test_ignores_non_numeric_suffix():
    assert (
        strip_context_window_suffix("deepseek-v4-flash[1x]") == "deepseek-v4-flash[1x]"
    )


def test_ignores_suffix_not_at_end():
    assert (
        strip_context_window_suffix("deepseek-v4-flash[1m]-beta")
        == "deepseek-v4-flash[1m]-beta"
    )


def test_strips_only_one_trailing_suffix():
    assert (
        strip_context_window_suffix("deepseek-v4-flash[1m][1m]")
        == "deepseek-v4-flash[1m]"
    )


def test_leaves_rest_of_name_untouched():
    assert (
        strip_context_window_suffix("nvidia-nim/deepseek-v4-flash[1m]")
        == "nvidia-nim/deepseek-v4-flash"
    )
