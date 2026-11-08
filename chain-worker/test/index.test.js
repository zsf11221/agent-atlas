import test from "node:test";
import assert from "node:assert/strict";
import worker, { parsePair, parsePool, decodeString, decodeUint256, assess, checkMint, tick, manualFlagsFor } from "../src/index.js";

const topic = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9";
const token0 = "0x" + "1".repeat(40);
const token1 = "0x" + "2".repeat(40);
const pair = "0x" + "3".repeat(40);
const pad = (v) => "0x" + "0".repeat(24) + v.slice(2);
const event = {
  topics: [topic, pad(token0), pad(token1)],
  data: pad(pair) + "0".repeat(63) + "1",
  blockNumber: "0x186a0",
  transactionHash: "0x" + "f".repeat(64)
};

test("PairCreated extracts indexed addresses and pair data correctly", () => {
  assert.deepEqual(parsePair(event), { token0, token1, pair, block:100000, txHash:event.transactionHash });
  assert.equal(parsePair({ ...event, topics: [topic] }), null);
  assert.equal(parsePair({ ...event, data: "0x" }), null);
});
test("PoolCreated (V3) extracts tokens and pool from the fourth topic and data", () => {
  const poolTopic = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118";
  const fee = "0x" + "0".repeat(24) + "00000000000000000000000000000bb8"; // 3000 fee tier
  const tickSpacing = "0x" + "0".repeat(63) + "1";
  const poolEvent = {
    topics: [poolTopic, pad(token0), pad(token1), fee],
    data: tickSpacing + "0".repeat(24) + pair.slice(2),
    blockNumber: "0x186a0",
    transactionHash: "0x" + "e".repeat(64)
  };
  assert.deepEqual(parsePool(poolEvent), { token0, token1, pair, block: 100000, txHash: poolEvent.transactionHash });
  assert.equal(parsePool({ ...poolEvent, topics: poolEvent.topics.slice(0, 3) }), null);
  assert.equal(parsePool({ ...poolEvent, data: "0x" }), null);
});
test("ABI string and bytes32 reader", () => {
  const word = (v) => BigInt(v).toString(16).padStart(64,"0");
  const text = Buffer.from("AgentAtlas", "utf8").toString("hex");
  const dynamic = "0x" + word(32) + word(10) + text.padEnd(64,"0");
  assert.equal(decodeString(dynamic), "AgentAtlas");
  assert.equal(decodeString("0x" + text.padEnd(64,"0")), "AgentAtlas");
  assert.equal(decodeString("not hex"), "");
  assert.equal(decodeString("0x" + word(655360) + word(10) + text), "");
});
test("Mint uint256 reader only accepts a single 32-byte word", () => {
  assert.equal(decodeUint256("0x" + "0".repeat(63) + "1"), "1");
  assert.equal(decodeUint256("0x" + BigInt("1000000000000000000").toString(16).padStart(64, "0")), "1000000000000000000");
  assert.equal(decodeUint256("0x1234"), null);
  assert.equal(decodeUint256("not hex"), null);
  assert.equal(decodeUint256(null), null);
});

test("Mint check reads price, paused and supply without claiming safety", async () => {
  const uint = (v) => "0x" + BigInt(v).toString(16).padStart(64, "0");
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    const msg = JSON.parse(init?.body);
    const data = msg.params[0].data;
    let result = uint(0);
    if (data === "0x5c975abb") result = uint(0); // not paused
    else if (data === "0x18160ddd") result = uint(5);
    else if (data === "0x12345678") result = uint(0); // free mint price
    else throw Error("Unexpected mint call: " + data);
    return Response.json({ jsonrpc: "2.0", id: 1, result });
  };
  try {
    const checked = await checkMint({ BSC_RPC_URL: "https://rpc.example" }, {
      mint_id: "agentlings", contract_address: "0x" + "a".repeat(40),
      price_selector: "0x12345678", paused_selector: "0x5c975abb",
      total_supply_selector: "0x18160ddd", max_supply_selector: null
    });
    assert.equal(checked.priceWei, "0");
    assert.equal(checked.mintOpen, 1);
    assert.equal(checked.totalSupply, 5);
    assert.equal(checked.maxSupply, null);
    await assert.rejects(checkMint({ BSC_RPC_URL: "https://rpc.example" }, {
      mint_id: "bad", contract_address: "not-an-address", price_selector: "0x12345678"
    }), /invalid-mint-contract/);
  } finally {
    globalThis.fetch = original;
  }
});

