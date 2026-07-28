# LinkedIn Marketing AI Agent Demo

一个面向 LinkedIn 公司主页聚合分析数据的本地交互 Demo。用户可上传 Followers、Visitors、Content 的 XLSX、XLS 或 CSV 导出；系统安全解析并规范化数据，由确定性 TypeScript 引擎生成 Analysis Snapshot，再把用户批准的洞察和策略转换为可编辑的 30 天计划。**演示主界面使用 Streamlit。**

> 当前不会调用真实 LLM。内置 Mock 使用完全虚构的合成 CSV，并与真实上传共用解析、Snapshot、审批、计划和聊天输出契约。所有精确数值均由程序计算；Mock Agent 只解释现有指标和编排行动。

> 本项目不是 LinkedIn 官方产品，也未获得 LinkedIn 背书。上传者应确认自己有权处理相关导出数据。

## 功能范围

- 三模块 XLSX/XLS/CSV 本地解析、字段识别、标准化预览和质量门禁；
- 确定性指标、公式、时间范围、可靠性和文件/Sheet/行范围证据；
- 洞察与策略逐条批准/拒绝；
- 四周/约 30 天行动计划、实验、KPI 复盘、局部编辑和最近一次撤销；
- Lucy 内容审核、未来 14 天筛选和按渠道生成的 Buffer CSV 人工交接；
- 仅基于当前项目的证据问答和安全拒绝；
- Markdown 完整报告、CSV 内容日历、清洗后的 JSON 分析结果；
- Synthetic Mock 与上传 fixture 两条完整演示路径；
- 会话内清除、阶段重试、取消和可预测错误状态。

## 技术栈

- Streamlit 1.60：演示 UI、内存会话、上传与浏览器下载
- Python 3.10+：仅负责展示与 Bridge 进程管理，不重新计算指标
- Next.js 16（App Router、Route Handler）
- React 19
- TypeScript strict mode
- ESLint
- `@e965/xlsx@0.20.3`：服务端 XLSX/XLS/CSV 读取
- Node.js 原生测试运行器 + `tsx`

Streamlit 和解析库精确锁定版本。项目未采用 npm 上存在已知未修复公告的旧 `xlsx@0.18.5`。新增依赖前检查了 PyPI/npm 公告和维护状态。

## 本地启动

要求 Node.js 20.9+、npm 和 Python 3.10+。先安装 TypeScript 核心依赖：

```powershell
npm install
```

### Streamlit 演示主入口

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

