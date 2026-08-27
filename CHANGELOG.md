# Changelog

## Unreleased

### Added

- **「不重复造轮子」可机读规则（L1/L2/L3 三层结构）**：
  - **L1 元数据**：`plugin.json` 的 `dependencies` 由空数组 `[]` 改为 4 项数组（bmad-method required / superpowers recommended / lark-skills + project-management optional）。
  - **L2 边界登记**：新建 `.claude-plugin/CAPABILITY_BOUNDARIES.md`，21 个 skill 全部登记三行固定格式（边界/标签/别名），三分类 `UNIQUE` / `BOUNDARY_DECLARED` / `OVERLAP_REMOVED`。
  - **L3 校验脚本**：`scripts/check_capability_overlap.py`（stdlib only），用 Overlap 系数 `|A∩B|/min(|A|,|B|)` + 中文字 bigram + 触发句剥离，阈值 0.8 FAIL / 0.6 WARN / <0.6 PASS；CLI 三种：`--new-skill` / `--all --include-untracked` / `--diff <ref>`。
  - **L3 外部清单**：`.claude-plugin/external_skills.json` 登记 16 个 bmad-* + 1 个 superpowers 插件 + 3 个 lark-*。
  - **L3 CI**：`.github/workflows/skill-overlap-check.yml`，PR 修改 `skills/**` 等 6 类路径时触发，全量回归 + 单测 + diff 校验。
  - **单测**：16 个 unittest 覆盖 PASS/FAIL/触发句剥离/bigram/Overlap 系数等关键路径。
  - **ADR 0011**：记录 L1/L2/L3 三层结构 + 与 ADR 0004「不预设数字」的边界（校验阈值非业务阈值）。
  - **ADR 0001 观测指标**：新增「观测指标」章节，量化自建 skill 三分类占比（14 UNIQUE / 5 BOUNDARY_DECLARED / 2 OVERLAP_REMOVED）。

### Changed

- **`delivery-onboarding` SKILL.md:376**：「缺则提示跑 `bmad-generate-project-context` 或用本模块 `templates/project-context模板.md` 填」改为「缺则**优先**跑 `bmad-generate-project-context`（BMAD 已装时）；**否则**用本模块 `templates/project-context模板.md` 填」——保持「BMAD 装了更好，不装也能跑」的 ADR 0001 定位，软改不删。

## v0.2.1 (2026-08-21)

### Added

- **`project-progress.yaml` 支持 `meta` 顶层段**：`mode / modules / complexity / snapshot_at` 等透传字段可写入 `meta:` 段，简化解析器接受但不展开解析子字段；`validate_progress()` 不要求 `meta` 段存在，向后兼容无 `meta` 的项目。3 个新单测覆盖：带 meta 解析、无 meta 回退、未知顶层 key 拒绝。
- **`delivery layout` CLI**（只读扫描）：扫描项目根 + 阶段目录，输出「机器文件清单 / 散落文件（按主题分类）/ 建议创建的阶段目录 / 警告」。**不动任何文件**——AI 拿到结果后向人念方案，人点头才决定。配套 skill `delivery-project-layout`。
- **`delivery stage-next` CLI**（阶段推进草稿助手）：根据 `project-progress.yaml` 的 `current_stage` 输出「该阶段建议创建的草稿文件路径清单」+ 用途 + 是否已存在。**不创建任何文件**——草稿创建权归各阶段 skill 自己。配套 5 个新单测。
- **`delivery-project-layout` skill**：用户说"项目文件乱了 / 整理项目 / 按主题分类"时 AI 入口。强制遵守 `<execution_contract>` 5 条：不替人拍板、不动文件、不建产物、关卡产物不动、建议必有理由。
- **7+5 个新单测**：layout_scan 7 个（_classify_filename 2 + layout_scan 5），stage_next_drafts 5 个。**总测试数 119 → 134**。

### Changed

- **`delivery-onboarding` SKILL.md**：Step 0 / 0.5 加「问模式 + 问复杂度」流程，AI 不替用户拍板；`meta.mode / meta.modules` 写入 `project-progress.yaml` 的 `meta` 顶层段。

## v0.2.0 (2026-08-07)

### Added

