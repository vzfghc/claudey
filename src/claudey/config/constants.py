"""Shared defaults used by config models and provider adapters."""

# HTTP client connect timeout (seconds). Keep aligned with README.md and .env.example.
HTTP_CONNECT_TIMEOUT_DEFAULT = 10.0

# Anthropic Messages API default when the client omits max_tokens.
ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS = 81920

# Whisper device value for NVIDIA NIM backend.
NIM_WHISPER_DEVICE = "nvidia_nim"

# Local provider id -> (settings env-var name, default status-check path).
# Env-var names must match config/settings.py's validation_alias for each field.
LOCAL_PROVIDER_PATHS: dict[str, tuple[str, str]] = {
    "lmstudio": ("LM_STUDIO_BASE_URL", "/models"),
    "llamacpp": ("LLAMACPP_BASE_URL", "/models"),
    "ollama": ("OLLAMA_BASE_URL", "/api/tags"),
}
