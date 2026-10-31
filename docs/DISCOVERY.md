# Project discovery

AGENT ATLAS uses a GitHub Actions workflow every three hours (minute 17 UTC) and manual workflow dispatch.

Workflow: `.github/workflows/discover.yml`.

Data: `data/projects.json` and `data/pipeline_status.json`.

The Python collector searches public GitHub repository metadata; discovered records are always marked **candidate / unverified**. It does not certify identity, website ownership, AI Agent functionality, mint costs, security, authenticity or investment quality.

Sources can fail due to rate limits, removal or network errors. Errors are reported in `pipeline_status.json`; when every query fails the project database is preserved and the workflow fails.

### First run

Open repository → Actions → Discover ecosystem projects → Run workflow → main. If the run cannot commit, check repository Settings → Actions → General → Workflow permissions → Read and write permissions. No paid API key is required. Do not turn on billing automatically.

### Data limits

Up to 36 GitHub discovery candidates are retained, plus existing curated entries. The search is not a comprehensive list of all BNB Chain Agent projects. Check original repository links before participating in any opportunity.
