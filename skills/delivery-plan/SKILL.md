---
name: delivery-plan
description: 管理项目计划层：阶段、里程碑、依赖、并行工作线和团队容量。它不替代 project-progress.yaml，也不改变飞书执行状态真源。当用户说项目规划、阶段计划、WBS、里程碑、依赖或资源安排时使用。
---

<execution_contract>
本 skill 是逐步剧本。任何写入前必须先说明将读取什么、产出什么，等待用户明确确认后再执行。

1. 计划默认写入 `project-plan.json.draft.json`，确认后再转为正式文件。
2. 不要求负责人和日期；团队人数可以填写，具体分工由用户确认。
3. 不把飞书任务状态写入计划文件；执行状态仍由飞书维护。
4. 先运行 `delivery.py plan --root . --json` 检查当前计划，再决定新增、修改或拆分。
</execution_contract>

# 项目计划层

## 目标

把项目路线图与交付流水线、Story 和飞书执行任务连接起来。`project-progress.yaml` 仍表示宏观交付阶段；`project-plan.json` 表示业务建设阶段和依赖；飞书表示实际执行状态。

## 计划字段

- `phases`：业务阶段，支持 `pending / ready / in_progress / blocked / qa / accepted / done`。
- `dependencies`：前置阶段 ID。
- `parallel_with`：允许并行准备的阶段 ID。
- `completion_criteria`：阶段独立验收标准。
- `team_size`：团队人数，不自动分配负责人。

## 工作流

1. 读取 PRD、SPEC、客户确认、四层架构和已有计划。
2. 按阶段拆解里程碑、Epic、Story 边界和依赖。
3. 运行 `delivery.py plan --root . --json` 校验计划。
4. 展示当前阶段、可开始阶段和依赖阻塞。
5. 用户确认后才写入正式计划文件或生成 Story。
