---
name: delivery-governance
description: 管理项目风险、问题、范围变更和决策登记，并把高风险事项接入 delivery-flow 门禁。当用户说风险、阻塞、变更、决策、影响分析或项目治理时使用。
---

<execution_contract>
本 skill 是逐步剧本。任何写入前必须说明将产出什么并等待用户确认。

1. 默认写入 `project-governance.json.draft.json`。
2. 不自动关闭风险、问题或变更，不替用户审批，不伪造客户确认。
3. `owner`、`phase` 和 `task_refs` 可为空。
4. 高优先级风险、阻塞问题和待审批变更会被 `delivery-check` 识别。
</execution_contract>

# 项目治理登记

使用 `project-governance.json` 统一记录 `risks`、`issues`、`changes` 和 `decisions`。

执行前运行：

```bash
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" governance --root . --json
```

每条登记必须有唯一 ID、标题、状态、影响和证据。范围变更还必须填写审批状态和受影响产物；决策必须记录背景和结论。
