# delivery-flow — 交付型敏捷 AI 研发工作流

> 一套**可安装、可复制、能脱离个人独立运转**的团队交付流水线。
> 任何角色（产品经理 / 项目经理 / 研发）装上本插件后，全员按同一条流水线走。
> 本仓库是**通用层**，不含任何具体项目内容；项目特定约束只放在消费方项目根的 `project-context.md`。

## 它解决什么

商机确认 → 方案/报价 → **签约** → 需求接入 → BMAD 分析立项 → SPEC / PRD / UX → HTML 原型 → **客户签字** → 四层架构（业务/产品/技术/数据）/ 技术就绪 → Story 拆解进飞书 → Superpowers 研发 → **AI 评测** → 测试 → **客户验收**。全程有依据、有关卡。`project-progress.yaml` 持久化记录当前所处阶段，由关卡 skill 自动写入。

## 标准模式（本模块的定位）

**BMAD 的产品与规划能力全开**：分析研究、SPEC、PRD、UX、架构、技术就绪检查和 Story 拆解都优先复用 BMAD。**Superpowers** 负责研发阶段的 TDD、调试和验证。飞书是执行状态唯一写端，本地 `sprint-status.yaml` 仅由 `delivery-sprint-sync` 从飞书单向拉取，作为只读镜像。

本仓库提供的是 Markdown 工作流规范、模板、角色路由和本地只读 CLI（`check / trace / status / dry-run / progress / plan / governance / report`）。项目计划和治理登记属于本模块，真实飞书 API、评测执行器和自动门禁执行仍依赖外部技能或人工执行。

## 分层设计（只建市面上没有的）

```
Layer0 基座（安装，不自建）
  ├─ BMAD-METHOD v6  文档工具箱：角色 agent + PRD/story 模板 + project-context 生成
  └─ Superpowers      研发内功：TDD / 系统化调试 / 写计划 / 验证

Layer1 本模块差异化交付能力（补 BMAD 未覆盖的业务关卡与编排）
  ├─ delivery-presales       售前编排：商机确认 → 方案/报价 → 谈判跟进（生成 Trace 根）
  ├─ delivery-deal-gate      签约关卡：合同签约冻结商务基线，产出立项包
  ├─ delivery-crm-sync       商机 CRM：商机/客户/合同落飞书多维表格
  ├─ delivery-client-gate      入口：客户签字关卡（未签字不进开发）
  ├─ delivery-feishu-sync      拆任务：故事 → 飞书「清单>父任务>子任务」，飞书=执行真源
  ├─ delivery-sprint-sync       状态镜像：飞书 → 本地 sprint-status.yaml（只读）
  ├─ delivery-eval-loop        AI 评测内循环（Tier1 达阈值放行；Tier2 需专家）
  ├─ delivery-acceptance-gate  出口：客户验收关卡（对签字范围核 KPI/DoD）
  └─ delivery-prototype-html    规划编排：将 BMAD UX 产物转为可交互 HTML 演示原型

Layer2 上手编排（”装上就跑”入口）
  ├─ delivery-bootstrap    从零安装：环境检查 → 注册插件 → 装依赖 → 创建初始文件
  └─ delivery-onboarding   识别角色 → 确保基座就位 → 发放角色依据 → 路由到对应阶段
```

### 当前 Skill 清单（21 个）

- **上手与编排**：`delivery-bootstrap`、`delivery-onboarding`
- **售前与签约**：`delivery-presales`、`delivery-crm-sync`、`delivery-deal-gate`
- **需求到研发**：`delivery-prototype-html`、`delivery-client-gate`、`delivery-feishu-sync`、`delivery-sprint-sync`
- **质量与交付**：`delivery-eval-loop`、`delivery-acceptance-gate`
- **项目管理与治理**：`delivery-plan`、`delivery-governance`、`delivery-phase-gate`、`delivery-report`
- **本地只读检查**：`delivery-check`、`delivery-trace`、`delivery-status`、`delivery-dry-run`、`delivery-step-status`（进度巡检 + 撤回辅助）
- **项目布局助手**：`delivery-project-layout`（扫项目根 + 阶段目录，出主题类目建议，不动文件）

> Skill 数量以仓库 `skills/*/SKILL.md` 为准；BMAD、Superpowers、`lark-*` 属于外部依赖，不计入本插件数量。



