---

name: delivery-client-gate
description: 乙方交付的客户签字关卡。在 PRD/原型完成后、进入开发前，产出「客户确认记录+变更清单」并取得签字；未签字则阻断进开发。当用户说"客户确认"、"签字关卡"、"过客户关"、"client gate"时使用。
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

# 客户签字关卡（delivery-client-gate）

**目标**：BMAD 是内部研发框架，没有乙方↔客户的交付确认环节。本工作流补上这一关——把 SPEC.md + PRD/原型冻结成客户可签字的确认件，**未签字不放行开发**，从源头挡住"边做边改、验收扯皮"。范围快照从 SPEC.md 的机读字段（Why / Capabilities / Constraints）生成，不再靠人工提炼 PRD 全文猜范围。

**角色**：你是项目经理，负责组织客户确认、锁定范围、记录变更。

## 何时用

在 BMAD 产出 `SPEC.md`（机读契约）+ PRD（`bmad-prd`）与原型/UX（`bmad-ux`）之后、进入 `bmad-architecture` / `bmad-check-implementation-readiness` 之前。这是"产品设计 → 方案化"之间的强制关口。

三种入口：
- **A 全新确认**：范围还没跟客户对齐 → 组织一次确认并签字（走 step1→2→3→4）。
- **B 存量确认登记**：引入本流程前，客户已通过别的形式确认过范围（往返修改并认可的甲方原始需求材料、确认邮件、会议纪要）→ **不重签**，只把已有确认登记为范围基线（走 step1→2→4，跳过 step3 重新组织签字）。避免逼客户重走仪式（KISS）。
- **C 变更确认**：范围快照已冻结后，客户要求变更范围 → 就变更部分回本关卡重新确认（走 step1→2→3→4，仅针对变更部分）。变更来源包括客户口头变更、内部技术变更、或合同范围调整。不允在开发中静默变更。

## 输入

- `SPEC.md`（BMAD `bmad-spec` 产出，五字段机读契约：Why / Capabilities / Constraints / Non-goals / Success signal）——**范围快照的主要来源**，从机读字段生成范围清单
- PRD（BMAD `bmad-prd` 产出，`*prd*.md`）——功能细节补充
- 原型/UX 文档（`*ux*.md` 或项目原型目录，含 HTML 演示原型）——界面与交互依据
- 上一版客户确认记录（如有，用于比对变更）
- **（B 入口）客户已确认的原始材料**（甲方原始需求材料的往返确认件 / 确认邮件 / 会议纪要）——作为范围基线来源与登记依据

## 输出

- `客户确认记录-{date}.md`（写入交付制品目录，**路径由 project-context.md 或团队约定指定，不硬编码**；未指定则默认 `docs/delivery/`）
- 内含：确认范围快照、变更清单、客户签字位、放行结论

## 关卡纪律（流程约定，靠自觉不靠技术锁）

> 诚实说明：本关卡是**团队共识约定**，没有程序强制——真人硬跳过直接开发也没东西拦。但跳过=丢失范围基线、验收必扯皮。团队须共识遵守。

1. **范围未经客户确认 → 关卡状态「阻断」**，约定上不进入拆任务/开发。确认可以是本关卡新签（A 入口），也可以是已有留痕的登记（B 入口）——**要点是范围有可回溯的客户确认基线，不是形式**。
2. **范围快照一旦确认即冻结**。之后要改范围：更新本确认记录、补变更清单、回本关卡**就变更部分重新确认**，不在开发中静默变更。BMAD 的 correct-course 等重流程按需使用，不替代本关卡。
3. 确认记录是 `delivery-acceptance-gate` 的**验收唯一依据**。验收 DoD 必须可回溯到本记录的范围快照。
4. **B 入口只登记既有确认、不伪造签字**。若 PRD/原型已超出已确认范围，超出部分按"未确认"处理，退回 A 入口补确认。

<workflow>

