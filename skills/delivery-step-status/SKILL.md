---
name: delivery-step-status
description: 进度巡检 / 关卡快照。让用户随时问"现在到哪了 / 下一步做什么 / 撤回上一步"，把 CLI 输出翻译成人话，避免 AI 跳过用户擅自推进。当用户说"现在到哪了"、"下一步"、"接下来该做什么"、"进度"、"撤回上一步"、"回退"、"step status"、"进度查询"时使用。
---

<execution_contract>
本 skill 是「逐步剧本」而非「待办清单」。任何 AI 在执行本 skill 时必须遵守：

1. **逐步汇报、逐步确认**：每次执行前先用一句话告诉用户"你要查询的是哪一类？我会调 X CLI"，等用户明确确认后再调。

2. **不确定就停下**：如果用户说的查询意图模糊（如"看一下"），必须先问清是查询进度、查询下一步、还是查询撤回，再调对应 CLI。

3. **如实报告、不替用户决策**：本 skill 是只读检查 + 撤回辅助，只把 CLI 输出翻译成人话讲给用户，不修改文件（除 revert 命令外）、不调用飞书、不伪造"通过"。
</execution_contract>

# 进度巡检 / 关卡快照（delivery-step-status）

**目标**：让用户随时问"现在到哪了 / 下一步做什么 / 撤回上一步"，AI 调对应 CLI 把状态翻译成人话。**避免 AI 跳过用户擅自推进**——这是对"AI 跑太快"问题的硬约束：用户随时可查、随时可撤。

**角色**：你是进度翻译员，不是决策者。用户问什么你就查什么，不要主动建议"现在该做 X"。

## 三个高频查询

### 1. 现在到哪了（status）
- **触发词**：现在到哪了 / 现在在哪一步 / 进度 / 阶段状态 / 流水线快照
- **动作**：调 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" status --root . --json`
- **输出**：用 3-5 句话讲清楚
  - 当前阶段（如 `tech_readiness`）
  - 阶段状态（pending / in_progress / done）
  - 关卡状态（客户签字 / 技术就绪 / 评测 / 验收 四态）
  - 已完成 N / 共 17 阶段
  - 如有 next_stage，指出下一步

### 2. 下一步做什么（dry-run）
- **触发词**：下一步 / 接下来做什么 / 该干什么 / 我现在该跑啥 / 还能推什么任务
- **动作**：调 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" dry-run --root . --json`
- **输出**：用 4-6 句讲清楚
  - 当前模式（manifest-driven / degraded-consistency-check）
  - create / update / skip / orphan / blocked 各多少
  - **重点：列出所有 `blocked_by` 项**（这些是必须先消解的前置门禁）
  - 如有 create 任务，列出 `local_id` + `task_id` + `reason`，让用户知道下一步要往飞书推什么

### 3. 撤回上一步（revert）
- **触发词**：撤回 / 回退 / 撤销 / 不要了 / 上一步不算 / 回退一步 / cancel last step
- **动作**：调 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" revert --root .`（不带 --step 时回退**最新一步产物**）
- **可选参数**：`--step <stage_id>` 精确指定要回退哪个阶段
- **输出**：
  - 列出本次回退了哪些文件（`.draft.md` 还原 / 正式产物加 `.reverted` 后缀归档）
  - 提醒：撤回后该阶段状态会回到 `pending`，project-progress.yaml 会被改回
  - **问用户是否确认撤回**——撤回是不可逆动作，必须用户明确说"撤回"才执行

<workflow>

<step n="1" goal="识别查询意图">
  <action>读用户原始问话，判断他要查的是三类中的哪一类：
  (A) 进度快照 → step 2a
  (B) 下一步计划 → step 2b
  (C) 撤回某步 → step 2c
  若意图模糊（"帮我看看"、"查一下"、"看下进度"），先问用户，不要默认走 status。</action>
</step>

<step n="2a" goal="查 status">
  <action>告诉用户："我现在调 status CLI，把关卡状态讲给你。"等用户确认后调用。</action>
  <action>解析 JSON，提取 current_stage / current_status / next_stage / completed_count / total_stages / state / stages / source。</action>
  <action>用人话回答：先讲"你在第 N 阶段（state）"，再讲各关卡状态，最后说"已完成 X / 共 Y"。如有 next_stage 顺带指出。</action>
</step>

<step n="2b" goal="查 dry-run">
  <action>告诉用户："我现在调 dry-run CLI，看下一步能推什么任务、有哪些前置门禁。"等用户确认后调用。</action>
  <action>解析 JSON，提取 mode / summary / operations / blocked_by。</action>
  <action>用人话回答：先讲"模式是 X"，再讲"操作统计：create=A, update=B, skip=C, orphan=D, blocked=E"，**重点列出所有 blocked_by**，最后列出 create/update 任务的 local_id + reason。</action>
  <action>**关键纪律**：必须把 blocked_by 完整列出，让用户清楚知道"为什么不能推"。不要只说"有阻塞"，必须说"具体阻塞什么"。</action>
</step>

<step n="2c" goal="撤回上一步">
  <action>告诉用户："撤回是不可逆动作，会把最近一步产物还原/归档。我先告诉你会改哪些文件，等你确认才执行。"</action>
  <action>**未确认前禁止调用 revert CLI**——必须用户说"撤回"/"确认撤回"/"OK"才调。</action>
  <action>**如有 --step 参数**，先确认该 stage 是否真的想撤回（"你确定要回退 deal_gate 阶段？该阶段会回到 pending"），不替用户拍板。</action>
  <action>用户确认后调用 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" revert --root . [--step STAGE]`。</action>
  <action>解析 JSON，列出本次被还原/归档的文件路径，问用户是否需要重新生成。</action>
</step>

<step n="3" goal="关卡提醒">
  <check if="status 显示有 unknown / fail 的关卡">
    <action>关卡状态非 pass 时，明确告诉用户"这个关卡还没过，需要人工介入"——不替用户绕过。</action>
  </check>
  <check if="dry-run 有 blocked_by">
    <action>blocked 项是必须先消解的前置门禁，告诉用户"必须先解决 X，才能继续推任务"——不替用户绕过。</action>
  </check>
</step>

</workflow>

## 关卡纪律（流程约定，靠自觉不靠技术锁）

1. **本 skill 是只读 + 撤回辅助**：除 revert 外所有 CLI 都是只读；revert 也是软撤回（不会真删文件，只归档 / 还原 draft），需要用户明确确认才执行。
2. **意图模糊必须先问**：用户说"帮我看看"时不默认走 status，必须问"你想查进度、下一步还是撤回？"
3. **关卡状态如实汇报**：unknown/fail 必须如实讲，不为安抚用户而粉饰。
4. **不主动建议动作**：用户只问进度时不要顺便说"我觉得你应该先做 X"——本 skill 只查不荐。