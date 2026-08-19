---

name: delivery-sprint-sync
description: 从飞书单向拉取执行状态，刷新本地 sprint-status.yaml 镜像。飞书是唯一写端，本地只读。当用户说"同步状态"、"刷新看板"、"sprint sync"、"飞书状态拉取"时使用。
---
<execution_contract>
本 skill 是「逐步剧本」而非「待办清单」。任何 AI 在执行本 skill 时必须遵守：

1. **逐步汇报、逐步确认**：每个 `<step>` 的 `<action>` 开始前，必须先用一句话告诉用户
   "我现在要做 X，会产出 Y"，等用户明确确认（说"继续"/"OK"/"确认"等）后再执行。
   **禁止**把多个 step 合并执行。**禁止**"先全部做完再统一汇报"。

2. **不确定就停下**：遇到模糊、缺信息、多种合理方案的情况，必须停下来问用户，
   **不得替用户做决定**。

3. **契约交接禁止记忆交接**：每步执行前必须重新读相关源文件/schema/产物，
   不得凭上一步的"印象"直接产出（见 ADR 0009）。

4. **产物默认草稿态**：所有写入正式路径的产物，先写到 `<name>.draft.<ext>`，
   等用户确认后再 mv 到正式路径。

5. **关卡产物不动**：本 skill 产出的关卡结论（客户签字、技术就绪、验收）必须由真人/真合同触发，
   AI 只生成**待签件**和**检测是否已签**，不伪造签字。
</execution_contract>

# 飞书状态单向同步（delivery-sprint-sync）

**目标**：保持本地 `sprint-status.yaml` 与飞书执行状态一致——但**只有飞书是写端**，本 skill 只负责从飞书读最新状态、刷新本地镜像。单向流动，不反向写飞书。

**角色**：你是状态同步工具。不替用户决策，只做数据搬运和格式转换。

## 架构原则

```
飞书（唯一写端）──单向拉取──→ 本地 sprint-status.yaml（只读镜像）
     ↑                              ↑
   人工改状态                  AI agent / PM 读状态做决策
```

- **飞书 = 真源**：任何状态变更（待开发→开发中→测试中→已上线→缺陷→优化）只在飞书改。
- **本地 = 缓存镜像**：通过本 skill 单向拉取，不反向写飞书。
- **为什么需要本地镜像**：AI agent 在 Superpowers 里持续干活时，读本地 sprint-status.yaml 就能知道"当前 Sprint 还有几个 Story 没做完、哪个被阻塞、哪个今天要接"——不需要每次调飞书 API。
- **不做什么**：不改飞书、不做状态判断、不做 sprint 规划。只搬运数据。

## 依赖

- 飞书 task API（`lark-task` 或等效飞书 skill）
- `_映射表.json`（story/工作单元 ↔ 飞书 task_id 映射，由 `delivery-feishu-sync` 维护）

## 输入

- 飞书任务列表（含「阶段状态」单选字段值）
- `_映射表.json`

## 输出

- 刷新后的 `sprint-status.yaml`（本地镜像，路径由 `project-context.md` 指定）

## 何时用

- 新的一天/新的工作会话开始时，刷新本地状态
- 研发在飞书推进了状态，需要更新本地镜像供 agent 读取
- `delivery-onboarding` 定位阶段时，需要读 sprint-status 判断整体进度
- 人工感觉本地状态和飞书不一致时

## 工作流

<step n="1" goal="从飞书拉取最新状态">

<action>通过飞书 API 读取所有清单/父任务/子任务，提取「阶段状态」字段值。</action>

<action>按 `_映射表.json` 把飞书 task_id 映射回本地 story 标识。</action>

</step>

<step n="2" goal="格式转换为 sprint-status.yaml">

<action>按 BMAD `sprint-status.yaml` 格式写入本地镜像（保持与 BMAD 格式兼容，方便将来接回 BMAD 的状态机）:</action>

<action>· Epic/Story 名称</action>

<action>· 当前阶段状态（从飞书「阶段状态」映射）</action>

<action>· 阻塞项（飞书标注为「缺陷」或「优化」的条目）</action>

<action>· 完成率（已完成 Story 数 / 总 Story 数）</action>

</step>

<step n="3" goal="差异报告（可选）">

<action>对比本地旧状态，输出变更摘要：哪些从「待开发」→「开发中」，哪些新增阻塞。</action>

<action>若有本地状态但飞书找不到对应任务（`_映射表.json` 缺失映射），标出"漂移项"提示人工核查。</action>

</step>

## 飞书→本地状态映射

| 飞书「阶段状态」 | 本地 sprint-status.yaml 状态 |
|---|---|
| 待开发 | planned / todo |
| 开发中 | in_progress |
| 测试中 | in_review |
| 已上线 | done |
| 缺陷 | blocked |
| 优化 | in_progress（标注优化标记） |

## 注意事项

- **不自动写飞书**：任何需要改飞书状态的操作，提示用户手动在飞书 App 或飞书 CLI 操作。
- **`_映射表.json` 缺失映射 → 人工核查**：不自动创建新映射，防止把飞书里的其他项目任务混进来。
- **本 skill 是无状态的搬运工**：不判断"该不该进下一阶段"，只做数据搬运。状态判断留给 `delivery-onboarding` 和各关卡 skill。
