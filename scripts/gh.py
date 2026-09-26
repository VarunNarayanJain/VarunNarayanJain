"""The only thing in here that talks to GitHub.

Standard library only, so the workflow needs no pip install and cannot be
broken by a dependency that moved. Every call is made from inside your own
Action with the token the runner already provides, which is what keeps the
profile off the shared render services that rate-limit.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"


class NoToken(Exception):
    """Raised when live data was asked for and no token is available."""


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not tok:
        raise NoToken("set GITHUB_TOKEN to pull live data")
    return tok


def _request(url: str, data: dict | None = None, auth: bool = True) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-render",
        "Content-Type": "application/json",
    }
    if auth:
        headers["Authorization"] = "Bearer " + _token()
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


CONTRIB_QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def contributions(login: str, days: int = 371) -> list[tuple[date, int]]:
    """Every day in the window, oldest first, as (date, count).

    GitHub caps a single contributionsCollection at one year, which is
    exactly the window the calendar shows anyway.
    """
    to = datetime.now(timezone.utc)
    frm = to - timedelta(days=days)
    payload = {
        "query": CONTRIB_QUERY,
        "variables": {
            "login": login,
            "from": frm.isoformat().replace("+00:00", "Z"),
            "to": to.isoformat().replace("+00:00", "Z"),
        },
    }
    res = _request(GRAPHQL, payload)
    if "errors" in res:
        raise RuntimeError(res["errors"])
    cal = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    out = []
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            out.append((date.fromisoformat(day["date"]), day["contributionCount"]))
    return out


def repo(full_name: str) -> dict:
    """Stars, language and description for one repo. Unauthenticated is fine
    here -- 60 requests/hour is plenty for a handful of projects, and it means
    a local run works without a token."""
    try:
        return _request(f"{API}/repos/{full_name}", auth=bool(os.environ.get("GITHUB_TOKEN")))
    except (urllib.error.HTTPError, urllib.error.URLError, NoToken):
        return {}


def contributions_public(login: str) -> list[tuple[date, int]]:
    """Same calendar, no token, by reading the fragment GitHub serves to its
    own profile page. Handy locally; the workflow uses the GraphQL path."""
    import re

    url = f"https://github.com/users/{login}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "profile-render"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")

    # data-level is only a 0-4 bucket. The real count lives in the tool-tip
    # GitHub pairs to each cell by id, so read that instead.
    counts = {}
    for tip in re.finditer(r"<tool-tip[^>]*for=\"([^\"]+)\"[^>]*>([^<]*)</tool-tip>", html):
        head = tip.group(2).strip().split(" ", 1)[0]
        counts[tip.group(1)] = 0 if head.lower() == "no" else int(head.replace(",", ""))

    out = []
    for cell in re.finditer(r"<td[^>]*data-date=\"(\d{4}-\d{2}-\d{2})\"[^>]*>", html):
        tag = cell.group(0)
        cid = re.search(r"id=\"([^\"]+)\"", tag)
        if cid and cid.group(1) in counts:
            n = counts[cid.group(1)]
        else:
            lvl = re.search(r"data-level=\"(\d+)\"", tag)
            n = int(lvl.group(1)) if lvl else 0
        out.append((date.fromisoformat(cell.group(1)), n))
    return sorted(out)


def calendar(login: str) -> tuple[list[tuple[date, int]], str]:
    """Best available calendar, plus which path produced it."""
    try:
        return contributions(login), "graphql"
    except (NoToken, RuntimeError, urllib.error.HTTPError, urllib.error.URLError):
        pass
    try:
        return contributions_public(login), "public"
    except Exception:
        pass
    today = date.today()
    return [(today - timedelta(days=i), 0) for i in range(370, -1, -1)], "empty"