test("Risk flags cannot be a green safety badge", () => {
  assert.equal(assess(null, null).status, "insufficient-evidence");
  assert.equal(assess({is_open_source:"1",is_honeypot:"0"},null).status, "insufficient-evidence");
  assert.equal(assess({is_mintable:"1"},null).status, "caution");
  const h=assess({is_blacklisted:"1"},{honeypotResult:{isHoneypot:true}});
  assert.equal(h.status,"risk-detected");
  assert.ok(h.flags.some(x=>x.code==="honeypot-simulation"));
});
test("Read-only: rejects POST before reading D1", async () => {
  const res = await worker.fetch(new Request("https://chain.example/v1/leads",{method:"POST"}),{});
  assert.equal(res.status,405);
  const data=await res.json();
  assert.equal(data.error,"read-only");
});

test("Mocked BSC RPC + D1 end-to-end scan persists candidate, cursor and risk evidence", async () => {
  const sent = [];
  const rows = [];
  const logs = [{
    ...event,
    topics: [topic, pad("0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"), pad(token1)],
    blockNumber: "0x3de"
  }];
  const abi = (value) => {
    const hex = Buffer.from(value).toString("hex");
    return "0x" + BigInt(32).toString(16).padStart(64,"0") +
      BigInt(Buffer.byteLength(value)).toString(16).padStart(64,"0") +
      hex.padEnd(Math.ceil(hex.length/64)*64,"0");
  };
  const db = {
    prepare(sql) {
      let params = [];
      return {
        bind(...args){params=args;return this;},
        async first(){return null;},
        async all(){return {results:[]};},
        async run(){rows.push({sql,params});return {success:true};}
      };
    }
  };
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    sent.push({url,body:init?.body});
    if (String(url).includes("gopluslabs.io")) return Response.json({code:1,result:{[token1]:{is_mintable:"1"}}});
    if (String(url).includes("honeypot.is")) return Response.json({honeypotResult:{isHoneypot:false}});
    const msg = JSON.parse(init?.body);
    const method = msg.method;
    let result;
    if (method === "eth_chainId") result="0x38";
    else if (method === "eth_blockNumber") result="0x3e8";
    else if (method === "eth_getLogs") {
      // Only the PancakeSwap V2 factory emits the mocked pair; the other two
      // factories must still be queried (multi-source scan).
      result = msg.params[0].address === "0xca143ce32fe78f1f7019d7d551a6402fc5350c73" ? logs : [];
    }
    else if (method === "eth_call") result=abi(msg.params[0].data === "0x06fdde03"?"Agent Helper":"AGENT");
    else throw Error("Unexpected RPC: "+method);
    return Response.json({jsonrpc:"2.0",id:1,result});
  };
  try {
    const result = await tick({DB:db,BSC_RPC_URL:"https://rpc.example"});
    assert.equal(result.ok, true);
    assert.equal(result.matched, 1);
    assert.equal(result.cursor, 992);
    const logCalls = sent.filter(x => { try { return JSON.parse(x.body).method === "eth_getLogs"; } catch { return false; } });
    const queried = new Set(logCalls.map(x => JSON.parse(x.body).params[0].address.toLowerCase()));
    assert.ok(queried.has("0xca143ce32fe78f1f7019d7d551a6402fc5350c73"), "V2 factory queried");
    assert.ok(queried.has("0x858e3312ed3a876947ea49d572a7c42de08af7ee"), "Biswap factory queried");
    assert.ok(queried.has("0x0bfbcf9fa4f9c56b0f40a671ad40e0805a091865"), "V3 factory queried");
    assert.ok(rows.some(x=>x.sql.includes("INSERT INTO chain_leads") && x.params[0] === token1));
    assert.ok(rows.some(x=>x.sql.includes("INSERT INTO sync_state") && x.params[0] === "992"));
    assert.ok(rows.some(x=>x.sql.includes("INSERT INTO scan_runs") && x.sql.includes("VALUES(?,?,1")));
    assert.equal(sent.filter(x=>String(x.url).includes("honeypot.is")).length, 0,
      "risk checker should only process persisted rows returned by D1 pending query");
  } finally {
    globalThis.fetch = original;
  }
});

