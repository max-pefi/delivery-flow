---

name: delivery-prototype-html
description: 从 SPEC.md + PRD + UX 文档生成「整页可交互 HTML 演示原型」。产出物是离线可运行的完整原型（含导航/基础交互/模拟数据），用于客户签字前的演示验证和研发 UI 参考。与 bmad-ux 的静态 mock（2-4 屏）互补：bmad-ux 定视觉调子，本 skill 做全量可交互演示。当用户说"做 HTML 原型"、"原型演示"、"交互原型"、"可点击原型"、"交付原型"时使用。
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

# HTML 演示原型（delivery-prototype-html）

**目标**：在 PRD + UX 设计完成之后、客户签字之前，产出**整页可交互的 HTML 演示原型**——让客户/领导在没写代码前就能点着看、走通流程，降低确认成本；同时给研发提供比 ASCII 线框更精确的 UI 参考。

**角色**：你是原型工程师。不写后端，只做能跑的前端演示。

## 与 bmad-ux 的分工

| 维度 | bmad-ux | delivery-prototype-html（本 skill） |
|---|---|---|
| 视觉定调 | ✅ DESIGN.md（颜色/字体/圆角/组件规范） | ✅ 从 DESIGN.md 提取视觉变量 |
| 交互规范 | ✅ EXPERIENCE.md（信息架构/状态/动效/旅程） | ✅ 从 EXPERIENCE.md 提取交互逻辑 |
| 线框 | ✅ Excalidraw 线框 | ✅ 作为页面结构依据 |
| HTML 产出 | 2-4 屏**静态** mock（离线无 JS） | **全页面可交互**原型（有 JS、可导航、可点击） |
| 定位 | 视觉语言定稿 | 交互流程验证 + 客户演示 |
| 产品负责人 | bmad-ux 设计产出交付物 | 本 skill 的输入来源 |

**不替代 bmad-ux**：如果还没做过 bmad-ux，先用 bmad-ux 产出 DESIGN/EXPERIENCE，再进本 skill。本 skill 从 DESIGN/EXPERIENCE 读视觉和交互规范，**不是从零设计**。

## 输入

- `SPEC.md`（机读契约，功能范围 + Success signal 验收标准）
- PRD（`*prd*.md`，功能细节 + 字段定义 + 接口描述）
- `DESIGN.md` + `EXPERIENCE.md`（bmad-ux 产出，视觉 + 交互规范）
- 线框图（Excalidraw 或 ASCII，页面结构依据）
- `project-context.md`（红线 / 产物路径约定）

## 输出

```
prototype/
├── index.html          # 入口页
├── app.js              # 页面路由 + 交互逻辑
├── data.js             # 模拟数据（固定 mock 数据，不调真实 API）
├── styles.css          # 从 DESIGN.md 提取的视觉变量
└── pages/              # 每个页面一个子模块
    ├── page-a.js
    ├── page-b.js
    └── ...
```

**输出目录路径**：优先读 `project-context.md` 中的产物路径约定；未指定则默认 `prototype/`（与 planning_artifacts 同级）。

## 质量标准（放行门槛）

- ✅ **离线可运行**：双击 `index.html` 能在浏览器打开，不依赖后端 / 不联网
- ✅ **全页面可导航**：每个页面都能从菜单/按钮进入，不是孤立页面
- ✅ **核心交互可点跑**：按钮点击 / 表单填写 / 列表翻页等核心路径有 JS 响应（用模拟数据）
- ✅ **视觉对齐 DESIGN.md**：颜色 / 字体 / 圆角 / 间距从 DESIGN.md 提取，不自由发挥
- ✅ **页面数量**：覆盖 SPEC.md Capabilities 的每个功能入口 + 关键交互页面（通常 6-12 页，视产品复杂度）
- ❌ **不做的事**：真实 API 调用 / 后端逻辑 / 登录鉴权 / 数据持久化 / 响应式适配（原型阶段桌面优先）

## 依赖

- SPEC.md + PRD + DESIGN.md + EXPERIENCE.md（上阶段产物）
- `project-context.md`（产物路径约定）

## 何时用

- **交付阶段（正式）**：PRD + bmad-ux（DESIGN/EXPERIENCE）已完成，进入客户签字之前
- **售前阶段（演示）**：客户签约前想看效果，需要快速生成演示原型提升赢率
- 客户/领导需要"点着看"的演示材料，而非文档
- 研发需要比线框更精确的 UI 参考

## 演示模式分支

本 skill 支持两种模式，根据是否有 DESIGN.md 自动判断：

| 维度 | 交付模式（正式） | 售前模式（演示） |
|------|----------------|----------------|
| 触发时机 | PRD + UX 完成后 | 方案报价阶段，客户想看效果 |
| 前置条件 | SPEC.md + PRD + DESIGN.md + EXPERIENCE.md | SPEC.md 或 商机档案 + 技术方案 |
| 视觉来源 | 从 DESIGN.md 提取 CSS 变量 | 使用默认品牌视觉变量（见下） |
| 页面数量 | 覆盖 SPEC.md 全部 Capabilities（6-12 页） | 核心流程 3-5 页，快速演示 |
| 输出路径 | `05-设计/演示原型/` | `02-方案报价/演示原型/` |
| 标注 | 无 | 原型首页标注"售前演示用，交付阶段基于正式 UX 重新生成" |
| 质量标准 | 全页面可导航 + 核心交互可点跑 | 核心流程可走通即可 |

