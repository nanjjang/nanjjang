"""Everything under the wordmark, drawn in the wordmark's hand.

Same four colours, same two type styles, same stroke weight as scripts/profile.py.
Three kinds of image come out of here:

  card(...)      one repository: its name, one line, and where it sits in the year
  repos(...)     every public repository as one block, counted by language and by year
  records(...)   the three numbers, set in digits built like the wordmark's letters

Each comes in two sizes. The wide one is drawn on the wordmark's own width, so
its edges meet the wordmark's. The narrow one is redrawn for a phone, not
scaled down, so its type stays readable there.
"""
import math

from profile import SW, R, n

WIDE = 860.8      # the wordmark's width
NARROW = 360.0    # a phone column, close to one unit per pixel
HALF = WIDE / 2   # a card is half the column; two of them make the wordmark's width
GUTTER = 44.0     # between the two columns of cards

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR','Malgun Gothic',sans-serif"
STYLE = (
    "svg{--ink:#1f2328;--mute:#59636e;--faint:#d1d9e0;--hot:#f0501a}"
    "@media(prefers-color-scheme:dark){svg{--ink:#f0f6fc;--mute:#9198a1;--faint:#3d444d;--hot:#ff7a45}}"
    "text{fill:var(--mute);font-size:12.5px}"
    ".m{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.06em}"
    f".c{{font-family:{SANS};font-size:14px}}"
    f".t{{font-family:{SANS};font-size:20px;font-weight:600;fill:var(--ink)}}"
    ".k{fill:var(--ink)}.q{fill:var(--mute)}.f{fill:var(--faint)}.h{fill:var(--hot)}"
    ".e{fill:none;stroke:var(--faint);stroke-width:1.6}"
    ".s{fill:none;stroke:var(--ink)}"
    ".r{transform-box:fill-box;transform-origin:50% 100%;animation:rise .5s cubic-bezier(.2,.7,.2,1) both}"
    ".w{stroke-dasharray:1;animation:draw .7s cubic-bezier(.6,0,.2,1) both}"
    "@keyframes rise{from{transform:scaleY(0)}}"
    "@keyframes draw{from{stroke-dashoffset:1}}"
    "@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
)
TONES = ["k", "q", "f"]   # this year, last year, before that


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def svg(width, height, label, body, above=0.0, below=0.0, left=0.0, right=0.0):
    """The margins are empty space kept inside the image, so spacing on the page is ours."""
    w, h = width + left + right, height + above + below
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{n(w)}" height="{n(h)}" '
        f'viewBox="{n(-left)} {n(-above)} {n(w)} {n(h)}" role="img" aria-label="{esc(label)}">'
        f"<style>{STYLE}</style>{body}</svg>\n"
    )


# ── measuring text without a font ───────────────────────────────────────────
MONO = 12.5 * 0.6 + 12.5 * 0.06     # one monospace cap, with its letter-spacing


def mono_w(s):
    return len(s) * MONO


def sans_w(s, size=14.0, bold=False):
    w = 0.0
    for ch in s:
        o = ord(ch)
        if o >= 0x1100:
            w += 0.9                # Hangul and other wide glyphs
        elif ch == " ":
            w += 0.27
        elif ch in ".,·:;'|!ilj":
            w += 0.29
        elif ch.isupper() or ch in "mw":
            w += 0.68
        elif ch.isdigit():
            w += 0.6
        else:
            w += 0.54
    return w * size * (1.05 if bold else 1)


def wrap(words, width, measure, sep=" "):
    """Greedy line breaking on the given pieces."""
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + sep + word
        if cur and measure(trial) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def month(iso):
    return iso[:7].replace("-", ".")


# ── repository card ─────────────────────────────────────────────────────────
# No box. A card is the wordmark's strip again at a smaller size: the whole
# year in faint, one bar per week, and the weeks this repository was committed
# to in ink.
CARD_H = 122.0
STRIP_H = 40.0
STRIP_BASE = 98.0


