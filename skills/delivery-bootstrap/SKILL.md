---

name: delivery-bootstrap
description: 从零把新项目装到 delivery-flow 就绪状态。仅在插件已加载时生效。检查 AI 工具类型 → 引导创建 marketplace.json（L1 插件市场）→ 检测 BMAD（L2 方法论基座）→ 检测 lark（L3 飞书集成，可选）→ 创建 project-context.md + project-progress.yaml（L4 项目实例），完成后交接给 delivery-onboarding。当用户说"装 delivery-flow"、"初始化项目"、"bootstrap"、"从零开始装插件"、"新项目安装"时使用。
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

# delivery-flow 安装引导（delivery-bootstrap）

**目标**：让一个从未接触过 delivery-flow 的用户，在新电脑/新项目上从零完成环境搭建，无论使用 Claude Code、Codex、Cursor 还是 Windsurf，都能自动适配。

**角色**：你是安装秘书。按清单逐步检查、修复、创建，不替用户做业务决策，但可以问必要的配置问题。

## ⚠️ 前置前提：本 skill 仅在插件已加载后可用

**delivery-flow 插件未加载到 AI 工具前，对话中的 AI agent 看不到这个 skill**——它的指令来自 `skills/delivery-bootstrap/SKILL.md`，而这个文件只有插件加载后才会被 AI 读取。

因此：
- **首次安装必须手动完成 L1（插件市场注册）并重启 Claude Code**，然后才能调用 `delivery-bootstrap`
- 如果用户在插件未加载时问"怎么装 delivery-flow"，AI 必须**直接告诉用户手动步骤**（参见 `docs/安装与上手.md` 或 `安装指南.md` 的"快速开始"），不要装作执行了 `delivery-bootstrap`
- 自检命令：`claude plugin list` 应能看到 `delivery-flow`

## 何时用

- 用户在已加载 delivery-flow 的新项目中首次做安装引导
- 用户说"装 delivery-flow""从零开始""bootstrap"
- 项目缺少关键依赖文件（`_bmad/`、`project-context.md`、`project-progress.yaml`）

## 不何时用

- 项目已安装完毕，用户只是想进入工作流 → 直接用 `delivery-onboarding`
- 项目已有 `project-progress.yaml` 且各阶段在推进 → 不需要重新 bootstrap

## 安装分层概览

| 层级 | 组件 | 安装方式 | 是否必须 |
|------|------|---------|---------|
| **L1 插件市场** | `delivery-flow` + `superpowers` | marketplace.json 注册 + 重启 | delivery-flow 必需；superpowers 推荐 |
| **L2 方法论基座** | BMAD-METHOD v6 | `npx bmad-method install` | 必需 |
| **L3 飞书集成** | `lark-*` 技能 | 按 lark-* 各自说明 | 可选 |
| **L4 项目实例** | `project-context.md` + `project-progress.yaml` | 由本 skill 引导生成 | 必需 |

**安装顺序**：L1 → L2 →（L3 可选）→ L4

## 支持的工具

| 工具 | 配置文件 | L1 注册位置 | 说明 |
|---|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | 项目根 `.claude-plugin/marketplace.json` | 原生插件系统；source 必须是对象 `{"source":"github","repo":"..."}` |
| Codex (OpenAI) | `AGENTS.md` | 项目根 `AGENTS.md` | 项目级指令文件 |
| Cursor | `.cursor/rules/delivery-flow.mdc` | `.cursor/rules/` | Rules 规则文件 |
| Windsurf | `.windsurf/rules/delivery-flow.md` | `.windsurf/rules/` | Rules 规则文件 |
| 其他工具 | `docs/跨工具安装指南.md` | 手动 | 手动步骤 |

## 全局原则

1. **只做安装，不做业务决策**——项目红线、验收标准等内容让用户自己填，bootstrap 只负责搭脚手架。
2. **每步有明确的成功判定**——不靠"大概装好了"，必须看到具体文件/目录/配置项才算完成。
3. **失败可恢复**——任何一步失败都不阻断后续检查，最后汇总报告哪些成功、哪些需要手动处理。
4. **幂等**——重复执行不会创建重复文件、不会覆盖用户已填好的内容。
5. **诚实声明未做之事**——本 skill 不执行真实飞书 API、不跑 AI 评测、不做自动门禁；遇到需要外部系统介入的步骤，明确告知用户手动操作。

