#!/usr/bin/env python3
"""Generate the 1280x640 GitHub social preview image.

Maintainer tool. Requires Pillow, which is why it lives in tools/ rather than in a
skill: bundled skill scripts must stay standard-library only.

    python tools/make_social_preview.py            # writes assets/social-preview.png
    python tools/make_social_preview.py --out x.png

GitHub has no API for the social preview, so upload the result by hand:
Settings > General > Social preview > Edit.

The image is what renders in every Reddit, X, Slack and Discord unfurl, so it is
designed to survive being scaled down: the title and the severity/evidence contract
stay legible at roughly a third of full size, and nothing important sits in small text.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("error: Pillow is required. Install it with `pip install Pillow`.")

W, H = 1280, 640

BG = "#0d1117"        # GitHub dark canvas
PANEL = "#161b22"
BORDER = "#30363d"
FG = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#7ee787"    # green, for the evidence path
SEV = "#ff7b72"       # red, for the severity label
BLUE = "#79c0ff"

TITLE = "Review Skills"
SUBTITLE = "Evidence-first code audits for any SKILL.md agent"

SKILLS = [
    "feature-audit", "security-audit", "test-gap-audit", "docs-sync-audit",
    "repo-health-audit", "feature-brainstorm", "pr-branch-summary",
]

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts"), Path("/Library/Fonts")]
SANS_BOLD = ["arialbd.ttf", "DejaVuSans-Bold.ttf", "Helvetica.ttc"]
SANS = ["arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"]
MONO = ["consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"]
MONO_BOLD = ["consolab.ttf", "DejaVuSansMono-Bold.ttf", "Menlo.ttc"]


def font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for directory in FONT_DIRS:
        for name in candidates:
            p = directory / name
            if p.is_file():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    continue
        # Also search one level down, which is how Linux font dirs are laid out.
        if directory.is_dir():
            for name in candidates:
                for hit in directory.rglob(name):
                    try:
                        return ImageFont.truetype(str(hit), size)
                    except OSError:
                        continue
    return ImageFont.load_default()


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the GitHub social preview image.")
    ap.add_argument("--out", default="assets/social-preview.png", help="Output PNG path.")
    args = ap.parse_args()

    # Auto-fit the title. It is the string most likely to be edited later, and a
    # longer name would otherwise run off the canvas with no warning.
    f_title = font(SANS_BOLD, 68)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    size = 68
    while size > 34 and probe.textlength(TITLE, font=f_title) > W - 62 * 2:
        size -= 2
        f_title = font(SANS_BOLD, size)
    f_sub = font(SANS, 30)
    f_chip = font(MONO, 23)
    f_code = font(MONO, 21)
    f_code_b = font(MONO_BOLD, 21)
    f_foot = font(SANS, 22)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # A single accent rule down the left edge, so the image reads as deliberate
    # rather than as a screenshot.
    d.rectangle([0, 0, 10, H], fill=ACCENT)

    x = 62
    d.text((x, 54), TITLE, font=f_title, fill=FG)
    d.text((x, 138), SUBTITLE, font=f_sub, fill=MUTED)

    # Skill name chips, wrapped to fit the width.
    cx, cy = x, 200
    for name in SKILLS:
        tw = d.textlength(name, font=f_chip)
        if cx + tw + 26 > W - 62:
            cx, cy = x, cy + 44
        d.rounded_rectangle([cx, cy, cx + tw + 26, cy + 36], radius=8,
                            fill=PANEL, outline=BORDER)
        d.text((cx + 13, cy + 7), name, font=f_chip, fill=BLUE)
        cx += tw + 26 + 10

    # The sample finding: this is the product, so it gets the most visual weight.
    py = cy + 66
    d.rounded_rectangle([x, py, W - 62, py + 172], radius=12, fill=PANEL, outline=BORDER)
    ty = py + 22
    d.text((x + 26, ty), "Security Audit: exports", font=f_code_b, fill=FG)
    ty += 38
    d.text((x + 26, ty), "1. ", font=f_code, fill=MUTED)
    d.text((x + 26 + d.textlength("1. ", font=f_code), ty), "P1:", font=f_code_b, fill=SEV)
    d.text((x + 26 + d.textlength("1. P1: ", font=f_code), ty),
           "Team members can request another team's export by ID.",
           font=f_code, fill=FG)
    ty += 32
    d.text((x + 26, ty), "   Abuse path: an authenticated user guesses an export ID.",
           font=f_code, fill=MUTED)
    ty += 32
    d.text((x + 26, ty), "   Evidence: ", font=f_code, fill=MUTED)
    d.text((x + 26 + d.textlength("   Evidence: ", font=f_code), ty),
           "app/api/exports.ts:88", font=f_code_b, fill=ACCENT)

    # The install command earns its place here: people read preview images without
    # clicking through, and it also fills what was otherwise dead vertical space.
    iy = py + 172 + 34
    cmd = "npx skills add specialone0007/review-skills"
    d.text((x, iy), "$", font=f_code_b, fill=MUTED)
    d.text((x + 24, iy), cmd, font=f_code_b, fill=FG)

    d.text((x, H - 50), "Every finding carries a severity and a line you can open.",
           font=f_foot, fill=MUTED)

    out = Path(args.out)
    if not out.is_absolute():
        out = Path(__file__).resolve().parent.parent / out
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print(f"{out}  {img.size[0]}x{img.size[1]}  {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