### 售前模式默认视觉变量

当 DESIGN.md 不存在时，使用以下默认 CSS 变量（不自由发挥）：

```css
:root {
  --color-primary: #1890ff;      /* 主色：蓝色 */
  --color-success: #52c41a;      /* 成功：绿色 */
  --color-warning: #faad14;      /* 警告：橙色 */
  --color-error: #ff4d4f;        /* 错误：红色 */
  --color-text: #333333;         /* 正文：深灰 */
  --color-text-secondary: #666666; /* 次要文字 */
  --color-bg: #f5f5f5;           /* 背景：浅灰 */
  --color-border: #d9d9d9;       /* 边框 */
  --color-white: #ffffff;        /* 白色 */
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-size-base: 14px;
  --radius-base: 6px;
  --spacing-unit: 8px;
}
```

> **注意**：售前模式生成的原型仅用于商务演示，**不可替代交付阶段的正式原型**。正式原型必须在 UX 完成后重新生成。

## 工作流

<step n="1" goal="判定演示模式">

<action>检查是否存在 DESIGN.md + EXPERIENCE.md：</action>
<action if="存在">→ **交付模式（正式）**：读 SPEC.md + PRD + DESIGN.md + EXPERIENCE.md 作为输入。</action>
<action if="不存在">→ **售前模式（演示）**：读 SPEC.md（如有）或 商机档案 + 技术方案，使用默认视觉变量。在原型首页标注"售前演示用，交付阶段基于正式 UX 重新生成"。</action>
<action>读 `project-context.md`，确认原型产物输出路径。售前模式默认输出到 `02-方案报价/演示原型/`。</action>

</step>

<step n="2" goal="设计原型结构">

<action>从 EXPERIENCE.md 的信息架构和 SPEC.md 的 Capabilities，列出「页面清单」：每个页面叫什么、URL path、从哪进、可点什么。</action>

<action>为每个页面定义「模拟数据结构」：基于 PRD 的字段定义，产出 data.js 里的 mock 数据。</action>

<action>列出「核心交互路径」：从 EXPERIENCE.md 的用户旅程提取 2-3 条最关键的端到端路径（如：登录 → 进入主页 → 创建一条记录 → 查看列表）。</action>

</step>

<step n="2.5" goal="售前模式：仅覆盖核心流程">

<action mode="售前">从技术方案或商机档案中提取 3-5 个核心功能页面，不追求全覆盖。</action>
<action mode="售前">使用默认视觉变量（见"售前模式默认视觉变量"），不读 DESIGN.md。</action>
<action mode="售前">核心交互路径精简为 1-2 条最短演示路径。</action>

</step>

<step n="3" goal="产出 HTML 原型">

<action>写 `styles.css`：从 DESIGN.md 提取视觉变量（交付模式），或使用默认视觉变量（售前模式），定义基础组件样式（按钮、输入框、卡片、导航栏）。</action>

<action>写 `index.html` + `app.js`：实现页面路由（hash 路由或简单 show/hide）、每个页面的 HTML 结构、核心交互的 JS 逻辑。</action>

<action>写 `data.js`：基于 PRD 字段定义的 mock 数据，按页面模块组织。</action>

<action>每个页面按需拆 `pages/page-{name}.js`，保持 `app.js` 不超过 300 行。</action>

<action mode="售前">在 `index.html` 首页添加标注："本原型为售前演示用，交付阶段将基于正式 UX 设计重新生成。"</action>

</step>

<step n="4" goal="验证">

<action>自查：在浏览器打开 `index.html`，走通 2-3 条核心交互路径，确认能点、能跳、数据能展示。</action>

<action>检查清单：离线可运行 ✅ / 全页面可导航 ✅ / 核心交互可点跑 ✅ / 视觉对齐 DESIGN.md ✅ / 不调真实 API ✅</action>

</step>

<step n="5" goal="交付">

<action>输出原型目录到约定路径：交付模式 → `05-设计/演示原型/`；售前模式 → `02-方案报价/演示原型/`。告知用户原型位置和打开方式（双击 index.html）。</action>

<action>**写入进度**：更新 `project-progress.yaml`，将 `prototype` 阶段标记为 `done` + `completed_at`，`current_stage` 更新为 `client_gate`。**若文件不存在，不要自己复制模板**——告诉用户先跑 `delivery-bootstrap` 完成 L4 初始化。</action>

<action>建议：原型完成后走 `delivery-client-gate` 的 A 入口（全新确认），附上原型目录给客户走查。</action>

<action mode="售前">提醒：售前原型不替代交付阶段正式原型，签约后需在 UX 完成后重新生成。</action>

</step>

</workflow>

## 给 LLM 的编码约束

- 用原生 HTML/CSS/JS（不依赖 React/Vue 等框架），保证离线可运行
- CSS 变量从 DESIGN.md 提取，命名规范：`--color-{name}` / `--font-{name}` / `--radius-{name}` / `--spacing-{name}`
- `data.js` 用固定 mock 数据，不调 API、不 fetch
- 交互逻辑用事件监听（addEventListener），不用框架的事件系统
- 每个页面不超过 200 行 HTML + 100 行 JS；超了就拆子模块
- 注释用中文，关键交互点加简短说明
