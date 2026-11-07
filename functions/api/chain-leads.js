// Cloudflare Pages Function: GET /api/chain-leads?kind=health|leads|mint-checks
// Proxy fixed read-only endpoints to the optional separate Cloudflare Worker.
// CHAIN_WORKER_URL is a Pages environment variable, never a client-supplied URL.
export async function onRequestGet({ request, env }) {
  const headers = { "content-type": "application/json; charset=utf-8",
    "cache-control": "public, max-age=30, s-maxage=30",
    "x-content-type-options": "nosniff" };
  const json = (data, status) => new Response(JSON.stringify(data), {status, headers});
  const configured = String(env.CHAIN_WORKER_URL || "").trim();
  if (!configured) return json({ok:false, state:"not-configured",
    message:"BSC chain indexer has not been deployed to Cloudflare Workers."}, 503);
  try {
    const base = new URL(configured);
    const host = base.hostname.toLowerCase();
    if (base.protocol !== "https:" || base.port ||
        !(host.endsWith(".workers.dev") || host === "chain.agentatlas.vip") ||
        base.username || base.password) throw new Error("invalid-config");
    const url = new URL(request.url);
    const rawKind = url.searchParams.get("kind");
    const kind = rawKind === "health" ? "health" : rawKind === "mint-checks" ? "mint-checks" : "leads";
    const limit = Math.min(30, Math.max(1, parseInt(url.searchParams.get("limit") || "12", 10) || 12));
    const target = new URL("/v1/" + kind, base);
    if (kind !== "health") target.searchParams.set("limit", String(limit));
    const res = await fetch(target.toString(), {
      headers: { "accept": "application/json" },
      signal: AbortSignal.timeout(9000)
    });
    if (!res.ok) return json({ok:false,state:"upstream-unavailable"},503);
    const payload = await res.json();
    if (!payload || typeof payload.ok !== "boolean") throw new Error("invalid-response");
    return json(payload,200);
  } catch {
    return json({ok:false,state:"upstream-unavailable",
      message:"The independent chain indexer is temporarily unreachable."},503);
  }
}