macOS/Linux：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m streamlit run streamlit_app.py
```

打开 <http://localhost:8501>。Streamlit 每次操作会启动一个短生命周期 Node Bridge。

运行时优先使用已提交的 `dist/streamlit-bridge.cjs` 单文件 Bridge。
`npm install` 用于开发、测试和在 TypeScript 核心变化后重新生成该文件；Streamlit
Community Cloud 不需要在启动时安装 npm 包。

### Next.js 工程界面

Next.js 上传/识别工作区仍可用于开发和回归：

```powershell
npm run dev
```

打开 <http://localhost:3000>。

其他命令：

```powershell
npm test
npm run lint
npm run typecheck
npm run build
npm start
.\.venv\Scripts\python.exe -m unittest discover -s python_tests -v
```

## 环境变量

- **当前版本需要输入的 API Key 总数为 0。**
- Mock 和上传演示不需要任何 AI API Key。
- 不要把 API Key 放入浏览器、Streamlit session state、上传文件或仓库。
- Bridge 子进程会移除名称含 `API_KEY`、`TOKEN`、`SECRET`、`PASSWORD` 或 `AUTHORIZATION` 的环境变量。
- 可使用标准 Streamlit 环境变量调整本地端口，例如 `STREAMLIT_SERVER_PORT=8502`。
- `.streamlit/config.toml` 已关闭 Streamlit 使用统计并设置 10 MB 上传限制；`.streamlit/secrets.toml` 已忽略。

### API Key 审计

| 能力 | Key 数量 | 输入位置 | 当前实现 |
| --- | ---: | --- | --- |
| AI / LLM | 0 | 无 | 洞察、计划和聊天使用确定性 Mock，没有 Provider SDK 或外部模型请求 |
| LinkedIn | 0 | 无 | 只读取用户上传的分析导出，不调用 LinkedIn API |
| Buffer | 0 | 无 | 只生成 CSV 人工交接，不调用 Buffer API |
| GitHub | 0 | 无 | 应用代码不调用 GitHub API；部署时的平台 GitHub 授权由 Streamlit 管理 |
| Streamlit secrets | 0 | 无 | 代码没有读取 `st.secrets`；Cloud 的 Secrets 字段保持空白 |

`.streamlit/secrets.toml` 仅作为未来扩展的忽略规则存在，不是当前启动条件。
若以后接入真实 LLM 或 Buffer OAuth，必须新增服务端密钥读取、权限隔离和轮换，
不能把 Key 放入前端或提交到 Git。

## 部署到 Streamlit Community Cloud

当前仓库已经具备直接从 GitHub 创建 **Streamlit Demo App** 所需的文件：

- `streamlit_app.py`：Cloud 入口；
- `requirements.txt`：固定 Python 依赖；
- `packages.txt`：要求 Community Cloud 通过 Debian `apt-get` 安装 `nodejs`；
- `dist/streamlit-bridge.cjs`：已捆绑 TypeScript 分析核心与工作簿读取器，
  Cloud 运行时不依赖 `node_modules`、`tsx` 或 `npm install`；
- `.streamlit/config.toml`：上传大小、主题和遥测配置。

Streamlit 官方说明：Python 依赖从 `requirements.txt` 安装，非 Python 系统依赖从
根目录 `packages.txt` 安装。Community Cloud 当前基于 Debian Linux：

- [App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Deploy](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

### 推送前

```powershell
npm ci
npm run build:streamlit-bridge
npm test
git add .
git commit -m "Prepare Streamlit Community Cloud demo"
git push
```

不要提交 `Data/`、`data/`、`.env*` 或 `.streamlit/secrets.toml`。每次修改
Bridge 使用的 TypeScript 核心后，都应重新运行 `npm run build:streamlit-bridge`
并提交更新后的 `dist/streamlit-bridge.cjs`。

### 在 Community Cloud 创建 App

1. 将仓库推送到 GitHub，并让 Streamlit Community Cloud 获得该仓库访问权限。
2. 在 <https://share.streamlit.io> 选择 **Create app**。
3. 选择仓库和分支，Main file path 填 `streamlit_app.py`。
4. Advanced settings 使用 Python **3.12**。
5. Secrets 保持空白；当前应用不需要任何 Key。
6. 创建 App，构建日志应显示安装 `requirements.txt` 和 `packages.txt`。
7. 打开 App 后先执行 Synthetic Demo，再用脱敏 fixture 验证上传路径。

GitHub 私有仓库的访问授权属于 Streamlit 平台配置，不是在应用中填写 GitHub
Personal Access Token。此部署适合可重置的交互 Demo；Community Cloud 重启、
休眠或会话结束后状态会丢失。项目仍不具备生产级登录、持久化、后台任务、
审计存储或发布 SLA。

## 使用流程

1. 分别上传 Followers、Visitors、Content 文件，或点击“使用脱敏示例”。
2. 服务端重新校验扩展名、MIME、大小和文件签名。
3. 每个 Sheet 独立定位表头、判断模块并建立字段映射。
4. 查看时间范围、行数、映射/冲突/未映射字段、标准化预览和质量问题。
5. 低置信度或模块不一致时，按明确模块重新识别；必要时修改字段映射并重新校验。
6. 确认三个模块后生成数据质量摘要和确定性指标。
7. 查看公式、时间范围、可靠性及文件/Sheet/行范围来源。
8. 阻断问题禁止进入策略与计划；非阻断警告需用户确认。
9. 确认业务目标，逐条批准或拒绝洞察与策略。
10. 设置开始日期、时区、每周发帖能力、团队、资源和重点受众。
11. 生成四周计划，在列表或日历视图接受、拒绝或修改单项内容，并可撤销最近一次修改。
12. 使用证据聊天查询指标、质量、洞察和建议，或提交可审查的计划修改。
13. 在“交付 Buffer”审核已批准内容，默认选择未来 14 天并按渠道校验。
14. 修复阻断项、确认 Warning 后，按渠道下载 Buffer 导入准备 CSV；状态只更新为 `exported_to_buffer`。
15. 准备并下载完整 Markdown 报告、30 天内容日历 CSV 和结构化 JSON。
16. 点击“清除当前项目数据”移除分析、计划、聊天、Buffer 交接记录、导出缓存和上传控件。

完整刷新、会话断开或服务重启会重置状态；Demo 不使用数据库或浏览器持久化。

## Streamlit 演示架构

```text
streamlit_app.py
  -> streamlit_demo/bridge_client.py
    -> 短生命周期 Node 子进程
      -> dist/streamlit-bridge.cjs（由 src/streamlit/bridge.ts 构建）
        -> 现有解析、Snapshot、策略、计划、聊天和导出纯逻辑