| 能力 | 由谁提供 |
|---|---|
| 角色 agent（分析/PM/UX 等）+ SPEC / PRD / Story 模板 | BMAD |
| 项目宪法（AI 必守规则）| BMAD `generate-project-context` → `project-context.md` |
| 研发内功（TDD/调试/验证）| Superpowers |
| **售前编排（商机确认 → 方案/报价 → Trace 根）** | **本模块 delivery-presales** |
| **合同签约关卡（冻结商务基线、产立项包）** | **本模块 delivery-deal-gate** |
| **商机/客户/合同飞书 CRM 同步** | **本模块 delivery-crm-sync** |
| **客户签字关卡（入口）** | **本模块 delivery-client-gate** |
| **飞书任务 SSOT 同步（飞书=执行真源）** | **本模块 delivery-feishu-sync**（编排 lark-* skills）|
| **飞书状态本地只读镜像** | **本模块 delivery-sprint-sync** |
| **项目计划层（阶段/依赖/容量）** | **本模块 delivery-plan** |
| **风险/问题/变更/决策登记** | **本模块 delivery-governance** |
| **阶段级 readiness/QA/验收门禁** | **本模块 delivery-phase-gate** |
| **项目健康报告** | **本模块 delivery-report** |
| **HTML 交互原型编排** | **本模块 delivery-prototype-html**（读取 bmad-ux 产物）|
| **AI 输出评测内循环** | **本模块 delivery-eval-loop** |
| **客户验收关卡（出口）** | **本模块 delivery-acceptance-gate** |
| **从零安装引导** | **本模块 delivery-bootstrap** |

> BMAD 的产品与规划能力全开；`sprint-status.yaml` 不作为本地写端，仅由 `delivery-sprint-sync` 从飞书单向刷新。

## 新人 3 分钟上手

> 第一次用 delivery-flow？只看这一节即可。细节见后续章节。

### 一、装好插件（只做一次）

```bash
# 1. 把插件 clone 到本地固定路径（建议 D:/tools/delivery-flow）
git clone https://github.com/fredsimas782-jpg/delivery-flow.git D:/tools/delivery-flow
```

### 二、新建项目（每个新项目做一次）

#### 一键脚本（推荐）

**Git Bash / macOS / Linux**：
```bash
mkdir D:/code/我的新项目 && cd D:/code/我的新项目
bash <(curl -fsSL https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.sh) \
  --plugin-path D:/tools/delivery-flow
```

需要同时装 BMAD（推荐）：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.sh) \
  --plugin-path D:/tools/delivery-flow \
  --bmad \
  --bmad-tools claude-code \
  --bmad-timeout 600
```

**一步到位**（推荐新项目用）：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.sh) \
  --plugin-path D:/tools/delivery-flow \
  --bmad --init
```

加 `--init` 会顺便把 `project-context.md` 和 `project-progress.yaml` 从 `templates/` 复制到项目根，**替换 `{{项目名}}` 为当前目录名**。开 AI 第一句话就能直接 `delivery progress` 跑起来，不用再手填。

**PowerShell / Windows**：
```powershell
New-Item -ItemType Directory D:\code\我的新项目 | Out-Null; cd D:\code\我的新项目
irm https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.ps1 | iex `
  -PluginPath D:\tools\delivery-flow
```

需要同时装 BMAD：

```powershell
irm https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.ps1 | iex `
  -PluginPath D:\tools\delivery-flow `
  -Bmad `
  -BmadTools claude-code `
  -BmadTimeout 600
```

**一步到位**：

```powershell
irm https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.ps1 | iex `
  -PluginPath D:\tools\delivery-flow `
  -Bmad -Init