<workflow>

<step n="1" goal="环境预检与工具检测">
  <action>检查当前目录是否有 `.git/` 目录——判断是否在 git 仓库内。记录仓库根目录路径。</action>
  <check if="不在 git 仓库内">
    <action>提示用户："建议在项目根目录初始化 git（`git init`），delivery-flow 的很多产物需要 git 追踪。是否现在初始化？"如用户同意则执行 `git init`。</action>
  </check>
  <action>**检测当前 AI 工具**，按优先级依次判断：</action>
  <action>1. 检查 `.claude-plugin/` 目录是否存在 → 是则标记为 **Claude Code**</action>
  <action>2. 检查 `AGENTS.md` 是否存在于项目根 → 是则标记为 **Codex**</action>
  <action>3. 检查 `.cursor/` 目录是否存在 → 是则标记为 **Cursor**</action>
  <action>4. 检查 `.windsurf/` 目录是否存在 → 是则标记为 **Windsurf**</action>
  <action>5. 以上都不存在 → 询问用户当前使用的工具，或标记为 **其他**</action>
  <action>记录检测结果：工具类型 + 项目根目录路径，后续步骤据此生成对应配置。</action>
  <action>**自检 delivery-flow 是否已加载**（仅 Claude Code）：执行 `claude plugin list 2>&1 | grep -i delivery`，若无输出说明插件未加载，按本文档"前置前提"段提示用户手动完成 L1 后重启。</action>
</step>

<step n="2" goal="L1 插件市场注册（生成 marketplace.json 或 AGENTS.md / rules）">
  <check if="工具 = Claude Code">
    <action>检查项目根是否存在 `.claude-plugin/marketplace.json`。</action>
    <check if="文件不存在">
      <action>创建 `.claude-plugin/` 目录和 `marketplace.json`：</action>
      <action>
```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "<项目名>-marketplace",
  "owner": { "name": "<用户填入>" },
  "plugins": [
    {
      "name": "delivery-flow",
      "source": { "source": "github", "repo": "fredsimas782-jpg/delivery-flow" }
    },
    {
      "name": "superpowers",
      "source": { "source": "github", "repo": "obra/superpowers" }
    }
  ]
}
```
      </action>
      <action>**重要**：写完后提示用户"必须重启 Claude Code（或运行 `claude plugin marketplace update`）让插件生效。在重启之前，下面的 BMAD 检测、lark 检测、project-context 生成等步骤必须由用户按 `安装指南.md` 手动操作，或在重启后由本 skill 继续。"</action>
    </check>
    <check if="文件已存在但没有 delivery-flow 条目">
      <action>读取现有 `marketplace.json`，在 `plugins` 数组中追加 delivery-flow + superpowers 条目（用 `github` source 对象形式）。保留已有条目不动。</action>
    </check>
    <check if="文件已存在且已有 delivery-flow 条目">
      <action>跳过，提示"delivery-flow 已注册"。</action>
    </check>
  </check>

  <check if="工具 = Codex">
    <action>在项目根创建或更新 `AGENTS.md`，追加以下内容（不覆盖已有内容）：</action>
    <action>
```
## delivery-flow 交付工作流

delivery-flow 已安装，技能文件位于 `<delivery-flow 路径>/skills/`。
当需要执行交付流程时，按以下顺序读取并遵循对应 SKILL.md：
- `delivery-bootstrap` — 安装引导（首次使用）
- `delivery-onboarding` — 流程入口与角色路由
- `delivery-client-gate` — 客户签字关卡
- `delivery-feishu-sync` — 飞书任务同步
- 其余技能见 `<delivery-flow 路径>/skills/` 目录

项目约束文件：`project-context.md`（必须存在）
阶段进度文件：`project-progress.yaml`
```
    </action>
  </check>

  <check if="工具 = Cursor">
    <action>创建 `.cursor/rules/` 目录（如不存在），写入 `delivery-flow.mdc`：</action>
    <action>
