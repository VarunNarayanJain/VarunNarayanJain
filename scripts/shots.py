"""Normalise project screenshots to one aspect ratio.

The /deployments row is a three-column table, and a table cell is as tall as
its tallest content. The source screenshots run from 0.79 (a phone screenshot,
portrait) to 2.17 (a wide dashboard), so dropping them in raw makes one column
tower over the other two and the row stops reading as a set.

GitHub markdown has no CSS, so there is no object-fit to reach for. Instead
every card image is cropped to 16:10 here and committed, which is the same
crop the portfolio site does at render time.

    python scripts/shots.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "photos"
OUT = ROOT / "assets" / "cards"

RATIO = 16 / 10
WIDTH = 1200

# (file, x anchor, y anchor) as fractions of the slack being cropped away.
# 0 keeps the left/top edge, 1 the right/bottom, 0.5 centres.
CARDS = [
    # A tall phone screenshot. Anchored past the header so the crop lands on
    # the tender match itself rather than the contact name.
    ("gem-telegram.png", 0.5, 0.30),
    # Nearly 16:10 already; nudged down to keep the heatmap legend in frame.
    ("retail-heatmap.png", 0.5, 0.30),
    # Ultra-wide. Anchored right of centre so the headline survives the crop,
    # at the cost of the logo in the far-left corner.
    ("aews-dashboard.png", 0.58, 0.0),
]


def crop_to_ratio(im: Image.Image, ax: float, ay: float) -> Image.Image:
    w, h = im.size
    if w / h > RATIO:
        new_w = round(h * RATIO)
        x = round((w - new_w) * ax)
        return im.crop((x, 0, x + new_w, h))
    new_h = round(w / RATIO)
    y = round((h - new_h) * ay)
    return im.crop((0, y, w, y + new_h))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, ax, ay in CARDS:
        im = Image.open(SRC / name).convert("RGB")
        card = crop_to_ratio(im, ax, ay)
        card = card.resize((WIDTH, round(WIDTH / RATIO)), Image.LANCZOS)
        dest = OUT / name
        card.save(dest, optimize=True)
        print("  %-24s %s -> %s  %d KB"
              % (name, im.size, card.size, dest.stat().st_size // 1024))


if __name__ == "__main__":
    main()
