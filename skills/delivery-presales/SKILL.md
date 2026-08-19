---

name: delivery-presales
description: 交付流水线最上游的售前编排 / 商机路由器。乙方售前从商机确认到签约前的编排入口：生成商机编号（Trace 根）→ 委托 BMAD 做商机分析/方案 →（可选）演示原型 → 产出报价单 → 商机/客户落飞书 CRM → 移交签约关卡。当用户说"来了个商机"、"新客户咨询"、"做方案报价"、"售前"、"presales"、"跟进商机"时使用。
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

# 售前编排 / 商机路由（delivery-presales）

**目标**：把乙方售前从"商机确认→方案/报价→谈判"这段编排进流水线，让售前不再游离于交付之外。核心是**在商机确认时就生成商机编号（Trace 根）**，一路带到 SPEC/Story/验收——从源头把商务和交付缝在一起。售前分析能力全部委托 BMAD（不重造），本模块只做**路由 + Trace 起链 + 报价产出 + CRM 落库编排**。

**角色**：你是售前/商务负责人，也是售前阶段的流程引导员。不替 BMAD 做分析，而是把商机领到正确的子阶段和工具，并守住 Trace 根与飞书 CRM 真源。

## 分层设计（本模块的定位）

BMAD 在此当**售前分析工具箱**：`bmad-brainstorming`（需求发散）、`bmad-market-research`/`bmad-domain-research`（市场/领域深挖）、`bmad-product-brief`/`bmad-prfaq`（方案概念锁定）全开——售前方案不用另起炉灶。`delivery-prototype-html` 提供签约前"可点着看"的演示原型。飞书 `lark-base` 当商机/客户/合同的 CRM SSOT（委托 `delivery-crm-sync`）。本模块只补 BMAD 没有的乙方售前编排层。

## 售前子流程（谁在哪一环）

```
商机确认 ─→ 商机分析 ─→ 方案设计 ─→ (演示原型) ─→ 报价 ─→ 谈判跟进 ─→【签约关卡】
opportunity   (BMAD)     (BMAD)     prototype-html          negotiation    deal-gate
生成Trace根    market/    product-   可选:客户签约            报价单-{date}   商机状态→签约
OPP-YYYY-NNN   domain     brief/                                          移交立项包
              research    prfaq
```

> 方括号 = 移交给 `delivery-deal-gate`。销售漏斗细粒度状态（线索/商机/方案/报价/谈判/签约/输单）记在飞书商机表的「阶段状态」字段，不进 project-progress 宏观阶段——同 sprint-status(细) vs project-progress(宏) 的分层。宏观阶段只有 `opportunity`/`proposal`/`deal_gate` 三格。

## Trace 根：商机编号

- **格式**：`OPP-{YYYY}-{NNN}`（如 `OPP-2026-001`），年份 + 三位流水号，本模块在商机确认时生成，全局唯一、不可变更。
- **落点**：商机档案 → 飞书商机表 → 报价单头部 → 立项包 → SPEC.md 头部引用行 → project-progress.yaml 顶层 `trace_id`。
- **作用**：赢单后即项目交付编号；`delivery-trace` 靠它把商机→SPEC→Story→飞书→评测→验收串成一条可追溯链。**一个商机一个编号，从售前用到验收。**

## 角色 → 依据 → 阶段 → 工具

| 售前子阶段 | 工作依据 | 调用 | 产出 |
|---|---|---|---|
| 商机确认 | 客户咨询原文 / 线索 | 本模块（生成商机编号）→ `delivery-crm-sync` 建商机/客户记录 | 商机档案（含 Trace 根）、飞书商机表记录 |
| 商机分析 | 商机档案 + 客户背景 | `bmad-brainstorming`、`bmad-market-research`、`bmad-domain-research` | 市场/领域研究（BMAD 产物） |
| 方案设计 | 分析结论 + 客户需求意向 | `bmad-product-brief`、`bmad-prfaq` | product-brief / PRFAQ（BMAD 产物） |
| 演示原型（可选） | product-brief / 方案 | `delivery-prototype-html` | 可交互 HTML 演示原型 |
| 报价 | 方案 + 合同范围意向 | 本模块（填报价单模板） | `报价单-{date}.md` |
| 谈判跟进 | 报价单 + 客户反馈 | `delivery-crm-sync`（更新商机阶段状态） | 飞书商机表阶段状态流转 |
| 移交签约 | 报价单 + 商机档案 + 合同 | `delivery-deal-gate` | 合同签约确认记录 + 立项包 |

## 依赖

- BMAD（分析/方案工具箱）、`delivery-prototype-html`（演示原型，可选）
- `delivery-crm-sync`（商机/客户/合同落飞书 CRM SSOT）
- `delivery-deal-gate`（下游签约关卡）
- 报价单模板 `templates/报价单模板.md`、商机档案模板 `templates/商机档案模板.md`

## 输出