```

脚本会自动生成 `AGENTS.md`、`.claude/plugins/` 软链接、`.cursor/rules/`、`.windsurf/rules/`，**一行命令完成所有配置**。加 `--bmad` 后还会自动调用 `npx bmad-method install` 把 BMAD 装到当前目录（首次需要联网下载包，约 1-3 分钟）。

#### 手动三步（如果不跑脚本）

```bash
# 1. 复制精简版 AGENTS.md 到项目根（改第 3 行路径为 D:/tools/delivery-flow）
# 2. 建软链接
mkdir -p .claude/plugins
ln -s /d/tools/delivery-flow .claude/plugins/delivery-flow
# 3. 验证：ls .claude/plugins/delivery-flow/skills/ 应看到 21 个 skill 目录
```

#### 先 dry-run 看一眼要做什么（推荐）

```bash
bash setup.sh --plugin-path D:/tools/delivery-flow --bmad --init --dry-run
```

脚本只打印「将要创建/修改哪些文件」+「将要执行的命令」，**不实际执行**。确认无误后去掉 `--dry-run` 真跑。

#### 装完跑一遍 verify（可选但推荐）

```bash
# Git Bash
bash <(curl -fsSL https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup-verify.sh)
# PowerShell
irm https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup-verify.ps1 | iex
# 加 --json / -Json 给 AI 解析
```

脚本会扫7 项关键配置并分色打印：✅ OK / ⚠️ WARN / ❌ ERROR / ℹ️ INFO。退出码：
- `0` — 全 OK，AI 可直接接管
- `1` — 有 WARN，功能可用但建议补齐
- `2` — 有 ERROR，必须修复（通常是软链接不可达）

**AI 排错入口**：在 Claude Code 里说「帮我 verify 一下当前配置」，AI 跑 `--json` 自动识别问题。

### 三、打开 AI 工具，第一句话

> "按 AGENTS.md 走，现在到哪了"

AI 会自动：
1. 读 `AGENTS.md` → 加载 delivery-flow 路径
2. 调 `delivery progress` → 拿当前阶段
3. 复述 `next_action_suggestion.suggested_question` 给你

### 四、之后每个新对话

```
你说话              AI 干活              你确认
─────────────────────────────────────────────
"我是 PM，做 PRD"   调 BMAD write-prd   "继续"
"客户签字了"        调 client-gate      签字记录模板
"下一步"            调 dry-run 列出操作  "OK"
"撤回"              调 delivery revert  看回退结果
```

### 完整工作流（21 个关卡）

详见下方「## 安装」起的全部章节。日常使用只需记住**三步循环**（见末尾「## 日常使用三步循环」）。

---

## 安装

> **最快方式**：在 Claude Code 中说 **"装 delivery-flow"** 或 **"bootstrap"**，`delivery-bootstrap` 会检查四层依赖并引导你完成安装；它不会替你调用外部安装器、飞书 API 或自动填充业务证据。

📖 **快速安装指南** → 详见 [`安装指南.md`](安装指南.md)。含 Claude Code 一键安装和其他工具（Codex / Cursor / Windsurf）分步指引。

📖 **分步安装与上手指引** → 详见 [`docs/安装与上手.md`](docs/安装与上手.md)。含安装命令、角色分工表、端到端示例流程。

🔧 **非 Claude Code 工具安装** → 详见 [`docs/跨工具安装指南.md`](docs/跨工具安装指南.md)。Codex / Cursor / Windsurf 各有对应配置步骤。

### 快速开始（按工具）

**Claude Code**：在你的项目目录打开 Claude Code，说"装 delivery-flow"，由 `delivery-bootstrap` 检查并引导 L1 插件、L2 BMAD、L3 飞书（可选）和 L4 项目实例四层配置。

**Codex / Cursor / Windsurf**：
```bash
# 1. clone 本仓库
git clone https://github.com/fredsimas782-jpg/delivery-flow.git

# 2. 进入你的项目，安装 BMAD
cd <你的项目>
npx bmad-method install

