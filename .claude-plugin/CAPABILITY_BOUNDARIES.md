# delivery-flow 能力边界登记

> **作用**：把 ADR 0001「不重复造轮子」从 prose 升级为可机读的边界声明。
> 每个自建 skill 必须有一段三行固定格式（边界 / 标签 / 别名），校验脚本 `scripts/check_capability_overlap.py` 解析此文件判定能力重叠。
> **三分类标签**：
> - `UNIQUE` — 外部生态无等价能力，必须自建
> - `BOUNDARY_DECLARED` — 与外部 skill 有能力重叠，但已显式声明边界（引用 ADR / SKILL.md 中的分工段落）
> - `OVERLAP_REMOVED` — 历史上引用过外部 skill 但实际未用，已软改为「外部优先，否则本地」

---

### delivery-acceptance-gate
> 边界：乙方交付的客户验收关卡（出口关卡），与 client-gate 对称。BMAD 流程无客户验收环节。
> 标签：UNIQUE
> 别名：acceptance, sign-off, DoD, KPI, 验收

### delivery-bootstrap
> 边界：从零把新项目装到 delivery-flow 就绪状态的安装秘书。BMAD 安装步骤独立（`npx bmad-method install`），bootstrap 仅检测 `_bmad/` 是否存在。
> 标签：UNIQUE
> 别名：bootstrap, install, scaffold, L1, L2, L3, L4, 安装

### delivery-check
> 边界：只读检查交付项目的产物完整性、阶段前置条件和关卡证据。与 delivery-trace（追溯链）/ delivery-status（sprint 镜像）/ delivery-step-status（进度巡检）职责分明：check 跑「产物链静态校验」，trace 跑「SPEC-Story-飞书映射追溯」，status 跑「sprint 镜像聚合」。
> 标签：UNIQUE
> 别名：check, readiness, evidence, 产物完整性

### delivery-client-gate
> 边界：乙方交付的客户签字关卡（入口关卡）。BMAD 无客户签字环节，本模块从 SPEC.md 机读字段生成范围快照并取得签字。
> 标签：UNIQUE
> 别名：client gate, sign-off, scope snapshot, 客户签字, 入口

### delivery-crm-sync
> 边界：把商机/客户/合同推成飞书多维表格三张表的镜像脚本。lark-base 是数据落地工具，本模块是编排层（决定三张表的 schema 与同步幂等性）。
> 标签：BOUNDARY_DECLARED
> 别名：CRM, 商机, 客户, 合同, funnel, lark-base, Bitable

### delivery-deal-gate
> 边界：乙方售前的合同签约关卡。与 client-gate（范围签字）/ acceptance-gate（客户验收）对称，三关卡分别对应「签约 → 范围冻结 → 验收」三个签字时刻。
> 标签：UNIQUE
> 别名：deal gate, contract, 签约, 立项包

### delivery-dry-run
> 边界：预览推送飞书的任务计划但**不联网、不写文件**。与 feishu-sync（真实同步）形成 dry-run vs apply 配对；与 sprint-sync（状态镜像）职责不同。
> 标签：UNIQUE
> 别名：dry-run, preview, 预演, 推送计划

### delivery-eval-loop
> 边界：AI 应用（RAG/Agent）的业务侧忠实度/幻觉率/拒答正确率评测内循环。**显式区分** bmad-eval-runner（评 skill 本身是否胜过裸模型），本模块评「AI 应用回答业务问题时对不对」。
> 标签：UNIQUE
> 别名：eval, faithfulness, hallucination, RAG eval, 评测内循环

### delivery-feishu-sync
> 边界：把用户故事拆成飞书「清单>父任务>子任务」三层结构。lark-task 是底层 API，本模块是编排层（决定映射规则与幂等性）。
> 标签：BOUNDARY_DECLARED
> 别名：feishu, tasklist, SSOT, 任务同步, lark-task

### delivery-governance
> 边界：管理项目风险、问题、范围变更和决策登记。与 superpowers 的 `guard` / `freeze`（代码层保护）不同，本模块管**项目层**登记；与 delivery-plan（计划层）形成 plan vs governance 分工。
> 标签：BOUNDARY_DECLARED
> 别名：governance, risk, issue, change request, 治理登记

