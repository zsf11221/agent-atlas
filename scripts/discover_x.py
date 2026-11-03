#!/usr/bin/env python3
"""Read-only X recent-search lead discovery. Disabled unless explicitly enabled.

Only post IDs, authored summaries and source links are published, not X post text.
No API calls occur in --self-test mode. Python standard library only.
"""
import argparse
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
PROJECTS_FILE = DATA / "x_projects.json"
STATUS_FILE = DATA / "x_pipeline_status.json"
API = "https://api.x.com/2/tweets/search/recent"
# 2 searches x 10 returned posts per run. The ledger reserves all potential
# reads BEFORE calls and caps this workflow at 800 per UTC calendar month.
# $0.005/read is an estimate, not a guarantee or account-wide spending limit.
MAX_RESULTS_PER_QUERY = 10
MONTHLY_READ_CAP = 800
MAX_STORED_LEADS = 160
QUERY_PAIRS = (
    '(("AI agent" OR agentic OR DeFAI) (BNB OR BSC)) -is:retweet -is:reply',
    '("Binance Agentic Wallet" OR "Agent ID") (agent OR mint OR launch) -is:retweet -is:reply',
)
BSC = re.compile(r"\b(?:BNB(?:\s+(?:Smart\s+)?Chain)?|BSC|Binance\s+(?:Smart\s+Chain|Agentic\s+Wallet|Agent\s+ID)|opBNB)\b|币安(?:智能)?链|币安(?:钱包|智能体)|BNB链", re.I)
AGENT = re.compile(r"\b(?:AI\s+agents?|agentic|autonomous\s+agents?|DeFAI|agent\s+ID|agent\s+wallet)\b|智能体|智能代理|自主代理|智能代理", re.I)
RELEASE = re.compile(r"\b(?:launch|launched|launching|mint|coming soon|build|building|develop|beta|demo|testnet|mainnet|deploy|introduc|announce|released|open source)\b|发布|上线|推出|开发|开放|铸造|测试|公测|预告|启动", re.I)
NOT_PROJECT = re.compile(r"\b(?:giveaway|airdrops? bot|100x|guaranteed returns|free money)\b", re.I)
SKIP_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "t.co",
              "dexscreener.com", "www.dexscreener.com", "t.me", "telegram.me"}
UTC = dt.timezone.utc


def now():
    return dt.datetime.now(UTC)


def trim(s, limit=250):
    return re.sub(r"[\x00-\x1f]+", " ", str(s or "")).strip()[:limit]


def parse_record(post, seen_at):
    """Never treat a matching post as a verified official project account."""
    if not isinstance(post, dict):
        return None
    pid = str(post.get("id") or "")
    author = str(post.get("author_id") or "")
    content = str(post.get("text") or "")
    if not pid.isdigit() or not author.isdigit() or not content:
        return None
    if not (BSC.search(content) and AGENT.search(content) and RELEASE.search(content)):
        return None
    if NOT_PROJECT.search(content):
        return None

    created = trim(post.get("created_at"), 40)
    date = created[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", created[:10]) else ""
    urls = []
    for ent in (post.get("entities") or {}).get("urls", []):
        raw = ent.get("expanded_url") or ent.get("url")
        if not raw:
            continue
        try:
            u = urllib.parse.urlsplit(raw)
            host = (u.hostname or "").lower()
            if u.scheme != "https" or not host or u.username or host in SKIP_HOSTS:
                continue
            if host.endswith(".x.com") or host.endswith(".twitter.com"):
                continue
            urls.append(trim(raw, 500))
        except ValueError:
            continue
    project_url = urls[0] if urls else ""
    title = "X 早期项目线索 · " + pid[-6:]
    if project_url:
        domain = urllib.parse.urlsplit(project_url).hostname or ""
        title = trim(domain.removeprefix("www."), 68)
    hint = "发布或开发动态"
    if re.search(r"\b(?:mint|whitelist|claim)\b|铸造|白名单|领取", content, re.I):
        hint = "Mint 或参与公告"
    elif re.search(r"\b(?:demo|beta|launch|testnet|mainnet)\b|公测|上线", content, re.I):
        hint = "产品发布或演示"
    link = "https://x.com/i/web/status/" + pid
    return {
        "id": "x-post-" + pid,
        "name": title,
        "symbol": "X",
        "category": "early",
        "chain": "BNB Chain (X claim only)",
        "type": "candidate",
        "stage": "x-lead-unverified",
        "source": link,
        "website": project_url or link,
        "authorId": author,
        "postId": pid,
        "descriptionZh": "X 上发现与 BSC AI Agent 相关的" + hint + "。该帖所指项目的身份、功能与上线时间尚未独立核实。" + (" 来源提供项目链接。" if project_url else " 尚未发现独立项目官网。"),
        "descriptionEn": "Public X lead mentioning BSC and AI agents. Project identity, product functionality and launch time are unverified.",
        "tags": ["X", "Early lead", "Unverified"],
        "evidence": "Public X post ID and author ID; no independently verified project identity",
        "date": date,
        "firstSeen": seen_at.date().isoformat(),
        "lastActivityAt": date,
        "lastCheckedAt": seen_at.isoformat(),
        "discoverySource": "x-recent-search",
        "verification": "x-post-claim-only",
        "mint": "unknown",
    }


def read_json(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def api_search(token, query):
    qs = urllib.parse.urlencode({
        "query": query,
        "max_results": str(MAX_RESULTS_PER_QUERY),
        "tweet.fields": "author_id,created_at,entities",
    })
    req = urllib.request.Request(API + "?" + qs, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "AgentAtlas-X-Discovery/1.0",
    })
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Oversized X API response")
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("data", []), list):
        raise ValueError("Unexpected X search response")
    return data.get("data", [])


