# AgentAtlas — BSC Chain Worker

This is an independent read-only Cloudflare Worker + D1 database supporting the existing Cloudflare Pages site. Leave the current Pages deployment settings intact.

## Scope and safety

- BNB Smart Chain mainnet, Chain ID 56 only.
- Every five minutes, scan new-pair events on three factories: PancakeSwap V2 PairCreated (0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73), Biswap V2 PairCreated (0x858E3312ed3A876947EA49d572A7C42DE08af7EE), and PancakeSwap V3 PoolCreated (0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865; V3 pools can share a token pair across fee tiers, so the pool address is stored). Factory addresses and the V3 PoolCreated topic were verified on-chain 2026-11-08 (V3 `getPool` returns real pools; Biswap `getPair` returns a real pair). This is NOT every BSC contract, every launchpad, or every new token.
- Consider only pools paired with WBNB/USDT/USDC. Inspect token name/symbol and store Agent-related keyword candidates. Keyword matches do not establish Agent product legitimacy or that a pool has liquidity.
- For at most four pending candidate tokens per run, query GoPlus security and Honeypot.is as best-effort external checks. Flag suspicious authorities, honeypot indicators and fees. Missing fields or simulation failures mean insufficient evidence, NEVER a green safety badge or audit.
- Cursor is durable in D1 and moves only after successful block window processing; the first scan starts near the current head. Scan limits: at most 5 groups of 100 blocks across 3 factories (up to 15 log queries per run), up to 30 token metadata probes, up to 4 risk checks. Provider API usage and limits are your responsibility.
- RPC provider (2026-11-08): Chainstack Developer, free, no card required, 3M RU/month, `eth_getLogs` capped at 100 blocks per call — that is why chunks are 100. Ankr was the earlier recommendation, but a new Ankr account now shows 0 credits and asks for a $10 Premium pay-as-you-go top-up before issuing a usable endpoint, so do not use Ankr unless you already have a funded account.
- The Worker has only read-only public endpoints. It never asks users to sign transactions or exposes a write endpoint.

## Windows PowerShell — one-time setup

Prerequisites: a Cloudflare account, Node.js, and a BSC mainnet RPC endpoint supporting eth_getLogs. Public BSC dataseeds may not provide historical logs. Use a Chainstack Developer endpoint (free, no card, `eth_getLogs` capped at 100 blocks — matches the Worker's chunk size). Never send RPC keys in public messages or GitHub commits.

Open PowerShell inside the repository folder.

Step 1. Login:

    cd chain-worker
    npm install
    npm test
    npx wrangler login

Step 2. Create D1:

    npx wrangler d1 create agent-atlas-chain --location apac

Copy the UUID returned as database_id. In this local directory edit wrangler.jsonc: replace REPLACE_WITH_YOUR_D1_DATABASE_UUID with the real D1 database UUID. Do not share your RPC key.

Step 3. Create database tables and deploy:

    npx wrangler d1 migrations apply agent-atlas-chain --remote
    npx wrangler deploy
    npx wrangler secret put BSC_RPC_URL

For the secret prompt, input the full private HTTPS RPC endpoint with eth_getLogs enabled. The secret is stored by Cloudflare, not in your source or HTML. Wrangler shows a public Worker URL such as https://agent-atlas-chain.<your-subdomain>.workers.dev.

Step 4. Connect the EXISTING Cloudflare Pages site:

Open Cloudflare dashboard → Workers & Pages → agent-atlas → Settings → Variables and Secrets → Production. Add:

    Name:  CHAIN_WORKER_URL
    Value: https://agent-atlas-chain.<your-subdomain>.workers.dev

Use the actual URL returned by Wrangler. Redeploy the Pages Production deployment to apply the environment setting. The Pages Function at /api/chain-leads securely proxies only the fixed read-only Worker endpoints. HTML never contains a private RPC key.

Step 5. Verify:
- Worker URL /v1/health returns ok:true, chainId:56 and a real successful lastScan.
- https://agentatlas.vip/api/chain-leads?kind=health returns that status after configuration.
- https://agentatlas.vip/api/chain-leads?kind=leads returns candidate data, possibly an empty list.
- Only after a real successful scan will the site show the onchain candidate panel. Do not confuse the separate existing /api/bsc block/gas readout with event indexing.

If there is no successful scan, inspect Worker Logs and the scan_runs table in D1. Keep the Worker secret and Cloudflare account access private.

## Optional GitHub Actions automatic deployment

The workflow .github/workflows/deploy-chain-worker.yml stays DISABLED until you opt in.

Create D1 first, then in GitHub → this repository → Settings → Secrets and variables → Actions configure:

Secrets (never Variables):
- CLOUDFLARE_API_TOKEN — least-privilege token allowed to deploy Workers and migrate D1.
- CLOUDFLARE_ACCOUNT_ID — account identifier.
- BSC_RPC_URL — your private BSC event-log-enabled RPC URL.

Variables:
- CHAIN_D1_DATABASE_ID — D1 UUID, not an RPC secret.
- ENABLE_CHAIN_DEPLOY — true.

Then select Actions → Deploy BSC chain Worker (opt-in) → Run workflow. It tests, migrates, deploys and sets the RPC secret. Future code pushes under chain-worker can deploy automatically while ENABLE_CHAIN_DEPLOY remains true.

Be careful granting deployment credentials to a public repository or its collaborators.

## Developer tests

    cd chain-worker
    node --test
    npx wrangler d1 migrations apply agent-atlas-chain --local
    npx wrangler dev

Worker endpoints: GET /v1/health, GET /v1/leads and GET /v1/mint-checks. No public write endpoints.

## Mint verification (scaffold, no contracts recorded yet)

- `mint_contracts` holds only contracts whose address and price method were
  confirmed from the project's own site/docs or BscScan. The migration creates
  the table empty; a price check is never run for a contract that is not there.
- Each 5-minute tick checks at most 2 recorded mint contracts (price, paused,
  total supply) and upserts `mint_checks`. A mint failure is recorded per
  contract and never fails the pair scan.
- A price/open check is evidence about cost and availability only, never a
  safety audit. Unrecorded mints stay unverified; do not invent an address or
  a price method. Mint contracts use different price methods, so the selector
  is stored per contract, not assumed.

## Coverage expansion

Only after proving this initial scanner should we add verified event factories for PancakeSwap V3, Four.Meme and Flap; liquidity depth, deployer-history investigations and phishing-site risk; and an onchain-to-Agent-project identity link. A new pool and an Agent-themed name are not proof of a working AI Agent project.
