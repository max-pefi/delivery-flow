---
name: delivery-report
description: 汇总项目计划、流水线、治理登记和飞书只读镜像，生成项目健康报告、阶段报告或管理摘要。当用户说项目状态、周报、健康度、关键路径或阶段报告时使用。
---

<execution_contract>
报告默认写入 `.draft.md`，不修改项目状态，不改变飞书任务，不替用户关闭风险或判定验收。
</execution_contract>

# 项目健康报告

运行：

```bash
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" report --root . --json
```

报告必须区分：流水线阶段、业务计划阶段、飞书执行镜像、风险/问题/变更和当前阻塞。没有负责人或截止日期时仍应正常生成，不得虚构。
