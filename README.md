# delivery-flow — 交付型敏捷 AI 研发工作流

> 一套**可安装、可复制、能脱离个人独立运转**的团队交付流水线。
> 任何角色（产品经理 / 项目经理 / 研发）装上本插件后，全员按同一条流水线走。
> 本仓库是**通用层**，不含任何具体项目内容；项目特定约束只放在消费方项目根的 `project-context.md`。

## 它解决什么

需求接入 → BMAD 分析立项 → SPEC / PRD / UX → HTML 原型 → **客户签字** → 架构 / 技术就绪 → Story 拆解进飞书 → Superpowers 研发 → **AI 评测** → 测试 → **客户验收**。全程有依据、有关卡。`project-progress.yaml` 持久化记录当前所处阶段，由关卡 skill 自动写入。

## 标准模式（本模块的定位）

**BMAD 的产品与规划能力全开**：分析研究、SPEC、PRD、UX、架构、技术就绪检查和 Story 拆解都优先复用 BMAD。**Superpowers** 负责研发阶段的 TDD、调试和验证。飞书是执行状态唯一写端，本地 `sprint-status.yaml` 仅由 `delivery-sprint-sync` 从飞书单向拉取，作为只读镜像。

本仓库提供的是 Markdown 工作流规范、模板和角色路由，不是带运行时代码的项目管理系统；飞书 API、评测执行器和自动门禁依赖外部技能或人工执行。

## 分层设计（只建市面上没有的）

```
Layer0 基座（安装，不自建）
  ├─ BMAD-METHOD v6  文档工具箱：角色 agent + PRD/story 模板 + project-context 生成
  └─ Superpowers      研发内功：TDD / 系统化调试 / 写计划 / 验证

Layer1 本模块差异化交付能力（补 BMAD 未覆盖的业务关卡与编排）
  ├─ delivery-client-gate      入口：客户签字关卡（未签字不进开发）
  ├─ delivery-feishu-sync      拆任务：故事 → 飞书「清单>父任务>子任务」，飞书=执行真源
  ├─ delivery-sprint-sync       状态镜像：飞书 → 本地 sprint-status.yaml（只读）
  ├─ delivery-eval-loop        AI 评测内循环（Tier1 达阈值放行；Tier2 需专家）
  ├─ delivery-acceptance-gate  出口：客户验收关卡（对签字范围核 KPI/DoD）
  └─ delivery-prototype-html    规划编排：将 BMAD UX 产物转为可交互 HTML 演示原型

Layer2 上手编排（“装上就跑”入口）
  ├─ delivery-bootstrap    从零安装：环境检查 → 注册插件 → 装依赖 → 创建初始文件
  └─ delivery-onboarding   识别角色 → 确保基座就位 → 发放角色依据 → 路由到对应阶段
```

## 与 BMAD 的分工（不重造轮子）

| 能力 | 由谁提供 |
|---|---|
| 角色 agent（分析/PM/UX 等）+ SPEC / PRD / Story 模板 | BMAD |
| 项目宪法（AI 必守规则）| BMAD `generate-project-context` → `project-context.md` |
| 研发内功（TDD/调试/验证）| Superpowers |
| **客户签字关卡（入口）** | **本模块 delivery-client-gate** |
| **飞书任务 SSOT 同步（飞书=执行真源）** | **本模块 delivery-feishu-sync**（编排 lark-* skills）|
| **飞书状态本地只读镜像** | **本模块 delivery-sprint-sync** |
| **HTML 交互原型编排** | **本模块 delivery-prototype-html**（读取 bmad-ux 产物）|
| **AI 输出评测内循环** | **本模块 delivery-eval-loop** |
| **客户验收关卡（出口）** | **本模块 delivery-acceptance-gate** |
| **从零安装引导** | **本模块 delivery-bootstrap** |

> BMAD 的产品与规划能力全开；`sprint-status.yaml` 不作为本地写端，仅由 `delivery-sprint-sync` 从飞书单向刷新。

## 安装

> **最快方式**：在 Claude Code 中说 **"装 delivery-flow"** 或 **"bootstrap"**，`delivery-flow` 会自动引导完成环境搭建，无需手动查阅文档。

📖 **快速安装指南** → 详见 [`安装指南.md`](安装指南.md)。含 Claude Code 一键安装和其他工具（Codex / Cursor / Windsurf）分步指引。

📖 **分步安装与上手指引** → 详见 [`docs/安装与上手.md`](docs/安装与上手.md)。含安装命令、角色分工表、端到端示例流程。

🔧 **非 Claude Code 工具安装** → 详见 [`docs/跨工具安装指南.md`](docs/跨工具安装指南.md)。Codex / Cursor / Windsurf 各有对应配置步骤。

### 快速开始（按工具）

**Claude Code**：在你的项目目录打开 Claude Code，说"装 delivery-flow"，自动完成全部安装。

**Codex / Cursor / Windsurf**：
```bash
# 1. clone 本仓库
git clone https://github.com/fredsimas782-jpg/delivery-flow.git

# 2. 进入你的项目，安装 BMAD
cd <你的项目>
npx bmad-method install

# 3. 让 AI 帮你创建配置文件（参考 docs/跨工具安装指南.md）
```

## 从零开始：完整使用场景

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

**关键节点（硬门禁，不可跳过）**：

| 节点 | 谁触发 | 说明 |
|---|---|---|
| 客户签字 | 项目经理 | 未签字不进开发 |
| 技术就绪检查 | 架构师/技术 Lead | 不达标不拆任务 |
| AI 评测 | AI 工程师 | Tier1 不达标不进测试 |
| 客户验收 | 项目经理 | 未验收不算交付完成 |

## 实例层（换项目只换这个）

项目特定的预算/技术红线/技术栈/性能验收线/风险防线 —— 全部放在**消费方项目根的 `project-context.md`**。本模块提供两份实例层占位模板：

- `templates/project-context模板.md` —— **面向 AI Agent 注入**的机读版（带 frontmatter）。复制到消费方项目根改名 `project-context.md`，或直接跑 BMAD `bmad-generate-project-context` 交互生成。
- `templates/项目宪法模板.md` —— **面向人读**的项目治理文档（一句话项目/预算模块边界/RACI 式团队规则）。