- `商机档案-{date}.md` 或飞书商机表记录（含商机编号 = Trace 根）——**路径由 project-context.md 或团队约定指定，不硬编码**；未指定则默认 `docs/presales/`
- `报价单-{YYYY-MM-DD}.md`（日期后缀，支持多轮报价）
- 飞书商机表/客户表记录（委托 `delivery-crm-sync`）

<workflow>

<step n="1" goal="确认基座与商机">
  <action>检查 BMAD 是否装（项目根有 `_bmad/`）——售前分析工具箱。缺则提示 `npx bmad-method install`。</action>
  <action if="涉及飞书">确认 lark-* skill 可用且已授权（商机/客户落库需要）。</action>
  <action>从客户咨询原文/线索判断：这是一个需要跟进的商机吗？是 → 进 step2 立商机；否（无效线索）→ 记录后终止，不生成编号。</action>
</step>

<step n="2" goal="商机确认 + 生成 Trace 根">
  <action>**生成商机编号** `OPP-{YYYY}-{NNN}`：读飞书商机表（或本地商机档案）现有最大流水号 +1；无则从 001 起。同一年内递增，跨年重置流水号。</action>
  <action>按 `templates/商机档案模板.md` 填写商机档案：商机编号、客户信息、需求意向、预算/工期意向、来源渠道、初始阶段状态=「商机」。</action>
  <action>委托 `delivery-crm-sync` 把商机/客户写入飞书商机表、客户表（阶段状态「商机」），回写 task/record id 到 `_商机映射表.json`。</action>
  <action>**商机编号一经生成不可变更**——后续所有产物都引用它。</action>
</step>

<step n="3" goal="商机分析（委托 BMAD）">
  <action>按需调用 `bmad-brainstorming`（发散客户真实诉求）、`bmad-market-research`/`bmad-domain-research`（市场/领域深挖）。</action>
  <action>分析产物属 BMAD 产出，本模块不复制其正文，只在商机档案里登记"已完成 X 分析，产物在 Y"。</action>
  <action>更新飞书商机阶段状态 → 「方案」（委托 crm-sync）。</action>
</step>

<step n="4" goal="方案设计 + 可选演示原型">
  <action>调用 `bmad-product-brief` / `bmad-prfaq` 锁定方案概念。</action>
  <action if="客户签约前想看效果">调用 `delivery-prototype-html` 产出可点击的整页演示原型（非静态 mock），提升赢单率。</action>
  <action>方案要圈定"合同范围意向"——这是后续报价与合同范围的基础，也是下游立项包合同范围的雏形。</action>
</step>

<step n="5" goal="报价">
  <action>按 `templates/报价单模板.md` 填写 `报价单-{date}.md`：头部写商机编号；含报价范围、金额构成、工期、付款方式、有效期、假设与除外项。</action>
  <action>报价范围必须与方案的合同范围意向一致；超出方案的项标注"需另行报价"。</action>
  <action>更新飞书商机阶段状态 → 「报价」（委托 crm-sync）。</action>
</step>

<step n="6" goal="谈判跟进">
  <action>记录客户对报价的反馈（认可/压价/改范围/改工期），必要时回 step5 出新版报价（新日期后缀，不覆盖旧版）。</action>
  <action>随谈判进展更新飞书商机阶段状态 → 「谈判」；赢单 → 移交 step7；输单 → 阶段状态「输单」并登记原因，终止（保留商机编号供复盘）。</action>
</step>

<step n="7" goal="移交签约关卡">
  <action>客户决定成交 → 交接 `delivery-deal-gate`：传入商机档案（含商机编号 = Trace 根）、最终报价单、客户已确认的合同材料。</action>
  <action>由 deal-gate 冻结商务基线、产出立项包、写 project-progress（`deal_gate: done`，`current_stage: requirements`，`trace_id` = 商机编号）。</action>
  <action>提醒：签约后商机编号即项目交付编号，全链路 Trace 从这里正式起链。</action>
</step>

</workflow>

## 关卡纪律（流程约定，靠自觉不靠技术锁）

1. **一个商机一个编号**：商机确认即生成 `OPP-{YYYY}-{NNN}`，不可变更，所有下游产物引用它。丢了编号 = 断了 Trace。
2. **报价不超方案、方案不超商机意向**：层层收敛，超出部分显式标注，不静默扩范围。
3. **售前分析委托 BMAD**：不在本模块重写市场/领域分析能力，只登记产物位置。
4. **商机/客户/合同真源在飞书 CRM**：本地商机档案是补充留痕，状态流转以飞书为准（同 SSOT 铁律），回读只读不覆盖。
5. **赢单才移交 deal-gate**：未成交不进签约关卡，不生成立项包，不投研发资源。

## 一步必须真人（工作流只能编排、不能代替）

- **商机真伪与赢单判断**：客户是否真有预算、是否真会成交，需商务人判断。工作流可记录、可路由，但不替商务人拍板成交或输单。
