-- Mint verification scaffold. No contract is verified by this migration alone.
-- Rows in mint_contracts are added only after a contract address and its
-- price method are confirmed from the project's own site/docs or BscScan.
-- mint_checks is written by the Worker; a price check is not a safety audit.
CREATE TABLE IF NOT EXISTS mint_contracts (
  mint_id TEXT PRIMARY KEY,
  contract_address TEXT NOT NULL,
  price_selector TEXT NOT NULL,
  paused_selector TEXT,
  total_supply_selector TEXT,
  max_supply_selector TEXT,
  evidence_url TEXT,
  added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mint_checks (
  mint_id TEXT PRIMARY KEY,
  contract_address TEXT NOT NULL,
  price_wei TEXT,
  mint_open INTEGER,
  total_supply INTEGER,
  max_supply INTEGER,
  checked_at TEXT NOT NULL,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_mint_checks_checked ON mint_checks(checked_at DESC);
