import test from "node:test";
import assert from "node:assert/strict";
import worker, { parsePair, decodeString, decodeUint256, assess, checkMint, tick } from "../src/index.js";

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
    else if (method === "eth_getLogs") result=logs;
    else if (method === "eth_call") result=abi(msg.params[0].data === "0x06fdde03"?"Agent Helper":"AGENT");
    else throw Error("Unexpected RPC: "+method);
    return Response.json({jsonrpc:"2.0",id:1,result});
  };
  try {
    const result = await tick({DB:db,BSC_RPC_URL:"https://rpc.example"});
    assert.equal(result.ok, true);
    assert.equal(result.matched, 1);
    assert.equal(result.cursor, 992);
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
