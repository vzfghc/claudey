"""Vendor provider logos from the local @lobehub/icons package into admin_static.

Writes one standalone monochrome SVG per PROVIDER_CATALOG key into
src/claudey/api/admin_static/logos/, plus anthropic.svg for the brand mark.
Every icon is filled with currentColor so the admin CSS controls its tint.

Source: the npm package @lobehub/icons, which the repo keeps vendored in
node_modules for offline icon extraction. Each brand's Mono component is a
React SVG whose compiled form contains one or more <path d="..."/> entries.

Usage:
    uv run python scripts/fetch_provider_logos.py          # regenerate
    uv run python scripts/fetch_provider_logos.py --check  # verify files exist

Provider ids are derived from claudey.config.provider_catalog.PROVIDER_CATALOG
so the logo set can never drift from the providers the server actually knows.
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = PROJECT_ROOT / "src" / "claudey" / "api" / "admin_static" / "logos"
ICONS_ROOT = PROJECT_ROOT / "node_modules" / "@lobehub" / "icons" / "es"

# provider_id -> LobeHub component directory name. None means the provider has
# no clean LobeHub source and gets a hand-drawn letter-chip fallback.
PROVIDER_LOBEHUB_BRAND: dict[str, str | None] = {
    "nvidia_nim": "Nvidia",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "azure_openai": "AzureAI",
    "open_router": "OpenRouter",
    "gemini": "Gemini",
    "vertex": "VertexAI",
    "deepseek": "DeepSeek",
    "mistral": "Mistral",
    "mistral_codestral": "Mistral",
    "opencode": "OpenCode",
    "opencode_go": "OpenCode",
    "vercel": "Vercel",
    "bedrock": "Bedrock",
    "huggingface": "HuggingFace",
    "cohere": "Cohere",
    "github_models": "Github",
    "wafer": None,
    "pecut": None,
    "novita": None,
    "qwen": None,
    "routeway": None,
    "scaleway": None,
    "kimi": "Kimi",
    "kimi_code": "Kimi",
    "kilo": "KiloCode",
    "minimax": "Minimax",
    "cerebras": "Cerebras",
    "groq": "Groq",
    "sambanova": "SambaNova",
    "fireworks": "Fireworks",
    "cloudflare": "Cloudflare",
    "zai": "ZAI",
    "ollama_cloud": "Ollama",
    "lmstudio": "LmStudio",
    "llamacpp": "LlamaIndex",
    "ollama": "Ollama",
}

BRAND_MARK_IDS = ("anthropic",)

_SVG_HEADER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">\n'
)
_SVG_FOOTER = "</svg>\n"
_PATH_RE = re.compile(r'\bd:\s*"([^"]*)"')

WAFER_FALLBACK_SVG = (
    _SVG_HEADER
    + '  <rect x="2" y="2" width="20" height="20" rx="6"/>\n'
    + '  <text x="12" y="16" text-anchor="middle" fill="white" font-size="12" font-weight="700">W</text>\n'
    + _SVG_FOOTER
)


def expected_logo_ids() -> list[str]:
    """Provider ids from the live catalog, falling back to the static map."""
    try:
        from claudey.config.provider_catalog import PROVIDER_CATALOG

        catalog_ids = list(PROVIDER_CATALOG.keys())
    except ImportError:
        catalog_ids = list(PROVIDER_LOBEHUB_BRAND.keys())
    unknown = [pid for pid in catalog_ids if pid not in PROVIDER_LOBEHUB_BRAND]
    if unknown:
        raise SystemExit(
            f"no LobeHub mapping for provider ids: {', '.join(sorted(unknown))}"
        )
    return catalog_ids


def extract_path_data(component_dir: Path) -> list[str]:
    """Return the d values of every <path> in a brand's compiled Mono component."""
    mono_path = component_dir / "components" / "Mono.js"
    source = mono_path.read_text(encoding="utf-8")
    matches = _PATH_RE.findall(source)
    if not matches:
        raise SystemExit(
            f"no path data found in {mono_path}; LobeHub Mono format may have changed"
        )
    return matches


def build_svg(path_data: list[str]) -> str:
    lines = [_SVG_HEADER]
    lines.extend(f'  <path d="{data}"/>\n' for data in path_data)
    lines.append(_SVG_FOOTER)
    return "".join(lines)


def generate(provider_id: str) -> str:
    brand = PROVIDER_LOBEHUB_BRAND.get(provider_id)
    if brand is None:
        return WAFER_FALLBACK_SVG
    component_dir = ICONS_ROOT / brand
    if not component_dir.is_dir():
        raise SystemExit(
            f"LobeHub component {brand!r} for {provider_id!r} missing at {component_dir}; "
            "reinstall node_modules/@lobehub/icons or add a letter-chip fallback"
        )
    return build_svg(extract_path_data(component_dir))


def regenerate() -> int:
    if not ICONS_ROOT.is_dir():
        raise SystemExit(
            f"@lobehub/icons not found at {ICONS_ROOT}; run `npm install` first"
        )
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for provider_id in expected_logo_ids() + list(BRAND_MARK_IDS):
        (LOGO_DIR / f"{provider_id}.svg").write_text(
            generate(provider_id), encoding="utf-8"
        )
        written.append(provider_id)
    print(f"wrote {len(written)} logos to {LOGO_DIR}: {', '.join(written)}")
    return 0


def verify() -> int:
    missing: list[str] = []
    for provider_id in expected_logo_ids() + list(BRAND_MARK_IDS):
        logo = LOGO_DIR / f"{provider_id}.svg"
        if not logo.is_file() or logo.stat().st_size == 0:
            missing.append(provider_id)
    if missing:
        missing_text = ", ".join(sorted(missing))
        print(
            f"missing provider logos: {missing_text}\n"
            f"run `uv run python scripts/fetch_provider_logos.py` to regenerate",
            file=sys.stderr,
        )
        return 1
    print(
        f"all {len(expected_logo_ids()) + len(BRAND_MARK_IDS)} provider logos present"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify expected logo files exist without regenerating them",
    )
    args = parser.parse_args()
    return verify() if args.check else regenerate()


if __name__ == "__main__":
    raise SystemExit(main())
