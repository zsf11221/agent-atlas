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
- `data/opportunities.json`：人工整理的 Mint 来源声明（费用及活动状态仍需核验）
- `data/mint_leads.json`：由既有 X 数据自动整理的 Mint / 领取候选清单，按来源网站去重
- `data/mint_pipeline_status.json`：Mint 候选整理状态、费用未知及来源声称分类数
- `data/external_projects.json`：DEX Screener 与 BNB Chain 官方来源记录（含每次采集状态）
- `data/x_projects.json`：X 最近帖子搜索收录线索（默认空，未启用实时抓取）
- `data/x_pipeline_status.json`：X API 搜索状态和月度读取上限记录
- `data/project_zh.json`：项目中文说明
- `data/pipeline_status.json`：项目采集运行状态
- `scripts/discover.py`：GitHub 候选项目采集器
- `scripts/discover_external.py`：DEX Screener / BNB Chain 官方来源采集器（标准库，无付费 API）
- `scripts/discover_x.py`：X API 最近 7 天项目线索发现器，含离线自测与预算控制
- `scripts/discover_mint.py`：离线整理有独立项目网站的 X Mint / 领取候选，不新增 API 请求
- `.github/workflows/discover_x.yml`：X 线索独立自动化，按预算设置默认停用
- `.github/workflows/discover.yml`：定时采集任务

GitHub Actions 按工作流设定的时间运行，自动更新项目库、X 线索及 Mint 候选来源。部分来源失败时保留已有数据；GitHub 定时任务可能延迟，不承诺精确整点更新。Mint 候选自动收集并不等于已核实费用、合约或开放状态。

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
- 已接入 X 最近帖子关键词搜索，但并非 X 全网完整历史索引；Four.Meme / Flap 发射台和 Mint 合约事件索引尚未接入。
- 数据采集错误和历史记录保留不意味着来源持续可用；应查看 `data/external_projects.json` 的 `sources` 状态。

## X API 早期线索（按量计费，需控制台限额）

付费调用需仓库变量 `ENABLE_X_DISCOVERY=true` 显式启用。Bearer Token 仅通过 GitHub Actions Secrets 注入，不会发送给前端；代码推送触发的自测不会调用付费 API。

1. GitHub Actions 推送检查：`python -m py_compile scripts/discover_x.py` 与 `python scripts/discover_x.py --self-test`。两者均不访问 X 网络或消耗 API 额度。
2. 仅在用户确认 X 开发者账户额度和月度付费上限后，才能于仓库的 **Settings → Secrets and variables → Actions → Variables** 添加 `ENABLE_X_DISCOVERY=true`。
3. 设置后，工作流按 UTC+8 每天 00:00、06:00、10:00、15:00、20:00 计划执行，可能延迟；每次最多 2 组最近搜索，各取最多 10 条。月度预留读取上限 800 条（按 $0.005/帖估算约 $4），因此可能在月初提前耗尽并停止付费读取。**实际收费及最终支出保护应以 X 控制台为准**，本地计数并非账户账单限额。
4. 读取结果只保存帖文 ID、来源链接、作者 ID 和自行撰写的中文线索摘要；不会公开复制原帖正文。筛选须有 BSC + Agent + 发布/开发的文本信号；不认为匹配关键词就证明项目存在或安全。
5. 任何 HTTP 401/402/403/429 等访问异常会在 `data/x_pipeline_status.json` 标记，不会制造或删除旧记录。没有可用 X API 额度时保持停用，不能声称实时 X 发现已启用。

## Mint / Claim 候选发现

- `data/opportunities.json` 保留人工整理的来源声明，分为免费和付费，均不代表已开放或安全。
- 每次 X 工作流执行 `scripts/discover_mint.py`，只使用已有的 `data/x_projects.json`，不额外访问 X API。候选必须包含可溯源的 X 帖子和独立 HTTPS 网站，按网站去重。
- 历史 X 记录缺乏原始费用证据，统一标记「待核验」。新采集帖子仅在出现明确免费/付费字样时，标记「来源声称免费」或「来源声称付费」，**绝不等同费用已确认**。
- Mint 前端仅展示有来源明确声称免费或付费的记录，保留「全部 / 免费 / 付费」筛选；费用未知的 X 候选仅留作内部数据排查，不对外展示，也不推断已验证或可安全参与。网站不进行自动 Mint、钱包签名或收费操作。
- 对已经收录的普通 GitHub / DEX 项目，不能仅因含有 Agent、token 或 NFT 关键词，就猜测其存在 Mint 活动。真正的 Mint 合约状态、资格和费用需要额外验证，当前未接入链上 Mint 事件索引。

官方参考：https://docs.x.com/x-api/posts/search/quickstart/recent-search 、https://docs.x.com/x-api/getting-started/pricing
