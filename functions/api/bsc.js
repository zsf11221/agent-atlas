// Read-only BNB Smart Chain mainnet status for AgentAtlas.
// Cloudflare Pages Functions: GET /api/bsc
const RPC_URL = 'https://bsc-dataseed.bnbchain.org';

async function rpc(method) {
  const response = await fetch(RPC_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params: [] }),
    signal: AbortSignal.timeout(7000)
  });
  if (!response.ok) throw new Error('RPC HTTP ' + response.status);
  const payload = await response.json();
  if (payload.error || typeof payload.result !== 'string' || !/^0x[0-9a-f]+$/i.test(payload.result)) {
    throw new Error('Invalid RPC response');
  }
  return BigInt(payload.result);
}

export async function onRequestGet() {
  const headers = {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'public, max-age=10, s-maxage=20',
    'x-content-type-options': 'nosniff'
  };
  try {
    const [block, gas] = await Promise.all([rpc('eth_blockNumber'), rpc('eth_gasPrice')]);
    return new Response(JSON.stringify({
      ok: true,
      network: 'BNB Smart Chain Mainnet',
      chainId: 56,
      blockNumber: Number(block),
      gasPriceGwei: Number(gas) / 1e9,
      checkedAt: new Date().toISOString(),
      readOnly: true,
      source: 'BNB Chain public JSON-RPC',
      note: 'Block and gas values do not imply .ai ID event indexing.'
    }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({
      ok: false,
      network: 'BNB Smart Chain Mainnet',
      chainId: 56,
      checkedAt: new Date().toISOString(),
      error: 'BSC public RPC is temporarily unavailable'
    }), { status: 503, headers: { ...headers, 'cache-control': 'no-store' } });
  }
}
