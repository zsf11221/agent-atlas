# AGENT ATLAS

An independent, bilingual (Chinese/English), evidence-led BNB Chain / Binance Agent ecosystem discovery site. **Not affiliated with Binance or BNB Chain.**

## Features

- Responsive editorial dashboard, dark/light theme and language switch
- Search, sector filter, network filter, sorting and project dossiers
- Browser-local watchlist, evidence links, source/provenance labels
- Opportunity radar that explicitly marks unavailable live feeds **as unavailable**
- No wallet connection, token trading or simulated safety conclusions

## Quick start

Static HTML/CSS/JS; no npm dependencies or paid API required.

```bash
cd agent-atlas
python -m http.server 8000
```

Open http://localhost:8000 . Do not open index.html using file:// because browsers block local JSON fetches.

## GitHub Pages

Create a public GitHub repository and upload the contents of this folder to its default branch root. In **Settings → Pages**, choose **Deploy from a branch** and select the default branch and `/ (root)` folder. The URL will be `https://USERNAME.github.io/REPO/` (GitHub may take time to publish). No workflow or package build required.

## Updating projects

Edit `data/projects.json`. Keep `id` unique and stable. List only verifiable projects, supply provenance in `source`, and never display inferred prices, live mint status, risk levels, tokenomics or social numbers as fact. Update `updatedAt` and `date` when rechecking information. Dynamic auto-ingestion needs a separate backend and source contracts; it is **not** implemented in this version.

## Data scope and limitations

This is a **working, source-backed curated MVP**, not a live on-chain scanner. Directory entries were prepared on **2026-10-31** from public Binance and BNB Chain sources. A source listing does not certify contract safety, project legitimacy, activity, usability or returns. Some ecosystem cards link to the BNB Chain directory when an independently verified official product page is not available. The source/provenance distinction in project dossiers must not be removed. The free-mint indicator is explicitly unset because this site has **not** simulated or verified mint transactions. The X engagement radar is a future module, not live. Watchlist stays in localStorage.

Public sources:
- https://web3.binance.com/en/agentic-hub
- https://developers.binance.com/en/docs/products/agentic-wallet/welcome
- https://www.bnbchain.org/en/solutions/ai-agent

## Security

All project-generated text is HTML-escaped before insertion. External links use `noopener noreferrer`. No private keys, wallet approvals, credential capture, analytics scripts or server components. Google Fonts are requested when online; system fonts are fallback.