def upsert(previous, fresh):
    known = {p["id"]: p for p in previous if isinstance(p, dict) and p.get("id")}
    added = 0
    for p in fresh:
        older = known.get(p["id"])
        if older:
            p["firstSeen"] = older.get("firstSeen") or p["firstSeen"]
            known[p["id"]] = {**older, **p}
        else:
            known[p["id"]] = p
            added += 1
    ordered = sorted(known.values(), key=lambda p: (p.get("firstSeen") or "", p.get("date") or ""), reverse=True)
    return ordered[:MAX_STORED_LEADS], added


def write_data(projects, stamp, status):
    DATA.mkdir(parents=True, exist_ok=True)
    PROJECTS_FILE.write_text(json.dumps({
        "updatedAt": stamp.isoformat(), "projects": projects,
        "methodology": "X recent-search leads; no claim of Agent verification, Mint eligibility, project identity or safety. Post IDs and authored summaries only."
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def live():
    if os.getenv("ENABLE_X_DISCOVERY") != "true":
        print("X discovery disabled: no API requests made.")
        return 0
    token = os.getenv("X_BEARER_TOKEN", "")
    if not token:
        print("X discovery disabled: no token configured.", file=sys.stderr)
        return 1

    stamp = now()
    month = stamp.strftime("%Y-%m")
    old = read_json(STATUS_FILE, {})
    reads = int(old.get("reservedPostReads", 0)) if old.get("monthUTC") == month else 0
    projects_old = read_json(PROJECTS_FILE, {"projects": []}).get("projects", [])
    sources = []
    new_leads = {}
    failure = False
    for q in QUERY_PAIRS:
        if reads + MAX_RESULTS_PER_QUERY > MONTHLY_READ_CAP:
            sources.append({"state": "monthly-cap-reached"})
            break
        # Conservative reservation: count up to 10 returned resources even on
        # timeout, to avoid retries repeatedly consuming untracked credits.
        reads += MAX_RESULTS_PER_QUERY
        try:
            for post in api_search(token, q):
                parsed = parse_record(post, stamp)
                if parsed:
                    new_leads[parsed["id"]] = parsed
            sources.append({"state": "ok"})
        except urllib.error.HTTPError as exc:
            sources.append({"state": "http-error", "status": exc.code})
            failure = True
            if exc.code in (401, 402, 403, 429):
                break
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            sources.append({"state": "unavailable"})
            failure = True
            break

    merged, added = upsert(projects_old, new_leads.values())
    status = {
        "monthUTC": month,
        "reservedPostReads": reads,
        "maxMonthlyPostReads": MONTHLY_READ_CAP,
        "worstCaseEstimatedUSD": round(reads * 0.005, 2),
        "checkedAt": stamp.isoformat(),
        "state": "error" if failure else ("cap-reached" if reads >= MONTHLY_READ_CAP else "ok"),
        "sources": sources,
        "newLeads": added,
        "total": len(merged),
        "note": "This ledger is only for AgentAtlas X searches, not an X account billing cap. Rates may change; check X Console. Results are unverified leads."
    }
    write_data(merged, stamp, status)
    print(json.dumps({"state": status["state"], "newLeads": added, "total": len(merged),
                      "reservedReadsThisMonth": reads, "sourceStates": sources}, ensure_ascii=False))
    return 1 if failure else 0


def self_test():
    stamp = dt.datetime(2026, 11, 4, 12, tzinfo=UTC)
    positive = {"id": "1234567890123456789", "author_id": "12345678",
                "text": "Launching our BSC AI agent demo for BNB Chain today.",
                "created_at": "2026-11-04T11:00:00Z",
                "entities": {"urls": [{"expanded_url": "https://agent-example.dev/demo"}]}}
    found = parse_record(positive, stamp)
    assert found and found["id"] == "x-post-1234567890123456789"
    assert found["name"] == "agent-example.dev" and found["source"].startswith("https://x.com/")
    assert parse_record({**positive, "text": "Launching our Solana AI agent demo today."}, stamp) is None
    assert parse_record({**positive, "text": "BSC meme token moon 100x!"}, stamp) is None
    merged, added = upsert([dict(found, firstSeen="2026-11-02")], [found])
    assert added == 0 and len(merged) == 1 and merged[0]["firstSeen"] == "2026-11-02"
    print("Self-test PASS: X classification, BSC restriction, no fake Agent verification, dedup.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    sys.exit(self_test() if args.self_test else live())
