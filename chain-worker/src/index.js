// AgentAtlas BSC chain discovery — read-only Cloudflare Worker.
// Monitors PancakeSwap V2 PairCreated, NOT all BSC contracts or every launchpad.
const FACTORY = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73";
const PAIR_CREATED = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9";
const WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c";
const QUOTES = new Set([WBNB, "0x55d398326f99059ff775485246999027b3197955", "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"]);
const TOKEN_RE = /\b(agent(?:ic|s)?|ai|a\.i|bot|autonomous|mcp|agentid|agent-id)\b/i;
const ADDRESS = /^0x[a-fA-F0-9]{40}$/;
const CHUNK_BLOCKS = 250;
const CHUNKS_PER_RUN = 5;
const TOKEN_PROBES_PER_RUN = 30;
const RISK_CHECKS_PER_RUN = 4;
const MINT_CHECKS_PER_RUN = 2;
// Common read-only selectors. A mint contract is only checked when its own
// price selector was recorded in mint_contracts with evidence; never guess it.
const PAUSED_SELECTOR = "0x5c975abb";
const TOTAL_SUPPLY_SELECTOR = "0x18160ddd";
const LOOKBACK_ON_BOOT = 40;
const CONFIRMATIONS = 8;

const responseHeaders = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "public, max-age=25",
  "x-content-type-options": "nosniff",
  "access-control-allow-origin": "https://agentatlas.vip",
  "vary": "Origin"
};
const respond = (payload, status = 200) =>
  new Response(JSON.stringify(payload), { status, headers: responseHeaders });

export function parsePair(log) {
  const topics = log?.topics;
  if (!Array.isArray(topics) || topics.length !== 3 || topics[0]?.toLowerCase() !== PAIR_CREATED) return null;
  const data = String(log.data || "");
  if (!/^0x[0-9a-f]{128,}$/i.test(data)) return null;
  const token0 = "0x" + String(topics[1] || "").slice(-40).toLowerCase();
  const token1 = "0x" + String(topics[2] || "").slice(-40).toLowerCase();
  const pair = "0x" + data.slice(26, 66).toLowerCase();
  if (![token0, token1, pair].every(x => ADDRESS.test(x))) return null;
  const block = Number.parseInt(log.blockNumber, 16);
  if (!Number.isSafeInteger(block) || block < 0) return null;
  return { token0, token1, pair, block, txHash: String(log.transactionHash || "") };
}

// EVM ABI dynamic string or bytes32 result; token contracts can use either encoding.
export function decodeString(hex) {
  if (!/^0x(?:[a-f0-9]{2})*$/i.test(hex || "")) return "";
  const raw = hex.slice(2);
  if (!raw || raw.length > 16000) return "";
  try {
    let bytes;
    if (raw.length === 64) {
      bytes = raw.match(/.{2}/g).map(s => parseInt(s, 16)).filter(x => x !== 0);
    } else {
      if (raw.length < 128) return "";
      const offset = Number(BigInt("0x" + raw.slice(0, 64)));
      if (!Number.isSafeInteger(offset) || offset > 512 || offset % 32) return "";
      const start = offset * 2;
      const len = Number(BigInt("0x" + raw.slice(start, start + 64)));
      if (!Number.isSafeInteger(len) || len > 160 || start + 64 + len * 2 > raw.length) return "";
      bytes = raw.slice(start + 64, start + 64 + len * 2).match(/.{2}/g)?.map(s => parseInt(s, 16)) || [];
    }
    return new TextDecoder("utf-8", { fatal: false }).decode(Uint8Array.from(bytes)).replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, 90);
  } catch {
    return "";
  }
}

async function readJson(url, init, ms = 8500) {
  const res = await fetch(url, { ...init, signal: AbortSignal.timeout(ms) });
  if (!res.ok) throw new Error("upstream-http-" + res.status);
  return res.json();
}

async function rpc(env, method, params) {
  const data = await readJson(env.BSC_RPC_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params })
  });
  if (data?.error || data?.result == null) throw new Error("rpc-" + method + "-" + (data?.error?.code || "missing-result"));
  return data.result;
}

// Strict uint256 reader for mint price / supply calls. Returns a decimal
// string, or null when the reply is not a single 32-byte word.
export function decodeUint256(hex) {
  if (!/^0x[0-9a-fA-F]{64}$/.test(hex || "")) return null;
  try {
    return BigInt(hex).toString(10);
  } catch {
    return null;
  }
}

async function callUint(env, token, data) {
  if (!/^0x[0-9a-fA-F]{8}$/.test(data || "")) return null;
  const raw = await rpc(env, "eth_call", [{ to: token, data }, "latest"]).catch(() => null);
  return decodeUint256(raw);
}

