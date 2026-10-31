#!/usr/bin/env python3
"""AGENT ATLAS source-led public GitHub discovery. Standard library only."""
import datetime as dt
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
QUERIES = [
    "topic:ai-agent topic:bnb-chain archived:false fork:false",
    "topic:ai-agent topic:binance-smart-chain archived:false fork:false",
    "bnb agent in:name,description archived:false fork:false",
]
MAX_CANDIDATES = 36
KEYWORDS = ("bnb", "binance", "opbnb", "bsc", "agent", "ai-agent", "ai agent")
def github_search(query):
    params = urllib.parse.urlencode({"q": query, "sort": "updated", "order": "desc", "per_page": 30})
    request = urllib.request.Request(
        "https://api.github.com/search/repositories?" + params,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AGENT-ATLAS-Discovery/1.3",
            **({"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"]} if os.environ.get("GITHUB_TOKEN") else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response).get("items", [])
def credible(item):
    topics = [str(x).lower() for x in (item.get("topics") or [])]
    name = str(item.get("full_name") or "")
    description = str(item.get("description") or "")
    corpus = (" ".join(topics) + " " + name + " " + description).lower()
    agent = any(x in corpus for x in ("agent", "agents", "agentic", "defai", "erc-8004"))
    bnb = any(x in corpus for x in ("bnb", "binance", "opbnb", "bsc", "binance-smart-chain"))
    return agent and bnb and not item.get("fork") and not item.get("archived") and not item.get("disabled")
def clean(value, limit=260):
    return re.sub(r"[\\x00-\\x1f]", " ", str(value or "")).strip()[:limit]
def candidate(item):
    full = clean(item["full_name"], 150)
    desc = clean(item.get("description"), 230) or "Public GitHub repository; functionality needs independent verification."
    created = clean(item.get("created_at"), 10)
    pushed = clean(item.get("pushed_at"), 10)
    url = item["html_url"]
    return {
        "id": "github-" + str(item["id"]),
        "name": clean(item.get("name"), 90),
        "symbol": "GH",
        "category": "developer",
        "chain": "BNB Chain (unverified)",
        "type": "candidate",
        "stage": "unverified",
        "source": url,
        "website": url,
        "descriptionZh": "GitHub 公开候选项目：" + desc,
        "descriptionEn": "Public GitHub discovery candidate: " + desc,
        "tags": ["GitHub", "Candidate", "Unverified"],
        "mint": "unknown",
        "evidence": "GitHub public repository metadata; independent verification pending",
        "date": created,
        "firstSeen": TODAY,
        "lastCheckedAt": NOW.isoformat(),
        "lastActivityAt": pushed,
        "discoverySource": "github-search",
        "verification": "repository-exists-only",
        "githubStars": int(item.get("stargazers_count") or 0),
    }
def run():
    DATA.mkdir(exist_ok=True)
    path = DATA / "projects.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    projects = original.get("projects", [])
    if not isinstance(projects, list):
        raise ValueError("projects must be a list")
    old = {p.get("id"): p for p in projects}
    matches = {}
    errors = []
    for q in QUERIES:
        try:
            for item in github_search(q):
                if credible(item):
                    matches[item["id"]] = item
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append(q + ": " + str(exc)[:160])
    # Never destroy previously collected sources on a failed run.
    discovered = [candidate(i) for i in matches.values()]
    discovered.sort(key=lambda p: p["lastActivityAt"], reverse=True)
    newly_added = 0
    changed = 0
    for p in discovered[:MAX_CANDIDATES]:
        prior = old.get(p["id"])
        if prior:
            p["firstSeen"] = prior.get("firstSeen", p["firstSeen"])
            if prior.get("descriptionZh") == p["descriptionZh"] and prior.get("githubStars") == p["githubStars"]:
                p["lastCheckedAt"] = prior.get("lastCheckedAt", p["lastCheckedAt"])
            else:
                changed += 1
            old[p["id"]] = {**prior, **p}
        else:
            old[p["id"]] = p
            newly_added += 1
    full = list(old.values())
    # Bounded list, preserving curated entries and recent discoveries.
    curated = [p for p in full if p.get("type") != "candidate"]
    candidates = sorted((p for p in full if p.get("type") == "candidate"), key=lambda p: p.get("lastActivityAt") or "", reverse=True)[:MAX_CANDIDATES]
    final = curated + candidates
    status = {
        "checkedAt": NOW.isoformat(),
        "state": "ok" if not errors else ("partial" if matches else "error"),
        "source": "GitHub public repository search",
        "queries": len(QUERIES),
        "queryFailures": errors,
        "matchingRepositories": len(matches),
        "newCandidates": newly_added,
        "changedCandidates": changed,
        "total": len(final),
        "note": "GitHub metadata only; candidate is NOT an official endorsement, security audit, mint eligibility or verified live Agent service.",
    }
    # Preserve input if ALL queries fail; report status, and fail the action after writing status.
    (DATA / "pipeline_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status["state"] == "error":
        print(json.dumps(status, ensure_ascii=False))
        return 1
    original.update({
        "updatedAt": NOW.isoformat(),
        "methodology": "Curated ecosystem sources plus public GitHub discovery. GitHub candidates are NOT independently verified; no automatic contract, mint or social audit.",
        "projects": final,
    })
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0
if __name__ == "__main__":
    sys.exit(run())
