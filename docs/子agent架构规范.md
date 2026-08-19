# delivery-flow 子 agent 架构规范

> 配套 ADR：[`0009-上下文与子agent边界.md`](adr/0009-上下文与子agent边界.md)。本规范是 ADR 的可执行版本，给 Skill 作者、子 agent prompt 作者、贡献者使用。

## 三层架构

```
主 agent      —— 只做路由和落盘，不持有原始资料
  ├─ 子 agent —— 压缩输入（读大文件 → 出结构化摘要）
  └─ CLI      —— 校验输出（读文件 → 出退出码）
```

主 agent = 任何 Claude Code / Codex / Cursor 等工具的主对话窗口。
子 agent = 通过 Task 工具派出去的独立 LLM 会话。
CLI = `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" <cmd> --root . --json`。

---

## 规则一：契约交接，禁止记忆交接

### 主 agent / Skill 的硬约束

1. **入口只读固定机器文件**。每个 Skill 的 step 1 必须列出本阶段必读文件列表（清单见 [`产物命名约定.md`](产物命名约定.md) 第一节）。
2. **禁止「上一轮讨论过 X」式输入**。即使对话里刚刚提到某个细节，跨阶段进入新 Skill 时必须重读对应文件。
3. **出口必须落盘**。Skill 跑完必须产出一份机器文件或人读产物文件，不允许只输出对话文字就声称「完成」。
4. **不允许主 agent 持有原始资料的全文**。当客户原始资料 > 100 KB，主 agent 必须先派子 agent 摘取（见规则二），主 agent 只读摘要。

### Skill 模板示例

每个 Skill 的 step 1 应长这样：

```markdown
## step 1: 重读本阶段入口契约

必读文件：
- `project-context.md`：红线 / 阈值 / 验收线
- `SPEC.md`：能力清单 / 约束 / 非目标 / 成功信号
- `04-需求分析/` 下本阶段必要产物

禁止读取：
- `00-项目资料/客户提供/` 原始文件（必须先跑摘取子 agent 见规则二）
- 其他阶段的人读产物（如 05-UX.md）

读取后立即跑 CLI 校验：
\`\`\`bash
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" check --root . --json
\`\`\`
退出码非 0 → 阻断并打印 findings。
```

---

## 规则二：子 agent 只用于压缩输入

### 允许派子 agent 的两个场景

#### 场景 1：客户原始资料摘取

**触发条件**：需要读 `00-项目资料/客户提供/` 下任意文件，且任意一份 > 50 KB。

**子 agent 契约**：

- 输入：`00-项目资料/客户提供/` 下文件路径列表
- 输出：写到 `00-项目资料/资料摘要.md` 的结构化摘要
  - 每条结论带原文定位（文件名 + 行号 / 段落 / 页码）
  - 字段：`原始证据 / 抽取结论 / 置信度（高/中/低） / 待人工确认项`
- 不做：主观判断、需求合并、改写原文

**主 agent 后续**：只读 `资料摘要.md`，禁止回读原始文件。

**禁止**：把原始文件路径列表整个复制到主 agent 上下文（这等价于让主 agent 自己读，没有意义）。

#### 场景 2：四层架构并行生成

**触发条件**：在 `06-架构/` 下需要产出业务/产品/技术/数据四份架构文档。

**子 agent 契约**：

- 输入：上游 SPEC.md + PRD.md + readiness-report.md（同一份，三份并行）
- 输出：分别写到 `06-架构/[01] 业务架构.md` / `[02] 产品架构.md` / `[03] 技术架构.md` / `[04] 数据架构.md`
- 不做：跨架构的一致性检查（这是主 agent 的工作）
- 不做：与下游 Story 的映射（这是 `delivery-feishu-sync` 的工作）

**主 agent 后续**：合并四份产物，跑一致性自检（命名一致性 / 引用一致性 / 与 readiness 对齐），发现冲突回到对应子 agent 修订。

### 禁止派子 agent 的场景

- 单阶段 Skill 执行（读 SPEC 写 PRD）——输入已经是机器文件，无需压缩；
- 串行多步流程（先 A 再 B）——派子 agent 只增加交接成本；
- 评测集生成 / 评测报告阅读——输入通常是 `SPEC.md` 的 success signal 段，< 5 KB；
- 验收报告生成——输入是 SPEC + 验收记录，机器文件已够；
- 任何需要「主 agent 反复介入」的场景——派子 agent 会丢上下文。

---

## 规则三：放行判断一律走 CLI 退出码

### 关卡 Skill 的硬约束

每个关卡 Skill（`delivery-client-gate` / `delivery-deal-gate` / `delivery-eval-loop` / `delivery-acceptance-gate`）的 step 1 必须：

```bash
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" check --root . --json
```

读退出码：

- `0`：继续本 Skill
- `1`：阻断，输出 findings 摘要给用户，不进入后续步骤
- `2`：阻断，向用户报告「输入解析错误」，建议修复相关文件

### 禁止的反模式

- ❌ 让主 agent「觉得」产物合格就放行；
- ❌ 让另一个子 agent「复核」子 agent 的产物；
- ❌ 跳过 `check` 直接进入下一个 Skill；
- ❌ 在 `check` 失败后继续往下走（无论 AI 是否「认为能解决」）。

---

## 检查清单（贡献者自检）

新增或修改 Skill 时，对照以下清单：

- [ ] step 1 列出了入口必读文件清单（机器文件 + 本阶段产物）
- [ ] step 1 明确禁止读取非本阶段文件
- [ ] 关卡 Skill 的 step 1 跑 `delivery check` 并读退出码
- [ ] 出口必产文件，写到固定机器文件或本阶段目录
- [ ] 不持有客户原始资料全文（> 50 KB 时走摘取子 agent）
- [ ] 不在串行场景派子 agent
- [ ] 不依赖对话记忆跨阶段传递信息

## 下一步（不在本规范范围）

- 资料摘取子 agent 的 prompt 模板（下一轮在真实项目验证）；
- 四层架构并行子 agent 的 prompt 模板（下一轮在真实项目验证）；
- 在 `delivery-bootstrap` 加一道门禁，检测 Skill 是否满足规则一/三的硬约束（脚本化检查）。