# AGENT ATLAS

独立的 BSC AI Agent 生态与 Binance .ai ID 相关机会发现站点。**非 Binance 或 BNB Chain 官方网站。**

**正式网站：** https://agentatlas.vip/

## 网站功能

- BSC Agent 项目目录、搜索、类别筛选、最近活动与名称排序
- 免费 / 付费 Mint 来源线索（未核验时明确标示）
- Binance .ai ID 相关指南；不宣称已接入钱包或链上资格核验
- 中英文界面、夜间主题与本机收藏
- GitHub Actions 定时采集公开 GitHub 项目线索

## 文件与自动更新

- `index.html`：正式网站页面及交互
- `data/projects.json`：项目数据库
- `data/opportunities.json`：Mint 机会来源
- `data/pipeline_status.json`：项目采集运行状态
- `scripts/discover.py`：GitHub 候选项目采集器
- `.github/workflows/discover.yml`：定时采集任务

GitHub Actions 按工作流设定的时间运行，自动提交项目数据库和采集状态的变化。GitHub 定时任务可能延迟，不承诺精确整点更新。Mint 数据目前不由该工作流自动核验。

## 本地预览

```bash
python -m http.server 8000
```

访问 http://localhost:8000/ 。不要直接双击 `index.html` 使用 `file://` 打开，否则浏览器可能阻止读取本地 JSON。

## 部署

仓库 `main` 分支推送后，由既有 Cloudflare Pages 集成发布到 https://agentatlas.vip/ 。修改生产站点前应确认现有绑定与构建设置。

## 数据可信度及安全边界

项目来源是线索而非背书。被纳入 BSC Agent 目录**不等于**支持 Binance .ai ID，也不等于经过安全审核。Mint 是否开放、费用、合约安全及资格要求，需要以对应官方原始来源和链上记录核对。

本站目前不连接用户钱包、不发起交易、不提供经过验证的实时区块事件流或自动跟单；任何未实际接入的数据都不可标注为实时。收藏保存在当前浏览器中。

如需新增项目，保持项目 `id` 稳定唯一，完善来源和更新时间，不要将推断的收益、热度或安全结论当作事实。

参考资料：
- https://web3.binance.com/en/agentic-hub
- https://developers.binance.com/en/docs/products/agentic-wallet/welcome
- https://www.bnbchain.org/en/solutions/ai-agent