// Read one recorded mint contract. Price is the only required call; paused /
// supply selectors are optional and a missing one stays unknown (null).
// A price read is evidence about cost only, never about contract safety.
export async function checkMint(env, contract) {
  const address = String(contract.contract_address || "").toLowerCase();
  if (!ADDRESS.test(address)) throw new Error("invalid-mint-contract");
  const priceWei = await callUint(env, address, contract.price_selector);
  if (priceWei === null) throw new Error("mint-price-unreadable");
  const pausedSel = contract.paused_selector || PAUSED_SELECTOR;
  const pausedRaw = await callUint(env, address, pausedSel).catch(() => null);
  const totalRaw = contract.total_supply_selector
    ? await callUint(env, address, contract.total_supply_selector).catch(() => null)
    : null;
  const maxRaw = contract.max_supply_selector
    ? await callUint(env, address, contract.max_supply_selector).catch(() => null)
    : null;
  const toInt = (v) => (v === null ? null : (Number(v) <= Number.MAX_SAFE_INTEGER ? Number(v) : null));
  return {
    mintId: contract.mint_id, address, priceWei,
    mintOpen: pausedRaw === null ? null : (pausedRaw === "0" ? 1 : 0),
    totalSupply: toInt(totalRaw), maxSupply: toInt(maxRaw),
    checkedAt: new Date().toISOString(), error: null
  };
}

async function tokenMetadata(env, token) {
  const [name, symbol] = await Promise.all([
    rpc(env, "eth_call", [{ to: token, data: "0x06fdde03" }, "latest"]).then(decodeString).catch(() => ""),
    rpc(env, "eth_call", [{ to: token, data: "0x95d89b41" }, "latest"]).then(decodeString).catch(() => "")
  ]);
  return { name, symbol };
}

const signal = (name, symbol) => TOKEN_RE.test(name + " " + symbol);
// Risk findings are evidence signals only; never calculate or render a "safe" score.
export function assess(goplus, honeypot) {
  const flags = [];
  const add = (field, value, severity) => { if (value === "1") flags.push({ code: field, severity }); };
  if (goplus && typeof goplus === "object") {
    add("honeypot-indicator", goplus.is_honeypot, "high");
    add("cannot-sell", goplus.cannot_sell_all, "high");
    add("blacklist-capability", goplus.is_blacklisted, "high");
    add("owner-change-balance", goplus.owner_change_balance, "high");
    add("hidden-owner", goplus.hidden_owner, "high");
    add("proxy-upgradeable", goplus.is_proxy, "medium");
    add("mintable-supply", goplus.is_mintable, "medium");
    add("transfer-pausable", goplus.transfer_pausable, "medium");
    add("modifiable-fees", goplus.slippage_modifiable, "medium");
    if (goplus.is_open_source === "0") flags.push({ code: "source-not-open", severity: "medium" });
  }
  if (honeypot?.honeypotResult?.isHoneypot === true) {
    flags.push({ code: "honeypot-simulation", severity: "high" });
  }
  for (const [code, value] of [["buy-tax", goplus?.buy_tax], ["sell-tax", goplus?.sell_tax]]) {
    const n = Number(value);
    if (value !== "" && value != null && Number.isFinite(n) && n >= 20) {
      flags.push({ code: code + "-20pct-plus", severity: n >= 45 ? "high" : "medium" });
    }
  }
  return { status: flags.some(f => f.severity === "high") ? "risk-detected" :
           flags.length ? "caution" : "insufficient-evidence",
           flags, sources: { goplus: !!goplus, honeypot: !!honeypot }, checkedAt: new Date().toISOString() };
}

async function riskFor(token) {
  let go = null, hp = null;
  try {
    const g = await readJson("https://api.gopluslabs.io/api/v1/token_security/56?contract_addresses=" + token);
    go = g?.result?.[token.toLowerCase()] || null;
  } catch { /* unavailable remains unknown */ }
  try {
    hp = await readJson("https://api.honeypot.is/v2/IsHoneypot?chainID=56&address=" + token);
  } catch { /* untestable is NOT safe */ }
  return assess(go, hp);
}

async function storeLead(env, info) {
  const now = new Date().toISOString();
  await env.DB.prepare(
    "INSERT INTO chain_leads(token_address, token_name, symbol, pair_address, first_block, tx_hash, first_seen, last_seen, classification, risk_status, risk_json, risk_checked_at) " +
    "VALUES(?,?,?,?,?,?,?,?,'agent-keyword-lead','not-checked',NULL,NULL) " +
    "ON CONFLICT(token_address) DO UPDATE SET last_seen=excluded.last_seen"
  ).bind(info.token, info.name, info.symbol, info.pair, info.block, info.txHash, now, now).run();
}

