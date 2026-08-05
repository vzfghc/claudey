"""Generate the Claudey app icon PNGs from the starburst mark.

Renders the same design as assets/claudey-icon.svg (the Anthropic starburst
in coral on a white rounded square with a hairline border) with Pillow at
every standard icon size. The center triangle of the logo path has the
opposite winding, so it is punched out as a hole with the background color.

Outputs assets/claudey-icon.png (512px master) and
assets/icons/claudey-icon-{512,256,128,64,32,16}.png.

Usage:
    uv run python scripts/generate_icons.py          # regenerate PNGs
    uv run python scripts/generate_icons.py --check  # verify files exist
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_DIR = ASSETS_DIR / "icons"
MASTER_ICON_PNG = ASSETS_DIR / "claudey-icon.png"
SOURCE_ICON_SVG = ASSETS_DIR / "claudey-icon.svg"

ICON_SIZES = (512, 256, 128, 64, 32, 16)
SUPERSAMPLE = 4

CORAL = "#D97757"
WHITE = "#FFFFFF"
BORDER = "#E7E5E4"

# Starburst geometry in the 24-unit logo space (matches the SVG paths).
_PETALS: tuple[tuple[tuple[float, float], ...], ...] = (
    ((13.827, 3.52), (17.43, 3.52), (24.0, 20.0), (20.397, 20.0)),
    (
        (6.569, 3.52),
        (10.336, 3.52),
        (16.906, 20.0),
        (13.232, 20.0),
        (11.889, 16.539),
        (5.017, 16.539),
        (3.673, 20.0),
        (0.0, 20.0),
    ),
)
_CENTER_HOLE: tuple[tuple[float, float], ...] = (
    (10.701, 13.479),
    (8.453, 7.687),
    (6.205, 13.48),
)

_STARBURST_HEIGHT = 20.0 - 3.52
_STARBURST_CENTER_X = 12.0
_STARBURST_CENTER_Y = 11.76
_STARBURST_FRACTION = 0.5625  # starburst height as a fraction of the icon
_CORNER_FRACTION = 0.2305
_BORDER_FRACTION = 0.0195


def _starburst_points(
    points: tuple[tuple[float, float], ...], canvas_size: int
) -> list[tuple[float, float]]:
    """Map logo-space coordinates into a canvas of the given size."""

    scale = canvas_size * _STARBURST_FRACTION / _STARBURST_HEIGHT
    offset_x = canvas_size / 2 - _STARBURST_CENTER_X * scale
    offset_y = canvas_size / 2 - _STARBURST_CENTER_Y * scale
    return [(x * scale + offset_x, y * scale + offset_y) for x, y in points]


def generate() -> int:
    """Render every PNG size (supersampled for smooth edges)."""

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required to generate icons. Install it with "
            "`uv pip install Pillow` (or `pip install Pillow`), then rerun."
        ) from exc

    def render_icon(size: int) -> Image.Image:
        canvas_size = size * SUPERSAMPLE
        image = Image.new("RGB", (canvas_size, canvas_size), WHITE)
        draw = ImageDraw.Draw(image)

        border = max(1, round(canvas_size * _BORDER_FRACTION))
        inset = border / 2
        draw.rounded_rectangle(
            [inset, inset, canvas_size - inset, canvas_size - inset],
            radius=round(canvas_size * _CORNER_FRACTION),
            fill=WHITE,
            outline=BORDER,
            width=border,
        )
        for petal in _PETALS:
            draw.polygon(_starburst_points(petal, canvas_size), fill=CORAL)
        draw.polygon(_starburst_points(_CENTER_HOLE, canvas_size), fill=WHITE)

        return image.resize((size, size), Image.Resampling.LANCZOS)

    ICON_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for size in ICON_SIZES:
        destination = ICON_DIR / f"claudey-icon-{size}.png"
        render_icon(size).save(destination)
        written.append(destination.name)
    MASTER_ICON_PNG.write_bytes((ICON_DIR / "claudey-icon-512.png").read_bytes())
    written.append(MASTER_ICON_PNG.name)
    print(f"wrote {len(written)} icons: {', '.join(written)}")
    return 0


def expected_assets() -> list[Path]:
    """The full icon asset set the repo must keep in sync."""

    return [
        SOURCE_ICON_SVG,
        MASTER_ICON_PNG,
        *[ICON_DIR / f"claudey-icon-{size}.png" for size in ICON_SIZES],
    ]


def verify() -> int:
    """Verify every expected icon asset exists without regenerating them."""

    missing = [
        path
        for path in expected_assets()
        if not path.is_file() or path.stat().st_size == 0
    ]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        print(
            f"missing app icons: {missing_text}\n"
            f"run `uv run python scripts/generate_icons.py` to regenerate",
            file=sys.stderr,
        )
        return 1
    print(f"all {len(expected_assets())} app icon assets present")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify expected icon files exist without regenerating them",
    )
    args = parser.parse_args()
    return verify() if args.check else generate()


if __name__ == "__main__":
    raise SystemExit(main())
