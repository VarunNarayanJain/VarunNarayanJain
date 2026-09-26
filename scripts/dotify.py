"""Turn a photograph into a dot-matrix SVG that scans itself in, row by row.

Every pixel of a downscaled copy becomes one <circle>. Brightness sets the
radius, so the picture is carried by dot size rather than by colour, and it
survives being shown at 300px on a GitHub profile.

The reveal is CSS keyframes inside the SVG with a per-row animation-delay.
GitHub serves the file through its image proxy into an <img>, and CSS that
lives inside an SVG document still runs there -- script and external
stylesheets do not, which is why neither is used.

    python scripts/dotify.py public/varun.jpg -o assets/portrait \
        --cols 104 --crop 0.18,0.02,0.84,0.70 --equalize
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# Shadow -> mid -> highlight. Duotone keeps the portrait inside the page's
# palette instead of dragging a second colour scheme in with it.
RAMPS = {
    "amber": ((0x14, 0x1E, 0x33), (0xC2, 0x6F, 0x25), (0xF6, 0xCC, 0x82)),
    "mono":  ((0x1A, 0x1F, 0x27), (0x8B, 0x94, 0x9E), (0xE6, 0xED, 0xF3)),
}


def ramp(t: np.ndarray, stops) -> np.ndarray:
    """Piecewise-linear 3-stop colour ramp over t in [0, 1]."""
    lo, mid, hi = (np.array(s, dtype=float) for s in stops)
    t = t[..., None]
    lower = lo + (mid - lo) * (t / 0.5)
    upper = mid + (hi - mid) * ((t - 0.5) / 0.5)
    return np.where(t < 0.5, lower, upper)


def build(src: Path, out: Path, cols: int, crop, equalize: bool,
          detail: float, floor: float, colour: str, cell: int = 10) -> Path:
    img = Image.open(src).convert("RGB")
    w, h = img.size

    if crop:
        x0, y0, x1, y1 = crop
        img = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))

    rows = max(1, round(cols * img.height / img.width))
    small = img.resize((cols, rows), Image.LANCZOS)

    grey = ImageOps.equalize(small.convert("L")) if equalize else small.convert("L")
    lum = np.asarray(grey, dtype=float) / 255.0

    if colour == "photo":
        rgb = np.asarray(small, dtype=float)
    else:
        rgb = ramp(lum, RAMPS[colour])

    r_max = cell / 2.0
    radii = r_max * np.clip(lum, 0, 1) ** detail

    width, height = cols * cell, rows * cell
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="Dot-matrix portrait of Varun Narayan Jain">'
    ]

    # One keyframe, one class per row. Rows land 25ms apart, so a 100-row
    # portrait finishes assembling in about two and a half seconds.
    css = ["@keyframes dm{from{opacity:0}to{opacity:1}}",
           ".rw{animation:dm .45s ease-out both}",
           "@media(prefers-reduced-motion:reduce){.rw{animation:none}}"]
    css += [f".r{i}{{animation-delay:{i * 0.025:.3f}s}}" for i in range(rows)]
    parts.append("<style>" + "".join(css) + "</style>")

    drawn = 0
    for y in range(rows):
        dots = []
        for x in range(cols):
            r = radii[y, x]
            if r < floor:
                continue  # background stays empty, which is what reads as depth
            cr, cg, cb = (int(v) for v in rgb[y, x])
            dots.append(
                f'<circle cx="{x * cell + r_max:.0f}" cy="{y * cell + r_max:.0f}" '
                f'r="{r:.2f}" fill="#{cr:02x}{cg:02x}{cb:02x}"/>'
            )
        if not dots:
            continue
        drawn += len(dots)
        parts.append(f'<g class="rw r{y}">' + "".join(dots) + "</g>")

    parts.append("</svg>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    print(f"{out.name}: {cols}x{rows} grid, {drawn} dots, {out.stat().st_size // 1024} KB")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("-o", "--out", type=Path, required=True, help="path without extension")
    p.add_argument("--cols", type=int, default=104)
    p.add_argument("--crop", type=str, default=None, help="x0,y0,x1,y1 as fractions")
    p.add_argument("--equalize", action="store_true")
    p.add_argument("--detail", type=float, default=0.62, help="lower = fuller dots")
    p.add_argument("--floor", type=float, default=0.55, help="skip dots smaller than this")
    p.add_argument("--colour", choices=("amber", "mono", "photo"), default="amber")
    a = p.parse_args()

    crop = tuple(float(v) for v in a.crop.split(",")) if a.crop else None
    build(a.source, a.out.with_suffix(".svg"), a.cols, crop,
          a.equalize, a.detail, a.floor, a.colour)


if __name__ == "__main__":
    main()
