#!/usr/bin/env python3
"""Generate the animated SVG pieces of the profile (stdlib only):

    assets/orbit.svg    — tech stack orbiting a glowing core, in (fake-but-exact) 3D
    assets/wave.svg     — a perspective field of particles rippling like an ocean
    assets/divider.svg  — thin particle-wave section divider (transparent, works on light + dark)

No JavaScript runs inside README images, so the 3D motion is built from pure maths:
an element moving along cos(ωt) is just a CSS animation that eases between -a and +a with
cubic-bezier(.37,0,.63,1) (≈ easeInOutSine) in `alternate` mode. A circular orbit seen at an
angle is then two such animations (x and y, 90° apart); depth is a third one driving
scale + opacity in phase with the "front" half of the orbit. Phases are baked into negative
animation-delays.

    python scripts/gen_svgs.py
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICONS = json.loads((Path(__file__).with_name("orbit-icons.json")).read_text())
MONO = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
EASE = "cubic-bezier(.37,0,.63,1)"  # easeInOutSine → sin/cos motion when alternating
# prefers-reduced-motion: freeze (don't remove) the animations — the baked phases keep every element where it belongs
REDUCED = "@media (prefers-reduced-motion:reduce){*{animation-play-state:paused!important}}"


def f(x: float, n: int = 2) -> str:
    s = f"{x:.{n}f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


# ═════════════════════════════════ orbit.svg ═════════════════════════════════
# brand colours, lightened where the official one disappears on a dark background
CHIPS = {
    "python": "#5ba2e0", "fastapi": "#1fc7b6", "typescript": "#4a97ef", "svelte": "#ff5a2a",
    "html5": "#ff6a3d", "css": "#b07be0", "swift": "#ff6a50", "unity": "#e8eefc",
    "git": "#ff5b4a", "github": "#e6edf3", "csharp": "#b56ddb",
}
# (a, b, tilt°, period s, direction, [(icon, phase°) …])   a/b = orbit radii of the projected ellipse
RINGS = [
    (132, 40, -14, 15, +1, [("python", 0), ("fastapi", 120), ("git", 240)]),
    (226, 70, 7, 24, -1, [("svelte", 20), ("typescript", 110), ("html5", 200), ("css", 290)]),
    (332, 102, -5, 36, +1, [("swift", 35), ("unity", 125), ("csharp", 215), ("github", 305)]),
]
CSHARP = (  # simple-icons dropped C#, so draw a clean hexagon + "C#" (24×24 box)
    '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">'
    '<path stroke-width="1.7" d="M12 1.6 21 6.8v10.4L12 22.4 3 17.2V6.8z"/>'
    '<path stroke-width="1.9" d="M11.6 9.2a3.4 3.4 0 1 0 0 5.6"/>'
    '<path stroke-width="1.1" d="M14.3 9v6M16.6 9v6M13.2 10.7h4.5M13.2 13.3h4.5"/></g>'
)


def orbit_offsets(phi0: float, period: float, direction: int) -> tuple[float, float]:
    """Return (x_offset, y_offset) in seconds so that x=a·cosφ, y=b·sinφ with φ=d·ωt+φ0."""
    w = 2 * math.pi / period
    if direction > 0:
        ox, oy = (phi0 + math.pi) / w, (phi0 + math.pi / 2) / w
    else:
        ox, oy = (math.pi - phi0) / w, (1.5 * math.pi - phi0) / w
    return ox % period, oy % period


def build_orbit() -> str:
    W, H = 880, 400
    cx, cy = W / 2, H / 2 + 6
    rnd = random.Random(11)
    css = [
        f"text{{font-family:{MONO}}}",
        ".tw{animation:tw var(--d) ease-in-out var(--l) infinite alternate}",
        "@keyframes tw{from{opacity:.12}to{opacity:.95}}",
        f".ox{{animation:ox var(--D) {EASE} var(--lx) infinite alternate}}",
        f".oy{{animation:oy var(--D) {EASE} var(--ly) infinite alternate}}",
        f".os{{animation:os var(--D) {EASE} var(--ly) infinite alternate}}",
        "@keyframes ox{from{transform:translateX(calc(var(--a)*-1px))}to{transform:translateX(calc(var(--a)*1px))}}",
        "@keyframes oy{from{transform:translateY(calc(var(--b)*-1px))}to{transform:translateY(calc(var(--b)*1px))}}",
        "@keyframes os{from{transform:scale(.76);opacity:.58}to{transform:scale(1.2);opacity:1}}",
        ".flow{animation:flow var(--f) linear infinite}",
        "@keyframes flow{to{stroke-dashoffset:-6}}",
        ".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 5s ease-in-out infinite}",
        "@keyframes pulse{50%{transform:scale(1.14);opacity:.55}}",
        ".blink{animation:blink 2.4s ease-in-out infinite}",
        "@keyframes blink{50%{opacity:.25}}",
        REDUCED,
    ]
    defs = [
        '<radialGradient id="bg" cx="50%" cy="52%" r="75%"><stop offset="0" stop-color="#0d1434"/><stop offset=".6" stop-color="#060a1c"/><stop offset="1" stop-color="#03040b"/></radialGradient>',
        '<radialGradient id="neb1" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#7a4dff" stop-opacity=".30"/><stop offset="1" stop-color="#7a4dff" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="neb2" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#22c4ff" stop-opacity=".22"/><stop offset="1" stop-color="#22c4ff" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="halo" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#9bb4ff" stop-opacity=".55"/><stop offset=".45" stop-color="#5b6cff" stop-opacity=".22"/><stop offset="1" stop-color="#5b6cff" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="core" cx="38%" cy="32%" r="75%"><stop offset="0" stop-color="#ffffff"/><stop offset=".22" stop-color="#bfe0ff"/><stop offset=".55" stop-color="#5f86ff"/><stop offset="1" stop-color="#1a1f7a"/></radialGradient>',
        '<linearGradient id="ringfade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8aa4ff" stop-opacity=".12"/><stop offset=".5" stop-color="#8aa4ff" stop-opacity=".5"/><stop offset="1" stop-color="#c7a6ff" stop-opacity="1"/></linearGradient>',
    ]
    for k, c in CHIPS.items():
        defs.append(f'<radialGradient id="g-{k}" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="{c}" stop-opacity=".42"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Tech stack orbiting a glowing core: Python, FastAPI, Git, Svelte, TypeScript, HTML, CSS, Swift, Unity, C#, GitHub">',
        f"<style>{''.join(css)}</style>",
        f"<defs>{''.join(defs)}</defs>",
        f'<rect width="{W}" height="{H}" rx="16" fill="url(#bg)"/>',
        '<ellipse cx="170" cy="330" rx="260" ry="130" fill="url(#neb1)"/>',
        '<ellipse cx="730" cy="80" rx="280" ry="120" fill="url(#neb2)"/>',
    ]
    # twinkling starfield
    for _ in range(120):
        x, y = rnd.uniform(8, W - 8), rnd.uniform(8, H - 8)
        r = rnd.choice([.5, .6, .8, 1.0, 1.3])
        c = rnd.choice(["#cfe0ff", "#ffffff", "#a9b8ff", "#ffd9f2"])
        out.append(f'<circle class="tw" cx="{f(x,1)}" cy="{f(y,1)}" r="{r}" fill="{c}" style="--d:{f(rnd.uniform(1.6,5.5),1)}s;--l:-{f(rnd.uniform(0,6),1)}s"/>')

    out.append(f'<g transform="translate({cx} {cy})">')
    out.append('<circle class="pulse" r="118" fill="url(#halo)"/>')

    # rings (back half first would be ideal; chips are z-faded instead)
    for ri, (a, b, tilt, period, d, chips) in enumerate(RINGS):
        out.append(f'<g transform="rotate({tilt})">')
        out.append(f'<ellipse rx="{a}" ry="{b}" fill="none" stroke="url(#ringfade)" stroke-opacity=".5" stroke-width="1"/>')
        out.append(f'<ellipse class="flow" rx="{a}" ry="{b}" fill="none" stroke="url(#ringfade)" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="0.1 6" style="--f:{f(period/9,1)}s"/>')
        D = period / 2
        for icon, deg in chips:
            ox, oy = orbit_offsets(math.radians(deg), period, d)
            col = CHIPS[icon]
            if icon == "csharp":
                glyph = f'<g transform="translate(-10.5 -10.5) scale(.875)" color="{col}">{CSHARP}</g>'
            else:
                glyph = f'<path transform="translate(-10 -10) scale(.835)" d="{ICONS[icon]["path"]}" fill="{col}"/>'
            out.append(
                f'<g class="ox" style="--a:{a};--D:{f(D,2)}s;--lx:-{f(ox,2)}s">'
                f'<g class="oy" style="--b:{b};--D:{f(D,2)}s;--ly:-{f(oy,2)}s">'
                f'<g class="os" style="--D:{f(D,2)}s;--ly:-{f(oy,2)}s">'
                f'<circle r="36" fill="url(#g-{icon})"/>'
                f'<circle r="21.5" fill="#080d22" fill-opacity=".93" stroke="{col}" stroke-opacity=".6" stroke-width="1.4"/>'
                f"{glyph}</g></g></g>"
            )
        out.append("</g>")

    # glossy core
    out.append('<circle r="34" fill="url(#core)"/>')
    out.append('<circle r="34" fill="none" stroke="#cfe0ff" stroke-opacity=".35" stroke-width="1"/>')
    out.append('<ellipse rx="52" ry="14" fill="none" stroke="#bcd0ff" stroke-opacity=".35" stroke-width="1" transform="rotate(-18)"/>')
    out.append("</g>")

    # HUD
    out.append(f'<text x="26" y="34" font-size="12" letter-spacing="2.4" fill="#7384ad">// TECH ORBIT</text>')
    out.append(f'<text x="{W-26}" y="34" font-size="12" letter-spacing="1.6" fill="#7384ad" text-anchor="end">11 modules online</text>')
    out.append(f'<circle class="blink" cx="{W-196}" cy="30" r="3.2" fill="#58a6ff"/>')
    out.append(f'<text x="26" y="{H-24}" font-size="11" letter-spacing="1.6" fill="#4d5a80">backend · web · app · game</text>')
    out.append(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="none" stroke="#1b2547"/>')
    out.append("</svg>")
    return "".join(out)


# ═════════════════════════════════ wave.svg ═════════════════════════════════
def wave_dots(W: int, rows: int, y_top: float, y_span: float, per_row: tuple[int, int], amp: tuple[float, float],
              radius: tuple[float, float], period: float, rnd: random.Random) -> tuple[str, str]:
    """Return (css, dots) for a perspective sheet of particles with a travelling sine wave."""
    D = period / 2
    w = 2 * math.pi / period
    css = (
        f".w{{animation:w var(--D) {EASE} var(--l) infinite alternate}}"
        "@keyframes w{from{transform:translateY(calc(var(--A)*-1px))}to{transform:translateY(calc(var(--A)*1px))}}"
    )
    dots = []
    for r in range(rows):
        v = r / (rows - 1)
        y0 = y_top + y_span * v ** 1.55
        n = round(per_row[0] + (per_row[1] - per_row[0]) * v)
        a_row = amp[0] + (amp[1] - amp[0]) * v ** 1.3
        rad = radius[0] + (radius[1] - radius[0]) * v
        op = 0.28 + 0.72 * v
        for i in range(n):
            x = 14 + (W - 28) * (i + rnd.uniform(-.25, .25)) / (n - 1)
            u = x / W
            A = a_row * (0.55 + 0.45 * math.sin(2 * math.pi * u * 2.3 + r * 0.9))
            phi = 2 * math.pi * (u * 1.55 + r * 0.085)           # wave travels along x, lags with depth
            off = (phi / w) % period
            rr = rad * rnd.uniform(.85, 1.15)
            style = f'--A:{f(A,1)};--D:{f(D,2)}s;--l:-{f(off,2)}s'
            if v >= 0.55:   # near rows get a soft halo so they read as glowing particles
                dots.append(f'<g class="w" style="{style}"><circle cx="{f(x,1)}" cy="{f(y0,1)}" r="{f(rr * 3.1)}" fill-opacity="{f(op * .13)}"/>'
                            f'<circle cx="{f(x,1)}" cy="{f(y0,1)}" r="{f(rr)}" fill-opacity="{f(op)}"/></g>')
            else:
                dots.append(f'<circle class="w" cx="{f(x,1)}" cy="{f(y0,1)}" r="{f(rr)}" fill-opacity="{f(op)}" style="{style}"/>')
    return css, "".join(dots)


def build_wave() -> str:
    W, H = 880, 210
    rnd = random.Random(5)
    css, dots = wave_dots(W, 9, 56, 112, (100, 38), (3.2, 27), (0.8, 3.0), 7.0, rnd)
    stars = "".join(
        f'<circle class="tw" cx="{f(rnd.uniform(8,W-8),1)}" cy="{f(rnd.uniform(8,70),1)}" r="{rnd.choice([.5,.7,.9])}" fill="#cfe0ff" style="--d:{f(rnd.uniform(1.6,5),1)}s;--l:-{f(rnd.uniform(0,5),1)}s"/>'
        for _ in range(46)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="A field of glowing particles rippling like waves">'
        f"<style>{css}.tw{{animation:tw var(--d) ease-in-out var(--l) infinite alternate}}@keyframes tw{{from{{opacity:.1}}to{{opacity:.9}}}}{REDUCED}</style>"
        '<defs>'
        '<linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="880" y2="0"><stop offset="0" stop-color="#38b6ff"/><stop offset=".5" stop-color="#a07dff"/><stop offset="1" stop-color="#ff6fd0"/></linearGradient>'
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#03040b"/><stop offset=".7" stop-color="#070b1f"/><stop offset="1" stop-color="#14123a"/></linearGradient>'
        '<radialGradient id="hz" cx="50%" cy="100%" r="70%"><stop offset="0" stop-color="#7a5cff" stop-opacity=".38"/><stop offset="1" stop-color="#7a5cff" stop-opacity="0"/></radialGradient>'
        "</defs>"
        f'<rect width="{W}" height="{H}" rx="16" fill="url(#bg)"/><rect width="{W}" height="{H}" rx="16" fill="url(#hz)"/>'
        f'{stars}<g fill="url(#g)">{dots}</g>'
        f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="none" stroke="#1b2547"/>'
        "</svg>"
    )


# ═════════════════════════════════ divider.svg ═════════════════════════════════
def build_divider() -> str:
    W, H = 880, 40
    rnd = random.Random(3)
    D, period = 2.6, 5.2
    w = 2 * math.pi / period
    dots = []
    n = 92
    for i in range(n):
        x = 10 + (W - 20) * i / (n - 1)
        u = x / W
        env = math.sin(math.pi * u) ** 0.8                       # taper to nothing at both ends
        phi = 2 * math.pi * u * 2.2
        off = (phi / w) % period
        r = (0.9 + 1.4 * env) * rnd.uniform(.8, 1.2)
        dots.append(f'<circle class="d" cx="{f(x,1)}" cy="20" r="{f(r)}" style="--A:{f(2 + 8 * env,1)};--l:-{f(off,2)}s;opacity:{f(.25 + .75 * env)}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="presentation">'
        f"<style>.d{{animation:d {D}s {EASE} var(--l) infinite alternate}}@keyframes d{{from{{transform:translateY(calc(var(--A)*-1px))}}to{{transform:translateY(calc(var(--A)*1px))}}}}{REDUCED}</style>"
        '<defs><linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="880" y2="0"><stop offset="0" stop-color="#38b6ff"/><stop offset=".5" stop-color="#a07dff"/><stop offset="1" stop-color="#ff6fd0"/></linearGradient></defs>'
        f'<g fill="url(#g)">{"".join(dots)}</g></svg>'
    )


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    for name, svg in (("orbit.svg", build_orbit()), ("wave.svg", build_wave()), ("divider.svg", build_divider())):
        (ASSETS / name).write_text(svg, encoding="utf-8")
        print(f"assets/{name}  {len(svg) / 1024:.1f} KB")
