#!/usr/bin/env python3
"""Build the Agent Atlas daily brief for one Beijing date.

Reads only local data files plus the public read-only Worker endpoints
(/v1/health, /v1/leads, /v1/mint-checks). No secrets, no API cost, no writes
to any catalog or queue. Writes data/daily/YYYY-MM-DD.json and refreshes
data/daily/index.json (latest first).

A day with no new projects is reported as a dry day, never padded with
unverified claims. Mint supply numbers only appear when a contract is
registered in D1 and checked on-chain; source claims stay labelled as claims.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DAILY = DATA / "daily"
WORKER = os.getenv("CHAIN_WORKER_URL", "https://agent-atlas-chain.zsf197176.workers.dev")
CST = dt.timezone(dt.timedelta(hours=8))
MAX_ITEMS = 12


def beijing_today():
    return dt.datetime.now(CST).date()


def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return fallback


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                              "User-Agent": "AgentAtlas-Daily-Report/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(200_001)
    if len(raw) > 200_000:
        raise ValueError("Oversized Worker response")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Unexpected Worker response")
    return data


def is_today(value, day):
    return isinstance(value, str) and value[:10] == day.isoformat()


def recent_days(value, day, days=7):
    if not isinstance(value, str) or len(value) < 10:
        return False
    try:
        seen = dt.date.fromisoformat(value[:10])
    except ValueError:
        return False
    # Same inclusive window as the site's "7天内" (atlasRecent): up to `days` back.
    return 0 <= (day - seen).days <= days


def short_item(name, source=""):
    item = {"name": (name or "未命名")[:80]}
    if source:
        item["source"] = source[:300]
    return item


def build_report(day, worker_base=WORKER, fetcher=fetch_json):
    stamp = dt.datetime.now(CST)
    catalog = read_json(DATA / "catalog.json", {"projects": []})
    projects = catalog.get("projects", []) if isinstance(catalog, dict) else []
    new_catalog = [p for p in projects if is_today(p.get("firstSeen"), day)]
    new_7d = [p for p in projects if recent_days(p.get("firstSeen"), day, 7)]

    x_data = read_json(DATA / "x_projects.json", {"projects": []})
    x_leads = x_data.get("projects", []) if isinstance(x_data, dict) else []
    new_x = [p for p in x_leads if is_today(p.get("firstSeen"), day)]
    by_source = {}
    for p in new_x:
        key = p.get("discoverySource") or "x-recent-search"
        by_source[key] = by_source.get(key, 0) + 1
    x_status = read_json(DATA / "x_pipeline_status.json", {})

    mint_data = read_json(DATA / "mint_leads.json", {"leads": []})
    mint_leads = mint_data.get("leads", []) if isinstance(mint_data, dict) else []
    mint_status = read_json(DATA / "mint_pipeline_status.json", {})
    free_claims = sum(1 for p in mint_leads if p.get("mintType") == "free")
    paid_claims = sum(1 for p in mint_leads if p.get("mintType") == "paid")
    unknown_cost = sum(1 for p in mint_leads if p.get("mintType") not in ("free", "paid"))
    new_mint = [p for p in mint_leads if is_today(p.get("discoveredAt"), day)]

    chain = {"available": False, "note": "链上扫描接口暂不可达，本节只写可核实的部分。"}
    verified_checks = []
    try:
        health = fetcher(worker_base.rstrip("/") + "/v1/health")
        leads = fetcher(worker_base.rstrip("/") + "/v1/leads?limit=30")
        checks = fetcher(worker_base.rstrip("/") + "/v1/mint-checks")
        last = health.get("lastScan") if isinstance(health, dict) else None
        chain = {
            "available": bool(health.get("ok")) if isinstance(health, dict) else False,
            "lastScan": last if isinstance(last, dict) else None,
            "candidateCount": health.get("candidateCount") if isinstance(health, dict) else None,
            "leadsToday": [short_item(p.get("name") or p.get("symbol"),
                                      "https://bscscan.com/token/" + p.get("address", ""))
                           for p in (leads.get("leads") or [])[:MAX_ITEMS]
                           if isinstance(leads, dict) and is_today(p.get("firstSeen"), day)],
            "note": "数据来自链上扫描 Worker（只读）。当日新对总数未单独统计，只列最近一轮扫描与今日候选。",
        }
        for c in (checks.get("checks") or [])[:MAX_ITEMS]:
            if not isinstance(c, dict):
                continue
            verified_checks.append({
                "mintId": c.get("mint_id"),
                "priceWei": c.get("price_wei"),
                "mintOpen": c.get("mint_open"),
                "totalSupply": c.get("total_supply"),
                "maxSupply": c.get("max_supply"),
                "checkedAt": c.get("checked_at"),
            })
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        chain = {"available": False, "note": "链上扫描接口暂不可达（%s），本节只写可核实的部分。" % type(exc).__name__}

    parts = []
    parts.append("目录新增 %d 个" % len(new_catalog) if new_catalog else "目录无新增")
    parts.append("X 新线索 %d 条" % len(new_x) if new_x else "X 无新线索")
    parts.append("Mint 线索 %d 条（免费 %d、付费 %d）" % (len(mint_leads), free_claims, paid_claims))
    if chain.get("available") and chain.get("lastScan"):
        last = chain["lastScan"]
        parts.append("链上最近一轮扫描 %d 个新对、%d 个候选" % (last.get("pairs_seen") or 0, last.get("candidates") or 0))
    elif not chain.get("available"):
        parts.append("链上扫描接口暂不可达")
    summary = "；".join(parts) + "。"

    return {
        "date": day.isoformat(),
        "generatedAt": stamp.isoformat(),
        "timezone": "Asia/Shanghai",
        "summaryZh": summary,
        "catalog": {
            "total": len(projects),
            "newTodayCount": len(new_catalog),
            "newToday": [short_item(p.get("name"), p.get("website") or p.get("source") or "")
                         for p in sorted(new_catalog, key=lambda p: p.get("name") or "")[:MAX_ITEMS]],
            "newLast7DaysCount": len(new_7d),
        },
        "x": {
            "newTodayCount": len(new_x),
            "bySource": by_source,
            "newToday": [short_item(p.get("name"), p.get("source") or "")
                         for p in sorted(new_x, key=lambda p: p.get("name") or "")[:MAX_ITEMS]],
            "reservedReadsThisMonth": x_status.get("reservedPostReads"),
            "monthlyCap": x_status.get("maxMonthlyPostReads"),
            "state": x_status.get("state"),
        },
        "mint": {
            "total": len(mint_leads),
            "freeClaims": free_claims,
            "paidClaims": paid_claims,
            "costUnknown": unknown_cost,
            "newTodayCount": len(new_mint),
            "newToday": [short_item(p.get("name"), p.get("source") or "")
                         for p in sorted(new_mint, key=lambda p: p.get("name") or "")[:MAX_ITEMS]],
            "verifiedChecks": verified_checks,
            "verifiedNote": ("已登记核验的 Mint 合约 %d 个，铸造量只写链上核验数；未登记的只写来源声称，不写进已铸数量。"
                             % len(verified_checks)),
        },
        "chain": chain,
        "notes": [
            "首次收录日期不代表项目创建日期；X 线索未经核实，不等于项目发布或安全背书。",
            "Mint 免费/付费是来源声称，未经链上核验前不作为费用结论。",
        ],
    }


def write_report(report):
    DAILY.mkdir(parents=True, exist_ok=True)
    path = DAILY / (report["date"] + ".json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index_path = DAILY / "index.json"
    index = read_json(index_path, {"reports": []})
    entries = [e for e in index.get("reports", []) if isinstance(e, dict) and e.get("date") != report["date"]]
    entries.append({
        "date": report["date"],
        "generatedAt": report["generatedAt"],
        "summaryZh": report["summaryZh"],
        "newCatalog": report["catalog"]["newTodayCount"],
        "newX": report["x"]["newTodayCount"],
        "mintFree": report["mint"]["freeClaims"],
        "mintPaid": report["mint"]["paidClaims"],
        "chainCandidates": (report["chain"].get("lastScan") or {}).get("candidates"),
    })
    entries.sort(key=lambda e: e.get("date") or "", reverse=True)
    index_path.write_text(json.dumps({
        "updatedAt": report["generatedAt"],
        "reports": entries[:60],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def self_test():
    import tempfile
    day = dt.date(2026, 11, 8)

    def fake_fetch(url, timeout=15):
        if url.endswith("/v1/health"):
            return {"ok": True, "chainId": 56, "candidateCount": 1,
                    "lastScan": {"id": 11, "ok": 1, "from_block": 100, "to_block": 140,
                                 "pairs_seen": 2, "candidates": 1,
                                 "started_at": "2026-11-08T07:30:17Z", "finished_at": "2026-11-08T07:30:18Z"}}
        if "/v1/leads" in url:
            return {"ok": True, "leads": [{"name": "Agent Test", "symbol": "AGT",
                                           "address": "0x" + "a" * 40, "firstSeen": "2026-11-08T07:30:00Z"}]}
        if url.endswith("/v1/mint-checks"):
            return {"ok": True, "checks": [{"mint_id": "agentlings", "price_wei": "0",
                                            "mint_open": 1, "total_supply": 8667, "max_supply": 10000,
                                            "checked_at": "2026-11-08T07:00:00Z"}]}
        raise ValueError("unexpected url " + url)

    with tempfile.TemporaryDirectory() as tmp:
        global DATA, DAILY
        old_data, old_daily = DATA, DAILY
        DATA = pathlib.Path(tmp) / "data"
        DAILY = DATA / "daily"
        (DATA).mkdir(parents=True)
        (DATA / "catalog.json").write_text(json.dumps({"projects": [
            {"name": "Today One", "firstSeen": "2026-11-08", "website": "https://today.one"},
            {"name": "Old One", "firstSeen": "2026-11-01", "website": "https://old.one"},
        ]}, ensure_ascii=False), encoding="utf-8")
        (DATA / "x_projects.json").write_text(json.dumps({"projects": [
            {"id": "x-post-1", "name": "X Today", "firstSeen": "2026-11-08",
             "source": "https://x.com/i/web/status/1", "discoverySource": "x-morning-report"},
        ]}, ensure_ascii=False), encoding="utf-8")
        (DATA / "x_pipeline_status.json").write_text(json.dumps(
            {"reservedPostReads": 340, "maxMonthlyPostReads": 2400, "state": "ok"}), encoding="utf-8")
        (DATA / "mint_leads.json").write_text(json.dumps({"leads": [
            {"name": "Free Mint", "mintType": "free", "discoveredAt": "2026-11-08", "source": "https://free.example"},
            {"name": "Paid Mint", "mintType": "paid", "discoveredAt": "2026-11-02", "source": "https://paid.example"},
        ]}, ensure_ascii=False), encoding="utf-8")
        (DATA / "mint_pipeline_status.json").write_text(json.dumps({"state": "ok"}), encoding="utf-8")
        try:
            report = build_report(day, fetcher=fake_fetch)
            assert report["date"] == "2026-11-08"
            assert report["catalog"]["newTodayCount"] == 1
            assert report["catalog"]["newLast7DaysCount"] == 2
            assert report["x"]["newTodayCount"] == 1
            assert report["x"]["bySource"] == {"x-morning-report": 1}
            assert report["mint"]["freeClaims"] == 1 and report["mint"]["paidClaims"] == 1
            assert report["mint"]["verifiedChecks"][0]["totalSupply"] == 8667
            assert report["chain"]["available"] is True
            assert len(report["chain"]["leadsToday"]) == 1
            assert "目录新增 1 个" in report["summaryZh"]
            path = write_report(report)
            assert path.exists()
            index = json.loads((DAILY / "index.json").read_text(encoding="utf-8"))
            assert index["reports"][0]["date"] == "2026-11-08"
            # Worker unreachable: report still builds, chain marked unavailable.
            def failing_fetch(url, timeout=15):
                raise urllib.error.URLError("down")
            dry = build_report(day, fetcher=failing_fetch)
            assert dry["chain"]["available"] is False
            assert dry["catalog"]["newTodayCount"] == 1
        finally:
            DATA, DAILY = old_data, old_daily
    print("Self-test PASS: daily brief counts, Beijing date, chain fallback, index.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--date", default=None, help="Beijing date YYYY-MM-DD (default: today)")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(self_test())
    day = dt.date.fromisoformat(args.date) if args.date else beijing_today()
    report = build_report(day)
    path = write_report(report)
    print(json.dumps({"date": report["date"], "path": str(path),
                      "summaryZh": report["summaryZh"]}, ensure_ascii=False))