def card(item, repo, weeks, hits, span, width, **margins):
    """weeks: the owner's contributions per week. hits: this repository's commits per week.
    span: the months it was committed in, as text."""
    parts = [f'<text class="t" x="0" y="18">{esc(item["name"])}</text>']

    # top right: one fact about it. A running service gets the orange dot and its address.
    if item.get("live"):
        tag = item["live"].upper()
        parts.append(f'<circle class="h" cx="{n(width-mono_w(tag)-10)}" cy="12.5" r="4"/>')
    else:
        tag = item.get("tag", "")
    if tag:
        parts.append(f'<text class="m" x="{n(width)}" y="17" text-anchor="end">{esc(tag)}</text>')

    parts.append(f'<text class="c" x="0" y="41">{esc(item["line"])}</text>')

    # the year, one bar per week, on the same dashed line the wordmark's strip stands on
    pitch = width / len(weeks)
    bw = pitch * 0.66
    top = max(max(weeks), max(hits)) or 1
    parts.append(
        f'<line class="e" x1="{n((pitch-bw)/2)}" x2="{n(width)}" y1="{n(STRIP_BASE-0.8)}" y2="{n(STRIP_BASE-0.8)}" '
        f'stroke-dasharray="{n(bw)} {n(pitch-bw)}"/>'
    )
    for i, (total, mine) in enumerate(zip(weeks, hits)):
        c = max(total, mine)
        if not c:
            continue
        h = max(3.0, STRIP_H * math.log1p(c) / math.log1p(top))
        parts.append(
            f'<rect class="{"k" if mine else "f"} r" style="animation-delay:{i*0.008:.3f}s" '
            f'x="{n(i*pitch+(pitch-bw)/2)}" y="{n(STRIP_BASE-h)}" width="{n(bw)}" height="{n(h)}"/>'
        )

    # under the line: what it is written in, and when
    lang = (repo["primaryLanguage"] or {}).get("name", "")
    parts.append(f'<text class="m" x="0" y="{n(STRIP_BASE+20)}">{esc(lang.upper())}</text>')
    parts.append(
        f'<text class="m" x="{n(width)}" y="{n(STRIP_BASE+20)}" text-anchor="end">{esc(span)}</text>'
    )

    label = f'{item["name"]}. {item["line"]}. {lang}, {span}.'
    return svg(width, CARD_H, label, "".join(parts), **margins)


# ── every repository, one block each ────────────────────────────────────────
CELL_H = 20.0
LABEL_LH = 17.0


def lines_of(groups, limit):
    """Break the groups over several lines when one line would crowd the labels."""
    lines, cur, used = [], [], 0
    for g in groups:
        if cur and used + len(g[1]) > limit:
            lines.append(cur)
            cur, used = [], 0
        cur.append(g)
        used += len(g[1])
    return lines + [cur]