```
---
description: delivery-flow 交付工作流指令
globs: ["**/*.md", "**/*.yaml"]
---

# delivery-flow 交付工作流

delivery-flow 已安装，技能文件位于 `<delivery-flow 路径>/skills/`。
当需要执行交付流程时，按以下顺序读取并遵循对应 SKILL.md：
- `delivery-bootstrap` — 安装引导（首次使用）
- `delivery-onboarding` — 流程入口与角色路由
- `delivery-client-gate` — 客户签字关卡
- `delivery-feishu-sync` — 飞书任务同步
- 其余技能见 `<delivery-flow 路径>/skills/` 目录

项目约束文件：`project-context.md`（必须存在）
阶段进度文件：`project-progress.yaml`
```
    </action>
  </check>

  <check if="工具 = Windsurf">
    <action>创建 `.windsurf/rules/` 目录（如不存在），写入 `delivery-flow.md`：</action>
    <action>
```
# delivery-flow 交付工作流

delivery-flow 已安装，技能文件位于 `<delivery-flow 路径>/skills/`。
当需要执行交付流程时，按以下顺序读取并遵循对应 SKILL.md：
- `delivery-bootstrap` — 安装引导（首次使用）
- `delivery-onboarding` — 流程入口与角色路由
- `delivery-client-gate` — 客户签字关卡
- `delivery-feishu-sync` — 飞书任务同步
- 其余技能见 `<delivery-flow 路径>/skills/` 目录

项目约束文件：`project-context.md`（必须存在）
阶段进度文件：`project-progress.yaml`
```
    </action>
  </check>

  <check if="工具 = 其他">
    <action>提示用户："当前工具未在自动适配范围内。请参考 `delivery-flow/docs/跨工具安装指南.md` 手动配置。核心步骤：(1) 将 delivery-flow 的 `skills/` 目录路径告知 AI agent (2) 在项目中创建 `project-context.md`。"</action>
  </check>

  <action>**验证**：根据工具类型，重新读取对应配置文件，确认 delivery-flow 条目存在且路径可访问。Claude Code 还需执行 `claude plugin marketplace validate .` 确保 marketplace.json 通过校验。</action>
</step>

<step n="3" goal="L2 安装 BMAD-METHOD v6">
  <action>检查项目根是否存在 `_bmad/` 目录。</action>
  <check if="_bmad/ 已存在">
    <action>跳过，提示"BMAD 已安装"。检查 `_bmad/` 下是否有 `core/` 或 `agents/` 子目录，确认安装完整。</action>
  </check>
  <check if="_bmad/ 不存在">
    <action>提示用户："请执行 `npx bmad-method install` 安装 BMAD。"</action>
    <check if="插件已加载且能执行命令">
      <action>直接执行 `npx bmad-method install`，成功后验证 `_bmad/` 已创建。</action>
    </check>
    <check if="执行失败或用户尚未执行">
      <action>提示："BMAD 未安装。请手动运行 `npx bmad-method install`。安装完成后告诉我'BMAD 已装好'继续。**不阻断流程**——继续后续步骤，最终报告标记 BMAD 为'需手动完成'。"</action>
    </check>
  </check>
</step>

<step n="4" goal="L3 检测飞书技能（可选）">
  <action>列出已安装的 skill 名称，检查是否包含 `lark-task`、`lark-base` 或其他 `lark-*` 技能。</action>
  <check if="有 lark-* 技能">
    <action>记录"飞书技能已就位"。后续 onboarding 中如涉及飞书同步会用到。</action>
  </check>
  <check if="没有 lark-* 技能">
    <action>提示："飞书技能（lark-task / lark-base 等）未检测到。如项目需要推任务到飞书，请后续按 lark-* 技能的安装说明配置。当前不影响非飞书环节的使用。"**不阻断流程**。</action>
  </check>
</step>

