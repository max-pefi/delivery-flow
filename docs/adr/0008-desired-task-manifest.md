# ADR 0008: desired-task manifest 作为 dry-run 的本地写端

## 状态

2026-08-07 已落地。

## 背景

旧版 `dry-run` 用「sprint-status.yaml × _映射表.json」二元判定 `create / update / skip / orphan`，存在以下设计错误：

- `update` 的判定语义是「task_id 已变」，但 task_id 是飞书远端分配的，本地没有权限修改它。**真正会变的是任务的内容**（做什么 / DoD / 交付物）。
- `skip` 仅检查「sprint-status 里有这条」，不验证三要素是否真的未变。**只要有人改了 Story 文档但没改 sprint-status，dry-run 就误报 skip**，静默放过内容漂移。
- `create` 来自「映射表有但 sprint-status 没记录」——这意味着只要 Sprint 没拉过镜像，新任务永远被推到，但**完全无法验证本地意图的真实性**。
- 整个判定矩阵里**没有任何一条链路能告诉 PM「这条任务你想推什么」**。

## 决策

引入 `desired-tasks.json`（manifest）作为 PM 意图的本地写端 source of truth。dry-run 改为基于 `manifest × mapping` 二维判定，sprint-status 退出判定逻辑，仅作附加信息。

### 三个文件的不变量

| 文件 | 角色 | 谁能写 |
|---|---|---|
| `desired-tasks.json` | 本地写端 = PM 意图 | `delivery-feishu-sync` step 2 生成、PM 编辑 |
| `_映射表.json` | 远端 GUID 的本地索引 | `delivery-feishu-sync` step 3 推送成功时回写 |
| `sprint-status.yaml` | 飞书状态只读镜像 | `delivery-sprint-sync` 单向拉取 |

### 内容指纹（content_hash）

`what / dod / deliverable / spec_ref` 四字段的 SHA-256，字段顺序固定 + `sort_keys=True` + `separators=(",", ":")` + `ensure_ascii=False`，跨进程稳定。spec_ref 为空也参与计算（补写引用也触发 update）。

### mapping 向后兼容

`subtasks[local_id]` 允许两种形态：

- **旧格式**：`"A-1": "task-guid-abc"`（裸 string）。dry-run 标 `create_with_review`，提示升级。
- **新格式**：`"A-1": {"task_id": "task-guid-abc", "synced": {content_hash, synced_at, what, dod, deliverable, spec_ref?}}`。

无需迁移脚本——feishu-sync 下次推送成功时自然升级。

### 降级模式

manifest 缺失时自动降级为 `degraded-consistency-check`：**不输出 create**（不假装知道远端是否存在），只输出 `create_with_review` + `orphan`。退出码 1，提示先跑 `delivery-feishu-sync` 生成 manifest。

## 被否方案

### A. 在 sprint-status.yaml 里加内容字段

不行。sprint-status 是飞书状态只读镜像，加内容字段违反 SSOT。

### B. 用 git diff 比较 stories 前后变化

不行。PM 可能手工编辑 stories 但不 commit；git 状态不反映意图。

### C. 在 _映射表.json 里加 what/dod/deliverable 字段

不行。mapping 是远端索引，本地冗余内容字段会随推送时间漂移，应该独立于远端。

## 风险与缓解

1. **PM 必须先跑 feishu-sync 才能 dry-run**——缓解：dry-run 强提示「先跑 feishu-sync」+ feishu-sync step 1 增加 `generated_at` 过期警告。
2. **content_hash 不覆盖 local_id/tasklist/parent_task**——跨清单/父任务移动 = orphan + create，不视为 update。文档明示。
3. **旧 mapping 长期 create_with_review 噪音**——`check_project` 增加 `mapping.format_legacy` finding。
4. **零依赖下手写 schema 校验覆盖有限**——只能校验必填+类型+格式，复杂语义留给 feishu-sync 生成端自检。

## 不在范围

- 真实飞书 API 写入未实现，`delivery-feishu-sync` 依赖外部 `lark-*` 技能。
- 不实现并发推送、批量重试、增量同步（KISS 边界）。
- 不引入 jsonschema 第三方库，手写 schema 校验约 60 行（必填+类型+格式三层）。