def repos(nodes, width):
    """nodes: the repositories to draw, each with code in it."""
    narrow = width < 600
    gap, group_gap = (4.0, 14.0) if narrow else (4.4, 26.0)

    # tone says how old a repository is: this year's are ink, last year's grey, older ones faint
    newest = max(r["createdAt"][:4] for r in nodes)
    oldest = min(r["createdAt"][:4] for r in nodes)

    def tone(r):
        return TONES[min(int(newest) - int(r["createdAt"][:4]), 2)]

    by_lang = {}
    for r in sorted(nodes, key=lambda r: r["createdAt"]):
        by_lang.setdefault(r["primaryLanguage"]["name"], []).append(r)
    # most repositories first; a tie goes to the language touched most recently
    order = sorted(by_lang, key=lambda l: (len(by_lang[l]), max(r["pushedAt"] for r in by_lang[l])), reverse=True)
    # a group is (label pieces, repositories). Languages used once share the last group, each named.
    groups = [([f"{l.upper()} {len(by_lang[l])}"], by_lang[l]) for l in order if len(by_lang[l]) > 1]
    once = sorted((by_lang[l][0] for l in order if len(by_lang[l]) == 1), key=lambda r: r["createdAt"])
    if once:
        groups.append(([r["primaryLanguage"]["name"].upper() for r in once], once))

    lines = lines_of(groups, 10) if narrow else [groups]
    widest = max(lines, key=lambda ln: sum(len(g[1]) for g in ln))
    cells = sum(len(g[1]) for g in widest)

    def span(members, cw):
        return len(members) * (cw + gap) - gap

    def labels(pieces, members, cw):
        return wrap(pieces, max(span(members, cw), mono_w(pieces[0])), mono_w, sep=" · ")

    def crowded(cw, group_gap):
        # every label must end at least two characters before the next group starts
        for ln in lines:
            for pieces, members in ln[:-1]:
                longest = max(mono_w(s) for s in labels(pieces, members, cw))
                if longest + 2 * MONO > span(members, cw) + group_gap:
                    return True
        return False

    while True:   # widen the space between groups until no label runs into the next
        cw = (width - (cells - len(widest)) * gap - (len(widest) - 1) * group_gap) / cells
        if not crowded(cw, group_gap) or cw < 12:
            break
        group_gap += 2

    out, y, k = [], 0.0, 0
    for ln in lines:
        x, deepest = 0.0, 1
        for pieces, members in ln:
            rows = labels(pieces, members, cw)
            deepest = max(deepest, len(rows))
            for i, row in enumerate(rows):
                out.append(f'<text class="m" x="{n(x)}" y="{n(y+CELL_H+19+i*LABEL_LH)}">{esc(row)}</text>')
            for r in members:
                out.append(
                    f'<rect class="{tone(r)} r" style="animation-delay:{k*0.02:.2f}s" '
                    f'x="{n(x)}" y="{n(y)}" width="{n(cw)}" height="{n(CELL_H)}"/>'
                )
                x += cw + gap
                k += 1
            x += group_gap - gap
        y += CELL_H + 19 + (deepest - 1) * LABEL_LH + 22
    y -= 22

    # caption on the left, and on the right what the three tones mean
    years = [newest, str(int(newest) - 1)]
    if int(oldest) < int(newest) - 1:
        years.append(oldest if int(oldest) == int(newest) - 2 else f"{oldest}–{int(newest) - 2}")
    key, kw = [], 0.0
    for i, label in enumerate(reversed(years)):
        t = TONES[len(years) - 1 - i]
        key.append((kw, t, label))
        kw += 15 + mono_w(label) + 14
    kw -= 14
    y += 30
    cap = f'<text class="c" x="0" y="{n(y)}">저장소 하나에 칸 하나 · 주로 쓴 언어별</text>'
    if narrow:
        y += 24
        kx = 0.0
    else:
        kx = width - kw
    for off, t, label in key:
        cap += (f'<circle class="{t}" cx="{n(kx+off+4.5)}" cy="{n(y-4.5)}" r="4.5"/>'
                f'<text class="m" x="{n(kx+off+15)}" y="{n(y)}">{esc(label)}</text>')
    said = (f"{len(nodes)} public repositories by main language: "
            + ", ".join(f"{l} {len(by_lang[l])}" for l in order) + ".")
    return svg(width, y + 6, said, "".join(out) + cap)


# ── digits ──────────────────────────────────────────────────────────────────
# Built like the letters: one radius, one stroke, arcs and straight stems.
DR = 14.0                      # digit bowl radius
DSW = DR * SW / R              # same weight for its size as the wordmark
DH = 4 * DR                    # centre line height: two bowls