# 3. 让 AI 帮你创建配置文件（参考 docs/跨工具安装指南.md）
```

### 第一步：选运行模式（必须）

插件装好后，**第一步**永远是让 AI 问你要走哪种模式，由你（人）选，不是 AI 替你判断：

| 模式 | 适用场景 | 关键差异 |
|---|---|---|
| **交付模式**（默认） | 复杂/正式/风险高、需要客户签字确认 | 每步都要你确认产物方向；每个关卡都签字才推进；不难走的步骤不允许跳过 |
| **快速模式** | 紧急/售前演示/PoC/内部工具 | 合并可跳过步骤；产物可草稿态直接推飞书；关卡产物允许标记 `degraded-consistency` |

选完模式后，**交付模式还会再问复杂度**（低/中/高），决定要不要走完整治理登记。

> **为什么必须有这一步**：AI 不知道项目紧急度和精度要求。如果你不说，AI 可能按交付模式走慢节奏，要么按快速模式做出来的东西不能用于正式交付。**这一步直接决定后续所有 step 的执行强度**，并写入 `project-progress.yaml` 的 `meta.mode` 事后可追溯。

**完整对比表**：

| 触发场景 | 选哪个 |
|---|---|
| 客户已签字、差最后上线 | 交付模式 |
| 售前给客户演示 2 周后签约 | 快速模式 |
| 内部工具/同事需求 | 快速模式 |
| PoC 验证可行性 | 快速模式 |
| 合规项目/数据迁移 | 交付模式 |
| 1-2 个月定制项目 | 交付模式 |

**怎么选**：如果犹豫不决，先选**交付模式**（更安全）。后续任何时候都可以用 `python delivery.py revert --step <阶段>` 撤回重来。

### 多模块项目（可选）

项目包含多个独立可交付模块（如电商的用户/订单/支付模块）时，**阶段目录内按模块分子目录**，避免同名文件堆在一起分不清：

```
04-需求分析/
├── 00-总览/                ← 跨模块的总体 PRD / 架构
├── 用户模块/
│   ├── [01] PRD.md
│   └── [02] SPEC.md
└── 订单模块/
    └── [01] PRD.md
```

**判定标准**：客户点名了模块名 / 模块可独立交付 / 至少 2 个模块需要独立 PRD/UX/架构。**单模块项目不强制**——避免空目录噪音。

**机器文件无模块归属**：`SPEC.md` / `project-progress.yaml` / `_映射表.json` 仍放项目根。AI 在交付模式 + 复杂度 ≥ 中时会再问你"单模块 / 多模块"，选择写到 `meta.modules`。

完整规则与示例见 [delivery-onboarding/SKILL.md](skills/delivery-onboarding/SKILL.md)。

### 3 层封顶（模块内不分子模块）

超过 3 层就要警惕——很可能分错了，应把「子模块」升级为顶层模块：

```
阶段 → 模块 → Story 文件（顶）
 1 层    2 层     3 层
```

**Story 层用编号 + 文件名前缀区分子功能**，不分子目录：

```
07-开发/stories/订单模块/
├── STORY-001-创建订单.md    ← 子功能：下单
├── STORY-002-支付订单.md
└── STORY-004-查询订单.md    ← 子功能：查询
```

**升级条件**：客户明确点名 / 独立签字 / 跨多团队，才升级为顶层模块。

### 混乱项目接入（已有项目）

**不重命名、不迁移、轻量补建。** 项目级文件都是可选层：

1. 创建 `project-progress.yaml`：`current_stage` + `meta.mode: quick` + `meta.modules`
2. `delivery check --root . --json` 看哪些缺失
3. `delivery progress --root . --json` 拿下一步建议
4. 选关键产物补建——缺失 SPEC 跑 `bmad-spec` 重生成、缺失客户确认走 `delivery-client-gate` B 入口

AI 协助整理脚本入口：说「整理混乱项目」触发 `delivery-project-layout` skill，AI 调 `delivery layout --root . --json` 只读扫描，把建议清单念给人听，**插件不创建文件也不移动文件**——执行由人确认后手动 `mv` 或未来 `--apply` 选项。

完整规则见 [delivery-project-layout/SKILL.md](skills/delivery-project-layout/SKILL.md)。

## 本地 CLI 与 dry-run

CLI 只读、不调用网络、不写项目文件。两种调用方式二选一：

**方式 A（推荐）**：`pip install -e .` 后直接用 `delivery` 命令：
```bash
pip install -e /path/to/delivery-flow
delivery check --root <项目根> --json
delivery trace --root <项目根> --json
delivery status --root <项目根> --json
delivery dry-run --root <项目根> --json
delivery progress --root <项目根> --json
delivery plan --root <项目根> --json
delivery governance --root <项目根> --json
delivery report --root <项目根> --json
delivery revert --root <项目根> [--step <stage_id>] --json
delivery layout --root <项目根> --json
delivery stage-next --root <项目根> --json
```

**方式 B（未安装）**：用仓库根的 `delivery.py` 启动器：
```bash
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" check --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" trace --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" status --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" dry-run --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" progress --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" plan --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" governance --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" report --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" revert --root <项目根> [--step <stage_id>] --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" layout --root <项目根> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" stage-next --root <项目根> --json
```

`check` 会检查四态证据（`pass / unknown / fail`）、关卡顺序和已启用的计划/治理门禁；模板或缺证据不会算通过。`plan` 读取 `project-plan.json`，计算当前阶段、可开始阶段和依赖阻塞；`governance` 读取 `project-governance.json`；`report` 聚合计划、治理、流水线和飞书只读镜像。`dry-run` 只生成 `create / update / skip / orphan / create_with_review` 计划（基于 `desired-tasks.json` × `_映射表.json` 二维判定），真实飞书写入仍由外部 `lark-*` 技能负责。`trace` 是**文件级产物链完整性检查**（不解析 SPEC Capability / Story AC 字段语义）。

### 进度巡检与撤回（让 AI 不擅自推进）

> **设计初衷**：解决"提供材料后 AI 直接把所有产物生成完、跳过用户确认"的问题。所有 skill 顶部都加了 `<execution_contract>` 约束，CLI 也提供三个常用查询。

**三个高频查询**：

```bash
# 1. 现在到哪了
python delivery.py progress --root . --json
# → 返回 current_stage / current_status / next_stage / stages
#    还附带 next_action_suggestion.suggested_question（AI 可直接复述给用户的中文问句）

