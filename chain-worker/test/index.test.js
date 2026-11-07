import test from "node:test";
import assert from "node:assert/strict";
import worker, { parsePair, decodeString, assess } from "../src/index.js";

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
