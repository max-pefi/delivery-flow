---

name: delivery-check
description: 只读检查交付项目的产物完整性、阶段前置条件和关卡证据。当用户说“检查交付流程”“检查项目状态”“delivery check”时使用。
---
<execution_contract>
本 skill 是「逐步剧本」而非「待办清单」。任何 AI 在执行本 skill 时必须遵守：

1. **逐步汇报、逐步确认**：每次执行前先用一句话告诉用户"我要做 X，会调用 Y CLI"，
   等用户明确确认（说"继续"/"OK"/"确认"）后再执行。

2. **不确定就停下**：遇到参数不明、文件缺失等情况，必须问用户，不要替用户选默认值。

3. **如实报告、不替用户决策**：本 skill 是只读检查，只把 CLI 输出翻译成人话讲给用户，
   不修改文件、不调用飞书、不伪造"通过"或"已签"。
</execution_contract>

# 交付一致性检查（delivery-check）

调用本地 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" check --root . --json` 读取项目文件并报告问题，不修改任何文件、不调用飞书、不替代客户或专家判断。

## 四态检查语义

每个 finding 返回四态之一，**模板/空文件/缺字段都不能算通过**：

| 状态 | 含义 | 项目能否推进 |
|---|---|---|
| `pass` | 证据齐全、达到最小证据要求 | 可以 |
| `unknown` | 文件存在但内容是模板/占位符/缺最小证据字段——需要人工补齐 | 不可以（关卡未通过） |
| `fail` | 文件存在且有明确阻断/不通过结论 | 不可以（关卡未通过） |
| `found` | 仅找到文件（向后兼容） | 需要进一步检查 |

汇总 `summary.blocked = (fail > 0) or (unknown > 0)`，**关卡检查绝不能用 pass 掩盖 unknown**。

## 最小证据要求（缺一即 `unknown`）

- **客户确认记录**：放行结论（`放行`）+ 客户代表 + 确认方式 + 确认时间（YYYY-MM-DD）
- **技术就绪报告**：明确结论（`通过`/`不通过`/`待确认`）
- **验收报告**：验收结论（`通过`/`有条件通过`/`不通过`）+ 客户确认方式 + 客户确认时间（YYYY-MM-DD）
- **评测报告**：Tier1 实测 + 阈值 + 放行结论
- **Story 文档**：三要素——做什么 / DoD·AC / 交付物
- **映射表**：清单 GUID + 父任务 GUID + 非空飞书 task ID

## 检查范围

SPEC 五字段、客户确认、技术就绪、Story 三要素、映射表结构（含 GUID）、评测和验收证据，以及后段产物是否绕过前置关卡。

`fail` 或 `unknown` 都不能解释为通过。真人签字、Tier2 专家结论和技术取舍必须由对应角色确认。

## 关卡顺序纪律（阶段五）

**禁止绕过 readiness**：技术就绪未通过（含缺失、占位符、`pending`/`unknown`）时，下游任何产物都不应存在。检查项（只要 readiness 未通过 + 对应产物存在 → fail）：

| 检查 ID | 触发条件 |
|---|---|
| `order.client-before-readiness` | readiness 通过但客户签字关卡未通过 |
| `order.client-before-story` | 已有 Story 但客户签字关卡未通过 |
| `order.readiness-before-feishu` | 已有飞书映射但 readiness 未通过 |
| `order.readiness-before-story` | 已有 Story 但 readiness 未通过 |
| `order.readiness-before-dev` | 已有 `sprint-status.yaml` 但 readiness 未通过 |
| `order.readiness-before-eval` | 已有评测报告但 readiness 未通过 |
| `order.readiness-before-acceptance` | 已有验收报告但 readiness 未通过 |

完整关卡链：`client_gate → architecture → tech_readiness → story_breakdown → feishu_sync → development → eval → qa → acceptance_gate`。
