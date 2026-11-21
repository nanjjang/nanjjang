"""Generate a terminal-style GitHub dashboard SVG (assets/dashboard.svg)."""
import json
import os
import urllib.request
from datetime import datetime, timezone
from html import escape

USER = os.environ.get("GH_USER", "nanjjang")
TOKEN = os.environ["GITHUB_TOKEN"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, first: 100, isFork: false) {
      totalCount
      nodes { stargazerCount primaryLanguage { name } }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
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
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]["user"]


def streak(days):
    cur = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            cur += 1
        elif cur or d is not days[-1]:
            break
    best = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        best = max(best, run)
    return cur, best


ASCII = [
    "  _  _   _   _  _    _   _   _  _  ___ ",
    " | \\| | /_\\ | \\| |_ | | /_\\ | \\| |/ __|",
    " | .` |/ _ \\| .` | || |/ _ \\| .` | (_ |",
    " |_|\\_/_/ \\_\\_|\\_|\\__//_/ \\_\\_|\\_|\\___|",
]

GREENS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def level(c):
    if c == 0:
        return 0
    return 1 if c < 3 else 2 if c < 6 else 3 if c < 10 else 4


def build(u):
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"][-53:]
    days = [d for w in weeks for d in w["contributionDays"]]
    cur, best = streak(days)
    stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
    langs = {}
    for n in u["repositories"]["nodes"]:
        if n["primaryLanguage"]:
            langs[n["primaryLanguage"]["name"]] = langs.get(n["primaryLanguage"]["name"], 0) + 1
    top = ", ".join(k for k, _ in sorted(langs.items(), key=lambda x: -x[1])[:3]) or "-"

    W, H = 860, 420
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<style>text{font-family:'SFMono-Regular',Consolas,'Liberation Mono',monospace;}"
        ".g{fill:#39d353}.m{fill:#8b949e}.w{fill:#e6edf3}.b{fill:#58a6ff}"
        "@keyframes blink{50%{opacity:0}}.c{animation:blink 1s step-end infinite}"
        "@keyframes up{from{opacity:0}to{opacity:1}}.f{animation:up .6s ease-out both}</style>",
        f'<rect width="{W}" height="{H}" rx="14" fill="#0d1117" stroke="#30363d"/>',
        f'<rect width="{W}" height="34" rx="14" fill="#161b22"/><rect y="20" width="{W}" height="14" fill="#161b22"/>',
        '<circle cx="22" cy="17" r="6" fill="#ff5f56"/><circle cx="42" cy="17" r="6" fill="#ffbd2e"/><circle cx="62" cy="17" r="6" fill="#27c93f"/>',
        f'<text x="{W/2}" y="22" text-anchor="middle" font-size="13" class="m">{USER}@github: ~/contributions.sh</text>',
    ]
    for i, line in enumerate(ASCII):
        out.append(f'<text x="28" y="{66+i*16}" font-size="13" class="g" xml:space="preserve">{escape(line)}</text>')
    out.append(f'<text x="28" y="150" font-size="13"><tspan class="g">❯</tspan><tspan class="w"> ./contributions.sh --user {USER}</tspan></text>')
    out.append(f'<text x="28" y="172" font-size="12" class="m">{cal["totalContributions"]} contributions in the last year</text>')

    # contribution grid
    gx, gy, s = 28, 186, 11.5
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            di = datetime.fromisoformat(d["date"]).weekday()
            di = (di + 1) % 7
            out.append(f'<rect x="{gx+wi*(s+3)}" y="{gy+di*(s+3)}" width="{s}" height="{s}" rx="2.5" fill="{GREENS[level(d["contributionCount"])]}"/>')

    # stat boxes
    stats = [
        ("COMMITS", u["contributionsCollection"]["totalCommitContributions"]),
        ("PRs", u["contributionsCollection"]["totalPullRequestContributions"]),
        ("STARS", stars),
        ("REPOS", u["repositories"]["totalCount"]),
        ("STREAK", f"{cur}d"),
        ("BEST", f"{best}d"),
    ]
    bw, by = 128, 312
    for i, (k, v) in enumerate(stats):
        x = 28 + i * (bw + 8)
        out.append(f'<g><rect x="{x}" y="{by}" width="{bw}" height="58" rx="8" fill="#161b22" stroke="#30363d"/>'
                   f'<text x="{x+12}" y="{by+22}" font-size="11" class="m">{k}</text>'
                   f'<text x="{x+12}" y="{by+46}" font-size="20" font-weight="700" class="g">{v}</text></g>')

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out.append(f'<text x="28" y="396" font-size="12"><tspan class="g">❯</tspan><tspan class="m"> top: </tspan><tspan class="b">{escape(top)}</tspan>'
               f'<tspan class="m">  ·  followers {u["followers"]["totalCount"]}  ·  updated {now} </tspan><tspan class="g c">█</tspan></text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    with open("assets/dashboard.svg", "w") as f:
        f.write(build(fetch()))