<step n="5" goal="L4 创建 project-context.md">
  <action>检查项目根是否存在 `project-context.md`。</action>
  <check if="已存在">
    <action>跳过，提示"project-context.md 已存在，不覆盖"。读取 frontmatter，报告已填字段数/空字段数。</action>
  </check>
  <check if="不存在">
    <action>采用交互方式，依次询问用户以下关键字段（其余字段留占位符）：</action>
    <action>1. **项目名称**（用于 frontmatter 和文件内引用）</action>
    <action>2. **技术栈**：后端框架+版本、前端框架+版本、部署平台</action>
    <action>3. **AI 能力边界**：只做集成还是含训练？用哪家大模型 API？</action>
    <action>4. **技术红线**：列出 1-3 条最重要的"不做"事项</action>
    <action>5. **验收指标**：性能指标+阈值（其他指标留占位符，用户后续填）</action>
    <action>将用户回答填入 delivery-flow 的 `templates/project-context模板.md` 的对应 `{{}}` 占位符，其余未回答的字段保留占位符。输出到项目根，文件名 `project-context.md`。</action>
    <action>告知用户："已创建 project-context.md，填充了你提供的信息。其余占位符（标注 `{{}}` 的部分）请在正式开始工作前补全。这是 AI Agent 的'宪法级'注入文件，违反其中红线会导致返工。"</action>
  </check>
</step>

<step n="6" goal="L4 初始化 project-progress.yaml">
  <action>检查项目根是否存在 `project-progress.yaml`。</action>
  <check if="已存在">
    <action>跳过，提示"project-progress.yaml 已存在"。读取 `current_stage`，报告当前进度。</action>
  </check>
  <check if="不存在">
    <action>从 delivery-flow 的 `templates/project-progress模板.yaml` 复制到项目根。</action>
    <action>**重要**：将所有阶段的 `status` 改为 `pending`，删除 `completed_at` / `started_at` / `gate_evidence` / `trace_id` 等所有示范数据。`current_stage` 设为 `requirements`，`project` 设为 step 5 中用户提供的项目名。**`current_stage` 不能保留任何示范值（如 `architecture`）。**</action>
    <action>**说明**：`current_stage: null` 表示验收完成态（acceptance-gate 已通过）。这是后续阶段三要落地的语义变更点。</action>
  </check>
</step>

<step n="7" goal="汇总报告与交接">
  <action>输出安装结果汇总表：</action>
  <action>| 检查项 | 状态 | 备注 |</action>
  <action>| 当前工具 | — | 检测到: {工具类型} |</action>
  <action>| git 仓库 | ✅/⚠️ | ... |</action>
  <action>| L1 插件市场 | ✅/⚠️ | {对应文件名}（Claude Code 需重启生效）|</action>
  <action>| L2 BMAD | ✅/⚠️ | ... |</action>
  <action>| L3 飞书技能 | ✅/跳过 | ... |</action>
  <action>| L4 project-context.md | ✅/⚠️ | 已填 N/M 字段 |</action>
  <action>| L4 project-progress.yaml | ✅ | current_stage: requirements（全新项目） |</action>
  <check if="所有项为 ✅">
    <action>提示："安装完成！现在可以开始使用 delivery-flow 了。说 **'我该做什么'** 即可进入 delivery-onboarding，它会帮你识别角色、定位阶段、开始工作。"</action>
  </check>
  <check if="有 ⚠️ 项">
    <action>先逐一说明每个 ⚠️ 项的手动处理方式，再提示处理完后说"继续"或"我该做什么"来触发 delivery-onboarding。</action>
  </check>
</step>

</workflow>

## 与 delivery-onboarding 的关系

- **bootstrap 做的事**：环境检查 → L1 插件市场注册 → L2 BMAD 安装 → L3 飞书检测 → L4 项目实例文件创建 → 报告
- **onboarding 做的事**：检查基座就位（重新验证）→ 识别角色 → 定位当前阶段 → 路由到对应 skill
- bootstrap 完成后，onboarding 的 step 1（基座检查）会自动通过，直接进入 step 2（角色识别）
- **不重复检查**：bootstrap 创建了 `project-progress.yaml` 后，onboarding 直接读它定位阶段，跳过产物扫描

## 作为开源插件分发

delivery-flow 设计为可独立分发的开源插件：

```
# Claude Code 用户，三步开始：
# 1. 在项目根创建 .claude-plugin/marketplace.json（参见 docs/安装与上手.md Step 1）
# 2. 重启 Claude Code 让插件生效
# 3. 在对话中说"我该做什么"
```

- **Claude Code 用户**：L1 注册后重启，然后说"我该做什么"
- **其他工具用户**：打开 `docs/跨工具安装指南.md`，按工具类型找到对应安装步骤