---

name: delivery-feishu-sync
description: 把用户故事拆成飞书「清单>父任务>子任务」三层结构，团队从飞书领活干；飞书是执行状态的唯一真源。强制 SSOT 与任务三要素。当用户说"推飞书"、"同步飞书"、"拆任务进飞书"、"刷新看板"、"feishu sync"时使用。
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

# 飞书任务 SSOT 同步（delivery-feishu-sync）

**目标**：把已确认的故事推成飞书任务、团队从飞书领活；飞书就是开发与落地状态的唯一真源。每条子任务带 SPEC.md 引用，研发不丢失产品上下文。

**角色**：你是项目经理，负责把研发计划落到飞书、维护执行真源。

## 铁律：SSOT（单一真源，违反即数据错乱）

- **需求规格真源 = 本地文档**（SPEC.md / PRD / stories）。**执行状态真源 = 飞书**。二者不重叠。
- **本流程不启用 BMAD sprint-status.yaml 作为写端**：开发状态只在飞书维护。本地 `sprint-status.yaml`（如有）是通过 `delivery-sprint-sync` 从飞书单向拉取的只读镜像，不反向写飞书。
- 回读飞书**只读状态、绝不覆盖本地文档正文**。
- 每条任务带**三要素**：①做什么 ②DoD（引用户故事 AC）③交付物。三缺一不推。
- 每个故事/子任务带**SPEC.md 引用**：链接到对应 Capability 或 Success signal 字段，让研发不丢失产品上下文。

## 飞书三层结构（用自定义字段，不用分组）

```
清单     = 一个业务模块 / 一个 epic
  └─ 父任务 = 一个功能 / 一个页面 / 一个 story
      └─ 子任务 = 一个「可独立完成的工作单元」
```

- **子任务≠AC 条数**：一条 AC 可能拆多个开发动作，多条 AC 也可能一个动作覆盖。子任务按"能否独立完成、独立验收"切，DoD 里引对应 AC 编号。
- 单选字段 **「阶段状态」**：待开发/开发中/测试中/已上线/缺陷/优化。不用分组表达状态（表达不了流转）。

## 依赖

- 已确认的 stories/AC（BMAD create-story 产出或等价故事文档）
- `lark-task`（建清单/任务）、`lark-base`（自定义字段/看板视图）
- 映射表 `_映射表.json`（story/工作单元 ↔ 飞书 task_id），防重复推送。新建时参考 `templates/_映射表模板.json`
- 任务推送模板 `templates/_飞书任务模板.json`（父任务/子任务的标准结构和三要素）
- 清单创建模板 `templates/_飞书清单模板.json`（清单命名和参数）

## 输出

- 飞书清单/父/子任务（含阶段状态字段）
- 更新后的 `_映射表.json`
- 可选：本地看板镜像（**路径由 project-context.md 或团队约定指定，不硬编码文件名**；纯只读回显，飞书才是真源）

<workflow>

<step n="1" goal="门禁：先跑 CLI，读退出码">
    <action>**强制前置**：运行 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" check --root . --json`。退出码 0 才允许继续；非 0 立即停止并把 `findings` 原样打印给用户。</action>
    <action>门禁要求：客户确认放行（gate.client=pass）+ 四层架构齐全 + readiness 报告 pass + project-progress.tech_readiness=done + 全部 Story 三要素齐全 + 映射表不存在或 mapping.valid=pass。</action>
    <action>确认已过 delivery-client-gate（范围已签字）。</action>
    <action>读取 stories + SPEC.md。逐条校验三要素齐全：做什么 / DoD（引 AC）/ 交付物。缺失则回退补齐，不推残缺任务。</action>
    <action>读取 `_映射表.json`（不存在则新建空表）。</action>
</step>

<step n="2" goal="生成 desired-tasks.json 并映射到三层结构">
  <action>epic/模块 → 清单；story → 父任务。</action>
  <action>把每个 story 拆成「可独立完成的工作单元」做子任务——不机械等于 AC 条数。子任务标题=做什么；描述=DoD（引 AC 编号）+交付物。</action>
  <action>写入 `<项目根>/desired-tasks.json`（schema 见 `schemas/desired-tasks.schema.json`）。每条任务含 `local_id / tasklist / parent_task / what / dod / deliverable / spec_ref / content_hash`，其中 `content_hash` 由 what/dod/deliverable/spec_ref 四字段 SHA-256 生成（顺序固定 + sort_keys，跨进程稳定）。</action>
  <action>比对映射表：已存在的跳过或更新，不重复创建（幂等）。</action>
</step>

<step n="3" goal="推送飞书">
  <action>用 lark-task 建清单与父/子任务；用 lark-base 确保「阶段状态」单选字段存在并挂看板视图。</action>
  <action>新建任务阶段状态默认「待开发」。</action>
  <action>推送成功后回写 `_映射表.json` 的 subtasks：新格式 `{task_id, synced: {content_hash, synced_at, what, dod, deliverable, spec_ref}}`（旧格式裸 string 仍可读，dry-run 会标 create_with_review）。</action>
  <action>dry-run 模式只打印将创建的结构，不实际写飞书（供预演）。</action>
</step>

<step n="4" goal="回读刷新状态镜像">
  <action>研发在飞书直接推进「阶段状态」——飞书是真源。</action>
  <action>如项目配置了本地看板镜像，通过 `delivery-sprint-sync` 从飞书拉状态刷新它——只改状态、不动需求正文（SSOT）。</action>
  <action>汇总各阶段任务数、缺陷数、阻塞项，给项目经理一眼看清进度。</action>
</step>

</workflow>

## lark-cli 速查

> 详细模板见 `templates/_飞书任务模板.json`（任务结构+三要素）和 `templates/_飞书清单模板.json`（清单参数）。

```bash
# 前置：先读 lark-shared 的 SKILL.md（认证/身份）
# 身份：--as user 操作个人任务；每次调 API 前先 schema 查参数，不猜字段；写操作前先 --dry-run

# ① 建清单（参考 _飞书清单模板.json）
lark-cli task +tasklist-create --name "【<项目名>】<模块>" --as user

# ② 查自定义字段参数 → 建「阶段状态」字段
lark-cli schema task.custom_fields.create

# ③ 建父任务（参考 _飞书任务模板.json 的 parent_task 结构）
lark-cli task +create --data '{"title":"...","description":"..."}' --as user

# ④ 查子任务 schema → 建子任务（参考 _飞书任务模板.json 的 subtask 结构）
lark-cli schema task.subtasks.create
lark-cli task subtasks create --params '{"task_guid":"<父任务guid>"}' \
  --data '{"title":"...","description":"...","tasklists":[{"tasklist_guid":"<清单guid>"}]}' --as user

# ⑤ 回读验证
lark-cli task tasklists tasks --as user ...
```

- 飞书 API **无法创建"清单文件夹"**（左侧分组），只能靠命名前缀 `【<项目名>】` 归拢；左侧文件夹需在飞书 App 里手动拖入（一次性）。
- 飞书**子任务只有一层**，父任务→子任务到底，不能再往下分"孙任务"，拆任务别超过两层。
- 重复推送前**必查 `_映射表.json`**：已存在 → 更新；不存在 → 新建。绝不盲目新建。
