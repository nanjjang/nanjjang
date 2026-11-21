"""Redraw every image on the profile in one run.

    GITHUB_TOKEN=... python scripts/build.py                  # live data
    GITHUB_TOKEN=... python scripts/build.py --save file.json  # live data, and keep the response
    python scripts/build.py file.json                          # from a kept response, no network

Writes into assets/:
    profile.svg                          the wordmark and the year strip (scripts/profile.py)
    card-<repo>.svg, card-<repo>-narrow.svg   one pair per project in scripts/content.json
    repos.svg, repos-narrow.svg          every public repository with code, one block each
    records.svg, records-narrow.svg      the three numbers

What is written by hand lives in scripts/content.json. Languages, dates and
every bar are read from the GitHub API.
"""
import glob
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import elements  # noqa: E402
import profile  # noqa: E402  (scripts/profile.py, not the standard library's)

USER = profile.USER
HERE = os.path.dirname(os.path.abspath(__file__))

HISTORY = "nodes { committedDate } pageInfo { hasNextPage endCursor }"
QUERY = """
query($login: String!, $since: GitTimestamp!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes {
        name url createdAt pushedAt
        primaryLanguage { name }
        defaultBranchRef { target { ... on Commit {
          history(first: 100, since: $since) { totalCount %s }
          all: history { totalCount }
        } } }
      }
    }
  }
}
""" % HISTORY
MORE = """
query($login: String!, $name: String!, $since: GitTimestamp!, $after: String!) {
  repository(owner: $login, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, since: $since, after: $after) { %s }
    } } }
  }
}
""" % HISTORY


def ask(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if body.get("errors"):
        sys.exit(f"GitHub API: {body['errors'][0]['message']}")
    return body["data"]


def history(repo):
    ref = repo.get("defaultBranchRef")
    return ref["target"]["history"] if ref else None


def fetch(wanted):
    """One call for everything. A project with more than 100 commits in the year gets the rest."""
    since = (datetime.now(timezone.utc) - timedelta(days=385)).strftime("%Y-%m-%dT00:00:00Z")
    user = ask(QUERY, login=USER, since=since)["user"]
    for repo in user["repositories"]["nodes"]:
        h = history(repo)
        while h and repo["name"] in wanted and h["pageInfo"]["hasNextPage"]:
            page = ask(MORE, login=USER, name=repo["name"], since=since, after=h["pageInfo"]["endCursor"])
            page = page["repository"]["defaultBranchRef"]["target"]["history"]
            h["nodes"] += page["nodes"]
            h["pageInfo"] = page["pageInfo"]
    return user


def per_week(user):
    """[(first day, contributions)] for each week of the wordmark's year."""
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [
        (date.fromisoformat(w["contributionDays"][0]["date"]), sum(d["contributionCount"] for d in w["contributionDays"]))
        for w in weeks
    ]


def commits(repo, weeks):
    """This repository's commits in each of those weeks, and the months they span as text."""
    h = history(repo)
    days = sorted(date.fromisoformat(c["committedDate"][:10]) for c in h["nodes"]) if h else []
    hits = [0] * len(weeks)
    for d in days:
        i = (d - weeks[0][0]).days // 7
        if 0 <= i < len(weeks):
            hits[i] += 1
    # the months come from the commits when the year holds all of them, else from the repository's own dates
    whole = h and h["totalCount"] == repo["defaultBranchRef"]["target"]["all"]["totalCount"]
    first = days[0].isoformat() if days and whole else repo["createdAt"]
    last = days[-1].isoformat() if days else repo["pushedAt"]
    first, last = sorted((elements.month(first), elements.month(last)))
    return hits, first if first == last else f"{first} – {last}"


def write(name, text):
    with open(os.path.join("assets", name), "w", encoding="utf-8") as f:
        f.write(text)


# space kept inside the card images, so the grid's rhythm does not depend on the page's CSS
CARDS_ABOVE = 14.0     # over the first row
ROW_GAP = 38.0         # under every row


def main():
    args = sys.argv[1:]
    content = json.load(open(os.path.join(HERE, "content.json"), encoding="utf-8"))
    wanted = {item["repo"] for item in content["projects"]}
    if args and args[0] != "--save":
        user = json.load(open(args[0]))["data"]["user"]
    else:
        user = fetch(wanted)
        if args:
            json.dump({"data": {"user": user}}, open(args[1], "w"))
    nodes = user["repositories"]["nodes"]
    by_name = {r["name"]: r for r in nodes}
    weeks = per_week(user)
    totals = [t for _, t in weeks]

    os.makedirs("assets", exist_ok=True)
    write("profile.svg", profile.build(user))

    for old in glob.glob(os.path.join("assets", "card-*.svg")):
        os.remove(old)
    half = elements.GUTTER / 2
    for i, item in enumerate(content["projects"]):
        repo = by_name.get(item["repo"])
        if repo is None:
            sys.exit(f'content.json: no public repository named {item["repo"]}')
        hits, span = commits(repo, weeks)
        name = f'card-{item["repo"].lower()}'
        # two columns: the left card keeps half the gutter on its right, the right card on its left
        side = {"right": half} if i % 2 == 0 else {"left": half}
        write(name + ".svg", elements.card(
            item, repo, totals, hits, span, elements.HALF - half,
            above=CARDS_ABOVE if i < 2 else 0, below=ROW_GAP, **side))
        write(name + "-narrow.svg", elements.card(
            item, repo, totals, hits, span, elements.NARROW,
            above=CARDS_ABOVE if i < 1 else 0, below=ROW_GAP))

    # one block per repository with code in it. This repository draws the page, so it is not on it.
    coded = [r for r in nodes if r["primaryLanguage"] and r["name"] != USER]
    write("repos.svg", elements.repos(coded, elements.WIDE))
    write("repos-narrow.svg", elements.repos(coded, elements.NARROW))
    write("records.svg", elements.records(content["records"], elements.WIDE))
    write("records-narrow.svg", elements.records(content["records"], elements.NARROW))


if __name__ == "__main__":
    main()