def digit_paths(ch):
    """(centre-line width, stroke paths)"""
    r, top, bot = DR, -DSW / 2, DH + DSW / 2
    a = f"A{n(r)},{n(r)} 0"
    circle = lambda cy: f"M0,{n(cy)}{a} 1 1 {n(2*r)},{n(cy)}{a} 1 1 0,{n(cy)}Z"
    return {
        "0": (2 * r, [f"M0,{n(r)}{a} 0 1 {n(2*r)},{n(r)}V{n(3*r)}{a} 0 1 0,{n(3*r)}Z"]),
        "1": (0.0, [f"M0,{n(top)}V{n(bot)}"]),      # a bare stem, the wordmark's j without its dot
        "2": (2 * r, [f"M0,{n(r)}{a} 1 1 {n(r)},{n(2*r)}{a} 0 0 0,{n(3*r)}V{n(4*r)}H{n(2*r-top)}"]),
        "3": (2 * r, [f"M0,{n(r)}{a} 1 1 {n(r)},{n(2*r)}", f"M{n(r)},{n(2*r)}{a} 1 1 0,{n(3*r)}"]),
        "4": (2 * r, [f"M0,{n(top)}V{n(2.7*r)}H{n(2*r)}", f"M{n(2*r)},{n(top)}V{n(bot)}"]),
        "5": (2 * r, [f"M{n(2*r-top)},0H0V{n(2*r)}H{n(r)}{a} 0 1 {n(r)},{n(4*r)}H{n(top)}"]),
        "6": (2 * r, [circle(3 * r), f"M0,{n(3*r)}V{n(r)}{a} 0 1 {n(r)},0"]),
        "7": (2 * r, [f"M{n(top)},0H{n(2*r)}V{n(bot)}"]),
        "8": (2 * r, [circle(r), circle(3 * r)]),
        "9": (2 * r, [circle(r), f"M{n(2*r)},{n(r)}V{n(3*r)}{a} 0 1 {n(r)},{n(4*r)}"]),
    }[ch]


def number_w(value):
    """Width of a number from stroke edge to stroke edge."""
    return sum(digit_paths(ch)[0] + DSW for ch in str(value)) + 6 * (len(str(value)) - 1)


def number(value, x, y, delay=0.0):
    """Draw a number with its top-left stroke edge at (x, y)."""
    out, ox = [], x + DSW / 2
    for i, ch in enumerate(str(value)):
        width, paths = digit_paths(ch)
        for k, d in enumerate(paths):
            out.append(
                f'<path class="s w" pathLength="1" stroke-width="{n(DSW)}" '
                f'style="animation-delay:{delay+i*0.08+k*0.1:.2f}s" '
                f'transform="translate({n(ox)},{n(y+DSW/2)})" d="{d}"/>'
            )
        ox += width + DSW + 6
    return "".join(out)


def records(items, width):
    narrow = width < 600
    cols = 1 if narrow else len(items)
    col_w = width / cols
    row_h = DH + DSW + 26
    slot = 2 * DR + DSW                 # room for the widest digit
    parts, said = [], []
    for i, item in enumerate(items):
        count = len(item["items"])
        x0 = (i % cols) * col_w
        y0 = (i // cols) * row_h
        if narrow:    # stacked: digits end on one line, so every row's text starts on one line
            parts.append(number(count, x0 + slot - number_w(count), y0, delay=i * 0.12))
            tx = x0 + slot + 20
        else:         # side by side: the text follows its own digit
            parts.append(number(count, x0, y0, delay=i * 0.12))
            tx = x0 + number_w(count) + 20
        parts.append(f'<text class="m" x="{n(tx)}" y="{n(y0+10)}">{esc(item["label"])}</text>')
        room = x0 + col_w - tx - 12
        measure = lambda s: sans_w(s, 14.0)
        lines = []
        for piece in wrap(item["items"], room, measure, sep=" · "):
            lines += wrap(piece.split(" "), room, measure)
        for k, line in enumerate(lines[:2]):
            parts.append(f'<text class="c k" x="{n(tx)}" y="{n(y0+37+k*21)}">{esc(line)}</text>')
        said.append(f'{count} {item["label"]}: {", ".join(item["items"])}')
    rows = -(-len(items) // cols)
    return svg(width, rows * row_h - 26, ". ".join(said) + ".", "".join(parts))
