---

name: delivery-crm-sync
description: 把商机/客户/合同推成飞书多维表格三张表，售前从飞书看漏斗、报进度；飞书是商机状态的唯一真源。强制 SSOT 与商机编号锚定。当用户说"商机进飞书"、"同步 CRM"、"建商机表"、"更新商机状态"、"crm sync"时使用。
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

# 商机 CRM 飞书同步（delivery-crm-sync）

**目标**：把售前的商机/客户/合同推成飞书多维表格记录、售前从飞书看销售漏斗；飞书就是商机状态的唯一真源。每条商机带商机编号（Trace 根），售前不丢失全链路上下文。这是 `delivery-feishu-sync`（任务 SSOT）在售前阶段的对称件——那个管研发任务，这个管商机 CRM。

**角色**：你是售前/商务负责人，负责把商机落飞书、维护 CRM 真源。

## 铁律：SSOT（单一真源，违反即数据错乱）

- **商机意向真源 = 本地商机档案 / 报价单**（需求意向、方案范围）。**商机状态真源 = 飞书多维表格**。二者不重叠。
- 回读飞书**只读状态、绝不覆盖本地商机档案正文**。
- 每条商机带**商机编号 `OPP-{YYYY}-{NNN}`**（Trace 根）：是商机表主键，也是关联客户/合同、贯穿下游 SPEC/Story/验收的锚。无编号不推。
- 每条商机带**阶段状态**单选字段：线索/商机/方案/报价/谈判/签约/输单。用字段表达漏斗流转，不用分组。

## 为什么用多维表格（lark-base）而非任务（lark-task）

商机/客户/合同是**结构化记录**（多字段的行），不是"可完成的工作单元"。多维表格能存金额、工期、联系人等结构化字段并做漏斗视图；任务列表表达不了。故 CRM 用 `lark-base`，与研发任务用 `lark-task` 分工明确。

## 三张表结构（多维表格，字段化）

```
商机表  = 一行一个商机（主键=商机编号），核心漏斗表
客户表  = 一行一个客户单位，商机表按客户编号关联
合同表  = 一行一份合同，签约后建，按商机编号关联商机
```

- **商机表**：商机编号(主键) / 商机名称 / 客户 / 阶段状态(单选) / 预算意向 / 工期意向 / 报价金额 / 负责人 / 来源渠道 / 备注。
- **客户表**：客户单位 / 行业 / 关键联系人 / 决策人 / 客户背景。
- **合同表**：合同编号 / 关联商机编号 / 签约日期 / 合同金额 / 合同范围摘要 / 付款节点。
- 单选字段 **「阶段状态」**（商机表）：线索/商机/方案/报价/谈判/签约/输单。不用分组表达状态（表达不了流转）。

## 依赖

- 已确认的商机（`delivery-presales` 产出商机档案，或等价商机信息）
- `lark-base`（建多维表格/字段/视图）、`lark-shared`（认证/身份）
- 映射表 `_商机映射表.json`（商机编号/客户 ↔ 飞书 record_id），防重复推送。新建时参考 `templates/_商机映射表模板.json`
- 表结构模板 `templates/_商机表模板.json`、`templates/_客户表模板.json`、`templates/_合同表模板.json`

## 输出

- 飞书多维表格三张表（商机/客户/合同，含阶段状态字段与漏斗视图）
- 更新后的 `_商机映射表.json`
- 可选：本地漏斗镜像（**路径由 project-context.md 或团队约定指定，不硬编码**；纯只读回显，飞书才是真源）

<workflow>

<step n="1" goal="校验前置">
  <action>读取商机档案 / 报价单。逐条校验商机编号齐全（`OPP-{YYYY}-{NNN}` 格式）——无编号则回退 `delivery-presales` 先生成，不推无编号商机。</action>
  <action>读取 `_商机映射表.json`（不存在则新建空表）。</action>
  <action>先读 `lark-shared` 的 SKILL.md 确认认证/身份。</action>
</step>

<step n="2" goal="映射到三张表">
  <action>商机 → 商机表一行（主键=商机编号）；客户 → 客户表一行；签约后合同 → 合同表一行。</action>
  <action>比对映射表：商机编号已存在的 → 更新（阶段状态/金额等），不重复创建（幂等）。</action>