# 2. 下一步做什么（含阻塞项）
python delivery.py dry-run --root . --json
# → 列出 create / update / skip / orphan 操作 + 完整 blocked_by

# 3. 撤回上一步（产品/合同/技术就绪等任意阶段可撤回）
python delivery.py revert --root .                # 回退 project-progress.yaml 的 current_stage
python delivery.py revert --root . --step deal_gate  # 精确指定阶段
```

**三个核心纪律**（写在每个 SKILL.md 的 `<execution_contract>` 头部）：

1. **逐步汇报、逐步确认**：每个 `<step>` 的 `<action>` 开始前，AI 必须先用一句话告诉用户"我要做 X、会产出 Y"，等用户明确说"继续"/"OK"再执行。**禁止**把多个 step 合并执行。
2. **不确定就停下**：遇到模糊、缺信息的情况必须问用户，不替用户拍板。
3. **产物默认草稿态**：写入正式路径的产物先写到 `<name>.draft.<ext>`，用户确认后 `python delivery.py revert --step <stage>` 或手工 mv。

`delivery-step-status` skill 把以上三个查询封装成 AI 可直接调用的剧本（用户说"现在到哪了 / 下一步 / 撤回"即可触发）。

## 当前未实现

- 真实飞书 API 写入适配器（CLI 不创建、更新或删除飞书任务）
- AI 评测 runner（CLI 不执行 Tier1/Tier2 评测）
- 自动门禁执行器（CLI 不替客户签字、专家判断或自动推进阶段）
- 自动迁移旧项目文件布局（只读兼容根目录、阶段目录、`_meta`）



### 场景一：全新电脑，客户刚通过微信发了文件

这是最常见的启动场景，按以下步骤操作：

```bash
# 1. 在任意位置创建项目文件夹
mkdir D:\code\新项目名称
cd D:\code\新项目名称

# 2. 把微信收到的文件直接拖进这个文件夹
#    支持：Word、Excel、PDF、图片、文本，什么格式都行，不用整理

