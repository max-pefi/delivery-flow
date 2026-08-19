---

name: delivery-acceptance-gate
description: 乙方交付的客户验收关卡（出口关卡，与 client-gate 对称）。所有故事完成、评测放行、QA 通过后，对着已签字的范围快照逐条核对 KPI/DoD，取得客户验收签字。当用户说"客户验收"、"验收关卡"、"交付验收"、"acceptance gate"时使用。
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

# 客户验收关卡（delivery-acceptance-gate）

**目标**：BMAD 到 retrospective 就结束，没有乙方↔客户的**交付验收**环节。本工作流补上出口关卡——与 client-gate（入口签字）对称：入口冻结范围，出口对着这份范围逐条核对、取得客户验收签字，作为回款/收尾/转运维的依据。

**角色**：你是项目经理，负责组织客户验收、核对交付、留痕签字。

## 何时用

所有相关 story 完成、`delivery-eval-loop` 放行、QA 通过之后。这是"研发/测试 → 交付"的最终关口。

## 输入

- **已签字的 `客户确认记录`**（client-gate 冻结的范围快照 = 验收范围依据）
- `SPEC.md`（机读契约，`Success signal` 字段 = 验收 DoD 机读锚点）
- 交付物清单（系统/文档/培训材料/等）
- 性能/KPI 实测数据、评测报告、测试报告

## 输出

- `验收报告-{date}.md`（逐条核对 + KPI 实测 + 客户验收签字 + 未决项）

## 硬规则

1. **验收依据 = client-gate 冻结的范围快照 + SPEC.md 机读契约**。用 SPEC.md 的 `Success signal` 字段作验收 DoD 的机读锚点，不再靠人工提炼 PRD。只验签字范围内的，范围外的不在本次验收。
2. **未取得客户验收签字 → 关卡状态「未交付」**，项目不得标记完成/回款/转运维。
3. 未通过项走 **client-gate 的变更机制**（更新确认记录重签），不在验收时临时扩范围。

<workflow>

<step n="1" goal="调取验收依据">
  <action>读 SPEC.md，提取 `Success signal` 字段——这是每条验收 DoD 的机读锚点。</action>
  <action>读已签字的 `客户确认记录`，取范围快照与每条功能的验收 DoD。</action>
  <action>读交付物清单、KPI 目标、评测/测试报告。</action>
</step>

<step n="2" goal="逐条核对">
  <action>对范围快照每条功能：核对是否达 DoD，标 ✅/❌，附证据（截图/报告链接）。</action>
  <action>对每项 KPI/性能验收线：填实测值，对比目标，判达标/不达标。</action>
  <action>汇总交付物是否齐全。</action>
</step>

<step n="3" goal="组织客户验收">
  <action>把验收报告发客户方，逐条走查。记录反馈：通过/部分通过/不通过。</action>
  <check if="有未通过项">
    <action>判定是缺陷（研发修复后重验）还是范围争议（走 client-gate 变更机制重签），不临时扩范围。</action>
  </check>
</step>

<step n="4" goal="取得验收签字，判定交付">
  <action>客户在验收报告签字（形式与时间留痕，同 client-gate）。</action>
  <check if="已签字且全通过">
    <action>关卡状态「已交付」。提示收尾：归档、转运维、（如有）回款依据。</action>
    <action>**写入进度**：更新 `project-progress.yaml`，将 `acceptance_gate` 阶段标记为 `done` + `completed_at`，`current_stage` **置为 `null`（验收完成态，schema 允许 null）**。**若文件不存在，不要自己复制模板**——告诉用户先跑 `delivery-bootstrap` 完成 L4 初始化。</action>
  </check>
  <check if="未签字或部分通过">
    <action>关卡状态「未交付」。记录未决项、责任方、解决时限。项目不得标记完成。</action>
  </check>
</step>

</workflow>
