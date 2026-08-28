# evals — 最小 Content/Campaign Eval 门禁（Phase 01 / Subphase 07）

对共享 Harness 的确定性最小评测：golden 路径（各 Agent 用允许工具完成目标）
与 adversarial 路径（无审批的 L3、L4 和跨 Agent 工具调用必须被拒绝且不执行）。

```bash
pip install -e "packages/harness-core[dev]"
python -m pytest evals        # 仓库根，或 npm run eval:test
```

仅使用 FakeModel 与合成数据；不调用真实 LLM 或外部 API。后续 Phase 02/03
的 Golden/Adversarial Eval 在此目录扩展。
