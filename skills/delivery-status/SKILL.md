---

name: delivery-status
description: 只读聚合本地 sprint-status.yaml 镜像并报告状态。当用户说“查看交付状态”“汇总 sprint”“delivery status”时使用。
---
<execution_contract>
本 skill 是「逐步剧本」而非「待办清单」。任何 AI 在执行本 skill 时必须遵守：

1. **逐步汇报、逐步确认**：每次执行前先用一句话告诉用户"我要做 X，会调用 Y CLI"，
   等用户明确确认（说"继续"/"OK"/"确认"）后再执行。

2. **不确定就停下**：遇到参数不明、文件缺失等情况，必须问用户，不要替用户选默认值。

3. **如实报告、不替用户决策**：本 skill 是只读检查，只把 CLI 输出翻译成人话讲给用户，
   不修改文件、不调用飞书、不伪造"通过"或"已签"。
</execution_contract>

# 交付状态只读汇总（delivery-status）

调用本地 `delivery status --json` 读取本地状态镜像，汇总任务数量、状态和阻塞项。

飞书是执行状态真源；本地状态只读，禁止由本 Skill 写回飞书、刷新飞书或改变需求文档。