# 3. 安装 delivery-flow（仅第一次需要）
git clone https://github.com/fredsimas782-jpg/delivery-flow.git D:\tools\delivery-flow
npx bmad-method install
```

然后打开你的 AI 工具（Codex / Claude Code），对它说：

> 我的 delivery-flow 在 `D:\tools\delivery-flow`，帮我装到当前项目。
> 然后我是产品经理，客户刚给了这些文件（说一下文件名），帮我开始分析这个项目。

AI 会自动：读取文件 → 识别角色 → 调用分析流程 → 告诉你下一步做什么。

### 场景二：团队多人协作

```bash
# 项目经理装一次 delivery-flow，配好 project-context.md
# 其他人不用装，从飞书领任务即可
```

项目经理在 AI 工具中说：

> 我是项目经理，项目已经分析完了，帮我走客户签字流程

AI 会引导你：生成范围快照 → 组织客户确认 → 冻结变更基线 → 进入架构阶段。

### 场景三：研发接手已有项目

```bash
# 项目已经有飞书任务了，研发只需要领活
```

研发在 AI 工具中说：

> 我是研发，飞书上有一个子任务：用户登录模块开发，帮我开始

AI 会引导你：读取 Story AC → 用 Superpowers 做 TDD → 完成后回飞书改状态。

---

## 各角色使用指南与示例

### 产品经理

**什么时候用**：拿到需求文件后，从分析立项开始，一直到 HTML 原型交付给客户签字。

**怎么开始**：

> "我是产品经理，客户给了 xxx 需求文档，帮我开始分析立项"

**你会经历的流程**：

| 步骤 | 你说什么 | AI 做什么 | 产出物 |
|---|---|---|---|
| 分析立项 | "帮我分析这个需求" | 读文件 → 发散 brainstorming → 联网研究 → 锁定概念 | 产品 Brief / PRFAQ |
| 写 PRD | "基于分析结果写 PRD" | 引导式发现，问你关键问题 | PRD.md |
| UX 设计 | "帮我做 UX 设计" | 产出交互规范和线框 | DESIGN.md |
| HTML 原型 | "生成可交互的 HTML 原型" | 编排 UX 产物为可点击的演示 | prototype/ 目录 |
| SPEC 契约 | "生成 SPEC 机读契约" | 提取核心能力/约束/成功信号 | SPEC.md |

**示例对话**：

```
你：我是产品经理，客户发了一个智能客服系统的需求文档，
    文件在项目根目录，另外商务说预算在 30 万以内，帮我开始分析

AI：收到。我来读取需求文档...
    [读取文件]
    基于文档内容，我先做 brainstorming 发散：
    1. 核心问题：客户想解决什么？
    2. 目标用户是谁？
    3. 与现有系统的集成点？
    ...
    建议下一步做 market-research 和 domain-research，
    要我现在开始吗？

你：开始

AI：[调用 bmad-market-research，产出研究报告]
    研究完成，以下是关键发现：
    - 市场规模：...
    - 竞品分析：...
    建议锁定产品概念为 xxx，要我生成 PRFAQ 吗？
```

### 项目经理

**什么时候用**：客户签字、拆任务、跟进进度、验收。你是流程的推动者。

**怎么开始**：

> "我是项目经理，项目已经分析完了，帮我走客户签字流程"

**你会经历的流程**：

| 步骤 | 你说什么 | AI 做什么 | 产出物 |
|---|---|---|---|
| 客户签字 | "帮我组织客户签字" | 读 SPEC.md → 生成范围快照 → 签字记录 | 客户确认记录.md |
| 技术就绪 | "帮我检查技术就绪" | 调用 readiness-check，四文档对齐 | readiness-report |
| 拆任务 | "帮我拆任务进飞书" | 读 PRD → 拆 epics/stories → 推飞书三层结构 | 飞书任务 + 映射表.json |
| 跟进进度 | "帮我看当前进度" | 读 sprint-status.yaml，汇总状态 | 进度报告 |
| 客户验收 | "帮我做客户验收" | 对照 SPEC DoD 逐项验收 | 验收报告.md |

**示例对话**：

```
你：我是项目经理，产品分析阶段完成了，SPEC.md 已经写好，
    帮我组织客户签字

AI：收到。我来读取 SPEC.md 生成范围快照...
    [读取 SPEC.md]
    范围快照已生成，包含：
    - 核心能力：5 项
    - 非目标：3 项
    - 成功信号：4 条
    
    请确认以下内容，然后我把签字记录模板给你：
    [展示范围快照]
    你确认后，我可以生成客户确认记录.md

你：确认，生成签字记录

AI：[生成 客户确认记录-2026-08-02.md]
    签字记录已生成。请线下让客户签字确认。
    签字完成后告诉我，我帮你冻结变更基线，进入架构阶段。