```

- Python 不复制 CSV/XLSX 解析、指标公式、排名、增长率或计划验证。
- Bridge 通过 stdin/stdout 交换 JSON；上传文件临时使用 base64 传入，子进程结束后不保留 Buffer。
- Bridge 对上传执行与 Next Route Handler 相同的扩展名、MIME、大小、签名、损坏和加密校验。
- Bridge 成功响应只返回解析摘要、标准化预览、Snapshot 和业务结果；不返回原始单元格。
- Bridge 错误只返回稳定代码、中文消息、是否可重试、数据是否保留和下一步，不返回堆栈。

## Demo 演示步骤

### Synthetic Mock

1. 启动 Streamlit，点击“使用示例数据开始”。
2. 在“指标计算”检查 Followers、Visitors、Content 和 Proxy 指标的公式与证据。
3. 在 Audience/Content 页面批准洞察；在“策略建议”批准引用已批准洞察的策略。
4. 在“30 天计划”确认业务目标，设置时区、开始日期和每周内容数，生成计划。
5. 修改一条内容、接受或拒绝建议，然后测试“撤销最近一次修改”。
6. 在“证据问答”使用快捷问题；尝试询问收入或要求 system prompt，确认系统返回边界说明。
7. 确认计划后进入“交付 Buffer”：查看 ready、warning 和 blocked 项，选择被阻断的轮播项并改为文字短帖。
8. 确认非阻断 Warning，生成 LinkedIn Page 与 LinkedIn Profile 两个渠道文件；检查状态为“已生成交接文件”而非“已发布”。
9. 按页面步骤在 Buffer 当前渠道设置中下载最新模板、导入并人工复核；Demo 不访问 Buffer 账户。
10. 在“报告导出”准备三种分析文件并下载。
11. 点击“清除当前项目数据”或“重新开始 Synthetic Demo”。

### 上传 fixture

1. 在三个独立上传控件选择 synthetic XLSX/XLS/CSV fixture。
2. 点击“解析并计算 Analysis Snapshot”，检查模块、Sheet、字段映射、行数、日期范围和标准化预览。
3. 缺少模块时可继续质量检查，但洞察和计划会被阻断；补齐文件后从数据接入重试。
4. 完成审批、计划和导出。解析或 Bridge 单次失败不要求重新选择仍在当前会话中的文件。

所有 Synthetic 数据均为完全虚构，不包含真实公司或个人信息。

## 支持格式与字段

### 文件格式

- `.xlsx`
- `.xls`（包括 LinkedIn 常见 BIFF8 工作簿）
- `.csv`

单文件上限为 10 MB，单工作簿最多 30 个 Sheet，单 Sheet 最多读取 50,000 条数据行。

### Followers

- `date`
- `totalFollowers`
- `newFollowers`
- `organicFollowers`
- `sponsoredFollowers`
- `demographicDimension`
- `demographicValue`
- `demographicCount`
- `demographicPercentage`

### Visitors

- `date`
- `pageViews`
- `uniqueVisitors`
- `customButtonClicks`
- `demographicDimension`
- `demographicValue`
- `demographicCount`
- `demographicPercentage`

### Content

- `contentId`
- `title`
- `publishedAt`
- `contentType`
- `impressions`
- `uniqueImpressions`
- `clicks`
- `reactions`
- `comments`
- `reposts`
- `engagementRate`
- `clickThroughRate`

字段允许为 `null`。解析器不会用 `0` 或推测值填充缺失字段。

## 字段映射策略

- 在前 40 行中寻找最可能的单行表头，自动跳过空行和说明行。
- 模块判断同时使用表头组合、Sheet 名和文件名；文件名仅作为弱提示。
- 英文字段别名集中维护在 `src/data-processing/field-aliases.ts`，结构允许继续加入中文或其他语言别名。
- 每个 Sheet 单独识别，因此同一工作簿中的趋势、画像和逐帖数据不会被混成一张表。
- 上下文规则会区分歧义字段。例如：
  - `New followers` Sheet 的 `Total followers` 映射为 `newFollowers`；
  - 画像 Sheet 的 `Total followers` 映射为 `demographicCount`；
  - Visitors 优先采用 `Total page views (total)`，较窄口径列作为冲突提示展示；
  - Content 优先采用带 `(total)` 的汇总字段。
- 多个原始列竞争同一标准字段时，只有唯一、更明确的优先项会自动采用；其他列会显示冲突，不会静默覆盖。
- 用户可手动选择模块和字段映射，修改后由服务端重新规范化。

## 标准化与证据追踪

- 日期输出为 ISO 日期或 ISO 时间，同时在错误项中保留必要的原始值。
- 数字支持千位分隔符、空字符串和 `N/A`。
- 百分比支持字符串、百分数和 Excel 百分比格式；推断缩放时会给出警告。
- 无效数字不会静默变成 `0`。
- 每条记录保留模块、文件名、Sheet 名和原始行号。
- 完全空白行会跳过。
- 重复行会标记并保留，不会自动删除。
- 负数、异常百分比、歧义/异常日期会生成质量问题。
- 公式单元格不会执行，且其缓存值不会进入标准模型；类似公式的文本仅按普通文本保留并警告。

共享解析接口定义位于 `src/domain/linkedin.ts`。指标计算只消费 `FollowersRecord`、`VisitorsRecord`、`ContentRecord`，不再读取原始工作簿。

## Analysis Snapshot

`src/analysis/snapshot-engine.ts` 是 UI 和后续 Agent 的唯一 Snapshot 入口：

- `analysisInputFromParseResults(results, inputMode)`：从 Mock 或真实解析结果提取统一记录；
- `generateAnalysisSnapshot(input)`：执行质量检查和指标计算；
- 公共契约位于 `src/domain/analysis.ts`。

每个 `Metric` 包含：

- `metricId`、`label`、`value`、`formattedValue`、`unit`；
- `formula` 和 `period`；
- `sourceModules` 与聚合后的 `sourceReferences`（文件、Sheet、行范围、字段）；
- `reliability` 与 `reliabilityReasons`；
- 必要时提供 `caveat`。

### 核心公式

- Followers 净增长：`结束 totalFollowers - 起始 totalFollowers`；
- Followers 增长率：`净增长 / 起始 totalFollowers`；
- Organic / Sponsored 占比：只使用两个字段同时存在的相同周期，对应新增量除以两者之和；
- Page Views per Visitor：只在两个字段同时存在的相同记录中计算 `SUM(pageViews) / SUM(uniqueVisitors)`；
- Content CTR：只在 clicks 与 impressions 同时存在的相同记录中计算 `SUM(clicks) / SUM(impressions)`；
- Content Engagement Rate：只在 impressions 与四个互动组成项同时存在的相同记录中计算 `SUM(clicks + reactions + comments + reposts) / SUM(impressions)`；
- 内容高表现基线：逐帖互动率中位数；
- Visitor-to-Follower Proxy Ratio：仅在两个字段同时存在的同日期周期中计算 `SUM(newFollowers) / SUM(uniqueVisitors)`；
- 发布窗口相关性：共同时间桶中发布数量与 Visitors/Followers 变化的 Pearson 时间相关性。

除数为 `0`、字段缺失或时间不可比时返回 `unavailable`，不会估算。Proxy Ratio 不是用户级真实转化率；时间相关性不代表内容导致增长。

### 可靠性规则

- `reliable`：所需字段覆盖率至少 80%，时间条件可比且样本满足规则；
- `directional`：可以观察方向，但字段覆盖或样本量不适合精确决策；
- `unavailable`：缺少有效输入、除数为零，或时间范围/粒度条件不成立。

重复记录会保留并在质量结果中报告，但不会重复计入指标。缺失值与真实 `0` 始终分开处理。

### 数据质量规则

Snapshot 检查必要模块、共同时间范围、粒度一致性、日期缺口、重复、空值率、无效/负数、异常百分比、Followers 存量倒退、Visitors 逻辑一致性、Content 互动组成、样本量和发布时间范围。每项问题提供稳定代码、严重度、受影响来源、建议操作和 `blocksAnalysis`。

## 洞察与策略审批

- `src/domain/strategy.ts` 定义 `EvidenceInsight`、`StrategyRecommendation`、`MetricEvidenceReference` 和 `BusinessGoal`。
- 洞察与策略均具有 `draft`、`approved`、`rejected` 状态。
- 策略保留 `insightIds` 和 `metricIds`；引用洞察未批准时，策略不能批准。
- 修改策略目标后状态恢复为 `draft`，必须重新批准。
- 任何审批变化都会使当前计划失效，防止已撤回证据继续进入计划。
- 文案明确区分“数据显示”“可能意味着”和“建议验证”。

## 30 天 Action Plan

公共契约位于 `src/domain/action-plan.ts`，生成和校验位于 `src/agents/action-plan-agent.ts`。

### 输入

- 已确认 `BusinessGoal`；
- 当前 `snapshotId` 与分析时间范围；
- 仅包含 `approved` 状态的洞察和策略；
- 开始日期、IANA 时区、每周发帖能力；
- 可选团队规模、内容资源、目标市场和重点受众。

### 输出 Schema

`ActionPlan` 包含：

- `schemaVersion: 1.1`、可追溯的 `promptVersion`、`planId`、`snapshotId`；
- `analysisPeriod`、生成/更新时间、数据模块和来源洞察/策略 ID；
- `executiveSummary`、`assumptions`、`risksAndLimitations`；
- `fourWeekPlan`：每周目标、任务、内容项、负责人占位符、发布日期、受众、CTA、KPI、复盘和依赖；
- `contentCalendar`：日期/时间/IANA 时区、内部渠道 enum、主题、发布文案、形式、受众、CTA、媒体/链接、策略/洞察/指标引用、审批状态、Buffer 工作流状态和实验定义；
- `kpiDefinitions`、`kpiReviewPlan`、`nextImportQuestions`；
- 当前会话中的 `revisionHistory`。

计划默认覆盖开始日期起 30 天，发布内容分布在前四周。开始日期按用户时区校验且不得早于当地今天；UI 支持每周 1–7 条。不同内容不会安排到同一天。未提供团队信息时使用“待指定”占位符。

实验必须包含假设、成功标准、复盘日期和 KPI。成功标准只要求与 Snapshot 基线按相同口径比较，不承诺固定增长。KPI 只能引用当前 `available` Metric，或明确标记为 `future_collection` 的下一次导入指标。

生成后会执行结构和引用完整性检查。未批准引用、Snapshot 不匹配、过去日期、日期冲突、超出发布能力、无定义 KPI 或不完整实验都会产生稳定校验错误。

### 编辑与撤销

- 单项内容可接受、拒绝或修改主题、受众和 CTA；
- 开始日期、发帖能力和重点受众变化时，只重新生成排期、日历和 KPI 复盘，不重跑 Snapshot 或洞察；
- 当前会话保留计划历史，可撤销最近一次修改；
- 页面刷新后状态重置，不跨用户保存。

## Buffer CSV 人工交接

产品文案和实际边界均为：**“将已批准的内容计划导出，供 Lucy 在 Buffer 中审核和排期。”**

- 不实现 Buffer OAuth/API，不请求或保存 Buffer 用户名、密码、Token 或 API Key；
- 只支持当前适配器明确列出的 `linkedin_page` 与 `linkedin_profile`，界面名称和内部 enum 分离；
- 默认范围是项目时区中的今天起连续 14 天，可调整日期、时区和渠道；不会修改原 30 天计划；
- 复用 `ActionPlan.contentCalendar`，编辑文案、形式、日期、时间、时区、媒体链接和审批状态会回写同一计划；
- 只有现有 `status: confirmed`（用户已批准）的内容可导出；`ai_draft` 和 `rejected` 均被阻断；
- `workflowStatus: exported_to_buffer` 只表示已生成交接文件。导出器绝不会设置 `published`；
- 校验错误只跳过对应内容，不阻止其他合法内容；Warning 必须由 Lucy 明确确认；
- 当前会话仅记录 export ID、生成时间、范围、时区、渠道、导出/跳过 item ID、文件名和状态，不使用数据库。

### 官方字段映射依据

资料于 **2026-07-28** 检查：

- [Buffer 官方批量上传说明](https://support.buffer.com/article/926-how-to-upload-posts-in-bulk-to-buffer)；
- [Buffer 支持渠道](https://support.buffer.com/article/567-supported-channels)；
- [Buffer 队列限制](https://support.buffer.com/article/643-how-many-posts-can-i-schedule-in-advance)；
- [Buffer 渠道时区](https://support.buffer.com/article/514-setting-up-your-timezones-and-posting-schedules)。

官方说明要求针对每个渠道下载新模板，且列名区分大小写。当前 LinkedIn 渠道适配器按渠道分别生成文件，列为：

| Buffer 列 | 确定性映射 |
| --- | --- |
| `Text` | 已审核 `postText`；若 `linkUrl` 尚未包含在文案中，则在末尾追加 |
| `Image URL` | 首个且唯一的公开直接图片 URL |
| `Tags` | 可选 `campaignTag`；Lucy 必须确认同名 Buffer Tag 已存在 |
| `Posting Time` | `date + scheduledTime`，严格为 `YYYY-MM-DD HH:mm` |

官方 CSV 没有时区列。Buffer 按目标渠道设置的时区解释 `Posting Time`，因此 Demo 会显示并校验项目 IANA 时区，Lucy 仍必须在 Buffer 导入预览中确认渠道时区。官方批量上传当前仅支持文字和单图，不支持视频、轮播或首条评论；这些内容会被阻断并要求改版或在 Buffer Composer 中手动创建。

当前官方说明显示 Bulk Upload 对所有套餐开放：Free 每渠道每次最多 10 条并受剩余队列位限制，付费套餐每渠道每次最多 100 条；Free 队列当前每渠道最多 10 条。限制作为带资料日期的展示配置使用，只告警、不删除内容，也不阻止付费账户在确认后继续。

**验证状态：**字段映射已经对照上述官方帮助页并有自动化 CSV 测试，但没有可用 Buffer 测试账户，也没有从真实账户下载的当前渠道模板，因此尚未完成 Buffer 账户导入预览验证。生成物称为“Buffer 导入准备文件”，不承诺兼容所有渠道或未来模板。Lucy 应从目标渠道设置下载最新模板并在 Buffer 的 Review Content 页面完成最终确认。

## 证据聊天安全边界

`src/agents/evidence-chat-agent.ts` 只读取当前 Snapshot、当前洞察/策略和当前计划：

- 数值回答附带 `metricId`、时间范围、来源模块和可展开行级来源；
- 不确定或无数据时明确返回 `unavailable`，并说明需要补充的数据；
- Visitor-to-Follower Proxy 始终标记为代理观察，不称为真实转化率；
- 不识别匿名访客、具体关注者或个人购买意向；
- 拒绝密钥、system prompt、内部配置和绕过规则的请求；
- 收入、CRM、订单、网站转化和 ROI 等问题会要求补充相应数据源；
- 计划修改先返回 `SuggestedPlanChange`，由用户点击确认后应用，不静默改动。

## 安全导出

共享实现位于 `src/exports/report-exports.ts`，Next/Streamlit 之外不再复制导出规则：

- 文件名格式为 `{项目标识}-{类型}-{YYYY-MM-DD}.{扩展名}`，并清理操作系统非法字符；
- Markdown 包含 Executive Summary、数据范围、质量、指标公式、洞察、建议、四周计划、内容日历、KPI 复盘、下一次导入问题和限制；
- CSV 使用 UTF-8 BOM，正确转义逗号、双引号、换行和 Unicode；
- CSV 单元格若以 `= + - @`（允许前导空白）开头，会加安全撇号，防止电子表格公式注入；
- Buffer 文件复用同一 UTF-8 BOM、引号/换行/Unicode 和公式注入防护，并按渠道拆分；
- JSON 通过显式业务输入生成，不接收解析结果或原始记录；
- JSON 删除原始文件名，使用模块、Sheet 和行范围组成的 `sourceId` 保留证据；
- JSON 不包含 API Key、内部 Prompt、堆栈、Buffer 凭据/交接 CSV、原始单元格或调试字段；只保留可公开的 Prompt 版本号和计划业务状态；
- 没有计划时 Markdown/JSON 可导出当前分析，CSV 明确不可用，不生成虚构日历。

## 错误恢复

Streamlit 和 Bridge 对以下状态使用稳定错误代码和恢复提示：

- 空文件、格式/MIME/签名不符、损坏或加密工作簿；
- 缺少或重复模块，以及数据质量阻断；
- AI/Bridge 超时、限流、网络中断和无效结构；
- 重复点击、阶段取消、无效计划引用和导出失败。

计划、聊天或导出失败只需重试当前阶段；已解析 Snapshot 保留在当前 Streamlit session。计划取消不会删除上传、Snapshot 或审批。Bridge 是单请求进程，没有需要恢复的长期服务端会话。

## 解析 API

`POST /api/parse` 接受 `multipart/form-data`：

- `file`：必需；
- `expectedModule`：上传槽位模块；
- `moduleOverride`：用户明确确认的模块，可选；
- `mappingOverrides`：字段映射 JSON，可选。

成功返回 `FileParseResult`。失败返回稳定的 `ParseError.code` 和中文用户消息，不向前端返回堆栈。

## 安全与隐私边界

- 浏览器端先校验，Route Handler 再校验扩展名、MIME、文件大小和内容签名。
- 在读取 multipart body 前检查可用的 `Content-Length`，读取后再次检查真实文件大小。
- 只把上传内容交给电子表格读取器，不执行宏、公式、脚本或单元格内容。
- 不启用 VBA、依赖链、HTML 富文本或原始压缩文件导出。
- 响应设置 `Cache-Control: no-store` 和 `X-Content-Type-Options: nosniff`。
- 默认不写入磁盘、对象存储或数据库；请求结束前清零上传字节缓冲区。
- 普通日志不记录原始文件、单元格或解析预览。
- Streamlit Bridge 不把 stderr、异常消息、原始单元格或文件内容显示给用户；未知错误使用固定消息。
- Streamlit 使用统计已关闭；Demo 不发送产品 analytics。
- “清除当前项目数据”会替换上传控件并清空当前 session 中的分析、计划、聊天、Buffer 交接记录和导出缓存。
- 结构化导出移除来源文件名，保留不含原始内容的 evidence `sourceId`。
- `Data/` 已加入 `.gitignore`，真实 LinkedIn 导出不得提交。
- 数据是聚合分析数据；系统不能识别匿名访客、具体关注者或个人购买意向。
- 三种浏览器下载均由用户主动触发，仅在本地生成。
- 本 Demo 不是 LinkedIn 官方产品；用户应确保对上传数据具有合法处理权限。

## 源码结构

```text
streamlit_app.py             # Streamlit 演示主界面
streamlit_demo/              # 无状态 Bridge 客户端和上传内存编码
scripts/                     # Node Bridge stdin/stdout 启动器
dist/                        # 可提交的 Streamlit Cloud 单文件 Node Bridge
python_tests/                # Bridge 与 Streamlit AppTest
packages.txt                 # Streamlit Cloud Debian 系统依赖
src/
  agents/                 # 审批证据、Action Plan 与证据聊天纯逻辑
  app/                    # 页面、错误/加载状态、解析 Route Handler
  analysis/               # 纯函数质量评估、指标计算和 Snapshot 引擎
  components/             # 通用 UI、上传卡片和识别确认界面
  data-processing/        # 别名、文件校验、模块识别、规范化、就绪判定
  domain/                 # LinkedIn、Snapshot、策略、计划和聊天契约
  exports/                # Markdown、通用/Buffer CSV、安全工具和清洗 JSON
  mocks/                  # 完全虚构的合成 CSV
  server/parsing/         # 服务端工作簿解析器和 Mock 结果生成
  services/               # 浏览器端解析 API 客户端
  state/                  # 统一上传与确认 reducer
  streamlit/              # Bridge 协议与操作分发
  tests/                  # 内存生成的合成 fixture 与测试
