#!/usr/bin/env python3
"""AgentAtlas conservative, source-based BSC project identity and catalog builder.

Read-only, offline, standard library only. Raw discovery JSONs are never rewritten.
Do not merge by name, broad platform domain, or mere shared Agent terminology.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import urllib.parse
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UTC = dt.timezone.utc
ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
GENERIC_DOMAINS = {
    "github.com", "www.github.com", "x.com", "www.x.com", "twitter.com",
    "t.co", "www.bnbchain.org", "bnbchain.org", "web3.binance.com",
    "developers.binance.com", "binance.com", "agentidhub.eth.limo",
    "boltbook.fun", "dexscreener.com", "www.dexscreener.com",
    "pancakeswap.finance", "bscscan.com",
}
HIGH_QUALITY = {"curated", "mint", "x-profile"}
ORIGIN_PRIORITY = {"curated": 95, "mint": 88, "x": 72, "official": 58, "github": 46, "dex": 30}
SOURCE_LIMIT = 18


def read(path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def clean(value, max_chars=240):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_chars]


def url_parts(value):
    try:
        u = urllib.parse.urlsplit(str(value or ""))
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            return None
        return u
    except ValueError:
        return None


def site_key(url):
    """Exact site or provider-specific project identity; NEVER merge all hosted tenants."""
    u = url_parts(url)
    if not u:
        return ""
    host = u.hostname.lower().removeprefix("www.")
    segs = [x for x in u.path.lower().strip("/").split("/") if x]
    if host in ("github.com",):
        return "repo:" + "/".join(segs[:2]) if len(segs) >= 2 else ""
    if host == "dappbay.bnbchain.org":
        return "dappbay:" + segs[1] if len(segs) >= 2 and segs[0] == "detail" else ""
    if host in GENERIC_DOMAINS:
        return ""
    if host.endswith(".github.io"):
        return "site:" + host + ("/" + segs[0] if segs else "")
    # pages.dev, vercel.app and surge.sh tenants use distinct hostnames.
    # a shared project host by itself is still not a legal identity by name alone.
    return "site:" + host


def platform_source(url):
    u = url_parts(url)
    if not u:
        return ""
    host = u.hostname.lower().removeprefix("www.")
    if host in ("x.com", "twitter.com"):
        return "x"
    if host == "github.com":
        return "github"
    if host == "dexscreener.com":
        return "dex"
    if host in ("bnbchain.org", "dappbay.bnbchain.org"):
        return "official"
    return "curated"


def normalized_name(name):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(name or "").casefold())


def fallback_name(item, website, source):
    """Empty discovery names fall back to the repo slug, never to a blank card."""
    for url in (website, source):
        u = url_parts(url)
        if not u:
            continue
        host = (u.hostname or "").lower().removeprefix("www.")
        segs = [x for x in u.path.strip("/").split("/") if x]
        if host == "github.com" and len(segs) >= 2:
            return segs[1]
        if host and host not in GENERIC_DOMAINS:
            return host
    return ""


def bsc_related(item):
    chain = str(item.get("chain") or "")
    if re.search(r"\bopBNB\b", chain, re.I) and not re.search(r"\bBSC\b|\bBNB (?:Smart )?Chain\b", chain, re.I):
        return False
    if re.search(r"\bBSC\b|\bBNB (?:Smart )?Chain\b", chain, re.I):
        return True
    # "Multi-chain" requires explicit evidence of BSC; do not assume.
    if re.search(r"multi[- ]chain", chain, re.I):
        evidence = " ".join(str(item.get(x) or "") for x in ("descriptionZh", "descriptionEn", "evidence"))
        return bool(re.search(r"\bBSC\b|\bBNB (?:Smart )?Chain\b", evidence, re.I))
    return False


def valid_contract(item):
    addr = str(item.get("contractAddress") or "").strip()
    return addr.lower() if ADDRESS.fullmatch(addr) else ""


def desc_quality(text, name=""):
    t = clean(text, 460)
    if not t:
        return 0
    if any(q in t for q in ("X 上发现与 BSC AI Agent 相关", "BNB Chain 官方生态页面提及的", "DEX Screener 发现的 BSC Agent 主题代币线索", "GitHub 公开候选项目：")):
        return 0
    if "官网介绍「" in t:
        return 1
    return 3 if len(t) >= 40 else 1


def unique_desc(item, kind, translations, profile=None):
    name = clean(item.get("name") or "未命名项目", 85)
    translated = clean(translations.get(item.get("id")), 450)
    if translated and desc_quality(translated) >= 2:
        return translated, "reviewed-translation"
    if kind == "x" and profile and desc_quality(profile.get("descriptionZh")):
        return clean(profile.get("descriptionZh"), 450), profile.get("sourceKind", "website-metadata")
    zh = clean(item.get("descriptionZh"), 450)
    if desc_quality(zh):
        return zh, "source-description"
    en = clean(item.get("descriptionEn"), 300)
    if kind == "github":
        english = re.sub(r"^(Public GitHub discovery candidate: |GitHub 公开候选项目：)", "", en or zh, flags=re.I).strip()
        if len(english) >= 22 and not english.startswith("Public GitHub repo"):
            return "仓库「" + name + "」公开介绍：" + english[:200], "github-repository-description"
        return "「" + name + "」的开源仓库已被发现，公开资料暂不足以说明具体功能。", "limited-source"
    if kind == "official":
        return "BNB Chain 生态目录列出了「" + name + "」，可从来源页面了解其产品和进展。", "official-directory-mention"
    if kind == "dex":
        return "在 BSC 的 DEX 资料中发现「" + name + "」代币线索；代币信息本身不能证明存在可运行的 Agent 产品。", "dex-token-metadata"
    if kind == "x":
        return "发现与「" + name + "」相关的 X 帖子，但尚未取得足够的独立产品介绍。", "limited-source"
    return "来源页面提到了「" + name + "」，详情请查看项目的原始介绍。", "limited-source"


def candidates(data, translations, profiles):
    all_items = []
    review = []
    for collection, origin in (("projects", "curated"), ("external", "external"), ("mint", "mint"), ("x", "x")):
        for item in data[collection]:
            if not isinstance(item, dict) or not bsc_related(item):
                continue
            orig = origin
            if collection == "projects":
                orig = "github" if item.get("discoverySource") == "github-search" else (
                    "official" if item.get("type") == "official" or "bnbchain.org" in str(item.get("source")) else "curated")
            elif collection == "external":
                orig = "dex" if str(item.get("discoverySource") or "").startswith("dexscreener-") else "official"
            if collection == "mint" and item.get("mintType") not in ("free", "paid"):
                continue
            ref = clean(item.get("id"), 100)
            website = str(item.get("website") or (item.get("source") if origin == "mint" else "") or "")
            official_site = site_key(website)
            if collection == "x":
                host = url_parts(website)
                dom = host.hostname.lower().removeprefix("www.") if host else ""
                profile = profiles.get(dom)
                if not profile or not desc_quality(profile.get("descriptionZh")):
                    review.append({"id": ref, "name": clean(item.get("name"), 100),
                                   "reason": "x-post-without-specific-product-evidence",
                                   "source": clean(item.get("source"), 500)})
                    continue
            else:
                profile = None
            title = clean((profile or {}).get("name") or item.get("name"), 110) or fallback_name(item, website, str(item.get("source") or ""))
            description, basis = unique_desc(item, orig, translations, profile)
            if collection == "mint" and item.get("researchSource"):
                evidence = item.get("researchSource")
            else:
                evidence = (profile or {}).get("source") or item.get("source") or website
            contract = valid_contract(item)
            key = official_site
            if collection == "x" and not key:
                review.append({"id": ref, "name": title, "reason": "x-post-without-project-site",
                               "source": clean(item.get("source"), 500)})
                continue
            dated = str(item.get("firstSeen") or item.get("discoveredAt") or item.get("date") or "")[:10]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dated):
                dated = ""
            updated = str(item.get("lastActivityAt") or item.get("date") or dated or "")[:10]
            category = clean(item.get("category") or ("gaming" if "game" in str(item.get("kind")) else
                        "token" if "token" in str(item.get("kind")) else "ecosystem"), 32)
            all_items.append({
                "id": ref, "name": title, "descriptionZh": description, "descriptionEn": clean(item.get("descriptionEn") or (profile or {}).get("descriptionEn"), 450),
                "descriptionBasis": basis, "origin": orig, "siteKey": key,
                "website": website, "source": str(item.get("source") or website or ""),
                "evidenceUrl": str(evidence or ""), "socialX": str(item.get("socialX") or (item.get("source") if orig == "x" else "") or ""),
                "contractAddress": contract, "category": category, "type": item.get("type") or ("ecosystem" if orig == "mint" else "candidate"),
                "tags": item.get("tags") or [], "firstSeen": dated, "date": updated if re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated) else "",
                "priority": ORIGIN_PRIORITY.get(orig, 0) + (10 if basis == "reviewed-translation" else 5 if basis == "editorial-source-review" else 0),
                "mintType": item.get("mintType") if orig == "mint" else "",
            })
    return all_items, review


def combine(items, existing=None):
    """Deterministic identity union with contract-conflict veto and review queue."""
    existing = existing or []
    persistent = {}
    for p in existing:
        for sid in p.get("recordIds", []):
            persistent[sid] = p.get("id", "")
    ordered = sorted(items, key=lambda x: (-x["priority"], x["id"]))
    groups = []
    keys = defaultdict(list)
    conflicts = []
    for item in ordered:
        # Narrow exception: same official name + same exact official source,
        # no contract on either side. bnbchain.org is a generic hub, so it
        # yields no siteKey; without this, the same official listing appears
        # twice (curated copy + ecosystem-page copy). Different names, or a
        # contract on either side, never merge here.
        official_key = ""
        if item["origin"] == "official" and not item["contractAddress"] and item["source"]:
            nn = normalized_name(item["name"])
            if len(nn) >= 4:
                official_key = "official-name:" + nn + "|" + item["source"]
        possible = set()
        for key in ([item["siteKey"]] if item["siteKey"] else []) + (
                ["contract:bsc:" + item["contractAddress"]] if item["contractAddress"] else []) + (
                [official_key] if official_key else []):
            possible.update(keys.get(key, []))
        compatible = []
        for idx in sorted(possible):
            g = groups[idx]
            addresses = {x["contractAddress"] for x in g if x["contractAddress"]}
            if addresses and item["contractAddress"] and item["contractAddress"] not in addresses:
                conflicts.append({"name": item["name"], "recordIds": [item["id"]] + [x["id"] for x in g[:4]],
                                  "reason": "same-site-different-BSC-contracts-review-before-merge",
                                  "source": item["source"]})
                continue
            compatible.append(idx)
        # If multiple possible groups conflict, do not silently bridge them.
        if len(compatible) > 1:
            distinct_contracts = {v["contractAddress"] for i in compatible for v in groups[i] if v["contractAddress"]}
            if len(distinct_contracts) > 1:
                conflicts.append({"name": item["name"], "recordIds": [item["id"]],
                                  "reason": "multiple-identity-groups-conflict", "source": item["source"]})
                compatible = []
        if compatible:
            chosen = compatible[0]
            groups[chosen].append(item)
        else:
            chosen = len(groups)
            groups.append([item])
        if item["siteKey"] and chosen not in keys[item["siteKey"]]:
            keys[item["siteKey"]].append(chosen)
        if item["contractAddress"] and chosen not in keys["contract:bsc:" + item["contractAddress"]]:
            keys["contract:bsc:" + item["contractAddress"]].append(chosen)
        if official_key and chosen not in keys[official_key]:
            keys[official_key].append(chosen)
    # Colliding project names without a matching identity should stay separate.
    name_groups = defaultdict(list)
    for idx, group in enumerate(groups):
        if not group:
            continue
        best = sorted(group, key=lambda x: (-x["priority"], x["id"]))[0]
        name_groups[normalized_name(best["name"])].append((idx, best))
    for name, pairs in name_groups.items():
        if len(pairs) > 1 and len(name) >= 5:
            conflicts.append({"name": pairs[0][1]["name"], "reason": "same-name-different-identity-review",
                              "recordIds": [p[1]["id"] for p in pairs[:6]],
                              "source": pairs[0][1]["source"]})
    records = []
    for group in groups:
        if not group:
            continue
        group.sort(key=lambda x: (-x["priority"], x["id"]))
        primary = group[0]
        record_ids = sorted(set(p["id"] for p in group))
        previous = sorted({persistent[id] for id in record_ids if persistent.get(id)})
        catalog_id = previous[0] if len(previous) == 1 else primary["id"]
        origins = sorted(set(p["origin"] for p in group))
        # Prefer a specific summary over generic text even when its source is newer.
        best_description = sorted(group, key=lambda x: (
            -(3 if x["descriptionBasis"] in ("reviewed-translation", "editorial-source-review") else
               2 if x["descriptionBasis"] in ("source-description", "website-metadata", "github-repository-description") else 1),
            -x["priority"], x["id"]))[0]
        unique_sources = []
        urls = set()
        for p in group:
            for url, typ in ((p["source"], p["origin"]), (p["evidenceUrl"], "evidence")):
                if not url_parts(url) or url in urls:
                    continue
                urls.add(url)
                unique_sources.append({"source": typ, "url": url})
                if len(unique_sources) >= SOURCE_LIMIT:
                    break
            if len(unique_sources) >= SOURCE_LIMIT:
                break
        dates = sorted(x["firstSeen"] for x in group if x["firstSeen"])
        changed = sorted((x["date"] for x in group if x["date"]), reverse=True)
        sites = [p["website"] for p in group if p["siteKey"] and not p["siteKey"].startswith("repo:")]
        website = sites[0] if sites else primary["website"]
        contract = next((p["contractAddress"] for p in group if p["contractAddress"]), "")
        is_dex_only = origins == ["dex"]
        category = "token" if is_dex_only else next((p["category"] for p in group if p["origin"] != "dex"), primary["category"])
        evidence_level = ("source-backed-product" if best_description["descriptionBasis"] in (
            "reviewed-translation", "editorial-source-review", "website-metadata", "source-description") else
            "repository-description" if best_description["descriptionBasis"] == "github-repository-description" else
            "early-lead")
        records.append({
            "id": catalog_id, "name": primary["name"], "descriptionZh": best_description["descriptionZh"],
            "descriptionEn": best_description["descriptionEn"], "descriptionBasis": best_description["descriptionBasis"],
            "category": category, "chain": "BNB Chain", "type": primary["type"],
            "source": primary["source"], "website": website,
            "socialX": next((p["socialX"] for p in group if p["socialX"]), ""),
            "contractAddress": contract, "firstSeen": dates[0] if dates else "",
            "lastActivityAt": changed[0] if changed else "", "date": changed[0] if changed else "",
            "tags": list(dict.fromkeys(str(t) for p in group for t in p["tags"]))[:12],
            "origins": origins, "origin": primary["origin"], "recordIds": record_ids,
            "sources": unique_sources, "evidenceLevel": evidence_level,
            "mintTypes": sorted(set(p["mintType"] for p in group if p["mintType"])),
            "featured": primary["origin"] in ("curated", "official") and primary["type"] in ("ecosystem", "official"),
        })
    records.sort(key=lambda p: (p.get("firstSeen", ""), p["name"].lower()), reverse=True)
    return records, conflicts


def build(inputs, old=None, now=None):
    now = now or dt.datetime.now(UTC)
    docs = {
        "projects": inputs.get("projects", {}).get("projects", []),
        "external": inputs.get("external", {}).get("projects", []),
        "x": inputs.get("x", {}).get("projects", []),
        "mint": inputs.get("mint", {}).get("opportunities", []),
    }
    translations = inputs.get("translations", {}).get("translations", {})
    profiles = {str(p.get("domain", "")).lower(): p for p in inputs.get("profiles", {}).get("profiles", [])}
    candidates_list, pending = candidates(docs, translations, profiles)
    catalog, conflicts = combine(candidates_list, (old or {}).get("projects", []))
    # Never silently assert that an X match makes a project legitimate.
    reviews = (pending + conflicts)[:500]
    report = {"updatedAt": now.isoformat(), "projects": catalog,
              "inputCounts": {k: len(v) for k, v in docs.items()},
              "candidateRecords": len(candidates_list), "mergedGroups": len(catalog),
              "reviewCount": len(reviews),
              "methodology": "Conservative BSC-only identity merge on project-specific HTTPS site, exact GitHub repo or exact BSC contract; conflicting tokens and same-name cases stay separate. Source summaries are not audits or verification."}
    queue = {"updatedAt": now.isoformat(), "items": reviews,
             "methodology": "Raw candidate evidence retained in its original discovery files. Review before asserting identity or product functionality."}
    return report, queue


def self_test():
    base = {"chain": "BNB Chain", "category": "ecosystem", "descriptionZh": "这是一份针对 Agent 卡牌经济的产品介绍，涵盖自动战斗、卡牌等级和参与机制。"}
    inputs = {"projects": {"projects": [
        dict(base, id="p1", name="Panda", website="https://panda.example/", source="https://panda.example/"),
        dict(base, id="p2", name="Other Token", website="https://token.example/another", source="https://token.example/another", contractAddress="0x" + "1"*40),
        dict(base, id="p3", name="Other Token", website="https://token.example/y", source="https://token.example/y", contractAddress="0x" + "2"*40),
        dict(base, id="p4", name="Wallet One", website="https://web3.binance.com/en/agentic-hub", source="https://web3.binance.com/en/agentic-hub"),
        dict(base, id="p5", name="Wallet Two", website="https://web3.binance.com/en/agentic-hub", source="https://web3.binance.com/en/agentic-hub"),
        dict(base, id="p6", name="Wrong Chain", chain="opBNB", website="https://bad.example", source="https://bad.example"),
    ]}, "x": {"projects": [
        {"id":"x-post-12345","name":"Panda X","chain":"BNB Chain (X claim only)","website":"https://panda.example/mint",
         "source":"https://x.com/i/web/status/12345","firstSeen":"2026-11-04"}
    ]}, "profiles": {"profiles": [
        {"domain":"panda.example","name":"Panda","descriptionZh":base["descriptionZh"],"sourceKind":"editorial-source-review"}
    ]}, "mint":{"opportunities":[]}, "external":{"projects":[]}, "translations":{"translations":{}}}
    result, queue = build(inputs, now=dt.datetime(2026, 11, 7, tzinfo=UTC))
    matched = [p for p in result["projects"] if set(("p1", "x-post-12345")).issubset(set(p["recordIds"]))]
    assert len(matched) == 1, matched
    assert not any(p["name"] == "Wrong Chain" for p in result["projects"])
    assert any(x["reason"].startswith("same-site-different") for x in queue["items"])
    assert not any({"p4", "p5"}.issubset(set(p["recordIds"])) for p in result["projects"])
    assert len(result["projects"]) == 5, result["mergedGroups"]
    result2, _ = build(inputs, result, now=dt.datetime(2026, 11, 7, tzinfo=UTC))
    assert {p["id"] for p in result["projects"]} == {p["id"] for p in result2["projects"]}
    # Same official name + same exact official source merges; empty GitHub
    # names fall back to the repo slug instead of a blank card.
    inputs2 = {"projects": {"projects": [
        dict(base, id="o1", name="BNBAgent SDK", type="official", website="https://www.bnbchain.org/en/solutions/ai-agent", source="https://www.bnbchain.org/en/solutions/ai-agent"),
        dict(base, id="g1", name="", website="https://github.com/NachoLLMJS/STONKMUSE", source="https://github.com/NachoLLMJS/STONKMUSE", discoverySource="github-search"),
    ]}, "x": {"projects": []}, "profiles": {"profiles": []}, "mint": {"opportunities": []},
      "external": {"projects": [
        dict(base, id="o2", name="BNBAgent SDK", type="ecosystem", website="https://www.bnbchain.org/en/solutions/ai-agent", source="https://www.bnbchain.org/en/solutions/ai-agent", discoverySource="bnbchain-ecosystem-page"),
    ]}, "translations": {"translations": {}}}
    result3, _ = build(inputs2, now=dt.datetime(2026, 11, 7, tzinfo=UTC))
    merged = [p for p in result3["projects"] if set(("o1", "o2")).issubset(set(p["recordIds"]))]
    assert len(merged) == 1, result3["projects"]
    assert any(p["name"] == "STONKMUSE" for p in result3["projects"]), result3["projects"]
    assert not any(not p["name"] for p in result3["projects"])
    print("PASS: BSC scope, site dedup, contract collision veto, shared hub exclusion, stable IDs.")
    return 0


def run():
    now = dt.datetime.now(UTC)
    files = {"projects": "projects.json", "external": "external_projects.json",
             "x": "x_projects.json", "mint": "opportunities.json",
             "profiles": "x_profiles.json", "translations": "project_zh.json"}
    inputs = {k: read(DATA / v, {}) for k, v in files.items()}
    old = read(DATA / "catalog.json", {})
    result, review = build(inputs, old, now)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "catalog.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DATA / "review_queue.json").write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"rawSources": result["inputCounts"], "acceptedRecords": result["candidateRecords"],
                      "uniqueProjects": result["mergedGroups"], "reviewItems": result["reviewCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    raise SystemExit(self_test() if args.self_test else run())