```

### 研发工程师

**什么时候用**：从飞书领到任务后，用 TDD 方式开发，完成后回飞书改状态。

**怎么开始**：

> "我是研发，飞书上有一个子任务：xxx 模块开发，Story AC 是 xxx"

**你会经历的流程**：

| 步骤 | 你说什么 | AI 做什么 | 产出物 |
|---|---|---|---|
| 领任务 | "帮我读这个 Story" | 读取飞书任务描述和 AC | 理解需求 |
| 写计划 | "帮我写实现计划" | 用 Superpowers 写开发计划 | 计划.md |
| TDD 开发 | "开始写代码" | TDD 方式：先写测试 → 实现 → 通过 | 代码 + 测试 |
| 自测 | "帮我跑测试" | 执行测试套件 | 测试报告 |
| 回飞书 | "测试通过了，改飞书状态" | 更新飞书任务状态 | 状态变更 |

**示例对话**：

```
你：我是研发，飞书上领了一个任务"用户登录模块"
    AC：1. 支持手机号+验证码登录 2. 支持密码登录 3. 登录失败3次锁30分钟
    帮我开始

AI：收到。我来分析这个 Story 的实现方案...
    建议技术方案：
    - 验证码：接入短信 API（阿里云/腾讯云）
    - 密码：bcrypt 加密存储
    - 锁定：Redis 计数器，30分钟过期
    
    要我先写测试用例吗？

你：开始

AI：[调用 Superpowers TDD 流程]
    先写测试：
    - test_send_sms_code_success
    - test_login_with_sms_code
    - test_login_with_password
    - test_login_lock_after_3_failures
    ...
    测试已写好，现在开始实现代码...
```

### AI 工程师

**什么时候用**：研发完成后，跑 AI 评测，确认质量达标。

**怎么开始**：

> "我是AI工程师，项目开发完了，帮我跑 AI 评测"

**你会经历的流程**：

| 步骤 | 你说什么 | AI 做什么 | 产出物 |
|---|---|---|---|
| 准备评测 | "帮我生成评测集" | 读 SPEC Success signal → 生成评测用例 | 评测集.md |
| 跑评测 | "开始评测" | Tier1 自动化评测 | 评测报告.md |
| 看结论 | "评测结果怎么样" | 给出门禁结论：达标/未达标 | 放行建议 |

---

## 日常使用三步循环

装好之后，每天的工作就是这个循环：

```
1. 说"我该做什么"        → AI 识别你的角色，告诉你当前该做哪一步
2. 按提示执行对应工作     → 每一步都有对应的 skill 引导
3. 完成后说"下一步"       → AI 自动推进到下一阶段
```

**模型分层策略**（可选）：在 `project-context.md` 的「模型分层策略」节里填"哪个阶段用哪个级别的模型（Opus/SOL 思考 vs Sonnet/Haiku/Codex-mini 执行）"和触发词（"出方案"/"按方案执行"）。**双路径**：

- **同工具内分层**（都在 Claude Code / 都在 Codex CLI）：直接说"切到执行"/"切到思考"，AI 在当前工具内切换档位（Claude 用 `/think hard` 或 Task tool，Codex 用 `/plan` 或 `/code`）
- **跨工具交接**（⭐常见）：思考模型在工具 A 把方案写到 `.draft.md` → 关 A → 工具 B 第一句"读 `<交接文件>`，按方案执行"。「交接文件」列在 `project-context.md` 的 5 列表格里指定

填好后 AI 收到指令会按策略路由到对应模型；不填则按当前模型一路走完。Codex 用户额外看 `.codex-plugin/plugin.json` 的 `model_strategy` 字段。

**关键节点（硬门禁，不可跳过）**：

| 节点 | 谁触发 | 说明 |
|---|---|---|
| 合同签约 | 售前/商务 | 未签约不进需求接入 |
| 客户签字 | 项目经理 | 未签字不进开发 |
| 技术就绪检查 | 架构师/技术 Lead | 不达标不拆任务 |
| AI 评测 | AI 工程师 | Tier1 不达标不进测试 |
| 客户验收 | 项目经理 | 未验收不算交付完成 |

## 实例层（换项目只换这个）

项目特定的预算/技术红线/技术栈/性能验收线/风险防线 —— 全部放在**消费方项目根的 `project-context.md`**。本模块提供两份实例层占位模板：

- `templates/project-context模板.md` —— **面向 AI Agent 注入**的机读版（带 frontmatter）。复制到消费方项目根改名 `project-context.md`，或直接跑 BMAD `bmad-generate-project-context` 交互生成。
- `templates/项目宪法模板.md` —— **面向人读**的项目治理文档（一句话项目/预算模块边界/RACI 式团队规则）。
