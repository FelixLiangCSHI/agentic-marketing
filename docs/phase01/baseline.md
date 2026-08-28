# Phase 01 / Subphase 01 — 仓库基线记录

> 记录日期：2026-08-28（UTC）
> 执行模式：`repo`；仅文档与治理变更，无代码移动，无远端连接。

## 1. 基线标识

| 项 | 值 |
|---|---|
| HEAD SHA | `b1a9a3226e1d0e14266bf75a9219292019a73c40` |
| 分支 | `copilot/phase-01-development` |
| `git status --short` | 干净（无未提交变更） |
| Node.js | v24.19.0 |
| npm | 11.17.0 |
| Python | 3.12.3（仓库当前无 Python 代码或测试） |

## 2. 基线命令结果

| 命令 | 结果 | 备注 |
|---|---|---|
| `git rev-parse HEAD` | PASS | `b1a9a32…` |
| `git status --short` | PASS | 无输出，工作区干净 |
| `npm ci` | PASS | 仅 allow-scripts 警告，无错误 |
| `npm test` | PASS | 78 tests / 78 pass / 0 fail |
| `npm run lint` | PASS | ESLint 无告警 |
| `npm run typecheck` | PASS | `tsc --noEmit` 无错误 |
| `npm run build` | PASS | Next.js 16 生产构建成功 |
| `python -m unittest discover -s python_tests -v` | N/A | `python_tests/` 与 `requirements.txt` 已被用户从仓库删除（见 §4），无 Python 基线可运行；按规则不恢复 |

已知基线问题：无。所有存在的命令全部通过。

## 3. 现有资产盘点与处置

| 区域 | 内容 | 处置 | 约束 |
|---|---|---|---|
| `src/data-processing/`（5 文件） | XLSX/XLS/CSV 解析、表头识别、字段映射、标准化 | **复用** | 继续区分缺失值与 `0`，不静默猜测；后续补充特征测试 |
| `src/analysis/`（5 文件） | 确定性指标、公式、质量门禁、证据 | **复用** | 原始指标不可被模型输出覆盖 |
| `src/domain/`（8 文件） | 类型与契约定义 | **兼容** | 逐步提取到 `packages/domain-contracts/`（Subphase 02+）；先兼容测试再移动 |
| `src/agents/`（3 文件） | 证据驱动 Mock Agent 原型 | **兼容** | 作为原型参考；拆除对内存会话与 UI 的隐式耦合 |
| `src/tests/`（17 文件，78 用例） | 回归基线 | **复用** | 迁移过程中必须持续通过 |
| `src/app/`、`src/components/`、`src/server/`、`src/state/` | Next.js Portal 起点 | **复用** | 生产认证/授权/API 调用必须服务端执行；Portal 迁入 `apps/web/` 延后到 PR-D |
| `src/exports/`、`src/mocks/`、`src/services/`、`src/utils/` | 导出、Mock 数据、服务配置 | **复用** | 无变更 |
| Python 本地原型（`python_tests/` 等） | 已被用户删除 | **替换/延期** | 不恢复；生产 Python API/Worker 在 Subphase 02 起以新骨架建立 |

## 4. 用户已删除内容（不得恢复）

- `phases/` 目录（Phase 01–06 总控文档与子阶段 Prompt），删除于提交 `b1a9a32`。本子阶段依据 git 历史（`9f5defe`）中的文档执行，但不将其恢复到工作区。
- Streamlit 演示与 Python 本地原型（含 `python_tests/`、`requirements.txt`），删除于 PR #11 合并前的清理。

## 5. 两个 Agent 的隔离边界（冻结）

- Content Agent 与 Campaign Agent 使用**独立**的配置、Session、Tool Set、Memory Namespace、Queue 与 Service Identity/Credential Namespace。
- 任一 Agent 不得读取对方的 Session、Memory 或 Credential；后续以负向测试验证。
- 共享部分只有 `harness-core`（不含营销 Prompt、渠道 SDK 或供应商 Secret）与版本化 Domain Contract。

## 6. 外部 API / 供应商状态（冻结时点快照）

| 依赖 | 状态 | 默认处置 |
|---|---|---|
| DeepSeek / 企业 LLM | 候选，待企业审批 | `mode: mock` |
| Embedding 服务 | 待选定一套企业批准服务 | RAG 仅 Fake Contract |
| 即梦（媒体生成） | 候选，待采购确认 | `mode: mock` |
| LinkedIn Marketing API | 申请中 | Fake Connector |
| Google Ads Developer Token | 申请中 | Fake Connector |
| Product Data (MDM/PIM/DAM) | 待 Owner/Schema/批准确认 | 阻断批准 RAG |
| 企业 SSO (OIDC) | 待 DEV App | FakeIdentityProvider |