### delivery-onboarding
> 边界：交付流水线的总入口与角色路由器。BMAD onboarding 是开发者 onboarding（agent 培训），本模块是**交付项目** onboarding（识别角色 → 路由到当前该做的阶段）。`bmad-generate-project-context` 仅作为可选优先级，不阻断。
> 标签：OVERLAP_REMOVED
> 别名：onboarding, role router, 角色路由, 流水线入口

### delivery-phase-gate
> 边界：对项目计划中的单个建设阶段执行启动/readiness/开发/QA/验收五道门禁。与 client-gate（入口签字）/ deal-gate（签约）/ acceptance-gate（验收）三个**宏观**关卡不同，本模块管**单阶段内**的门禁。
> 标签：UNIQUE
> 别名：phase gate, readiness, QA gate, 阶段门禁

### delivery-plan
> 边界：管理项目计划层（阶段/里程碑/依赖/并行工作线/团队容量）。**不替代** project-progress.yaml，**不改变**飞书执行状态真源（ADR 0002「飞书 SSOT」）。
> 标签：BOUNDARY_DECLARED
> 别名：plan, milestone, WBS, capacity, 项目计划

### delivery-presales
> 边界：交付流水线最上游的售前编排/商机路由器。商机分析委托 BMAD（brainstorming / market-research / domain-research），CRM 数据落库委托 lark-base，本模块只补「乙方售前编排 + 商机编号生成 + Trace 根」层。
> 标签：UNIQUE
> 别名：presales, opportunity, 售前编排, 商机路由, OPP-

### delivery-project-layout
> 边界：项目布局助手，调 delivery layout CLI 做只读扫描并把方案念给人听。与 delivery-check 不同：check 跑产物链校验，layout 跑物理目录结构诊断。
> 标签：UNIQUE
> 别名：layout, 项目布局, 目录结构

### delivery-prototype-html
> 边界：从 SPEC.md + PRD + UX 文档生成整页可交互 HTML 原型。**显式分工**：bmad-ux 出 DESIGN/EXPERIENCE（视觉规范 + 2-4 屏静态 mock），本模块从这些产物读规范产出可点着看的完整演示。
> 标签：BOUNDARY_DECLARED
> 别名：prototype, HTML, interactive mock, 原型演示

### delivery-report
> 边界：聚合项目计划/流水线/治理登记/飞书只读镜像生成健康报告、阶段报告或管理摘要。**只读**，不写任何状态。
> 标签：UNIQUE
> 别名：report, summary, 健康报告, 阶段报告

### delivery-sprint-sync
> 边界：从飞书单向拉取执行状态刷新本地 sprint-status.yaml 镜像。**飞书是唯一写端，本地只读**（ADR 0002）。lark-task 是数据源，本模块是镜像同步层。
> 标签：BOUNDARY_DECLARED
> 别名：sprint, status mirror, sprint-status, 状态镜像

### delivery-status
> 边界：只读聚合本地 sprint-status.yaml 镜像并报告状态。三个「状态」skill 的分工：status 聚合镜像、step-status 翻译成自然语言、check 校验产物链完整性。
> 标签：UNIQUE
> 别名：status, mirror, 状态聚合

### delivery-step-status
> 边界：进度巡检/关卡快照，把 CLI 输出翻译成自然语言并支持撤回。让用户随时问「现在到哪了/下一步做什么/撤回上一步」，**避免 AI 跳过用户擅自推进**。
> 标签：UNIQUE
> 别名：step status, checkpoint, 进度巡检, 撤回

### delivery-trace
> 边界：只读检查 SPEC/Story/飞书映射/评测/验收之间的产物追溯链。**文件级**产物链完整性，不解析 SPEC Capability / Story AC 字段语义（避免与 client-gate 的机读字段重复）。
> 标签：UNIQUE
> 别名：trace, chain, provenance, 追溯链

---

## 三分类基线统计（2026-08-26 起每 PR 更新）

| 标签 | 数量 | 占比 |
|---|---|---|
| UNIQUE | 14 | 67% |
| BOUNDARY_DECLARED | 5 | 24% |
| OVERLAP_REMOVED | 1 | 5% |
| 总计 | 21 | 100% |

注：基线（plan 阶段估算）的 15 / 4 / 2 是粗数；落地后按实际三分类标签统计为准。校验脚本不依赖此表判定，只读每个段落的标签行。
