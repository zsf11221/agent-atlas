-- BSC-specific discovery candidates; no user wallets or personal data.
CREATE TABLE IF NOT EXISTS sync_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chain_leads (
  token_address TEXT PRIMARY KEY,
  token_name TEXT NOT NULL,
  symbol TEXT NOT NULL,
  pair_address TEXT NOT NULL,
  first_block INTEGER NOT NULL,
  tx_hash TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  classification TEXT NOT NULL DEFAULT 'agent-keyword-lead',
  risk_status TEXT NOT NULL DEFAULT 'not-checked',
  risk_json TEXT,
  risk_checked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_chain_first_seen ON chain_leads(first_seen DESC);
CREATE TABLE IF NOT EXISTS scan_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  ok INTEGER NOT NULL,
  from_block INTEGER,
  to_block INTEGER,
  pairs_seen INTEGER NOT NULL DEFAULT 0,
  candidates INTEGER NOT NULL DEFAULT 0,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_latest ON scan_runs(id DESC);
