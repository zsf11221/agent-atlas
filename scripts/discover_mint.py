#!/usr/bin/env python3
"""Project discovery -> Mint/claim watchlist. Standard-library only, no external requests.

This is a discovery queue, NOT a list of available, safe or cost-verified mints.
Published leads require an external HTTPS project link and an X post source.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
X_FILE = DATA / "x_projects.json"
CURATED_FILE = DATA / "opportunities.json"
OUT_FILE = DATA / "mint_leads.json"
STATUS_FILE = DATA / "mint_pipeline_status.json"
MAX_LEADS = 70
POST_ID = re.compile(r"^x-post-[0-9]+$")
MINT_HINT = re.compile(r"Mint 或参与公告|(?:mint|铸造|claim|领取|白名单|whitelist)", re.I)
SKIP_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "t.co",
              "dexscreener.com", "www.dexscreener.com", "localhost"}
UTC = dt.timezone.utc


def read(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def hostname(url):
    try:
        u = urllib.parse.urlsplit(str(url or ""))
        host = (u.hostname or "").lower().removeprefix("www.")
        if (u.scheme != "https" or not host or "." not in host or host in SKIP_HOSTS
                or u.username or u.password or host.endswith(".x.com")
                or host.endswith(".twitter.com") or host.endswith(".local")):
            return ""
        return host
    except ValueError:
        return ""


def x_mint_candidate(post):
    if not isinstance(post, dict) or not POST_ID.fullmatch(str(post.get("id") or "")):
        return False
    source = str(post.get("source") or "")
    if not re.fullmatch(r"https://x\.com/i/web/status/[0-9]+", source):
        return False
    chain = str(post.get("chain") or "")
    if not re.search(r"BNB Chain|BSC", chain, re.I) or re.search(r"opBNB", chain, re.I):
        return False
    if not hostname(post.get("website")):
        return False
    signal = post.get("mintSignal")
    return (signal in ("mint", "claim") or
            (signal is None and bool(MINT_HINT.search(str(post.get("descriptionZh") or "")))))


def category_for(post):
    """A cost category is only a claim from a source; never a verification."""
    if post.get("mintSignal") != "mint":
        return "unknown"
    cost = post.get("claimedMintCost")
    return cost if cost in ("free", "paid") else "unknown"


def build(x_posts, curated, previous, stamp):
    prior = {p["id"]: p for p in previous if isinstance(p, dict) and p.get("id")}
    curated_domains = {hostname(p.get("source")) for p in curated}
    curated_domains.discard("")
    by_domain = {}
    qualifying = 0
    for x in x_posts:
        if not x_mint_candidate(x):
            continue
        qualifying += 1
        domain = hostname(x["website"])
        if domain in curated_domains:
            continue
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(x)
    leads = []
    for domain, posts in by_domain.items():
        # Choose newest post as the provenance; retain the original first-seen date.
        posts.sort(key=lambda p: (str(p.get("date") or ""), str(p.get("postId") or "")), reverse=True)
        latest = posts[0]
        ident = "mint-x-" + domain
        old = prior.get(ident, {})
        categories = {category_for(p) for p in posts if category_for(p) != "unknown"}
        kind = categories.pop() if len(categories) == 1 else "unknown"
        # Legacy records contain no explicit price evidence: keep them unknown.
        is_claimed = kind in ("free", "paid")
        if is_claimed:
            price = ("帖子声称免费 Mint；实际交易 Gas、条件及开放状态待核验"
                     if kind == "free" else "帖子声称付费 Mint；具体价格及开放状态待核验")
        else:
            price = "未确认；需查看原帖与项目规则"
        leads.append({
            "id": ident,
            "name": domain,
            "chain": "BNB Chain (X claim only)",
            "kind": "mint-or-claim-lead",
            "mintType": kind,
            "costVerification": "x-post-claim-only" if is_claimed else "unknown",
            "currentAvailability": "unknown",
            "mintVerified": False,
            "source": latest["source"],
            "website": latest["website"],
            "announcedCost": price,
            "descriptionZh": (
                "X 上出现与 BSC Agent 相关的 Mint 或领取线索，并提供了该网站链接。"
                "当前无法证明该网站确实开放 Mint；项目身份、费用、资格和合约安全都需要进一步核对。"
            ),
            "descriptionEn": (
                "An X post links to a site and mentions a BSC Agent mint or claim. "
                "The project, cost, availability, eligibility and contract safety are not verified."
            ),
            "firstSeen": old.get("firstSeen") or latest.get("firstSeen") or stamp.date().isoformat(),
            "postDate": latest.get("date") or "",
            "lastCheckedAt": stamp.isoformat(),
            "sourceCount": len(posts),
            "evidenceLevel": "unverified-x-lead",
        })
    leads.sort(key=lambda p: (p.get("postDate") or "", p.get("firstSeen") or ""), reverse=True)
    return leads[:MAX_LEADS], {
        "xRecords": len(x_posts),
        "matchingXPostsWithWebsite": qualifying,
        "uniqueLeadsBeforeCap": len(by_domain),
        "dedupedCuratedDomains": sum(1 for xs in x_posts if x_mint_candidate(xs) and hostname(xs.get("website")) in curated_domains),
        "displayedLeads": min(len(leads), MAX_LEADS),
        "freeClaims": sum(p["mintType"] == "free" for p in leads[:MAX_LEADS]),
        "paidClaims": sum(p["mintType"] == "paid" for p in leads[:MAX_LEADS]),
        "costUnknown": sum(p["mintType"] == "unknown" for p in leads[:MAX_LEADS]),
    }


def self_test():
    stamp = dt.datetime(2026, 11, 7, 9, tzinfo=UTC)
    fixture = lambda pid, web, signal=None, cost=None: {
        "id": "x-post-" + str(pid), "source": "https://x.com/i/web/status/" + str(pid),
        "website": web, "chain": "BNB Chain (X claim only)",
        "mintSignal": signal, "claimedMintCost": cost, "firstSeen": "2026-11-06",
        "date": "2026-11-06", "descriptionZh": "Mint 或参与公告"}
    x = [
        fixture(1234, "https://hello.example/mint", "mint", "free"),
        fixture(1235, "https://hello.example/mint", "mint", "free"),
        fixture(1236, "https://another.example/claim", "claim", "free"),
        fixture(1237, "https://x.com/i/web/status/1237", "mint", "paid"),
        fixture(1238, "https://old.example/mint", "mint", "paid"),
        {**fixture(1239, "https://opbnb.example/mint", "mint", "paid"), "chain": "opBNB"},
    ]
    curated = [{"source": "https://old.example/mint"}]
    leads, status = build(x, curated, [], stamp)
    assert len(leads) == 2 and status["matchingXPostsWithWebsite"] == 4, status
    by_id = {p["id"]: p for p in leads}
    assert by_id["mint-x-hello.example"]["mintType"] == "free"
    assert by_id["mint-x-hello.example"]["sourceCount"] == 2
    assert by_id["mint-x-another.example"]["mintType"] == "unknown"
    assert all(p["currentAvailability"] == "unknown" and p["mintVerified"] is False for p in leads)
    assert not hostname("javascript:alert(1)") and not hostname("http://localhost/admin")
    print("Mint self-test PASS: source check, cost-claim caution, X/curated dedup, opBNB exclusion.")
    return 0


def run():
    stamp = dt.datetime.now(UTC)
    data = read(X_FILE, {"projects": []})
    curated = read(CURATED_FILE, {"opportunities": []})
    previous = read(OUT_FILE, {"leads": []})
    leads, counts = build(data.get("projects", []), curated.get("opportunities", []),
                          previous.get("leads", []), stamp)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "updatedAt": stamp.isoformat(),
        "leads": leads,
        "methodology": (
            "Public X posts with external HTTPS project links that mention BSC Agent mint/claim. "
            "Unverified watchlist, not proof of a real mint, live status, eligibility or safe contract. "
            "Only explicit cost claims can be classified free/paid; all legacy X leads are unknown."
        ),
    }
    status = {"checkedAt": stamp.isoformat(), "state": "ok", **counts,
              "note": "No network/API requests. Reads existing X and curated records only."}
    OUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    sys.exit(self_test() if args.self_test else run())
