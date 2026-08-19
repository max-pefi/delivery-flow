# 运行时自动化边界

## 定位

`delivery-flow` 的运行时自动化只做本地确定性检查和预演，不建设完整流程平台。

```text
需求规格真源：本地 SPEC / PRD / Story
执行状态真源：飞书
本地 sprint-status.yaml：飞书单向拉取的只读镜像
本地 project-progress.yaml：流水线宏观阶段追踪（关卡 skill 自动写入）
```

## 机器文件位置

```text
需求规格真源：项目根 SPEC.md（兼容 04-需求分析/SPEC.md、_meta/SPEC.md）
执行状态真源：飞书
本地 sprint-status.yaml：项目根（兼容 07-开发/、_meta/）；飞书单向拉取的只读镜像
本地 project-progress.yaml：项目根（兼容 _meta/）；流水线宏观阶段追踪
本地 _映射表.json：项目根（兼容 07-开发/、_meta/）；飞书任务映射
```

`core.py` 的 `resolve_artifact()` 按 **根 → 阶段目录 → `_meta`** 顺序兼容读取。新项目统一写根，不自动迁移用户已有文件。

## 命令

在仓库根目录运行：

```bash
# 插件随仓库走，免安装。Skill 内统一调用：
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" check --root <项目根目录> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" trace --root <项目根目录> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" status --root <项目根目录> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" dry-run --root <项目根目录> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" progress --root <项目根目录> --json
python "${CLAUDE_PLUGIN_ROOT}/delivery.py" revert --root <项目根目录> [--step <stage_id>]  --json
```

也可直接调底层模块（仓库内调试用，需在仓库根目录运行）：

```bash
python -m scripts.delivery_flow.cli check --root <项目根目录>
```

增加 `--json` 输出机器可读 JSON。所有命令默认只读，不连接网络。

## 能力边界

- `check`：检查 SPEC、客户确认、技术就绪、Story、映射表和流程乱序；关卡证据使用 `pass / unknown / fail` 四态，模板或缺字段不算通过；
- `trace`：报告 商机 → SPEC → Story → 映射 → 评测/验收链路的缺项（存在商机编号 Trace 根时向上游延伸到售前）；
- `status`：只读聚合本地状态镜像（Story 粒度）；
- `dry-run`：预览飞书任务操作，明确输出 `create / update / skip / orphan / blocked`，不实际调用飞书或写入映射表；
- `progress`：显示流水线宏观阶段（读 `project-progress.yaml`，无则回退到产物扫描推断）。输出含 `next_action_suggestion`（含 `next_stage` / `should_ask_user` / `suggested_question` / `blocking_gates`），让 AI 知道现在该请示用户什么。
- `plan`：读取可选的 `project-plan.json`，输出业务阶段、依赖、可开始阶段、并行工作线和团队人数。
- `governance`：读取可选的 `project-governance.json`，输出风险、问题、变更和决策摘要。
- `report`：聚合流水线、计划、治理登记和飞书只读镜像；P0 风险、阻塞问题和待审批变更会返回 blocked。
- `revert`：撤回指定阶段的产物，是 CLI 唯一的写动作。无 `--step` 时回退 `project-progress.yaml` 的 `current_stage`。产物若有 `.draft.md` 同伴则删正式文件、保留草稿；否则改名归档为 `.reverted-{timestamp}`。`project-progress.yaml` 中该阶段 status 改回 `pending`，`current_stage` 回退到上一个 done 的阶段。这是配合"逐步确认 + 草稿态"契约的辅助命令，所有 skill 的 `<execution_contract>` 都要求产物先写 `<name>.draft.<ext>`、确认后用本命令清理。

程序不能代替客户签字、技术判断、Tier2 专家标注或客户验收。`unknown` 不折算为通过。

## 退出码

| 代码 | 含义 |
|---:|---|
| 0 | 通过或只有 warning |
| 1 | 存在流程阻断项 |
| 2 | 输入缺失、格式错误或 schema 问题 |
| 3 | 发生禁止的网络或写操作 |
| 4 | 内部异常 |

## 售前/商务的纳入方式

售前编排（`delivery-presales`）、签约关卡（`delivery-deal-gate`）与 CRM 同步（`delivery-crm-sync`）已作为流水线上游一环纳入，与其它 `delivery-*` skill 同为纯插件流程。它们对运行时的唯一要求是：`core.py` 识别 `opportunity`/`proposal`/`deal_gate` 三个宏观阶段、`trace_project` 在存在商机编号（Trace 根）时向上游延伸。**运行时本身仍只读**——商机/客户/合同数据的实际写入由 `lark-base` skill 承担，`core.py` 不联网、不写飞书，与需求侧 `delivery-feishu-sync` 的分工一致。

## 后续边界

真实飞书 API、写入适配器、增量同步和完整流程平台不属于当前运行时自动化范围（CRM 数据写入同样交由 lark skill，运行时只读不变）。