// Durable monotonic cursor; each completed block is checked before being saved.
export async function tick(env) {
  if (!env.DB || !env.BSC_RPC_URL) throw new Error("D1 or BSC_RPC_URL not configured");
  const chain = await rpc(env, "eth_chainId", []);
  if (String(chain).toLowerCase() !== "0x38") throw new Error("wrong-chain-rpc");
  const tip = Number.parseInt(await rpc(env, "eth_blockNumber", []), 16);
  if (!Number.isSafeInteger(tip) || tip <= CONFIRMATIONS) throw new Error("invalid-head");
  const safeHead = tip - CONFIRMATIONS;
  const item = await env.DB.prepare("SELECT value FROM sync_state WHERE key = 'pancake_v2_paircreated'").first();
  let cursor = item ? Number(item.value) : Math.max(0, safeHead - LOOKBACK_ON_BOOT);
  if (!Number.isSafeInteger(cursor) || cursor > safeHead) throw new Error("invalid-cursor");
  let scanned = 0, pairs = 0, matched = 0, probes = 0;
  const started = new Date().toISOString();
  try {
    for (let i = 0; i < CHUNKS_PER_RUN && cursor < safeHead; i++) {
      const until = Math.min(cursor + CHUNK_BLOCKS, safeHead);
      const logs = await rpc(env, "eth_getLogs", [{
        fromBlock: "0x" + (cursor + 1).toString(16),
        toBlock: "0x" + until.toString(16),
        address: FACTORY,
        topics: [PAIR_CREATED]
      }]);
      if (!Array.isArray(logs) || logs.length > 500) throw new Error("unexpected-log-count");
      let complete = true;
      for (const raw of logs) {
        const p = parsePair(raw);
        if (!p) throw new Error("malformed-pair-event");
        pairs++;
        const quote0 = QUOTES.has(p.token0), quote1 = QUOTES.has(p.token1);
        if (quote0 === quote1) continue; // only one well-known quote token
        if (probes >= TOKEN_PROBES_PER_RUN) {
          cursor = Math.max(0, p.block - 1); // reprocess same block next run, upserts are idempotent
          complete = false;
          break;
        }
        probes++;
        const token = quote0 ? p.token1 : p.token0;
        const meta = await tokenMetadata(env, token);
        if (!signal(meta.name, meta.symbol)) continue;
        matched++;
        await storeLead(env, { ...meta, token, pair: p.pair, block: p.block, txHash: p.txHash });
      }
      if (!complete) break;
      scanned += until - cursor;
      cursor = until;
      await env.DB.prepare("INSERT INTO sync_state(key,value) VALUES('pancake_v2_paircreated',?) " +
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value").bind(String(cursor)).run();
    }
    // Hard cap at 4 independent risk requests each run, only on candidate tokens.
    const pending = await env.DB.prepare(
      "SELECT token_address FROM chain_leads WHERE risk_checked_at IS NULL ORDER BY first_seen ASC LIMIT ?"
    ).bind(RISK_CHECKS_PER_RUN).all();
    for (const row of pending.results || []) {
      const risk = await riskFor(row.token_address);
      await env.DB.prepare("UPDATE chain_leads SET risk_status=?,risk_json=?,risk_checked_at=? WHERE token_address=?")
        .bind(risk.status, JSON.stringify(risk), risk.checkedAt, row.token_address).run();
    }
    // Mint verification, capped per run and never allowed to fail the scan.
    // mint_contracts is empty until a contract + price method are recorded
    // with evidence, so this is a no-op on a fresh database.
    try {
      const mintRows = await env.DB.prepare(
        "SELECT mint_id,contract_address,price_selector,paused_selector,total_supply_selector,max_supply_selector " +
        "FROM mint_contracts ORDER BY mint_id ASC LIMIT ?"
      ).bind(MINT_CHECKS_PER_RUN).all();
      for (const row of mintRows.results || []) {
        const now = new Date().toISOString();
        try {
          const checked = await checkMint(env, row);
          await env.DB.prepare(
            "INSERT INTO mint_checks(mint_id,contract_address,price_wei,mint_open,total_supply,max_supply,checked_at,error) " +
            "VALUES(?,?,?,?,?,?,?,NULL) ON CONFLICT(mint_id) DO UPDATE SET " +
            "price_wei=excluded.price_wei,mint_open=excluded.mint_open,total_supply=excluded.total_supply," +
            "max_supply=excluded.max_supply,checked_at=excluded.checked_at,error=NULL"
          ).bind(checked.mintId, checked.address, checked.priceWei, checked.mintOpen,
            checked.totalSupply, checked.maxSupply, checked.checkedAt).run();
        } catch (mintError) {
          await env.DB.prepare(
            "INSERT INTO mint_checks(mint_id,contract_address,price_wei,mint_open,total_supply,max_supply,checked_at,error) " +
            "VALUES(?,?,NULL,NULL,NULL,NULL,?,?) ON CONFLICT(mint_id) DO UPDATE SET checked_at=excluded.checked_at,error=excluded.error"
          ).bind(String(row.mint_id || ""), String(row.contract_address || ""), now,
            String(mintError.message || mintError).slice(0, 120)).run();
        }
      }
    } catch {
      /* mint table absent or unreadable on an old database: scan still counts */
    }
    await env.DB.prepare(
      "INSERT INTO scan_runs(started_at,finished_at,ok,from_block,to_block,pairs_seen,candidates,error) VALUES(?,?,1,?,?,?,?,NULL)"
    ).bind(started, new Date().toISOString(), Math.max(0, tip - CONFIRMATIONS - scanned), cursor, pairs, matched).run();
    return { ok: true, safeHead, cursor, scannedBlocks: scanned, pairs, matched };
  } catch (error) {
    await env.DB.prepare("INSERT INTO scan_runs(started_at,finished_at,ok,from_block,to_block,pairs_seen,candidates,error) VALUES(?,?,0,?,?,?,?,?)")
      .bind(started, new Date().toISOString(), Math.max(0, tip - CONFIRMATIONS - scanned), cursor, pairs, matched, String(error.message || error).slice(0,180)).run();
    throw error;
  }
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(tick(env).catch(err => console.error("agent-atlas-chain-scan:", String(err?.message || err))));
  },
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET") return respond({ ok: false, error: "read-only" }, 405);
    if (!env.DB) return respond({ ok: false, state: "not-configured" }, 503);
    try {
      if (url.pathname === "/v1/health") {
        const last = await env.DB.prepare("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1").first();
        const count = await env.DB.prepare("SELECT COUNT(*) AS n FROM chain_leads").first();
        return respond({ ok: true, network: "BSC", chainId: 56, configured: !!env.BSC_RPC_URL,
          scope: "PancakeSwap V2 new WBNB/USDT/USDC pairs with Agent keyword signal",
          automatedSafetyAudit: false, lastScan: last || null, candidateCount: count?.n || 0 });
      }
      if (url.pathname === "/v1/mint-checks") {
        const limit = Math.min(50, Math.max(1, Number.parseInt(url.searchParams.get("limit") || "25", 10) || 25));
        const data = await env.DB.prepare(
          "SELECT mint_id,contract_address,price_wei,mint_open,total_supply,max_supply,checked_at,error " +
          "FROM mint_checks ORDER BY checked_at DESC LIMIT ?").bind(limit).all();
        const checks = (data.results || []).map(p => ({
          mintId: p.mint_id, address: p.contract_address, priceWei: p.price_wei,
          mintOpen: p.mint_open === null ? null : p.mint_open === 1,
          totalSupply: p.total_supply, maxSupply: p.max_supply,
          checkedAt: p.checked_at, error: p.error
        }));
        return respond({ ok: true, chainId: 56, checks,
          note: "A price/open check is evidence about cost and availability only, never a safety audit." });
      }
      if (url.pathname === "/v1/leads") {
        const limit = Math.min(30, Math.max(1, Number.parseInt(url.searchParams.get("limit") || "12", 10) || 12));
        const data = await env.DB.prepare(
          "SELECT token_address,token_name,symbol,pair_address,first_block,tx_hash,first_seen,risk_status,risk_json,risk_checked_at " +
          "FROM chain_leads ORDER BY first_seen DESC LIMIT ?").bind(limit).all();
        const leads = (data.results || []).map(p => ({
          address: p.token_address, name: p.token_name, symbol: p.symbol, pair: p.pair_address,
          firstBlock: p.first_block, txHash: p.tx_hash, firstSeen: p.first_seen,
          classification: "agent-keyword-lead", riskStatus: p.risk_status,
          risk: p.risk_json ? JSON.parse(p.risk_json) : null, riskCheckedAt: p.risk_checked_at
        }));
        return respond({ ok: true, chainId: 56, leads, note: "Keyword match alone does not verify an Agent product or token safety." });
      }
      return respond({ ok: false, error: "not-found" }, 404);
    } catch (error) {
      console.error("chain-api:", String(error?.message || error));
      return respond({ ok: false, error: "indexer-unavailable" }, 503);
    }
  }
};
