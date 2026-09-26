"""Draw every generated panel on the profile, as SVG, into assets/.

Deliberately not github-readme-stats or any other shared instance: those run
on one public deployment that hits GitHub's API rate limit regularly, and when
it does, every card on every profile using it turns into a broken image. This
writes plain files into this repo instead, so a visitor loads static SVG from
raw.githubusercontent.com and there is nothing left to be down.

Everything is emitted twice, dark and light, and the README picks between them
with <picture media="(prefers-color-scheme: dark)">.

    python scripts/render.py            # all panels, both themes
    python scripts/render.py --demo     # synthetic data, for checking layout
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import gh

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"

W = 880  # GitHub renders README images up to roughly this wide

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

THEMES = {
    "dark": {
        "bg": "#0D1117", "surf": "#161B22", "border": "#2A3139",
        "ink": "#E6EDF3", "muted": "#8B949E", "amber": "#E8A33D",
        "ok": "#3FB950", "crit": "#F85149", "grid": "#1C2430",
    },
    "light": {
        "bg": "#FFFFFF", "surf": "#F6F8FA", "border": "#D1D9E0",
        "ink": "#1F2328", "muted": "#59636E", "amber": "#9A6700",
        "ok": "#1A7F37", "crit": "#CF222E", "grid": "#EAEEF2",
    },
}

# A monospace glyph is very close to 0.6em wide, which is the whole reason
# these panels use one: widths can be laid out without measuring anything.
EM = 0.63


def mw(text: str, size: float) -> float:
    return len(text) * size * EM


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, *, size=12, fill="#fff", weight=400, anchor="start",
        spacing=None, opacity=None) -> str:
    extra = ""
    if spacing:
        extra += ' letter-spacing="%s"' % spacing
    if opacity is not None:
        extra += ' opacity="%s"' % opacity
    return ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" font-weight="%s" '
            'fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, MONO, size, weight, fill, anchor, extra, esc(s)))


def box(x, y, w, h, *, fill, stroke=None, r=6) -> str:
    s = ' stroke="%s"' % stroke if stroke else ""
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" fill="%s"%s/>'
            % (x, y, w, h, r, fill, s))


def wrap(parts, w: int, h: int, label: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" '
            'height="%d" role="img" aria-label="%s">%s</svg>'
            % (w, h, w, h, esc(label), "".join(parts)))


def write(name: str, theme: str, body: str) -> None:
    path = ASSETS / ("%s-%s.svg" % (name, theme))
    path.write_text(body, encoding="utf-8")
    print("  %-22s %d KB" % (path.name, len(body) // 1024 or 1))


# --------------------------------------------------------------------------
# banner: service name, status, and 90 days of activity as uptime bars
# --------------------------------------------------------------------------

def banner(theme: str, prof: dict, days) -> str:
    c = THEMES[theme]
    H, PAD = 168, 26
    p = [box(0.5, 0.5, W - 1, H - 1, fill=c["surf"], stroke=c["border"])]

    p.append(txt(PAD, 44, "svc/", size=21, fill=c["muted"], weight=600))
    p.append(txt(PAD + mw("svc/", 21), 44, prof["service"], size=21,
                 fill=c["ink"], weight=600))
    sub = "%s  ·  %s  ·  %s" % (prof["role"], prof["location"], prof["education"])
    p.append(txt(PAD, 66, sub, size=12, fill=c["muted"]))

    # status pill, right-aligned
    label = "OPERATIONAL"
    pw = mw(label, 11) + 40
    px = W - PAD - pw
    p.append(box(px, 28, pw, 24, fill="none", stroke=c["ok"], r=12))
    p.append('<circle cx="%.1f" cy="40" r="3.5" fill="%s"/>' % (px + 15, c["ok"]))
    p.append(txt(px + 25, 44, label, size=11, fill=c["ok"], weight=600, spacing="0.09em"))

    # Uptime bars. Height is that day's contributions against the window peak;
    # colour follows the status-page convention, so a quiet day reads as an
    # incident rather than quietly disappearing into the background.
    window = days[-90:]
    peak = max([v for _, v in window] + [1])
    top, tall, gap = 92, 46, 2.0
    n = len(window)
    bw = (W - 2 * PAD - gap * (n - 1)) / n
    total = sum(v for _, v in days)
    base = top + tall + 20

    # An all-zero window means either nothing was fetched or nothing was
    # *attributed* -- see the warning in main(). Either way, 90 red bars would
    # say something false about the person, so the empty state is flat, grey,
    # and honest about being empty.
    if sum(v for _, v in window) == 0:
        for i in range(n):
            p.append('<rect x="%.2f" y="%.2f" width="%.2f" height="6" rx="1" fill="%s"/>'
                     % (PAD + i * (bw + gap), top + tall - 6, bw, c["grid"]))
        p.append(txt(W / 2, base, "no public contributions in this window",
                     size=10, fill=c["muted"], anchor="middle"))
        return wrap(p, W, H, "%s, service banner" % prof["name"])

    active = 0
    for i, (_, v) in enumerate(window):
        frac = v / peak
        if v == 0:
            h, fill = 6.0, c["grid"]
        else:
            active += 1
            h = max(9.0, tall * (frac ** 0.55))
            fill = c["ok"] if frac >= 0.6 else c["amber"]
        p.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="1" fill="%s"/>'
                 % (PAD + i * (bw + gap), top + tall - h, bw, h, fill))

    p.append(txt(PAD, base, "90 days ago", size=10, fill=c["muted"]))
    win_total = sum(v for _, v in window)
    mid = "%d contributions  ·  %d active day%s  ·  %s this year" % (
        win_total, active, "" if active == 1 else "s", format(total, ","))
    p.append(txt(W / 2, base, mid, size=10, fill=c["muted"], anchor="middle"))
    p.append(txt(W - PAD, base, "today", size=10, fill=c["muted"], anchor="end"))

    return wrap(p, W, H, "%s, service banner with 90 days of activity as uptime bars"
                % prof["name"])


# --------------------------------------------------------------------------
# metrics: four stat panels
# --------------------------------------------------------------------------

def spark(shape: str, x: float, y: float, w: float, h: float, c: dict):
    """One small figure per metric, shaped like the change it describes
    rather than a generic sparkline stamped four times."""
    a, ok = c["amber"], c["ok"]
    if shape == "drop":
        d = ("M%.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f"
             % (x, y + h * .12, x + w * .25, y + h * .12, x + w * .38, y + h * .28,
                x + w * .5, y + h * .55, x + w * .64, y + h * .82,
                x + w * .82, y + h * .9, x + w, y + h * .92))
        return ['<path d="%s L%.1f %.1f L%.1f %.1f Z" fill="%s" opacity="0.14"/>'
                % (d, x + w, y + h, x, y + h, a),
                '<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (d, a),
                '<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (x + w, y + h * .92, ok)]
    if shape == "bars":
        vals = [.22, .34, .18, .58, .42, .80, .52, .68, 1.0, .46]
        step = w / len(vals)
        bw = step * 0.62
        out = []
        for i, v in enumerate(vals):
            bh = max(3.0, h * v)
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1" fill="%s"/>'
                       % (x + i * step, y + h - bh, bw, bh, ok if v == 1.0 else a))
        return out
    if shape == "converge":
        out = []
        for i in range(5):
            y0 = y + h * (i / 4.0)
            out.append('<path d="M%.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f" fill="none" '
                       'stroke="%s" stroke-width="1.4" opacity="0.6"/>'
                       % (x, y0, x + w * .45, y0, x + w * .55, y + h / 2,
                          x + w - 4, y + h / 2, a))
        out.append('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>' % (x + w - 3, y + h / 2, ok))
        return out
    # toggles
    out = []
    tw, gap = w / 4.6, w / 22
    for i in range(4):
        tx = x + i * (tw + gap)
        on = i != 2
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" '
                   'opacity="%s" stroke="%s" stroke-width="1"/>'
                   % (tx, y + h * .28, tw, h * .44, h * .22, a, 0.2 if on else 0.08, a))
        kx = tx + tw - h * .22 if on else tx + h * .22
        out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                   % (kx, y + h * .5, h * .16, ok if on else a))
    return out


def metrics(theme: str, items) -> str:
    c = THEMES[theme]
    GAP = 12
    PW, PH = (W - GAP) / 2, 156
    H = int(PH * 2 + GAP)
    p = []
    for i, m in enumerate(items[:4]):
        x = (i % 2) * (PW + GAP)
        y = (i // 2) * (PH + GAP)
        p.append(box(x + .5, y + .5, PW - 1, PH - 1, fill=c["surf"], stroke=c["border"]))
        p.append(txt(x + 18, y + 26, m["label"].upper(), size=10, fill=c["muted"],
                     spacing="0.09em"))
        p.append(txt(x + 18, y + 62, m["value"], size=29, fill=c["amber"], weight=600))
        p.append(txt(x + 18, y + 82, m["unit"], size=11.5, fill=c["ink"]))
        p.extend(spark(m["shape"], x + PW - 152, y + 36, 132, 46, c))
        p.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (x + 18, y + PH - 36, x + PW - 18, y + PH - 36, c["border"]))
        p.append(txt(x + 18, y + PH - 16, "%s   →   %s" % (m["before"], m["after"]),
                     size=10.5, fill=c["muted"]))
    return wrap(p, W, H, "Four production changes, each as a before and an after")


# --------------------------------------------------------------------------
# stack: filled = shipped to production, dashed = studied
# --------------------------------------------------------------------------

def stack(theme: str, groups) -> str:
    c = THEMES[theme]
    PAD, SIZE, TH, TG = 22, 11.5, 24, 6
    p = []
    y = 34
    for g in groups:
        p.append(txt(PAD, y, g["group"].upper(), size=10, fill=c["muted"], spacing="0.09em"))
        y += 16
        x = PAD
        for it in g["items"]:
            tw = mw(it["name"], SIZE) + 20
            if x + tw > W - PAD:
                x, y = PAD, y + TH + TG
            if it["prod"]:
                p.append(box(x, y, tw, TH, fill=c["amber"], r=3))
                p.append(txt(x + 10, y + 16.5, it["name"], size=SIZE, fill=c["bg"], weight=600))
            else:
                p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="3" fill="none" '
                         'stroke="%s" stroke-dasharray="3 3"/>'
                         % (x + .5, y + .5, tw - 1, TH - 1, c["border"]))
                p.append(txt(x + 10, y + 16.5, it["name"], size=SIZE, fill=c["muted"]))
            x += tw + TG
        y += TH + 22
    # Legend, drawn rather than written, so the two states are shown in the
    # same form the tags above use.
    ly = y - 6
    p.append(box(PAD, ly, 18, 11, fill=c["amber"], r=2))
    p.append(txt(PAD + 26, ly + 10, "shipped to production", size=10, fill=c["muted"]))
    lx = PAD + 26 + mw("shipped to production", 10) + 26
    p.append('<rect x="%.1f" y="%.1f" width="18" height="11" rx="2" fill="none" '
             'stroke="%s" stroke-dasharray="3 3"/>' % (lx, ly, c["border"]))
    p.append(txt(lx + 26, ly + 10, "studied or prototyped", size=10, fill=c["muted"]))
    H = int(y + 18)
    return wrap([box(.5, .5, W - 1, H - 1, fill=c["surf"], stroke=c["border"])] + p, W, H,
                "Tools, split by whether they have been run in production")


# --------------------------------------------------------------------------
# traces: the contribution calendar
# --------------------------------------------------------------------------

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def traces(theme: str, days) -> str:
    c = THEMES[theme]
    GAP, LEFT, TOP, RIGHT = 3, 52, 52, 24
    days = days[-371:]
    # pad back to the Sunday before the window so the columns are real weeks
    lead = (days[0][0].weekday() + 1) % 7
    cells = [None] * lead + list(days)
    weeks = (len(cells) + 6) // 7
    peak = max([v for _, v in days] + [1])

    # Size the cell to the columns actually present. A year is 53 or 54 weeks
    # depending on where it starts, and a fixed cell overflows on the long one.
    CELL = min(13, int((W - LEFT - RIGHT + GAP) / weeks) - GAP)
    H = TOP + 7 * (CELL + GAP) + 36
    p = [box(.5, .5, W - 1, H - 1, fill=c["surf"], stroke=c["border"])]

    seen = set()
    for wi in range(weeks):
        for di in range(7):
            idx = wi * 7 + di
            if idx >= len(cells) or cells[idx] is None:
                continue
            d, v = cells[idx]
            x = LEFT + wi * (CELL + GAP)
            y = TOP + di * (CELL + GAP)
            if v == 0:
                fill, op = c["grid"], 1.0
            else:
                fill, op = c["amber"], 0.3 + 0.7 * min(1.0, (v / peak) ** 0.45)
            p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2.5" fill="%s" opacity="%.2f"/>'
                     % (x, y, CELL, CELL, fill, op))
            if di == 0 and d.day <= 7 and d.month not in seen:
                seen.add(d.month)
                p.append(txt(x, TOP - 10, MONTHS[d.month - 1], size=10, fill=c["muted"]))

    for di, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        p.append(txt(LEFT - 10, TOP + di * (CELL + GAP) + 10, lab, size=10,
                     fill=c["muted"], anchor="end"))

    total = sum(v for _, v in days)
    title = ("awaiting the first refresh" if total == 0
             else "%s contributions in the last year" % format(total, ","))
    p.append(txt(LEFT, 28, title, size=12,
                 fill=c["muted"] if total == 0 else c["ink"], weight=600))

    # legend, laid out right to left from the panel edge
    p.append(txt(W - 24, H - 14, "more", size=10, fill=c["muted"], anchor="end"))
    for i in range(5):
        x = W - 24 - mw("more", 10) - 8 - (5 - i) * 14
        fill = c["grid"] if i == 0 else c["amber"]
        op = 1.0 if i == 0 else 0.3 + 0.7 * (i / 4.0)
        p.append('<rect x="%.1f" y="%d" width="10" height="10" rx="2" fill="%s" opacity="%.2f"/>'
                 % (x, H - 23, fill, op))
    p.append(txt(W - 24 - mw("more", 10) - 8 - 5 * 14 - 6, H - 14, "less",
                 size=10, fill=c["muted"], anchor="end"))

    return wrap(p, W, H, "Contribution calendar, %d contributions in the last year" % total)


# --------------------------------------------------------------------------

def demo_days():
    """Plausible synthetic activity, for checking layout without a token."""
    import random
    rng = random.Random(20260926)
    today = date.today()
    out = []
    for i in range(370, -1, -1):
        d = today - timedelta(days=i)
        base = 0.35 if d.weekday() >= 5 else 1.0
        streak = 1.8 if (i // 30) % 3 == 0 else 1.0
        out.append((d, max(0, int(rng.gauss(4 * base * streak, 3)))))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true", help="synthetic activity, nothing fetched")
    args = ap.parse_args()

    prof = json.loads((DATA / "profile.json").read_text(encoding="utf-8"))
    mets = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))
    tools = json.loads((DATA / "stack.json").read_text(encoding="utf-8"))

    if args.demo:
        days, source = demo_days(), "demo"
    else:
        days, source = gh.calendar(prof["username"])
    print("activity source: %s  (%d days)" % (source, len(days)))
    if source == "empty":
        print("  ! no token and github.com unreachable - panels render flat")
        print("  ! the refresh workflow fills them in on its first run")

    year_total = sum(v for _, v in days)
    if source != "empty" and year_total < 150:
        print("  ! only %d contributions attributed in the last year." % year_total)
        print("  ! repos here were pushed in months the graph shows as empty, which")
        print("  ! means commits are authored with an email GitHub cannot match to")
        print("  ! the account. Check: Settings > Emails, and git config user.email.")
        print("  ! Also: Settings > Profile > include private contributions.")

    ASSETS.mkdir(exist_ok=True)
    for theme in THEMES:
        print("%s:" % theme)
        write("banner", theme, banner(theme, prof, days))
        write("metrics", theme, metrics(theme, mets))
        write("stack", theme, stack(theme, tools))
        write("traces", theme, traces(theme, days))


if __name__ == "__main__":
    main()
