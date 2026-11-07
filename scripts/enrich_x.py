#!/usr/bin/env python3
"""Make distinct, source-derived X project blurbs from public website metadata.

No X API requests, no wallet interactions, no LLM API, no paid services.
Entries with no meaningful external project page remain raw X posts, not projects.
"""
import argparse
import datetime as dt
import html
from html.parser import HTMLParser
import ipaddress
import json
import pathlib
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
X_FILE = ROOT / "data/x_projects.json"
OUT_FILE = ROOT / "data/x_profiles.json"
MAX_FETCHES = 12
MAX_BYTES = 160_000
UTC = dt.timezone.utc
PROJECT_WORDS = re.compile(
    r"\b(agent(?:ic|s)?|mint(?:ing)?|NFT|token|staking|on.?chain|crypto|blockchain|BNB|BSC|wallet|"
    r"game|collectible|claim|DeFi|panda|robots?|pixel|ai|launchpad|smart contract)\b|智能体|铸造|钱包|区块链",
    re.I
)
SKIP = {"x.com", "twitter.com", "t.co", "localhost", "127.0.0.1", "dexscreener.com",
        "bscscan.com", "github.com", "google.com"}
NOISE = re.compile(r"(?i)^(home|homepage|welcome|mint|agent|coming soon|launching soon|dashboard|"
                   r"connect wallet|click here|loading|website|nothing here)$")


def clean(s, limit=230):
    s = html.unescape(re.sub(r"\s+", " ", str(s or ""))).strip()
    return re.sub(r"[\x00-\x1f]", " ", s)[:limit]


def get_host(url):
    try:
        u = urllib.parse.urlsplit(str(url or ""))
        host = (u.hostname or "").lower().removeprefix("www.")
        if u.scheme != "https" or not host or "." not in host or u.username or u.password:
            return ""
        if host in SKIP or any(host.endswith("." + a) for a in SKIP):
            return ""
        if any(host.endswith(x) for x in (".local", ".internal", ".localhost", ".test", ".invalid")):
            return ""
        if len(host) > 90 or not re.fullmatch(r"[a-z0-9.-]+", host):
            return ""
        try:
            ipaddress.ip_address(host)
            return ""  # refuse IP literals; also prevents localhost/metadata IPs
        except ValueError:
            pass
        return host
    except ValueError:
        return ""


class Metas(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.title = ""
        self.heading = ""
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key in ("og:title", "twitter:title", "description", "og:description", "twitter:description"):
                val = clean(attrs.get("content"), 320)
                if val:
                    self.meta[key] = val
        if tag == "title":
            self._in_title = True
        if tag == "h1" and not self.heading:
            self._in_h1 = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data[:180]
        if self._in_h1 and not self.heading:
            self.heading = clean(data, 140)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def public_dns(host):
    """Avoid fetching private service targets from untrusted X URLs."""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses:
            return False
        for info in addresses:
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                return False
        return True
    except (socket.gaierror, ValueError, OSError):
        return False


def scrape(url):
    host = get_host(url)
    if not host or not public_dns(host):
        return None
    # Only fetch the origin homepage. Do not follow arbitrary paths/redirects.
    target = "https://" + host + "/"
    req = urllib.request.Request(target, headers={
        "User-Agent": "AgentAtlasDiscovery/1.0 (+https://agentatlas.vip)",
        "Accept": "text/html",
    })
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=3) as res:
            if not (res.headers.get("Content-Type", "").lower().startswith("text/html")):
                return None
            body = res.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                return None
            encoding = res.headers.get_content_charset() or "utf-8"
        parser = Metas()
        parser.feed(body.decode(encoding, "replace"))
    except (urllib.error.URLError, OSError, ValueError, UnicodeError, LookupError):
        return None
    name = clean(parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.heading or parser.title, 95)
    desc = clean(parser.meta.get("og:description") or parser.meta.get("description") or parser.meta.get("twitter:description"), 220)
    if NOISE.fullmatch(name) or len(name) < 7:
        name = host
    if len(desc) < 35 or not PROJECT_WORDS.search(desc + " " + name):
        return None
    # Preserve the homepage's own words, but do NOT hallucinate a Chinese translation.
    short = clean(desc, 155)
    intro = "官网介绍「" + short + "」。该描述来自项目页面，具体功能与参与规则请以原始来源为准。"
    return {"domain": host, "name": name, "descriptionZh": intro,
            "descriptionEn": desc, "source": target, "sourceKind": "website-metadata"}


def profile_summary(x_posts, prior, now):
    seen_urls = {}
    for p in x_posts:
        if not re.fullmatch(r"x-post-\d+", str(p.get("id") or "")):
            continue
        host = get_host(p.get("website"))
        if not host:
            continue
        seen_urls.setdefault(host, p["website"])
    known = {p["domain"]: p for p in prior if isinstance(p, dict) and get_host("https://" + str(p.get("domain") or ""))}
    queries = 0
    new = 0
    for host, url in sorted(seen_urls.items()):
        existing = known.get(host)
        # Retain individually researched Chinese summaries instead of overwriting
        # them with scraped English marketing metadata.
        if existing and existing.get("sourceKind") == "editorial-source-review":
            continue
        if existing and existing.get("descriptionZh") and existing.get("sourceKind") == "website-metadata":
            last = str(existing.get("checkedAt") or "")[:10]
            if last:
                try:
                    if (now.date() - dt.date.fromisoformat(last)).days < 7:
                        continue
                except ValueError:
                    pass
        if queries >= MAX_FETCHES:
            break
        queries += 1
        record = scrape(url)
        if record:
            record["checkedAt"] = now.isoformat()
            record["firstSeen"] = (existing or {}).get("firstSeen") or now.date().isoformat()
            if not existing:
                new += 1
            known[host] = record
    result = {"updatedAt": now.isoformat(), "profiles": sorted(known.values(), key=lambda p: p["domain"]),
              "scannedThisRun": queries, "newProfiles": new,
              "methodology": "Public HTTPS metadata only. Descriptions are sourced summaries or quotes, not independent verification."}
    return result


def self_test():
    a = Metas()
    a.feed('<html><head><title>Agent Panda - BSC</title><meta name="description" '
           'content="An onchain NFT card project on BNB Chain for AI agents, with pandas and trading."></head></html>')
    assert a.title == "Agent Panda - BSC"
    assert len(a.meta["description"]) > 35
    assert get_host("https://agentpandabnb.xyz/mint") == "agentpandabnb.xyz"
    for bad in ("http://example.org", "https://127.0.0.1/", "https://169.254.169.254/",
                "https://localhost/", "javascript:alert(1)", "https://user:pass@example.org"):
        assert not get_host(bad), bad
    print("PASS: website metadata parser, URL restrictions and no X API call")
    return 0


def run():
    now = dt.datetime.now(UTC)
    data = json.loads(X_FILE.read_text(encoding="utf-8"))
    old = json.loads(OUT_FILE.read_text(encoding="utf-8")) if OUT_FILE.exists() else {}
    result = profile_summary(data.get("projects", []), old.get("profiles", []), now)
    OUT_FILE.parent.mkdir(exist_ok=True, parents=True)
    OUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sourceDomains": len({get_host(x.get("website")) for x in data.get("projects", []) if get_host(x.get("website"))}),
                      "cachedProfiles": len(result["profiles"]), "probed": result["scannedThisRun"],
                      "new": result["newProfiles"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    raise SystemExit(self_test() if args.self_test else run())