test("Tick writes a mint check for a recorded contract and still records the scan", async () => {
  const uint = (v) => "0x" + BigInt(v).toString(16).padStart(64, "0");
  const rows = [];
  const mintRow = {
    mint_id: "agentlings", contract_address: "0x" + "a".repeat(40),
    price_selector: "0x12345678", paused_selector: "0x5c975abb",
    total_supply_selector: "0x18160ddd", max_supply_selector: null
  };
  const db = {
    prepare(sql) {
      let params = [];
      return {
        bind(...args) { params = args; return this; },
        async first() { return null; },
        async all() {
          return { results: sql.includes("mint_contracts") ? [mintRow] : [] };
        },
        async run() { rows.push({ sql, params }); return { success: true }; }
      };
    }
  };
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    const msg = JSON.parse(init?.body);
    let result;
    if (msg.method === "eth_chainId") result = "0x38";
    else if (msg.method === "eth_blockNumber") result = "0x3e8";
    else if (msg.method === "eth_getLogs") result = [];
    else if (msg.method === "eth_call") {
      const data = msg.params[0].data;
      result = data === "0x5c975abb" ? uint(0) : data === "0x18160ddd" ? uint(5) : uint(0);
    } else throw Error("Unexpected RPC: " + msg.method);
    return Response.json({ jsonrpc: "2.0", id: 1, result });
  };
  try {
    const result = await tick({ DB: db, BSC_RPC_URL: "https://rpc.example" });
    assert.equal(result.ok, true);
    const mintWrite = rows.find((x) => x.sql.includes("INSERT INTO mint_checks"));
    assert.ok(mintWrite, "expected a mint_checks upsert");
    assert.equal(mintWrite.params[0], "agentlings");
    assert.equal(mintWrite.params[2], "0");
    assert.equal(mintWrite.params[3], 1);
    assert.ok(rows.some((x) => x.sql.includes("INSERT INTO scan_runs") && x.sql.includes("VALUES(?,?,1")));
  } finally {
    globalThis.fetch = original;
  }
});

test("Manual review flags attach to flagged leads only", async () => {
  const flaggedA = "0x0662311fab76d4871628434d14cd8573a7517777";
  const flaggedB = "0x7dc663a352e83df5fb96b14ddfb0201a80d17777";
  const clean = "0x" + "5".repeat(40);
  const row = (address) => ({
    token_address: address, token_name: "WORKBUDDY", symbol: "WORKBUDDY",
    pair_address: "0x" + "3".repeat(40), first_block: 132358837,
    tx_hash: "0x" + "f".repeat(64), first_seen: "2026-11-08T08:15:18.269Z",
    risk_status: "insufficient-evidence", risk_json: null, risk_checked_at: "2026-11-08T08:15:19.335Z"
  });
  const rows = [row(flaggedA), row(flaggedB), row(clean)];
  const db = {
    prepare() {
      return {
        bind() { return this; },
        async first() { return null; },
        async all() { return { results: rows }; },
        async run() { return { success: true }; }
      };
    }
  };
  const res = await worker.fetch(new Request("https://chain.example/v1/leads"), { DB: db });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.ok, true);
  assert.deepEqual(data.leads[0].manualFlags, ["同名复制", "无流动性", "筹码集中"]);
  assert.deepEqual(data.leads[1].manualFlags, ["同名复制", "无流动性", "筹码集中"]);
  assert.equal(data.leads[2].manualFlags, undefined);
  // Case-insensitive lookup: an uppercase address must still match.
  assert.deepEqual(manualFlagsFor(flaggedA.toUpperCase()), ["同名复制", "无流动性", "筹码集中"]);
  assert.equal(manualFlagsFor(clean), null);
});