<step n="0" goal="判定入口">
  <action>先读 SPEC.md，提取 Why / Capabilities / Constraints 三字段——这是后续所有步骤的范围锚点。</action>
  <action>问（或从上下文判断）：客户是否**已经**以某种形式确认过本次范围？</action>
  <action>否 → 走 **A 全新确认**：step1 → 2 → 3 → 4。</action>
  <action>是 → 走 **B 存量确认登记**：step1 → 2 → 4，**跳过 step3**（不再组织客户重新走查签字）。要求用户指明已有确认的**留痕位置与形式**（甲方原始需求材料的往返确认件、确认邮件、会议纪要）。</action>
</step>

<step n="1" goal="冻结范围快照">
  <action>读 SPEC.md + PRD 与原型/UX 文档。B 入口下，**同时读取客户已确认的原始材料**，以其为范围基线的事实来源。</action>
  <action>从 SPEC.md 机读字段生成「本次交付范围」：</action>
  <action>· Why → 一句话说清"做这个产品为了解决什么问题"（给客户看）</action>
  <action>· Capabilities → 逐条转成功能清单（每条功能一句话说清做成什么样）</action>
  <action>· Constraints → 转成限制说明（预算/工期/技术约束，给客户明确边界）</action>
  <action>· Non-goals → 转成「本次明确不做」（防止客户事后主张）</action>
  <action>· Success signal → 转成验收 DoD 摘要（每个 success signal 对应一条验收标准）</action>
  <action>PRD/原型作功能细节与界面依据补充，不主驱动范围快照。</action>
  <action>若存在上一版确认记录，逐条比对，生成「变更清单」（新增/修改/删除 + 原因 + 对工期/预算影响）。</action>
  <check if="B 入口">
    <action>核对 SPEC.md / PRD / 原型是否与客户已确认的原始材料一致。**若发现超出或偏离已确认范围**，标出差异——这部分属于"尚未确认"，需退回 A 入口就差异部分补确认，不能默认放行。</action>
  </check>
</step>

<step n="2" goal="生成客户确认记录">
  <action>按 `skills/delivery-client-gate/templates/客户确认记录模板.md` 填写：范围快照、变更清单、验收 DoD 摘要、遗留/待定项。</action>
  <action>语言直白、面向客户，避免内部术语。每条功能一句话说清"做成什么样算完成"。</action>
  <check if="B 入口">
    <action>「签字」栏登记**已有确认的形式与出处**（如"客户于 {date} 邮件确认甲方原始需求材料 vX"），并附留痕链接/路径。这是登记既有事实，不是补签新字。</action>
  </check>
  <action>写入交付制品目录。</action>
</step>

<step n="3" goal="组织客户确认（仅 A 入口）">
  <action>把确认记录发给客户方，逐条走查范围与 DoD。</action>
  <action>记录客户反馈：认可 / 要改 / 有异议。</action>
  <check if="客户要求修改范围">
    <action>更新范围快照与变更清单，重新走查，直到客户认可。</action>
  </check>
</step>

<step n="4" goal="判定放行">
  <check if="A 入口">
    <action>客户在确认记录签字（线下签字扫描件 / 线上确认留痕 / 邮件回复确认，三选一并注明形式与时间）。</action>
  </check>
  <check if="已签字 或 B入口已登记有效存量确认">
    <action>关卡状态标记「放行」，冻结范围快照。</action>
    <action>**写入进度**：更新 `project-progress.yaml`，将 `client_gate` 阶段标记为 `done` + `completed_at`，`current_stage` 更新为 `architecture`。**若文件不存在，不要自己复制模板**——告诉用户先跑 `delivery-bootstrap` 完成 L4 初始化。</action>
    <action>提示下一步：进入 `delivery-architecture` 产出四层架构 → `delivery-tech-readiness` 产 readiness 报告 → `delivery-story-breakdown` 拆 Story → `delivery-feishu-sync` 推飞书。固定链路，不可跳步。</action>
  </check>
  <check if="未签字（A 入口）或 存量确认与 PRD/原型有未消解差异（B 入口）">
    <action>关卡状态标记「阻断」。明确告知：在消解前，不启动相关开发。</action>
    <action>记录阻断原因与待客户决策项。</action>
  </check>
</step>

</workflow>
