"""Generate assets/profile.svg: the wordmark, and one line per day of the last year.

No fonts and no third-party services. The letters are built from arcs and
stems, the strip is the contribution calendar, and the colours follow the
viewer's light/dark setting.
"""
import json
import math
import os
import sys
import urllib.request
from datetime import date

USER = os.environ.get("GH_USER", "nanjjang")
OUT = "assets/profile.svg"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]["user"]


def n(v):
    """Short number for SVG attributes."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ── wordmark ────────────────────────────────────────────────────────────────
# Monoline letters on one bowl radius. y grows downward; the bowl's centre
# line touches y=0 (x-height) and y=2R (baseline).
R = 44.0          # bowl radius, centre line
SW = 24.0         # stroke width
GAP = 22.0        # space between two straight sides
TOP = -SW / 2     # where a stem starts, level with the top of a bowl
BOT = 2 * R + SW / 2
DESC = 2 * R + 1.2 * R            # lowest point of j and g
DOT_R = SW * 0.58
DOT_Y = TOP - SW * 0.55 - DOT_R

BOWL = f"M{n(2*R)},{n(R)}A{n(R)},{n(R)} 0 1 0 0,{n(R)}A{n(R)},{n(R)} 0 1 0 {n(2*R)},{n(R)}"


def hook():
    """Right stem of g, running down into the tail."""
    y0 = DESC - SW / 2 - R
    a = math.radians(125)
    ex, ey = R + R * math.cos(a), y0 + R * math.sin(a)
    return f"M{n(2*R)},{n(TOP)}V{n(y0)}A{n(R)},{n(R)} 0 0 1 {n(ex)},{n(ey)}"


LETTERS = {
    # name: (visual width, left side is round?, stroke paths)
    "n": (2 * R + SW, False, [f"M0,{n(TOP)}V{n(BOT)}", f"M0,{n(R)}A{n(R)},{n(R)} 0 0 1 {n(2*R)},{n(R)}V{n(BOT)}"]),
    "a": (2 * R + SW, True, [BOWL, f"M{n(2*R)},{n(TOP)}V{n(BOT)}"]),
    "g": (2 * R + SW, True, [BOWL, hook()]),
    "j": (SW, False, [f"M0,{n(TOP)}V{n(DESC)}"]),
}


def wordmark(word):
    parts, dots, x = [], [], 0.0
    for i, ch in enumerate(word):
        width, _, paths = LETTERS[ch]
        ox = x + SW / 2
        for k, d in enumerate(paths):
            delay = 0.07 * i + 0.12 * k
            parts.append(
                f'<path class="s" pathLength="1" style="animation-delay:{delay:.2f}s" '
                f'transform="translate({n(ox)})" d="{d}"/>'
            )
        if ch == "j":
            dots.append(
                f'<circle class="o" style="animation-delay:{0.07*i+0.75:.2f}s" '
                f'cx="{n(ox)}" cy="{n(DOT_Y)}" r="{n(DOT_R)}"/>'
            )
        x += width
        if i + 1 < len(word):
            x += GAP * (0.8 if LETTERS[word[i + 1]][1] else 1)
    return "".join(parts + dots), x


# ── year strip ──────────────────────────────────────────────────────────────
STRIP_H = 104.0
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def strip(days, width, base, height):
    pitch = width / len(days)
    bw = pitch * 0.66
    top = max(d["contributionCount"] for d in days) or 1
    out = [
        f'<line class="e" x1="{n((pitch-bw)/2)}" x2="{n(width)}" y1="{n(base-0.8)}" y2="{n(base-0.8)}" '
        f'stroke-dasharray="{n(bw)} {n(pitch-bw)}"/>'
    ]
    for i, d in enumerate(days):
        c = d["contributionCount"]
        x = i * pitch + (pitch - bw) / 2
        if c:
            # log scale: a quiet day still shows, a huge one does not flatten the rest
            h = max(3.0, height * math.log1p(c) / math.log1p(top))
            out.append(
                f'<rect class="d" style="animation-delay:{0.9+i*0.003:.3f}s" '
                f'x="{n(x)}" y="{n(base-h)}" width="{n(bw)}" height="{n(h)}"/>'
            )
        day = date.fromisoformat(d["date"])
        if day.day == 1 and x < width - 30:
            out.append(f'<text class="m" x="{n(x)}" y="{n(base+20)}">{MONTHS[day.month - 1]}</text>')
    return "".join(out)


def build(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    active = sum(1 for d in days if d["contributionCount"])
    span = f'{days[0]["date"][:7].replace("-", ".")} – {days[-1]["date"][:7].replace("-", ".")}'

    mark, width = wordmark(USER)
    base = DESC + 40 + STRIP_H       # strip baseline
    y0 = DOT_Y - DOT_R - 6
    y1 = base + 56

    style = (
        "svg{--ink:#1f2328;--mute:#59636e;--faint:#d1d9e0;--hot:#f0501a}"
        "@media(prefers-color-scheme:dark){svg{--ink:#f0f6fc;--mute:#9198a1;--faint:#3d444d;--hot:#ff7a45}}"
        ".s{fill:none;stroke:var(--ink);stroke-width:%s;stroke-dasharray:1;animation:draw .8s cubic-bezier(.6,0,.2,1) both}"
        ".o{fill:var(--hot);transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.3,1.5,.5,1) both}"
        ".d{fill:var(--ink);transform-box:fill-box;transform-origin:50%% 100%%;animation:rise .6s cubic-bezier(.2,.7,.2,1) both}"
        ".e{stroke:var(--faint);stroke-width:1.6}"
        "text{fill:var(--mute);font-size:12.5px}"
        ".m{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.06em}"
        ".c{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR','Malgun Gothic',sans-serif;font-size:14px}"
        "@keyframes draw{from{stroke-dashoffset:1}}"
        "@keyframes pop{from{transform:scale(0)}}"
        "@keyframes rise{from{transform:scaleY(0)}}"
        "@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
    ) % n(SW)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {n(y0)} {n(width)} {n(y1-y0)}" '
        f'role="img" aria-label="{USER}. {cal["totalContributions"]} contributions in the last year.">'
        f"<style>{style}</style>"
        f"{mark}"
        f"{strip(days, width, base, STRIP_H)}"
        f'<text class="c" x="0" y="{n(base+47)}">하루에 선 하나 · {span}</text>'
        f'<text class="c" x="{n(width)}" y="{n(base+47)}" text-anchor="end">'
        f'{cal["totalContributions"]:,} contributions · {active}일</text>'
        "</svg>\n"
    )


if __name__ == "__main__":
    # `python scripts/profile.py saved.json` renders from a saved API response.
    user = json.load(open(sys.argv[1]))["data"]["user"] if len(sys.argv) > 1 else fetch()
    os.makedirs("assets", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build(user))