- **关卡结论契约**：三个关卡模板（客户确认/验收/评测）统一为「命名字段 + 全角/半角冒号 + 值」格式，解析器只读命名字段不做全文语义猜测。三态归一化：`pass / conditional / fail / unknown`，「有条件放行」不再误判为 pass。
- **11 个真实模板回归测试**：直接读 `skills/*/templates/*.md` 原文，校验 fill/parse 往返（placeholders → 结论字段提取），含「正文含反向词但结论行正向」的 codex 明确回归用例。
- **progress 合法性接入 CLI**：`current_stage_summary()` 读取 `project-progress.yaml` 后立即调用 `validate_progress()`，错误带 `fix_hint`，CLI 退出码 2。模板默认 `requirements.status: in_progress`（不再与 `current_stage` 冲突）。
- **全量 Story + 四层架构校验**：`check_project()` 用 `find_all` 校验所有 Story 三要素，缺失任意一份即 `fail`；四层架构（业务/产品/技术/数据）必须全部存在。
- **飞书写入前可执行门禁**：新增 `order.arch-before-feishu` / `order.readiness-report-before-feishu` / `order.progress-tech-readiness-done-before-feishu` / `order.story-complete-before-feishu` 四项检查。`delivery-feishu-sync` step 1 改为强制先跑 `delivery.py check --json` 读退出码。
- **desired-task manifest** (`schemas/desired-tasks.schema.json` + `desired-tasks.json`)：PM 意图的本地写端 source of truth，`content_hash`（what/dod/deliverable/spec_ref 四字段 SHA-256）判定 update/skip。
- **mapping 向后兼容**：`_映射表.json` 的 `subtasks[local_id]` 允许 string（旧格式）或 `{task_id, synced?}`（新格式），无需迁移脚本。
- **dry-run 重写为 manifest-driven**：基于 `manifest × mapping` 二维判定五态 `create / update / skip / orphan / create_with_review`。manifest 缺失时降级为 `degraded-consistency-check`，不输出 create。`sprint-status.yaml` 退出判定逻辑，仅作 `feishu_status` 附加信息。
- **路径兼容**：阶段目录支持 glob 前缀（兼容 `[04] 04-需求分析/`），多目录命中返回 `ambiguous`。
- **CLI 启动器 `delivery.py`**（插件根，12 行）：`python "${CLAUDE_PLUGIN_ROOT}/delivery.py" <cmd> --root . --json`，免安装、跨平台路径独立。Skill 内统一调用。
- **3 个 launcher 合约测试**：验证从仓库外临时目录调用（`${CLAUDE_PLUGIN_ROOT}` 路径独立性）。
- **子 agent 架构规范** (`docs/子agent架构规范.md` + `docs/adr/0009-上下文与子agent边界.md`)：明确「压缩输入才派子 agent」「校验一律走 CLI 退出码」「不派总 agent 复核」三条规则。
- **ADR 0008** (`docs/adr/0008-desired-task-manifest.md`)：记录 desired-task manifest 决策、被否方案、风险。

### Changed

- **`resolve_artifact()` 阶段目录 glob 兼容**：从精确名改为 `root.glob(f"*{hint}")`，命中多个 → `ambiguous`。
- **`delivery-onboarding` SKILL 目录示例**：机器文件（`SPEC.md` / `project-progress.yaml` / `sprint-status.yaml` / `_映射表.json` / `_商机映射表.json`）移到项目根固定位，人读产物才带 `[NN]` 前缀和 emoji。删除 `_meta/` 推荐。
- **`delivery-client-gate` SKILL**：移除「进入 bmad-create-epics-and-stories 拆解，再走 delivery-feishu-sync」跳步文案，改为固定链路 `客户确认 → 四层架构 → readiness → Story 拆解 → 飞书同步`。
- **`delivery-feishu-sync` SKILL** step 2：新增「生成 desired-tasks.json」；step 3：推送成功后回写 mapping 的 `synced`。
- **`delivery-dry-run` SKILL**：重写，说明 `manifest-driven` / `degraded-consistency-check` 两种模式 + 退出码语义。
- **`_映射表模板.json`**：新增 `_subtasks 格式` 说明 + 新格式示例。
- **`docs/产物命名约定.md`**：增加 `desired-tasks.json` 行（项目根 + 兼容 `07-开发/` / `_meta/`）。
- **`README.md` / `docs/runtime.md`**：CLI 命令统一改为 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" <cmd> --json`。
- **`插件现状与待办.md`**：从 87 测试基线重写为 119 测试、20 Skill、9 CLI 子命令、8 Schema 的真实快照。

### Removed

- `dry-run` 旧判定逻辑（基于 sprint-status.yaml × mapping 的二元判定）——被 manifest-driven 取代。
- `delivery-onboarding` SKILL 目录示例中 `[02] SPEC.md` 等机器文件带 `[NN]` 前缀的示例 ——违反机器文件固定名约定。

---

## v0.1.0 (2026-07-24)

### Added

- **插件从首个消费方项目剥离为独立可安装插件**：完成通用化剥离，所有项目特定内容移入消费方 `project-context.md`
- **15 个 Skill 完整可用**：
  - 4 个差异化关卡 skill：`delivery-client-gate` / `delivery-feishu-sync` / `delivery-eval-loop` / `delivery-acceptance-gate`
  - 2 个流程编排：`delivery-onboarding` / `delivery-prototype-html`
  - 状态镜像：`delivery-sprint-sync`
  - 从零安装：`delivery-bootstrap`
  - 横切工具：`delivery-check` / `delivery-trace` / `delivery-status` / `delivery-dry-run` / `delivery-progress`
- **4 份关卡模板**：客户确认记录、评测集、评测报告、验收报告（含 Tier1/Tier2 分层、自检清单）
- **实例层占位模板**：`project-context模板.md`（AI Agent 注入）、`项目宪法模板.md`（人读治理）
- **6 份 ADR**：分层设计、飞书 SSOT、Tier1/Tier2 分层评测、阈值不预设、关卡流程约定、lark-cli 踩坑

### 能力边界

- 本仓库提供 Markdown Skill、模板、示范文档和本地只读 CLI，不包含真实飞书 API 写入、AI 评测 runner 或自动门禁执行器。
- 飞书操作依赖外部 `lark-*` 技能；BMAD 安装命令仍需在真实消费方项目中验证。
- v0.1.0 的 `dry-run` 基于 sprint-status.yaml × mapping 二元判定，已在 v0.2.0 被 manifest-driven 取代。