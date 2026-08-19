---
name: delivery-phase-gate
description: 对项目计划中的单个建设阶段执行启动、readiness、开发、QA 和客户验收门禁。当用户说阶段验收、阶段放行、阶段关闭或 phase gate 时使用。
---

<execution_contract>
本 skill 是逐步剧本。每个门禁动作开始前必须先汇报并等待用户确认。

1. 阶段证据默认以 `.draft` 形式生成。
2. AI 只能检查证据和生成待签件，不能伪造客户验收或专家结论。
3. 前置依赖未完成、P0 风险未关闭或变更未审批时，不允许阶段进入正式 Story/飞书同步。
4. 阶段关闭必须同时具备完成标准、QA 证据和客户验收证据。
</execution_contract>

# 阶段门禁

先运行：

```bash
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" plan --root . --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" governance --root . --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" check --root . --json
```

阶段顺序为：计划依赖 → 客户变更确认 → 四层架构/readiness → Story → 飞书同步 → 开发/测试 → 阶段验收。非 AI 项目可以跳过 AI 评测，但不能跳过 QA 和客户验收。