```

## 测试覆盖

测试 fixture 全部在内存中生成并标记为 synthetic，不读取 `Data/`：

- 正常 CSV、XLSX 和旧式 XLS；
- 多 Sheet；
- 表头不在第一行；
- 手动模块与字段映射；
- 千位分隔符和多种百分比；
- 混合日期与歧义日期；
- 空文件、不支持格式、MIME/签名不一致和损坏输入；
- 缺失关键字段；
- 重复行和重复模块；
- 无法识别模块；
- 公式单元格和类似公式文本不执行；
- Route Handler multipart 校验；
- Mock 流程与空状态。
- 数据质量阻断与非阻断警告确认；
- 缺失值与零、除数为零、时间不重叠和粒度冲突；
- 比率只使用同记录/同日期的完整字段对，稀疏证据行范围不会包含未参与计算的中间行；
- 重复记录、百分比、并列排名、中位数和小样本；
- Proxy Ratio 命名/警告、来源追踪和行顺序不变性；
- Snapshot 指标公式、来源展开、unavailable 空状态和 Agent 输入门禁。
- 未批准洞察/策略隔离、Snapshot 引用匹配和 Action Plan 结构校验；
- 用户时区、过去日期、四周/30 天范围、每周发布上限和日期冲突；
- KPI 定义完整性、实验假设/成功标准/复盘时间；
- 单项计划修改、局部排期更新、确认状态和最近一次撤销；
- 计划生成取消与重试，以及 Mock/未来模型输出的同一 Schema 校验；
- 数值聊天证据、无法回答、Proxy 命名、Prompt injection 和密钥请求拒绝。
- Markdown 必需章节和 Evidence ID；
- CSV 公式注入、逗号、引号、换行和 Unicode；
- JSON 原始文件名、原始单元格、密钥和内部 Prompt 排除；
- Bridge 协议、Synthetic/上传/部分模块、审批门禁、计划和安全错误映射；
- Python Bridge 启动、超时、文件签名错误和项目保留语义；
- Streamlit AppTest 的 Synthetic 全流程、计划修改/撤销、证据聊天、三种导出和清除；
- Streamlit AppTest 的三模块上传 fixture、Snapshot 和导出。
- Buffer 连续 14 天、跨月/年、IANA 时区和 DST 不存在时间；
- 内容审批、渠道/日期过滤、空文案、URL/媒体、单图、字符长度、冲突、重复文案和重复导出；
- Buffer CSV 官方列、渠道拆分、文件名、中文/逗号/引号/换行和公式注入；
- 一项失败不影响其他合法项、`exported_to_buffer` 不会变为 `published`；
- Streamlit AppTest 的“确认计划 → 修复 blocked 项 → 确认 warning → 双渠道导出 → 人工导入指引”。

运行：

```powershell
npm test
.\.venv\Scripts\python.exe -m unittest discover -s python_tests -v
```

## 当前未覆盖

- 加密或密码保护工作簿只会返回明确错误，不支持解密。
- 未支持 XLSB、ODS、Google Sheets API 或压缩包。
- 当前表头定位针对单行表头；复杂合并单元格、多行层级表头仍需扩展。
- 已覆盖常见英文 LinkedIn 字段；中文及更多历史版本别名尚未系统补齐。
- CSV 已验证 UTF-8 与常见英文导出；特殊代码页和非常规分隔符仍需更多 fixture。
- 月/日都不超过 12 的斜杠日期按月/日/年解释并警告，尚无地区设置选择器。
- 不从画像计数推算缺失占比，也不把 Post link 虚构为 `contentId`。
- 画像变化趋势只在记录具有可比较时间维度时计算；多数 LinkedIn 画像导出仅为当前聚合快照。
- 不对粒度不同或时间范围不重叠的模块做跨模块计算。
- 尚未接入真实 LLM API；当前洞察、策略、计划和聊天为确定性 Mock，但未来模型响应必须通过同一 Schema 与引用校验。
- 没有用户管理、数据库或跨设备持久化；刷新页面会清空审批、计划和聊天。
- Buffer 只支持 CSV 人工交接，不实现 OAuth/API、媒体上传或发布回执；没有在真实 Buffer 账户中验证导入预览。
- 当前 Buffer 适配器只覆盖 LinkedIn Page/Profile 的官方通用列；其他渠道可能要求额外字段，必须新增渠道级适配器。
- Buffer 套餐、队列、字符和模板可能变化；界面展示资料检查日期，最终以目标账户当前页面和新下载模板为准。
- 视频、轮播、多图、首条评论和无法公开访问的媒体 URL 需在 Buffer 中手动处理。
- 计划不会自动发布内容，也不连接 LinkedIn API、CRM、网站分析或项目管理工具。
- 聊天目前使用规则意图识别，不提供开放域问答或多轮语义记忆。
- Streamlit 的“取消当前阶段”在当前同步 Mock 中表示丢弃计划草稿并保留上游数据；尚不提供对外部模型流式请求的中途终止。
- 支持部署为 Streamlit Community Cloud 可重置 Demo，但不提供生产级登录、持久化、
  后台任务、长期服务端会话或 SLA。
- 验收时 `npm audit --omit=dev` 与 `pip-audit` 均为 0；完整 `npm audit` 仍报告 ESLint 9 工具链中旧 Minimatch/brace-expansion 的开发期 glob DoS 公告。该链不进入应用运行依赖，也不处理上传内容；直接强制新版会破坏现有 ESLint 插件的 CommonJS API，后续应随 Next/ESLint 插件升级移除。
