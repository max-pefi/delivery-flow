---

name: delivery-dry-run
description: 预览推送飞书的任务计划但不联网、不写文件。当用户说"预演推飞书""dry run""预览任务"时使用。
---
<execution_contract>
本 skill 是「逐步剧本」而非「待办清单」。任何 AI 在执行本 skill 时必须遵守：

1. **逐步汇报、逐步确认**：每次执行前先用一句话告诉用户"我要做 X，会调用 Y CLI"，
   等用户明确确认（说"继续"/"OK"/"确认"）后再执行。

2. **不确定就停下**：遇到参数不明、文件缺失等情况，必须问用户，不要替用户选默认值。

3. **如实报告、不替用户决策**：本 skill 是只读检查，只把 CLI 输出翻译成人话讲给用户，
   不修改文件、不调用飞书、不伪造"通过"或"已签"。
</execution_contract>

# 飞书任务预演（delivery-dry-run）

调用本地 `python "${CLAUDE_PLUGIN_ROOT}/delivery.py" dry-run --root . --json` 读取 `desired-tasks.json`（manifest）和 `_映射表.json`，输出 `create / update / skip / orphan / create_with_review` 五种操作的预演。

本 Skill 严格无副作用：不调用网络、不写入映射表、不创建或更新飞书任务、不刷新本地状态。

## 两种模式

### manifest-driven（正常）

manifest 存在且 schema 合规。基于 `manifest × mapping` 二维判定：

| 判定 | 含义 |
|---|---|
| `create` | manifest 有，mapping 无该 local_id → 首次推送 |
| `create_with_review` | mapping 有但无 `synced.content_hash`（旧格式残留）→ 建议人工确认是否需 update |
| `skip` | manifest 与 mapping 的 `synced.content_hash` 一致 → 三要素未变 |
| `update` | manifest 与 mapping 的 hash 不一致 → 三要素已变 |
| `orphan` | mapping 有，manifest 无该 local_id → 远端残留 |

`sprint-status.yaml` **退出** create/update 判定，仅作附加信息 `feishu_status` 展示，不参与汇总。

### degraded-consistency-check（降级）

manifest 缺失或 schema 错误时自动降级：**不输出 create**（不假装知道远端是否存在），只输出 `create_with_review`（每个 manifest 任务）+ `orphan`（mapping 残留），用于存量项目一致性预演。

降级模式下 `blocked_by` 必含「manifest 不可用」一条，提示先跑 `delivery-feishu-sync` 生成 manifest。

## 退出码

- `0`：门禁全过、manifest 齐全、可放心推送
- `1`：业务阻断（任意 `blocked_by` 项命中：客户确认非 pass / 四层架构缺一份 / readiness 非 pass / progress.tech_readiness != done / Story 三要素不全 / manifest 缺失降级 / 映射表缺失或结构错误）
- `2`：输入解析错误（manifest/mapping/progress 文件结构错误）

## 内容指纹

`content_hash` = `SHA-256(json.dumps({"what","dod","deliverable","spec_ref"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")))`。

字段顺序固定、`sort_keys=True`，确保跨进程稳定。`spec_ref` 为空字符串也参与计算（补写引用会触发 update）。