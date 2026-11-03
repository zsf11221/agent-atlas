#!/usr/bin/env python3
"""Source-backed BSC project discovery beyond GitHub. Standard library only."""
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "external_projects.json"
UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
STAMP = NOW.isoformat()
DATE = NOW.date().isoformat()
AGENT_TERMS = re.compile(r"\b(?:ai[ -]?agents?|agentic|autonomous agents?|defai|agent infrastructure|agent economy)\b", re.I)
ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
MAX_RECORDS = 160
DEX_ENDPOINTS = [
    ("profiles", "https://api.dexscreener.com/token-profiles/latest/v1"),
    ("boosts", "https://api.dexscreener.com/token-boosts/latest/v1"),
    ("search-agent", "https://api.dexscreener.com/latest/dex/search?q=ai%20agent"),
    ("search-agentic", "https://api.dexscreener.com/latest/dex/search?q=agentic"),
]
OFFICIAL_PAGE = "https://www.bnbchain.org/en/solutions/ai-agent"
# Names visibly published on the BNB Chain ecosystem page; do not infer launch dates.
OFFICIAL_NAMES = ("Pieverse", "Tearline", "ARK DeFAI", "Decentralized Intelligence", "BNBAgent SDK")


def request(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "AgentAtlasDiscovery/1.0 (+https://agentatlas.vip)",
        "Accept": "application/json,text/html;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read(1_500_001)
    if len(body) > 1_500_000:
        raise ValueError("Source response too large")
    return body.decode("utf-8", "replace")


def text(value, limit=500):
    return re.sub(r"[\x00-\x1f]+", " ", str(value or "")).strip()[:limit]


def link(value):
    value = text(value, 600)
    u = urllib.parse.urlsplit(value)
    return value if u.scheme == "https" and u.netloc and not u.username else ""


def iso_day(timestamp):
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        try:
            return dt.datetime.fromtimestamp(timestamp / 1000, UTC).date().isoformat()
        except (OverflowError, ValueError, OSError):
            pass
    return ""


def social_links(items):
    website = x_url = ""
    for item in items or []:
        u = link(item.get("url", ""))
        host = urllib.parse.urlsplit(u).hostname or ""
        if host in ("x.com", "twitter.com", "www.x.com") and not x_url:
            x_url = u
        elif u and not website and host not in ("dexscreener.com", "www.dexscreener.com"):
            website = u
    return website, x_url


def dex_project(record, origin):
    if not isinstance(record, dict) or str(record.get("chainId", "")).lower() != "bsc":
        return None
    is_pair = "baseToken" in record
    base = record.get("baseToken") if is_pair else {}
    addr = text(base.get("address") if is_pair else record.get("tokenAddress"), 42)
    if not ADDRESS.fullmatch(addr):
        return None
    pair_info = record.get("info") or {}
    desc = text(record.get("description") or pair_info.get("description") or "", 500)
    name = text(base.get("name") if is_pair else "", 90)
    symbol = text(base.get("symbol") if is_pair else "", 20)
    corpus = " ".join((name, symbol, desc))
    # Search results alone are not enough: require explicit Agent language in source metadata.
    if not AGENT_TERMS.search(corpus):
        return None
    urls = (pair_info.get("websites") or []) + (pair_info.get("socials") or []) if is_pair else record.get("links") or []
    website, social = social_links(urls)
    source = link(record.get("url", "")) or ("https://dexscreener.com/bsc/" + addr)
    if not name:
        name = "BSC Agent token " + addr[:8] + "…"
    pair_date = iso_day(record.get("pairCreatedAt"))
    return {
        "id": "dex-bsc-" + addr.lower(),
        "name": name,
        "symbol": symbol or "DEX",
        "category": "token",
        "chain": "BNB Chain",
        "type": "candidate",
        "stage": "unverified",
        "source": source,
        "website": website or source,
        "socialX": social,
        "contractAddress": addr,
        "descriptionZh": "DEX Screener 发现的 BSC Agent 主题代币线索。项目的 AI Agent 功能及安全性未经独立核验。" + ((" 来源描述：" + desc[:160]) if desc else ""),
        "descriptionEn": "BSC agent-themed token lead from DEX Screener. Agent functionality and safety have not been independently verified.",
        "tags": ["DEX Screener", "Candidate", "Unverified"],
        "mint": "unknown",
        "evidence": "DEX Screener public profile or pair metadata only; token listing does not establish an AI Agent product.",
        "date": pair_date,
        "projectCreatedAt": pair_date,
        "firstSeen": DATE,
        "lastCheckedAt": STAMP,
        "discoverySource": "dexscreener-" + origin,
        "verification": "token-metadata-only",
    }


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.words = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.words.append(data)


def official_candidates(page):
    parser = PlainText()
    parser.feed(page)
    body = " ".join(parser.words)
    result = []
    for name in OFFICIAL_NAMES:
        if not re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", body, re.I):
            continue
        result.append({
            "id": "bnb-official-mention-" + re.sub(r"[^a-z0-9]+", "-", name.lower()),
            "name": name,
            "symbol": "BNB",
            "category": "ecosystem",
            "chain": "BNB Chain",
            "type": "ecosystem",
            "stage": "source-mentioned",
            "source": OFFICIAL_PAGE,
            "website": OFFICIAL_PAGE,
            "descriptionZh": "BNB Chain 官方 AI Agent 生态页面提及的项目；上线时间和独立功能尚未在此核验。",
            "descriptionEn": "Mentioned on BNB Chain's official AI ecosystem page; independent project details not verified here.",
            "tags": ["Official source mention", "Ecosystem"],
            "mint": "unknown",
            "evidence": "Project name found on BNB Chain official AI Agent ecosystem page.",
            "date": "",
            "firstSeen": DATE,
            "lastCheckedAt": STAMP,
            "discoverySource": "bnbchain-ecosystem-page",
            "verification": "official-mention-only",
        })
    return result


def merge(old, found):
    prior = {r["id"]: r for r in old if isinstance(r, dict) and r.get("id")}
    added = updated = 0
    for p in found:
        before = prior.get(p["id"])
        if before:
            p["firstSeen"] = before.get("firstSeen") or p["firstSeen"]
            # Do not create a new last-checked timestamp on unchanged content.
            changes = ["name", "descriptionZh", "website", "socialX", "source", "stage"]
            if not any(before.get(k) != p.get(k) for k in changes):
                p["lastCheckedAt"] = before.get("lastCheckedAt", p["lastCheckedAt"])
            else:
                updated += 1
            prior[p["id"]] = {**before, **p}
        else:
            prior[p["id"]] = p
            added += 1
    # Keep confirmed official-mentions separate from early DEX candidates.
    ecosystem = [p for p in prior.values() if p.get("discoverySource") == "bnbchain-ecosystem-page"]
    dex = [p for p in prior.values() if str(p.get("discoverySource", "")).startswith("dexscreener-")]
    dex.sort(key=lambda p: p.get("firstSeen", ""), reverse=True)
    return ecosystem[:30] + dex[:MAX_RECORDS], added, updated


def run():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {}
    old = previous.get("projects", [])
    seen = {}
    states = {}
    for label, url in DEX_ENDPOINTS:
        try:
            response = json.loads(request(url))
            entries = response.get("pairs", []) if isinstance(response, dict) else response
            if not isinstance(entries, list):
                raise ValueError("Unexpected data format")
            count = 0
            for item in entries:
                p = dex_project(item, label)
                if p:
                    seen[p["id"]] = p
                    count += 1
            states[label] = {"ok": True, "qualified": count}
        except (ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
            states[label] = {"ok": False, "reason": type(exc).__name__}
    try:
        candidates = official_candidates(request(OFFICIAL_PAGE))
        for item in candidates:
            seen[item["id"]] = item
        states["bnbchain-official"] = {"ok": True, "qualified": len(candidates)}
    except (ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
        states["bnbchain-official"] = {"ok": False, "reason": type(exc).__name__}

    final, added, updated = merge(old, seen.values())
    result = {
        "updatedAt": STAMP,
        "methodology": "DEX Screener metadata + BNB Chain official source mentions. Candidate is NOT a verified Agent, free mint, endorsement, or safety audit. firstSeen is Atlas collection time, not a launch date.",
        "sources": states,
        "newCount": added,
        "changedCount": updated,
        "projects": final
    }
    # Preserve all previous records when sources fail. Never erase data during outage.
    if not any(s["ok"] for s in states.values()) and previous:
        previous["sources"] = states
        previous["lastFailedAt"] = STAMP
        result = previous
    TARGET.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": states, "new": added, "updated": updated, "total": len(result.get("projects", []))}))
    return 0 if any(s["ok"] for s in states.values()) else 1


if __name__ == "__main__":
    sys.exit(run())
