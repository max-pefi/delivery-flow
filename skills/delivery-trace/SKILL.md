---

name: delivery-trace
description: 只读检查 SPEC、Story、飞书映射、评测和验收之间的产物追溯链。当用户说“追溯需求”“检查上下文链”“delivery trace”时使用。
---
<execution_contract>
本 skill 是「逐步剧本」而非「待办清单」。任何 AI 在执行本 skill 时必须遵守：

1. **逐步汇报、逐步确认**：每次执行前先用一句话告诉用户"我要做 X，会调用 Y CLI"，
   等用户明确确认（说"继续"/"OK"/"确认"）后再执行。

2. **不确定就停下**：遇到参数不明、文件缺失等情况，必须问用户，不要替用户选默认值。

3. **如实报告、不替用户决策**：本 skill 是只读检查，只把 CLI 输出翻译成人话讲给用户，
   不修改文件、不调用飞书、不伪造"通过"或"已签"。
</execution_contract>

# 交付产物追溯（delivery-trace）

调用本地 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" trace --root . --json` 报告 SPEC / Story / 飞书映射 / 评测 / 验收之间的**文件级产物链完整性**：缺链、重复 ID、悬空映射、漂移。有售前商机编号时上溯到商机档案/签约。

**只读、只检查存在性与引用关系**——不解析 SPEC.md 的 Capability/AC 字段，不解析 Story 的 AC 列表，不解析飞书任务的 description 字段，也不校验 Capability ↔ task_id ↔ DoD 的语义闭环。能力边界见 `docs/runtime.md` 与 ADR 0009。

只报告缺链、重复 ID、悬空映射和漂移，不自动补链、不自动生成证据、不调用飞书。
