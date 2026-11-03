# AGENT ATLAS

独立的 BSC AI Agent 生态与 Binance .ai ID 相关机会发现站点。**非 Binance 或 BNB Chain 官方网站。**

**正式网站：** https://agentatlas.vip/

## 网站功能

- BSC 早期 AI Agent 项目与候选线索，支持 DEX / BNB 官方 / GitHub / 生态资料筛选
- 首次收录 24 小时 / 7 天 / 30 天筛选，以及最近收录、最近活动与名称排序
- 免费 / 付费 Mint 来源线索（未核验时明确标示）
- Binance .ai ID 相关指南；不宣称已接入钱包或链上资格核验
- 中英文界面、夜间主题与本机收藏
- GitHub Actions 定时发现 GitHub 项目、DEX Screener 上的 BSC Agent 主题代币及 BNB Chain 官方生态提及

## 文件与自动更新

- `index.html`：正式网站页面及交互
- `data/projects.json`：项目数据库
- `data/opportunities.json`：Mint 机会来源
- `data/external_projects.json`：DEX Screener 与 BNB Chain 官方来源记录（含每次采集状态）
- `data/pipeline_status.json`：项目采集运行状态
- `scripts/discover.py`：GitHub 候选项目采集器
- `scripts/discover_external.py`：DEX Screener / BNB Chain 官方来源采集器（标准库，无付费 API）
- `.github/workflows/discover.yml`：定时采集任务

GitHub Actions 按工作流设定的时间运行，自动提交两个项目数据集和采集状态。采集器支持部分来源失败时保留既有数据，且不会在数据缺失时生成项目。GitHub 定时任务可能延迟，不承诺精确整点更新。Mint 数据目前不由该工作流自动核验。

## 本地预览

```bash
python -m http.server 8000
```

访问 http://localhost:8000/ 。不要直接双击 `index.html` 使用 `file://` 打开，否则浏览器可能阻止读取本地 JSON。

## 部署

仓库 `main` 分支推送后，由既有 Cloudflare Pages 集成发布到 https://agentatlas.vip/ 。修改生产站点前应确认现有绑定与构建设置。

## 数据可信度及安全边界

项目来源是线索而非背书。`firstSeen` 指第一次被 AGENT ATLAS 收录，不是项目成立或首次发币的时间。DEX Screener 代币资料并不能证明背后存在可运行的 AI Agent 产品；BNB Chain 官方页面提及亦不代表安全审计。被纳入 BSC Agent 目录**不等于**支持 Binance .ai ID，也不等于经过安全审核。Mint 是否开放、费用、合约安全及资格要求，需要以对应官方原始来源和链上记录核对。

本站已通过 `/api/bsc` 提供 BSC 主网区块高度和 Gas 的只读查询，但尚未实现全链事件索引。网站不连接用户钱包、不发起交易、不提供自动跟单；任何未实际接入的数据都不可标注为实时。收藏保存在当前浏览器中。

如需新增项目，保持项目 `id` 稳定唯一，完善来源和更新时间，不要将推断的收益、热度或安全结论当作事实。

参考资料：
- https://web3.binance.com/en/agentic-hub
- https://developers.binance.com/en/docs/products/agentic-wallet/welcome
- https://www.bnbchain.org/en/solutions/ai-agent

## 采集边界

- DEX Screener 公共端点提供有限的近期资料或搜索结果，**并不是所有 BSC 新项目的完整数据源**。
- BNB Chain 官方生态扫描只读取公开页面中 BSC 相关提及，不收录 opBNB-only 项目。
- GitHub 候选可能不具备独立产品、代币或 Mint，不能当成经过核验的生态项目。
- X 全网搜索、Four.Meme / Flap 发射台和 Mint 合约进度索引尚未接入。
- 数据采集错误和历史记录保留不意味着来源持续可用；应查看 `data/external_projects.json` 的 `sources` 状态。