</step>

<step n="3" goal="推送飞书">
  <action>用 lark-base 建多维表格与三张数据表；确保商机表「阶段状态」单选字段存在并挂漏斗视图（按阶段状态分组的看板视图）。</action>
  <action>新建商机阶段状态按当前售前进度设置（默认「商机」）。回写 record_id 到 `_商机映射表.json`。</action>
  <action>dry-run 模式只打印将创建的表结构与记录，不实际写飞书（供预演）。</action>
</step>

<step n="4" goal="回读刷新漏斗镜像">
  <action>售前在飞书直接推进商机「阶段状态」——飞书是真源。</action>
  <action>如项目配置了本地漏斗镜像，从飞书拉状态刷新它——只改状态、不动商机档案正文（SSOT）。</action>
  <action>汇总各阶段商机数、金额、赢单率，给售前负责人一眼看清漏斗。</action>
</step>

</workflow>

## lark-cli 速查

> 详细模板见 `templates/_商机表模板.json` / `_客户表模板.json` / `_合同表模板.json`（表字段结构）和 `templates/_商机映射表模板.json`（映射结构）。

```bash
# 前置：先读 lark-shared 的 SKILL.md（认证/身份）
# 身份：--as user 操作；每次调 API 前先 schema 查参数，不猜字段；写操作前先 --dry-run

# ① 建多维表格 App（一个项目/团队一个 CRM App）
lark-cli base +app-create --name "【<团队/项目>】商机CRM" --as user

# ② 建数据表（商机表 / 客户表 / 合同表）
lark-cli schema base.table.create
lark-cli base table create --params '{"app_token":"<app_token>"}' \
  --data '{"table":{"name":"商机表"}}' --as user

# ③ 建「阶段状态」单选字段（漏斗）
lark-cli schema base.field.create
lark-cli base field create --params '{"app_token":"<app_token>","table_id":"<table_id>"}' \
  --data '{"field_name":"阶段状态","type":3,"property":{"options":[{"name":"线索"},{"name":"商机"},{"name":"方案"},{"name":"报价"},{"name":"谈判"},{"name":"签约"},{"name":"输单"}]}}' --as user

# ④ 新增商机记录（参考 _商机表模板.json 的字段）
lark-cli schema base.record.create
lark-cli base record create --params '{"app_token":"<app_token>","table_id":"<商机表table_id>"}' \
  --data '{"fields":{"商机编号":"OPP-2026-001","商机名称":"...","阶段状态":"商机"}}' --as user

# ⑤ 回读验证 / 更新状态
lark-cli base record list --params '{"app_token":"<app_token>","table_id":"<table_id>"}' --as user
lark-cli base record update --params '{"app_token":"<app_token>","table_id":"<table_id>","record_id":"<record_id>"}' \
  --data '{"fields":{"阶段状态":"报价"}}' --as user
```

- 飞书多维表格「单选」字段 `type=3`，选项在 `property.options` 里定义；建后新增选项要走字段 update。
- **商机编号是幂等主键**：推送前必查 `_商机映射表.json`：编号已存在 → update record；不存在 → create 后立即回写 record_id。绝不盲目新建。
- **绝不反向覆盖本地商机档案正文**：飞书只维护阶段状态等执行/漏斗字段，需求意向/方案范围的真源在本地档案。

## 与 feishu-sync 的分工（别混淆两个同步）

| | delivery-crm-sync（本 skill） | delivery-feishu-sync |
|---|---|---|
| 同步什么 | 商机/客户/合同 | 研发任务（story→子任务） |
| 飞书载体 | 多维表格（结构化记录） | 任务（清单>父任务>子任务） |
| 主键/锚 | 商机编号 `OPP-YYYY-NNN` | 本地子任务 ID |
| 阶段字段 | 线索/商机/方案/报价/谈判/签约/输单 | 待开发/开发中/测试中/已上线/缺陷/优化 |
| 映射表 | `_商机映射表.json` | `_映射表.json` |
| 用在 | 售前阶段 | 研发阶段 |

> 两者共享同一条 SSOT 哲学：飞书是状态真源、本地是规格/意向真源、回读只读不覆盖。商机编号在签约后转为项目交付编号，把两张同步网缝成一条 Trace 链。
