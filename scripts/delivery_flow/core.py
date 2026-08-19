"""交付产物读取、校验和追溯的纯本地实现。

机器文件路径解析（阶段二统一）：
- 推荐位置：项目根固定文件
- 兼容顺序：项目根 → 阶段目录 → `_meta` 旧路径
- 新写入统一落项目根，不自动迁移用户已有文件
- 所有产物匹配自动排除 `skills/`、`_bmad/`、`.agents/`、`.claude/`、模板/示范
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SPEC_FIELDS = ("Why", "Capabilities", "Constraints", "Non-goals", "Success signal")
STATUS_MAP = {
    "待开发": "planned",
    "开发中": "in_progress",
    "测试中": "in_review",
    "已上线": "done",
    "缺陷": "blocked",
    "优化": "in_progress",
}

# 路径排除段：这些目录是 skill/基座/工具资产，不是真实交付产物
EXCLUDED_PATH_PARTS = ("/skills/", "/_bmad/", "/.agents/", "/.claude/", "/.cursor/", "/.windsurf/")
EXCLUDED_NAME_SUBSTRINGS = ("template", "模板", "示范")


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """读取 JSON；错误作为数据返回，避免 CLI 直接崩溃。"""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "文件不存在"
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def markdown_has_heading(path: Path, heading: str) -> bool:
    """检查 Markdown 是否存在指定标题或字段。"""
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(rf"^\s*#+\s*{re.escape(heading)}\s*:?[ \t]*$", text, re.MULTILINE | re.IGNORECASE))


def _is_excluded(path: Path) -> bool:
    """判断路径是否位于 skill/基座/工具目录或本身就是模板——必须从产物匹配中排除。"""
    posix = path.as_posix()
    if any(part in posix for part in EXCLUDED_PATH_PARTS):
        return True
    name_lower = path.name.lower()
    if any(sub in name_lower for sub in ("template",)):
        return True
    if any(sub in path.name for sub in ("模板", "示范")):
        return True
    return False


def find_first(root: Path, patterns: tuple[str, ...]) -> Path | None:
    """按稳定顺序寻找第一个真实项目产物。

    自动排除 skill/基座/工具目录以及模板/示范文件。
    """
    for pattern in patterns:
        matches = sorted(root.glob(pattern))
        for path in matches:
            if path.is_file() and not _is_excluded(path):
                return path
    return None


def find_all(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    """收集所有未被排除的真实产物路径，按路径排序便于稳定输出。"""
    results: list[Path] = []
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and not _is_excluded(path) and path not in results:
                results.append(path)
    return results


# 机器文件 → 推荐阶段目录提示（兼容旧布局）
STAGE_DIR_HINTS = {
    "SPEC.md": ("04-需求分析", "06-架构"),
    "project-progress.yaml": ("_meta",),
    "sprint-status.yaml": ("07-开发", "_meta"),
    "_映射表.json": ("07-开发", "_meta"),
    "_商机映射表.json": ("_meta",),
    "PRD.md": ("04-需求分析",),
    "UX.md": ("05-设计",),
    "desired-tasks.json": ("07-开发", "_meta"),
    "project-plan.json": ("_meta",),
    "project-governance.json": ("_meta",),
}


def resolve_artifact(root: Path, fixed_name: str, stage_hints: tuple[str, ...] | None = None) -> tuple[Path | None, str]:
    """按兼容顺序解析机器文件位置：项目根 → 阶段目录 → `_meta` 旧路径。

    返回 (命中路径或 None, 命中来源 root|stage|legacy|missing|ambiguous)。
    新写入统一落项目根，不自动迁移用户已有文件。
    阶段目录支持前缀 glob（兼容 `[04] 04-需求分析/` 这种带序号/emoji 的命名），
    命中多个目录 → ambiguous。
    """
    hints = stage_hints if stage_hints is not None else STAGE_DIR_HINTS.get(fixed_name, ())

    # 1. 项目根固定路径（推荐位置）
    candidate = root / fixed_name
    if candidate.is_file() and not _is_excluded(candidate):
        return candidate, "root"

    # 2. 阶段目录（glob 兼容带前缀/emoji 的目录名）
    for hint in hints:
        if hint == "_meta":
            continue
        matches = sorted(p for p in root.glob(f"*{hint}") if p.is_dir() and not _is_excluded(p))
        if len(matches) > 1:
            return None, "ambiguous"
        if matches:
            candidate = matches[0] / fixed_name
            if candidate.is_file() and not _is_excluded(candidate):
                return candidate, "stage"

    # 3. `_meta` 旧路径（兼容 1.x 布局）
    candidate = root / "_meta" / fixed_name
    if candidate.is_file() and not _is_excluded(candidate):
        return candidate, "legacy"

    return None, "missing"


def parse_mapping_subtask(value: Any) -> tuple[str | None, dict[str, Any] | None]:
    """解析映射表 subtasks 的 value：新格式 = {task_id, synced?}，旧格式 = 裸字符串。

    返回 (task_id, synced)。task_id 为空表示结构错误。
    """
    if isinstance(value, str):
        return (value or None), None
    if isinstance(value, dict):
        tid = value.get("task_id")
        synced = value.get("synced") if isinstance(value.get("synced"), dict) else None
        return (tid if isinstance(tid, str) and tid.strip() else None), synced
    return None, None


def mapping_ids(data: dict[str, Any] | None) -> tuple[set[str], list[str]]:
    """提取三级映射中的本地子任务 ID 和结构错误。"""
    ids: set[str] = set()
    errors: list[str] = []
    if not isinstance(data, dict):
        return ids, ["映射表不是 JSON 对象"]
    tasklists = data.get("tasklists")
    if not isinstance(tasklists, dict):
        return ids, ["缺少 tasklists 对象"]
    for list_name, tasklist in tasklists.items():
        if not isinstance(tasklist, dict):
            errors.append(f"清单 {list_name} 不是对象")
            continue
        if not tasklist.get("guid"):
            errors.append(f"清单 {list_name} 缺少 guid")
        parents = tasklist.get("parent_tasks", {})
        if not isinstance(parents, dict):
            errors.append(f"清单 {list_name} 的 parent_tasks 不是对象")
            continue
        for parent_name, parent in parents.items():
            if not isinstance(parent, dict):
                errors.append(f"父任务 {parent_name} 不是对象")
                continue
            subtasks = parent.get("subtasks", {})
            if not isinstance(subtasks, dict):
                errors.append(f"父任务 {parent_name} 的 subtasks 不是对象")
                continue
            for local_id, value in subtasks.items():
                if local_id in ids:
                    errors.append(f"本地子任务 ID 重复：{local_id}")
                ids.add(local_id)
                tid, _synced = parse_mapping_subtask(value)
                if not tid:
                    errors.append(f"子任务 {local_id} 缺少飞书 task_id")
    return ids, errors


def mapping_guids(data: dict[str, Any] | None) -> list[str]:
    """验证映射表 schema 要求的 GUID 完整性。

    检查：清单 GUID、父任务 GUID、子任务 GUID、非空 task ID。
    返回错误列表，空列表表示通过。
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["映射表不是 JSON 对象"]
    tasklists = data.get("tasklists")
    if not isinstance(tasklists, dict):
        return ["缺少 tasklists 对象"]
    for list_name, tasklist in tasklists.items():
        if not isinstance(tasklist, dict):
            errors.append(f"清单 {list_name} 不是对象")
            continue
        if not tasklist.get("guid"):
            errors.append(f"清单 {list_name} 缺少 guid")
        parents = tasklist.get("parent_tasks", {})
        if not isinstance(parents, dict):
            errors.append(f"清单 {list_name} 的 parent_tasks 不是对象")
            continue
        for parent_name, parent in parents.items():
            if not isinstance(parent, dict):
                errors.append(f"父任务 {parent_name} 不是对象")
                continue
            if not parent.get("guid"):
                errors.append(f"父任务 {parent_name} 缺少 guid")
            subtasks = parent.get("subtasks", {})
            if not isinstance(subtasks, dict):
                errors.append(f"父任务 {parent_name} 的 subtasks 不是对象")
                continue
            for local_id, value in subtasks.items():
                tid, _synced = parse_mapping_subtask(value)
                if not tid:
                    errors.append(f"子任务 {local_id} 缺少飞书 task_id")
    return errors


# 模板/占位符标记：含这些 token 的文件不能算 pass
PLACEHOLDER_TOKENS = (
    "{{", "}}", "TODO", "TBD", "待填", "占位", "_PLACEHOLDER_",
    "<填写", "<YYYY-MM-DD", "____", "☐",
)
# 明确放行/通过的关键词（按出现频度排序，先 negative 后 positive 的兜底已移到 _normalize_decision）
DECISION_POSITIVE = ("放行", "已签字", "approved", "confirmed", "pass", "通过")
# 明确阻断/不通过的关键词
DECISION_NEGATIVE = ("阻断", "不通过", "不放行", "拒绝", "rejected", "failed")
# 「有条件」关卡：约束项未消解前不得扩大研发范围，禁止视为 pass
DECISION_CONDITIONAL = ("有条件放行", "有条件通过", "conditional")


def _is_placeholder_file(path: Path) -> bool:
    """判断文件是否是模板/占位符（不能算通过）。

    触发条件：
    - 文件不存在或不可读
    - 只有标题/空行
    - 含 {{ }} / TODO / TBD / 待填 / 占位 等占位符 token
    """
    if not path.is_file():
        return True
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return True
    # 空文件或只有标题/注释（不足两行正文）
    body_lines = [
        l for l in text.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if len(body_lines) < 2:
        return True
    if any(token in text for token in PLACEHOLDER_TOKENS):
        return True
    return False


def _extract_field(text: str, *patterns: str) -> str:
    r"""从 Markdown 文本中按正则提取字段值。

    去除首尾反引号和尖括号，避免模板里 `` `值` `` 形式被原样带回。
    """
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip().strip("`").strip().strip("<>").strip()
    return ""


def _decision_value(text: str) -> str:
    """从文本中识别放行结论（全文搜索，仅 parse_readiness 使用宽松语义）。

    返回 'pass' / 'conditional' / 'fail' / ''（未识别）。
    判定顺序：conditional → negative → positive（长串优先，避免「有条件放行」误判 pass）。
    """
    if any(tok in text for tok in DECISION_CONDITIONAL):
        return "conditional"
    if any(tok in text for tok in DECISION_NEGATIVE):
        return "fail"
    if any(tok in text for tok in DECISION_POSITIVE):
        return "pass"
    return ""


def _field_decision(text: str, *field_names: str) -> str:
    r"""只读命名的结论字段，不做全文语义猜测。

    支持两种 Markdown 形态：
    - 行首字段：^\s*字段名\s*[：:]\s*(.+?)\s*$
    - 表格行：  ^\s*\|\s*字段名\s*\|\s*(.+?)\s*\|

    返回首个命中的字段值（去除多余反引号/尖括号/引号 trim）。
    未命中返回空串。
    """
    for field in field_names:
        m = re.search(rf"^\s*{re.escape(field)}\s*[：:]\s*(.+?)\s*$", text, re.MULTILINE)
        if m:
            return m.group(1).strip().strip('"').strip("'").strip("`").strip().strip("<>").strip()
        m = re.search(rf"^\s*\|\s*{re.escape(field)}\s*\|\s*(.+?)\s*\|", text, re.MULTILINE)
        if m:
            return m.group(1).strip().strip('"').strip("'").strip("`").strip().strip("<>").strip()
    return ""


def _normalize_decision(raw: str) -> str:
    """归一化关卡结论字段值为四态之一：pass / conditional / fail / unknown。

    判定顺序：conditional → fail → pass → unknown。
    conditional 必须最先判（「有条件放行」含「放行」字面量，长串优先）。
    """
    if not raw:
        return "unknown"
    cleaned = raw.strip().strip('"').strip("'").strip("`").strip().strip("<>").strip()
    if not cleaned:
        return "unknown"
    low = cleaned.lower()

    # 1) conditional（长串优先）
    for tok in DECISION_CONDITIONAL:
        if tok in cleaned or tok in low:
            return "conditional"

    # 2) negative
    for tok in DECISION_NEGATIVE:
        if tok in cleaned or tok in low:
            return "fail"

    # 3) positive
    for tok in DECISION_POSITIVE:
        if tok in cleaned or tok in low:
            return "pass"

    return "unknown"


def parse_confirmation(path: Path) -> dict[str, Any]:
    """解析客户确认记录。

    返回字段：has_decision / decision / method / confirmed_at / representative / is_placeholder。
    占位符/空文件：has_decision=False, is_placeholder=True。

    decision 只读「放行结论」命名字段，三态归一化（pass/conditional/fail/unknown）。
    正文说明段出现「不放行」等反向词不影响判定，避免误判。
    """
    is_placeholder = _is_placeholder_file(path)
    if is_placeholder:
        return {
            "is_placeholder": True,
            "has_decision": False,
            "decision": "",
            "method": "",
            "confirmed_at": "",
            "representative": "",
        }
    text = path.read_text(encoding="utf-8")
    raw = _field_decision(text, "放行结论")
    decision = _normalize_decision(raw)
    return {
        "is_placeholder": False,
        "has_decision": decision == "pass",
        "decision": decision,
        "method": _extract_field(text, r"确认方式[:：]\s*(.+?)(?:\n|$)", r"签字方式[:：]\s*(.+?)(?:\n|$)"),
        "confirmed_at": _extract_field(text, r"确认日期\s*[：:]\s*(\d{4}-\d{2}-\d{2})", r"确认时间\s*[：:]\s*(\d{4}-\d{2}-\d{2})", r"\|\s*确认日期\s*\|\s*`?(\d{4}-\d{2}-\d{2})`?"),
        "representative": _extract_field(text, r"客户代表[:：]\s*(.+?)(?:\n|$)"),
    }


def parse_readiness(path: Path) -> dict[str, Any]:
    """解析技术就绪报告。返回 conclusion: pass/conditional/pending/fail/placeholder。

    仍走全文搜索（readiness 报告无固定模板，不在本轮统一）。
    """
    if _is_placeholder_file(path):
        return {"is_placeholder": True, "conclusion": "placeholder"}
    text = path.read_text(encoding="utf-8")
    decision = _decision_value(text)
    if decision == "pass":
        conclusion = "pass"
    elif decision == "conditional":
        conclusion = "conditional"
    elif decision == "fail":
        conclusion = "fail"
    elif "待确认" in text or "pending" in text.lower():
        conclusion = "pending"
    else:
        conclusion = "unknown"
    return {
        "is_placeholder": False,
        "conclusion": conclusion,
        "summary": _extract_field(text, r"##\s*(?:结论|Conclusion)[：:]?\s*(.+?)(?:\n|$)"),
    }


def parse_acceptance(path: Path) -> dict[str, Any]:
    """解析验收报告。返回 conclusion + 客户确认方式/时间。

    decision 只读「验收结论」命名字段，三态归一化。
    """
    if _is_placeholder_file(path):
        return {"is_placeholder": True, "conclusion": "placeholder"}
    text = path.read_text(encoding="utf-8")
    raw = _field_decision(text, "验收结论")
    decision = _normalize_decision(raw)
    return {
        "is_placeholder": False,
        "conclusion": decision,
        "method": _extract_field(text, r"客户确认方式\s*[：:]\s*(.+?)(?:\n|$)", r"确认方式\s*[：:]\s*(.+?)(?:\n|$)", r"\|\s*客户确认方式\s*\|\s*(.+?)(?:\n|$)"),
        "confirmed_at": _extract_field(text, r"客户确认时间\s*[：:]\s*(\d{4}-\d{2}-\d{2})", r"确认时间\s*[：:]\s*(\d{4}-\d{2}-\d{2})", r"验收日期\s*[：:]\s*(\d{4}-\d{2}-\d{2})", r"\|\s*验收日期\s*\|\s*`?(\d{4}-\d{2}-\d{2})`?"),
    }


def parse_evaluation(path: Path) -> dict[str, Any]:
    """解析评测报告。必须包含 Tier1 实测 + 阈值 + 放行结论才能 pass。

    decision 只读「评测结论」命名字段（模板当前缺失，已在批次一补加）。
    """
    if _is_placeholder_file(path):
        return {"is_placeholder": True, "conclusion": "placeholder"}
    text = path.read_text(encoding="utf-8")
    has_tier1 = bool(re.search(r"Tier1|第一级|自动.*评测", text))
    has_threshold = bool(re.search(r"阈值|threshold|达标线|>=?\s*\d", text))
    raw = _field_decision(text, "评测结论", "放行结论")
    decision = _normalize_decision(raw)
    if decision == "pass" and has_tier1 and has_threshold:
        conclusion = "pass"
    elif decision == "conditional":
        conclusion = "conditional"
    elif decision == "fail":
        conclusion = "fail"
    elif not (has_tier1 and has_threshold):
        conclusion = "incomplete"
    else:
        conclusion = "unknown"
    return {
        "is_placeholder": False,
        "conclusion": conclusion,
        "has_tier1": has_tier1,
        "has_threshold": has_threshold,
        "summary": _extract_field(text, r"##\s*(?:结论|放行结论)[：:]?\s*(.+?)(?:\n|$)"),
    }


def parse_story(path: Path) -> dict[str, Any]:
    """解析 Story 文档，验证三要素：做什么 / DoD·AC / 交付物。

    返回 {has_goal, has_ac, has_deliverable, is_placeholder}。
    """
    if _is_placeholder_file(path):
        return {"is_placeholder": True, "has_goal": False, "has_ac": False, "has_deliverable": False}
    text = path.read_text(encoding="utf-8")
    has_goal = bool(re.search(r"##\s*做什么|##\s*目标|##\s*Goal|##\s*Story", text))
    has_ac = bool(re.search(r"##\s*(?:DoD|验收标准|AC|完成定义)|##\s*Acceptance", text))
    has_deliverable = bool(re.search(r"##\s*(?:交付物|Deliverable|交付)", text))
    return {
        "is_placeholder": False,
        "has_goal": has_goal,
        "has_ac": has_ac,
        "has_deliverable": has_deliverable,
    }


def load_mapping(root: Path) -> tuple[dict[str, Any] | None, str | None, Path, str]:
    """读取约定位置的映射表，不自动创建或修复。

    返回 (data, error, path, source)，source 为 root|stage|legacy|missing。
    """
    path, source = resolve_artifact(root, "_映射表.json")
    candidate = path if path is not None else (root / "_映射表.json")
    data, error = read_json(candidate)
    return data, error, candidate, source


def _rel_path(root: Path, path: Path) -> str:
    """返回稳定的项目内相对路径，供 finding/report 输出。"""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _machine_artifact(root: Path, name: str) -> tuple[dict[str, Any] | None, str | None, Path, str]:
    """读取可选机器产物，保持根目录/旧布局兼容且不自动创建文件。"""
    path, source = resolve_artifact(root, name)
    if path is None:
        # 草稿可以被 plan/report 读取和校验，但不会被当作正式交付物写回。
        draft = root / f"{name}.draft"
        if draft.is_file():
            path, source = draft, "draft"
    candidate = path if path is not None else (root / name)
    data, error = read_json(candidate)
    return data, error, candidate, source


def _list_of_strings(value: Any, field: str, errors: list[str], *, required: bool = False) -> None:
    """校验机器文件中的字符串数组，避免 CLI 对错误输入静默降级。"""
    if value is None and not required:
        return
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{field} 必须是非空字符串数组")


PLAN_STATUSES = {"pending", "ready", "in_progress", "blocked", "qa", "accepted", "done"}


def validate_project_plan(data: dict[str, Any] | None) -> list[str]:
    """校验项目计划层；负责人和日期故意不设为必填。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["project-plan.json 不是有效对象"]
    for key in ("project", "version"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"缺少 {key} 或值为空")
    team_size = data.get("team_size")
    if not isinstance(team_size, int) or isinstance(team_size, bool) or team_size < 0:
        errors.append("team_size 必须是大于等于 0 的整数")
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases:
        return errors + ["phases 必须是非空数组"]

    phase_ids: set[str] = set()
    phase_by_id: dict[str, dict[str, Any]] = {}
    for index, phase in enumerate(phases, start=1):
        if not isinstance(phase, dict):
            errors.append(f"phases[{index}] 必须是对象")
            continue
        phase_id = phase.get("id")
        if not isinstance(phase_id, str) or not phase_id.strip():
            errors.append(f"phases[{index}] 缺少有效 id")
            continue
        if phase_id in phase_ids:
            errors.append(f"阶段 id 重复：{phase_id}")
        phase_ids.add(phase_id)
        phase_by_id[phase_id] = phase
        if not isinstance(phase.get("name"), str) or not phase["name"].strip():
            errors.append(f"阶段 {phase_id} 缺少 name")
        if phase.get("status") not in PLAN_STATUSES:
            errors.append(f"阶段 {phase_id} 的 status 非法：{phase.get('status')!r}")
        _list_of_strings(phase.get("dependencies"), f"阶段 {phase_id}.dependencies", errors, required=True)
        _list_of_strings(phase.get("completion_criteria"), f"阶段 {phase_id}.completion_criteria", errors, required=True)
        _list_of_strings(phase.get("parallel_with"), f"阶段 {phase_id}.parallel_with", errors)
        _list_of_strings(phase.get("milestones"), f"阶段 {phase_id}.milestones", errors)
        _list_of_strings(phase.get("epics"), f"阶段 {phase_id}.epics", errors)
        _list_of_strings(phase.get("gate_evidence"), f"阶段 {phase_id}.gate_evidence", errors)
        if "owner" in phase and phase["owner"] is not None and not isinstance(phase["owner"], str):
            errors.append(f"阶段 {phase_id}.owner 必须是字符串或 null")

    current_phase = data.get("current_phase")
    if current_phase is not None and current_phase not in phase_ids:
        errors.append(f"current_phase 不存在：{current_phase}")
    for phase_id, phase in phase_by_id.items():
        for ref in phase.get("dependencies", []) if isinstance(phase.get("dependencies"), list) else []:
            if ref not in phase_ids:
                errors.append(f"阶段 {phase_id} 依赖不存在：{ref}")
        for ref in phase.get("parallel_with", []) if isinstance(phase.get("parallel_with"), list) else []:
            if ref not in phase_ids:
                errors.append(f"阶段 {phase_id} 并行阶段不存在：{ref}")
    return errors


def load_project_plan(root: Path) -> tuple[dict[str, Any] | None, str | None, Path, str]:
    """读取项目计划；缺失是兼容旧项目，文件存在但损坏则必须报告。"""
    return _machine_artifact(root, "project-plan.json")


def plan_summary(root: Path) -> dict[str, Any]:
    """计算计划层的当前阶段、可开始阶段和依赖阻塞，不修改计划文件。"""
    data, error, path, source = load_project_plan(root)
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    if error == "文件不存在":
        return {"exists": False, "status": "missing", "path": rel, "path_source": source}
    if error:
        return {"exists": True, "status": "invalid", "path": rel, "path_source": source, "errors": [error]}
    errors = validate_project_plan(data)
    if errors:
        return {"exists": True, "status": "invalid", "path": rel, "path_source": source, "errors": errors}

    phases = data.get("phases", [])
    by_id = {phase["id"]: phase for phase in phases}
    completed = {phase_id for phase_id, phase in by_id.items() if phase.get("status") in {"accepted", "done"}}
    ready: list[str] = []
    dependency_blocked: dict[str, list[str]] = {}
    for phase_id, phase in by_id.items():
        if phase.get("status") not in {"pending", "ready"}:
            continue
        dependencies = phase.get("dependencies", [])
        missing = [ref for ref in dependencies if ref not in completed]
        if missing:
            dependency_blocked[phase_id] = missing
        else:
            ready.append(phase_id)

    current = data.get("current_phase")
    if not current:
        current = next((p["id"] for p in phases if p.get("status") == "in_progress"), None)
    if not current and ready:
        current = ready[0]
    status_counts = Counter(str(phase.get("status", "")) for phase in phases)
    return {
        "exists": True,
        "status": "draft" if source == "draft" else "pass",
        "draft": source == "draft",
        "path": rel,
        "path_source": source,
        "project": data.get("project", ""),
        "version": data.get("version", ""),
        "team_size": data.get("team_size", 0),
        "current_phase": current,
        "phase_count": len(phases),
        "status_counts": dict(status_counts),
        "ready_phases": ready,
        "dependency_blocked": dependency_blocked,
        "parallel_tracks": [p["id"] for p in phases if p.get("parallel_with")],
        "phases": phases,
    }


GOVERNANCE_SECTIONS = ("risks", "issues", "changes", "decisions")


def validate_project_governance(data: dict[str, Any] | None) -> list[str]:
    """校验统一治理登记，允许 owner/phase/task_refs 缺省。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["project-governance.json 不是有效对象"]
    if not isinstance(data.get("version"), str) or not data["version"].strip():
        errors.append("缺少 version 或值为空")
    for section in GOVERNANCE_SECTIONS:
        entries = data.get(section)
        if not isinstance(entries, list):
            errors.append(f"{section} 必须是数组")
            continue
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                errors.append(f"{section}[{index}] 必须是对象")
                continue
            for key in ("id", "title", "status", "impact", "evidence"):
                if key == "evidence":
                    _list_of_strings(entry.get(key), f"{section}[{index}].evidence", errors, required=True)
                elif not isinstance(entry.get(key), str) or not entry[key].strip():
                    errors.append(f"{section}[{index}] 缺少 {key}")
            if entry.get("priority") is not None and entry.get("priority") not in {"P0", "P1", "P2"}:
                errors.append(f"{section}[{index}].priority 非法")
    return errors


def load_project_governance(root: Path) -> tuple[dict[str, Any] | None, str | None, Path, str]:
    """读取项目治理登记；不自动创建、不自动关闭事项。"""
    return _machine_artifact(root, "project-governance.json")


def governance_summary(root: Path) -> dict[str, Any]:
    """汇总风险、问题、变更和决策，保留证据引用供报告和门禁使用。"""
    data, error, path, source = load_project_governance(root)
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    if error == "文件不存在":
        return {"exists": False, "status": "missing", "path": rel, "path_source": source}
    if error:
        return {"exists": True, "status": "invalid", "path": rel, "path_source": source, "errors": [error]}
    errors = validate_project_governance(data)
    if errors:
        return {"exists": True, "status": "invalid", "path": rel, "path_source": source, "errors": errors}

    risks = data.get("risks", [])
    issues = data.get("issues", [])
    changes = data.get("changes", [])
    decisions = data.get("decisions", [])
    closed = {"closed", "resolved", "mitigated", "accepted", "rejected"}
    open_p0_risks = [r for r in risks if r.get("priority") == "P0" and r.get("status") not in closed]
    blocked_issues = [i for i in issues if i.get("status") == "blocked"]
    pending_changes = [c for c in changes if c.get("approval") == "pending"]
    return {
        "exists": True,
        "status": "draft" if source == "draft" else "pass",
        "draft": source == "draft",
        "path": rel,
        "path_source": source,
        "version": data.get("version", ""),
        "counts": {section: len(data.get(section, [])) for section in GOVERNANCE_SECTIONS},
        "open_p0_risks": open_p0_risks,
        "blocked_issues": blocked_issues,
        "pending_changes": pending_changes,
        "open_risk_count": sum(1 for r in risks if r.get("status") not in closed),
        "open_issue_count": sum(1 for i in issues if i.get("status") not in closed),
        "pending_change_count": len(pending_changes),
        "decisions": decisions,
    }


def project_health_report(root: Path) -> dict[str, Any]:
    """聚合计划、治理、流水线和飞书镜像，形成不依赖负责人/日期的健康报告。"""
    progress = current_stage_summary(root)
    plan = plan_summary(root)
    governance = governance_summary(root)
    mirror = status_summary(root)
    blockers: list[str] = []
    if plan.get("status") == "invalid":
        blockers.extend(f"计划：{item}" for item in plan.get("errors", []))
    if governance.get("status") == "invalid":
        blockers.extend(f"治理：{item}" for item in governance.get("errors", []))
    blockers.extend(f"P0 风险未关闭：{item.get('id', '')}" for item in governance.get("open_p0_risks", []))
    blockers.extend(f"阻塞问题未关闭：{item.get('id', '')}" for item in governance.get("blocked_issues", []))
    blockers.extend(f"变更待审批：{item.get('id', '')}" for item in governance.get("pending_changes", []))
    return {
        "project": plan.get("project", progress.get("project", "")),
        "health": "blocked" if blockers else "healthy",
        "blockers": blockers,
        "progress": progress,
        "plan": plan,
        "governance": governance,
        "execution_mirror": mirror,
        "authority": "飞书是执行状态真源；本地 sprint-status.yaml 仅为只读镜像",
    }


def check_project(root: Path) -> list[dict[str, Any]]:
    """执行只读项目检查，结果稳定且不修改任何文件。

    SPEC / 映射表 / 状态文件统一走 resolve_artifact，
    其余人读产物仍走 find_first 并自动排除 skill/基座/工具目录。
    每个 finding 的 evidence 携带实际命中路径，便于用户诊断。
    """
    findings: list[dict[str, Any]] = []

    def add(item_id: str, status: str, message: str, evidence: list[str] | None = None, severity: str = "error") -> None:
        findings.append({
            "id": item_id,
            "severity": severity,
            "status": status,
            "evidence": evidence or [],
            "message": message,
        })

    # 新增治理层是可选兼容能力：只有项目创建对应机器文件后才纳入门禁，
    # 存量项目不会因为尚未迁移计划层而被旧检查强制阻断。
    plan_data, plan_error, plan_path, plan_source = load_project_plan(root)
    if plan_error != "文件不存在":
        plan_rel = _rel_path(root, plan_path)
        if plan_error:
            add("plan.valid", "fail", f"项目计划不可读取：{plan_error}", [plan_rel])
        else:
            plan_errors = validate_project_plan(plan_data)
            if plan_errors:
                add("plan.valid", "fail", f"项目计划结构错误：{'；'.join(plan_errors)}", [plan_rel])
            else:
                add("plan.valid", "pass", f"项目计划有效（{plan_source}）", [plan_rel], severity="info")

    governance_data, governance_error, governance_path, governance_source = load_project_governance(root)
    if governance_error != "文件不存在":
        governance_rel = _rel_path(root, governance_path)
        if governance_error:
            add("governance.valid", "fail", f"项目治理登记不可读取：{governance_error}", [governance_rel])
        else:
            governance_errors = validate_project_governance(governance_data)
            if governance_errors:
                add("governance.valid", "fail", f"项目治理登记结构错误：{'；'.join(governance_errors)}", [governance_rel])
            else:
                governance = governance_summary(root)
                add("governance.valid", "pass", f"项目治理登记有效（{governance_source}）", [governance_rel], severity="info")
                for risk in governance.get("open_p0_risks", []):
                    add("governance.p0-risk", "fail", f"P0 风险未关闭：{risk.get('id', '')} {risk.get('title', '')}", risk.get("evidence", []))
                for issue in governance.get("blocked_issues", []):
                    add("governance.blocked-issue", "fail", f"阻塞问题未关闭：{issue.get('id', '')} {issue.get('title', '')}", issue.get("evidence", []))
                for change in governance.get("pending_changes", []):
                    add("governance.pending-change", "fail", f"范围变更待审批：{change.get('id', '')} {change.get('title', '')}", change.get("evidence", []))

    # SPEC：兼容根 / 阶段目录 / `_meta`
    spec, spec_source = resolve_artifact(root, "SPEC.md")
    missing_fields = (
        [field for field in SPEC_FIELDS if not markdown_has_heading(spec, field)]
        if spec is not None else list(SPEC_FIELDS)
    )
    spec_rel = str(spec.relative_to(root)) if spec is not None else ""
    if spec is None:
        add("spec.exists", "fail", "缺少 SPEC.md（项目根 / 阶段目录 / `_meta` 均未找到）")
    elif missing_fields:
        add("spec.fields", "fail", f"SPEC 缺少字段：{', '.join(missing_fields)}", [spec_rel])
    else:
        add("spec.fields", "pass", f"SPEC 五字段齐全（来源 {spec_source}）", [spec_rel], severity="info")

    confirmation = find_first(root, ("*客户确认*.md", "**/*客户确认*.md"))
    readiness = find_first(root, ("*readiness*.md", "**/*readiness*.md", "**/*技术就绪*.md"))
    biz_arch = find_first(root, ("*业务架构*.md", "**/*业务架构*.md"))
    prod_arch = find_first(root, ("*产品架构*.md", "**/*产品架构*.md"))
    tech_arch = find_first(root, ("*技术架构*.md", "**/*技术架构*.md"))
    data_arch = find_first(root, ("*数据架构*.md", "**/*数据架构*.md"))
    acceptance = find_first(root, ("*验收报告*.md", "**/*验收报告*.md"))
    evaluation = find_first(root, ("*评测报告*.md", "**/*评测报告*.md"))

    def _rel(path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)

    # 关卡类产物：四态语义（pass/unknown/fail），模板/空文件不能算 pass
    if confirmation:
        info = parse_confirmation(confirmation)
        rel = _rel(confirmation)
        if info["is_placeholder"]:
            add("gate.client", "unknown", "客户确认记录是模板/占位符，未填实质证据", [rel])
        elif info["decision"] == "fail":
            add("gate.client", "fail", "客户确认记录含阻断/不通过结论", [rel])
        elif info["decision"] == "conditional":
            add("gate.client", "unknown", "客户确认为「有条件放行」：约束项未消解前不得扩大研发范围", [rel])
        elif info["decision"] != "pass":
            add("gate.client", "unknown", "客户确认记录缺少明确放行结论", [rel])
        else:
            missing: list[str] = []
            if not info["method"]:
                missing.append("确认方式")
            if not info["confirmed_at"]:
                missing.append("确认时间")
            if not info["representative"]:
                missing.append("客户代表")
            if missing:
                add("gate.client", "unknown", f"客户确认记录放行结论缺最小证据：{', '.join(missing)}", [rel])
            else:
                add("gate.client", "pass", f"客户确认签字完整（{info['representative']} @ {info['confirmed_at']}）", [rel], severity="info")
    else:
        add("gate.client", "unknown", "未找到客户确认记录，需要人工确认", severity="warning")

    if readiness:
        info = parse_readiness(readiness)
        rel = _rel(readiness)
        if info["is_placeholder"]:
            add("gate.readiness", "unknown", "技术就绪报告是模板/占位符，未填实质证据", [rel])
        elif info["conclusion"] == "pass":
            add("gate.readiness", "pass", f"技术就绪通过：{info.get('summary', '')}", [rel], severity="info")
        elif info["conclusion"] == "fail":
            add("gate.readiness", "fail", f"技术就绪不通过：{info.get('summary', '')}", [rel])
        elif info["conclusion"] == "pending":
            add("gate.readiness", "unknown", f"技术就绪待确认：{info.get('summary', '')}", [rel])
        else:
            add("gate.readiness", "unknown", f"技术就绪报告缺少明确结论：{info.get('summary', '')}", [rel])
    else:
        add("gate.readiness", "unknown", "未找到技术就绪报告，需要人工确认", severity="warning")

    if acceptance:
        info = parse_acceptance(acceptance)
        rel = _rel(acceptance)
        if info["is_placeholder"]:
            add("gate.acceptance", "unknown", "验收报告是模板/占位符，未填实质证据", [rel])
        elif info["conclusion"] == "fail":
            add("gate.acceptance", "fail", "验收报告含不通过结论", [rel])
        elif info["conclusion"] == "conditional":
            add("gate.acceptance", "unknown", "验收为「有条件通过」：遗留问题未关闭前不得转为正式通过", [rel])
        elif info["conclusion"] != "pass":
            add("gate.acceptance", "unknown", "验收报告缺少明确放行结论", [rel])
        else:
            missing: list[str] = []
            if not info["method"]:
                missing.append("客户确认方式")
            if not info["confirmed_at"]:
                missing.append("客户确认时间")
            if missing:
                add("gate.acceptance", "unknown", f"验收报告放行结论缺最小证据：{', '.join(missing)}", [rel])
            else:
                add("gate.acceptance", "pass", f"验收签字完整（{info['confirmed_at']}）", [rel], severity="info")
    else:
        add("gate.acceptance", "unknown", "未找到验收报告，需要人工确认", severity="warning")

    if evaluation:
        info = parse_evaluation(evaluation)
        rel = _rel(evaluation)
        if info["is_placeholder"]:
            add("gate.eval", "unknown", "评测报告是模板/占位符，未填实质证据", [rel])
        elif info["conclusion"] == "pass":
            add("gate.eval", "pass", f"评测放行（含 Tier1 + 阈值）：{info.get('summary', '')}", [rel], severity="info")
        elif info["conclusion"] == "fail":
            add("gate.eval", "fail", f"评测不通过：{info.get('summary', '')}", [rel])
        elif info["conclusion"] == "conditional":
            add("gate.eval", "unknown", "评测为「有条件放行」：约束项未消解前不得进 QA", [rel])
        elif info["conclusion"] == "incomplete":
            missing: list[str] = []
            if not info["has_tier1"]:
                missing.append("Tier1 实测")
            if not info["has_threshold"]:
                missing.append("阈值")
            add("gate.eval", "unknown", f"评测报告缺最小证据：{', '.join(missing)}", [rel])
        else:
            add("gate.eval", "unknown", f"评测报告缺少放行结论：{info.get('summary', '')}", [rel])
    else:
        add("gate.eval", "unknown", "未找到评测报告，需要人工确认", severity="warning")

    # Story 文档：三要素（做什么 / DoD·AC / 交付物）—— 校验所有 Story，不只看第一个
    story_files = find_all(root, ("stories/**/*.md", "**/*story*.md", "**/*stories*.md"))
    if story_files:
        story_problems: list[str] = []
        story_paths: list[str] = []
        for story_path in story_files:
            info = parse_story(story_path)
            rel = _rel(story_path)
            story_paths.append(rel)
            if info["is_placeholder"]:
                story_problems.append(f"{rel}:模板/占位符")
                continue
            missing: list[str] = []
            if not info["has_goal"]:
                missing.append("做什么")
            if not info["has_ac"]:
                missing.append("DoD/AC")
            if not info["has_deliverable"]:
                missing.append("交付物")
            if missing:
                story_problems.append(f"{rel}:缺{','.join(missing)}")
        if story_problems:
            add("stories.exists", "fail",
                f"{len(story_problems)}/{len(story_files)} 份 Story 缺三要素：{'；'.join(story_problems)}",
                story_paths)
        else:
            add("stories.exists", "pass",
                f"全部 {len(story_files)} 份 Story 三要素齐全", story_paths, severity="info")
    else:
        add("stories.exists", "unknown", "未找到 Story 文档，需要人工确认", severity="warning")

    # 四层架构：业务/产品/技术/数据 全部齐才算通过
    biz_arch = find_first(root, ("*业务架构*.md", "**/*业务架构*.md"))
    prod_arch = find_first(root, ("*产品架构*.md", "**/*产品架构*.md"))
    tech_arch = find_first(root, ("*技术架构*.md", "**/*技术架构*.md"))
    data_arch = find_first(root, ("*数据架构*.md", "**/*数据架构*.md"))
    arch_layers = [
        ("业务架构", biz_arch),
        ("产品架构", prod_arch),
        ("技术架构", tech_arch),
        ("数据架构", data_arch),
    ]
    missing_arch = [name for name, path in arch_layers if path is None]
    arch_paths = [_rel(p) for _, p in arch_layers if p is not None]
    if missing_arch:
        add("arch.business", "unknown",
            f"四层架构缺：{', '.join(missing_arch)}（需全部四层）",
            arch_paths, severity="warning")
    else:
        add("arch.business", "pass",
            "四层架构齐全（业务/产品/技术/数据）",
            arch_paths, severity="info")

    # 映射表：除了结构解析，还需校验 GUID 完整性
    mapping, mapping_error, mapping_path, mapping_source = load_mapping(root)
    mapping_rel = _rel(mapping_path)
    if mapping_error:
        add(
            "mapping.valid",
            "unknown" if mapping_error == "文件不存在" else "fail",
            f"映射表（{mapping_source}）：{mapping_error}",
            [mapping_rel],
            severity="warning" if mapping_error == "文件不存在" else "error",
        )
    else:
        guid_errors = mapping_guids(mapping)
        _, id_errors = mapping_ids(mapping)
        all_errors = guid_errors + id_errors
        if all_errors:
            add("mapping.valid", "fail", "映射表结构存在问题（GUID/ID 缺失）", all_errors)
        else:
            add("mapping.valid", "pass", f"映射表 GUID + 三级结构可读取（来源 {mapping_source}）", [mapping_rel], severity="info")

    # 后段产物存在而前置关卡缺失时，明确报告流程乱序。
    # 关卡顺序纪律：client_gate → architecture → tech_readiness → story_breakdown → feishu_sync → development → eval → qa → acceptance_gate
    # 只要 readiness 未通过（含缺失/占位符/未放行），下游任何产物都不应存在。
    readiness_pass = (
        readiness is not None
        and not parse_readiness(readiness).get("is_placeholder", True)
        and parse_readiness(readiness).get("conclusion") == "pass"
    )
    confirmation_pass = (
        confirmation is not None
        and not parse_confirmation(confirmation).get("is_placeholder", True)
        and parse_confirmation(confirmation).get("decision") == "pass"
    )
    # readiness 通过时，client_gate 必须先通过
    if readiness_pass and not confirmation_pass:
        add("order.client-before-readiness", "fail", "技术就绪已通过，但客户签字关卡未通过")
    stories_present = bool(story_files)
    if stories_present and not confirmation_pass:
        add("order.client-before-story", "fail", "已存在 Story 文档，但客户签字关卡未通过")
    if mapping and mapping_error is None and not readiness_pass:
        add("order.readiness-before-feishu", "fail", "已存在飞书映射，但技术就绪未通过")
    if stories_present and not readiness_pass:
        add("order.readiness-before-story", "fail", "已存在 Story 文档，但技术就绪未通过")
    # 四层架构任一缺失 → 飞书同步前阻断
    arch_layers_present = all([biz_arch, prod_arch, tech_arch, data_arch])
    if mapping and mapping_error is None and not arch_layers_present:
        add("order.arch-before-feishu", "fail",
            "已存在飞书映射，但四层架构未齐全（业务/产品/技术/数据 必须全部存在）")
    # readiness 报告本身未放行 → 飞书同步前阻断（避免只读了 progress 状态但没真出报告）
    if mapping and mapping_error is None and readiness is None:
        add("order.readiness-report-before-feishu", "fail",
            "已存在飞书映射，但找不到 readiness 报告，必须先产出技术就绪报告")
    # progress.tech_readiness != done → 飞书同步前阻断
    progress_path, _ = resolve_artifact(root, "project-progress.yaml")
    if mapping and mapping_error is None and progress_path is not None:
        progress_data = read_progress(progress_path)
        if progress_data:
            tech_readiness_status = (
                progress_data.get("stages", {}).get("tech_readiness", {}).get("status", "pending")
            )
            if tech_readiness_status != "done":
                add("order.progress-tech-readiness-done-before-feishu", "fail",
                    f"已存在飞书映射，但 project-progress.yaml 中 tech_readiness 状态为 {tech_readiness_status!r}（必须 done）")
    # 任一 Story 缺三要素 → 飞书同步前阻断
    if mapping and mapping_error is None and story_files:
        story_incomplete = []
        for sp in story_files:
            info = parse_story(sp)
            if info["is_placeholder"] or not (info["has_goal"] and info["has_ac"] and info["has_deliverable"]):
                try:
                    story_incomplete.append(str(sp.relative_to(root)))
                except ValueError:
                    story_incomplete.append(str(sp))
        if story_incomplete:
            add("order.story-complete-before-feishu", "fail",
                f"已存在飞书映射，但 Story 三要素不全：{', '.join(story_incomplete)}")
    # development 用 sprint-status.yaml 检测
    status_path, _ = resolve_artifact(root, "sprint-status.yaml")
    if status_path is not None and not readiness_pass:
        add("order.readiness-before-dev", "fail", "已存在开发状态文件，但技术就绪未通过")
    # acceptance / eval 必须在 readiness 之后
    if evaluation is not None and not readiness_pass:
        add("order.readiness-before-eval", "fail", "已存在评测报告，但技术就绪未通过")
    if acceptance is not None and not readiness_pass:
        add("order.readiness-before-acceptance", "fail", "已存在验收报告，但技术就绪未通过")
    return findings


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总检查结果，并保留未知状态不等同于通过。"""
    counts = Counter(item["status"] for item in findings)
    return {
        "pass": counts.get("pass", 0),
        "warn": counts.get("warn", 0) + counts.get("unknown", 0),
        "fail": counts.get("fail", 0),
        "blocked": counts.get("fail", 0) > 0 or counts.get("unknown", 0) > 0,
    }


TRACE_ID_RE = re.compile(r"商机编号[:：]\s*(OPP-\d{4}-\d+)")


def read_trace_id(root: Path) -> str:
    """读取商机编号（Trace 根）：优先 SPEC.md 头部引用行，回退 project-progress.yaml 顶层 trace_id。

    两个文件都按兼容顺序解析（根 → 阶段目录 → `_meta`）。
    """
    spec, _ = resolve_artifact(root, "SPEC.md")
    if spec is not None:
        try:
            match = TRACE_ID_RE.search(spec.read_text(encoding="utf-8"))
        except OSError:
            match = None
        if match:
            return match.group(1)
    progress_path, _ = resolve_artifact(root, "project-progress.yaml")
    if progress_path is not None:
        progress = read_progress(progress_path)
        if progress and progress.get("trace_id"):
            return str(progress["trace_id"])
    return ""


def trace_project(root: Path) -> dict[str, Any]:
    """基于文件和映射表生成只读追溯摘要，不伪造缺失链路。

    每个 link 附带实际命中路径和来源（root|stage|legacy），便于诊断。
    """
    mapping, error, mapping_path, mapping_source = load_mapping(root)
    ids, mapping_errors = mapping_ids(mapping)
    trace_id = read_trace_id(root)

    biz_arch = find_first(root, ("*业务架构*.md", "**/*业务架构*.md"))
    prod_arch = find_first(root, ("*产品架构*.md", "**/*产品架构*.md"))
    tech_arch = find_first(root, ("*技术架构*.md", "**/*技术架构*.md"))
    data_arch = find_first(root, ("*数据架构*.md", "**/*数据架构*.md"))
    spec_path, spec_source = resolve_artifact(root, "SPEC.md")
    opportunity = find_first(root, ("*商机档案*.md", "**/*商机档案*.md"))
    deal = find_first(root, ("立项包.md", "**/立项包.md", "*合同签约确认*.md", "**/*合同签约确认*.md"))
    stories = find_first(root, ("stories/**/*.md", "**/*story*.md", "**/*stories*.md"))
    evaluation = find_first(root, ("*评测报告*.md", "**/*评测报告*.md"))
    acceptance = find_first(root, ("*验收报告*.md", "**/*验收报告*.md"))

    # 每个 link 同时记录是否存在 + 命中路径 + 来源
    raw_links: dict[str, tuple[Path | None, str]] = {
        "spec": (spec_path, spec_source),
        "architecture": (
            biz_arch or prod_arch or tech_arch or data_arch,
            "found" if (biz_arch or prod_arch or tech_arch or data_arch) else "missing",
        ),
        "stories": (stories, "found" if stories else "missing"),
        "mapping": (mapping_path if error is None and not mapping_errors else None, mapping_source),
        "evaluation": (evaluation, "found" if evaluation else "missing"),
        "acceptance": (acceptance, "found" if acceptance else "missing"),
    }
    if trace_id:
        raw_links["opportunity"] = (opportunity, "found" if opportunity else "missing")
        raw_links["deal"] = (deal, "found" if deal else "missing")

    links: dict[str, bool] = {}
    paths: dict[str, str] = {}
    for name, (path, _source) in raw_links.items():
        links[name] = path is not None
        if path is not None:
            try:
                paths[name] = str(path.relative_to(root))
            except ValueError:
                paths[name] = str(path)

    missing = [name for name, present in links.items() if not present]
    return {
        "trace_id": trace_id,
        "links": links,
        "paths": paths,
        "mapping_path": str(mapping_path.relative_to(root)) if mapping_path.is_relative_to(root) else str(mapping_path),
        "mapping_source": mapping_source,
        "mapped_subtask_count": len(ids),
        "missing": missing,
        "mapping_errors": mapping_errors,
        "status": "pass" if not missing and not mapping_errors else "incomplete",
    }


def read_simple_status(path: Path) -> list[dict[str, str]]:
    """读取常见的 story/status 两列 YAML；复杂 YAML 留给未来适配器。

    支持顶层字段：story / id / key / status / blocked_by / task_id / assignee / updated。
    """
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {}
    supported_keys = {"story", "id", "key", "status", "blocked_by", "task_id", "assignee", "updated"}
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(-\s*)?([^:#]+):\s*([^#]+?)\s*$", raw)
        if not match:
            continue
        key = match.group(2).strip().lower()
        value = match.group(3).strip().strip('"\'')
        if key in {"story", "id", "key"} and current:
            rows.append(current)
            current = {}
        if key in supported_keys:
            current[key] = value
    if current:
        rows.append(current)
    return rows


def status_summary(root: Path, status_path: Path | None = None) -> dict[str, Any]:
    """聚合本地状态镜像，明确标记其只读属性。

    未显式传入 status_path 时，按兼容顺序解析 sprint-status.yaml。
    """
    if status_path is None:
        resolved, source = resolve_artifact(root, "sprint-status.yaml")
        path = resolved if resolved is not None else (root / "sprint-status.yaml")
    else:
        path = status_path
        source = "explicit"
    rows = read_simple_status(path)
    values = [row["status"] for row in rows if row.get("status")]
    try:
        path_str = str(path.relative_to(root))
    except ValueError:
        path_str = str(path)
    return {
        "source": "local-read-only-mirror",
        "authority": "feishu",
        "path": path_str,
        "path_source": source,
        "exists": path.is_file(),
        "row_count": len(rows),
        "status_counts": dict(Counter(values)),
        "note": "本地状态只读，不能反向写飞书",
    }


STAGES_ORDER = (
    # 售前上游三阶段（delivery-presales / delivery-deal-gate）
    "opportunity", "proposal", "deal_gate",
    # 交付主流水线（原 14 阶段不变）
    "requirements", "analysis", "prd", "ux", "prototype",
    "client_gate", "architecture", "tech_readiness",
    "story_breakdown", "feishu_sync", "development",
    "eval", "qa", "acceptance_gate",
)


def read_progress(path: Path) -> dict[str, Any] | None:
    """读取 project-progress.yaml（最小化解析，不依赖第三方 YAML 库）。

    支持：
    - 顶层 key: value
    - 阶段（缩进 2）下可多行字段或 inline dict `{key: val, key2: val2}`
    - 遇到文件不存在返回 None（让上层用回退扫描）
    - 遇到结构错误抛 ProgressParseError，由 CLI 退出码 2 处理
    """
    import re as _re

    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProgressParseError(f"无法读取 {path}: {exc}") from exc

    result: dict[str, Any] = {"project": "", "current_stage": "", "trace_id": "", "stages": {}}
    current_stage: str | None = None
    current_stage_data: dict[str, str] = {}
    has_stages = False

    inline_re = _re.compile(r"\{([^}]+)\}")

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        try:
            # 顶层 key: value
            if indent == 0 and ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key in ("project", "trace_id"):
                    if not key:
                        raise ProgressParseError(f"第 {lineno} 行：键名不能为空")
                    result[key] = val
                elif key == "current_stage":
                    if val in ("", "null", "~", "None"):
                        result["current_stage"] = None
                    else:
                        result["current_stage"] = val
                elif key == "stages":
                    has_stages = True
                    continue
                else:
                    raise ProgressParseError(f"第 {lineno} 行：未知顶层字段 {key!r}")
            # stages 下的子 key（缩进 2），支持 inline dict
            elif indent == 2 and ":" in stripped:
                head, _, rest = stripped.partition(":")
                stage_name = head.strip()
                rest = rest.strip()
                if current_stage and current_stage_data:
                    result["stages"][current_stage] = current_stage_data
                if not stage_name:
                    raise ProgressParseError(f"第 {lineno} 行：阶段名不能为空")
                current_stage = stage_name
                current_stage_data = {}
                # inline dict: {key: val, key2: val2}
                if rest.startswith("{") and rest.endswith("}"):
                    body = rest[1:-1]
                    for pair in body.split(","):
                        if ":" not in pair:
                            continue
                        k, _, v = pair.partition(":")
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k:
                            current_stage_data[k] = v
            # stage 内的字段（缩进 4）
            elif indent >= 4 and ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if current_stage and key:
                    current_stage_data[key] = val
        except ValueError as exc:
            raise ProgressParseError(f"第 {lineno} 行解析失败：{exc}") from exc

    if current_stage and current_stage_data:
        result["stages"][current_stage] = current_stage_data

    # 必填字段检查
    if not has_stages:
        raise ProgressParseError("缺少 stages 段")
    if not result["project"]:
        raise ProgressParseError("缺少 project 字段")

    return result


class ProgressParseError(Exception):
    """project-progress.yaml 结构错误——CLI 应退出码 2。"""


# 合法阶段清单（含售前上游）
ALL_STAGE_KEYS = (
    "opportunity", "proposal", "deal_gate",
    "requirements", "analysis", "prd", "ux", "prototype",
    "client_gate", "architecture", "tech_readiness",
    "story_breakdown", "feishu_sync", "development",
    "eval", "qa", "acceptance_gate",
)
# 关卡阶段：这些阶段 done 时应携带 gate_evidence
GATE_STAGES = {"deal_gate", "client_gate", "acceptance_gate"}


def validate_progress(data: dict[str, Any] | None) -> list[str]:
    """校验 project-progress 结构。返回错误列表，空列表表示通过。

    校验规则：
    - current_stage 必须为 None 或合法阶段
    - stages 包含全部 17 个阶段键
    - 每个阶段必须有 status
    - 最多一个 in_progress 阶段
    - 当前阶段不能是 pending（必须是 in_progress 或 done；None 表示验收完成）
    - done 阶段必须有 completed_at（除非在 ALLOW_DONE_WITHOUT_DATE 列表内）
    - gate_evidence 只在关卡阶段出现
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["progress 文件不是有效的 YAML 对象"]

    current = data.get("current_stage")
    if current is not None and current not in STAGES_ORDER:
        errors.append(f"非法 current_stage：{current!r}（合法值：None 或 {list(STAGES_ORDER)}）")

    stages = data.get("stages")
    if not isinstance(stages, dict):
        errors.append("stages 字段不是对象")
        return errors

    # 必备 17 阶段
    missing_keys = [k for k in STAGES_ORDER if k not in stages]
    if missing_keys:
        errors.append(f"缺少阶段：{', '.join(missing_keys)}")

    # 统计 in_progress
    in_progress_stages: list[str] = []
    for stage_id, stage_data in stages.items():
        if not isinstance(stage_data, dict):
            errors.append(f"阶段 {stage_id} 不是对象")
            continue
        status = stage_data.get("status", "")
        if status not in {"pending", "in_progress", "done"}:
            errors.append(f"阶段 {stage_id} 非法 status：{status!r}")
            continue
        if status == "in_progress":
            in_progress_stages.append(stage_id)
        if status == "done" and not stage_data.get("completed_at"):
            errors.append(f"阶段 {stage_id} 标记为 done 但缺少 completed_at")
        if stage_data.get("gate_evidence") and stage_id not in GATE_STAGES:
            errors.append(f"阶段 {stage_id} 不应使用 gate_evidence（仅关卡阶段可用）")

    if len(in_progress_stages) > 1:
        errors.append(f"多个阶段同时 in_progress：{', '.join(in_progress_stages)}")

    # 当前阶段不能是 pending
    if current is not None:
        current_status = stages.get(current, {}).get("status", "")
        if current_status == "pending":
            errors.append(f"current_stage={current!r} 的 status 是 pending，应为 in_progress 或 done")
        if current == "acceptance_gate" and current_status == "done":
            errors.append("acceptance_gate 已 done，current_stage 应为 null（验收完成态）")

    return errors


def current_stage_summary(root: Path) -> dict[str, Any]:
    """汇总当前流水线阶段，优先读 project-progress.yaml，回退到产物扫描。

    project-progress.yaml 按兼容顺序解析（根 → `_meta`）。
    校验失败抛 ProgressParseError（带 fix_hint），由 CLI 退出码 2 处理。
    """
    progress_path, progress_source = resolve_artifact(root, "project-progress.yaml")
    progress = read_progress(progress_path) if progress_path is not None else None
    if progress:
        errors = validate_progress(progress)
        if errors:
            raise ProgressParseError(
                "project-progress.yaml 结构错误：" + "；".join(errors)
                + " | fix_hint: 检查 templates/project-progress模板.yaml 或 docs/runtime.md 的合法字段表"
            )
        # 校验 current_stage 必须是合法阶段，否则报错让用户修复
        current = progress.get("current_stage")  # 允许 None
        if current is not None and current not in STAGES_ORDER:
            raise ProgressParseError(f"非法 current_stage: {current!r}")
        stages = progress.get("stages", {})

        # 验收完成态：current_stage = None 且 acceptance_gate.done
        if current is None:
            acc = stages.get("acceptance_gate", {})
            return {
                "source": "project-progress.yaml",
                "source_path": str(progress_path.relative_to(root)) if progress_path.is_relative_to(root) else str(progress_path),
                "source_layout": progress_source,
                "project": progress.get("project", ""),
                "trace_id": progress.get("trace_id", ""),
                "current_stage": None,
                "current_status": acc.get("status", ""),
                "next_stage": "",
                "completed_count": sum(1 for s in stages.values() if s.get("status") == "done"),
                "total_stages": len(STAGES_ORDER),
                "stages": {k: v.get("status", "pending") for k, v in stages.items()},
                "state": "completed",
            }

        current_info = stages.get(current, {})
        next_stage = ""
        found_current = False
        for stage_id in STAGES_ORDER:
            if stage_id == current:
                found_current = True
                continue
            if found_current and stages.get(stage_id, {}).get("status") == "pending":
                next_stage = stage_id
                break
        try:
            source_path = str(progress_path.relative_to(root))
        except ValueError:
            source_path = str(progress_path)
        return {
            "source": "project-progress.yaml",
            "source_path": source_path,
            "source_layout": progress_source,
            "project": progress.get("project", ""),
            "trace_id": progress.get("trace_id", ""),
            "current_stage": current,
            "current_status": current_info.get("status", ""),
            "next_stage": next_stage,
            "completed_count": sum(1 for s in stages.values() if s.get("status") == "done"),
            "total_stages": len(STAGES_ORDER),
            "stages": {k: v.get("status", "pending") for k, v in stages.items()},
            "state": "in_progress",
        }
    # 回退：通过产物扫描推断（与 onboarding step 3 逻辑一致）
    biz_arch = find_first(root, ("*业务架构*.md", "**/*业务架构*.md"))
    prod_arch = find_first(root, ("*产品架构*.md", "**/*产品架构*.md"))
    tech_arch = find_first(root, ("*技术架构*.md", "**/*技术架构*.md"))
    data_arch = find_first(root, ("*数据架构*.md", "**/*数据架构*.md"))
    checks = [
        ("opportunity", find_first(root, ("*商机档案*.md", "**/*商机档案*.md"))),
        ("proposal", find_first(root, ("*报价单*.md", "**/*报价单*.md"))),
        ("deal_gate", find_first(root, ("立项包.md", "**/立项包.md", "*合同签约确认*.md", "**/*合同签约确认*.md"))),
        ("prd", root / "PRD.md"),
        ("ux", root / "UX.md"),
        ("prototype", find_first(root, ("**/演示原型/index.html", "**/prototype/index.html", "prototype/index.html"))),
        ("client_gate", find_first(root, ("*客户确认*.md", "**/*客户确认*.md"))),
        ("architecture", biz_arch or prod_arch or tech_arch or data_arch),
        ("tech_readiness", find_first(root, ("*readiness*.md", "**/*readiness*.md"))),
        ("story_breakdown", find_first(root, ("stories/**/*.md",))),
        ("feishu_sync", find_first(root, ("_映射表.json", "**/_映射表.json"))),
        ("eval", find_first(root, ("*评测报告*.md", "**/*评测报告*.md"))),
        ("acceptance_gate", find_first(root, ("*验收报告*.md", "**/*验收报告*.md"))),
    ]
    inferred = "requirements"
    for stage_id, path_or_none in checks:
        if path_or_none and (isinstance(path_or_none, Path) and path_or_none.exists() if isinstance(path_or_none, Path) else True):
            inferred = stage_id
    return {
        "source": "inferred-from-files",
        "current_stage": inferred,
        "note": "未找到 project-progress.yaml，根据产物存在性推断。建议创建 project-progress.yaml 以获得准确追踪。",
    }


def compute_content_hash(what: str, dod: str, deliverable: str, spec_ref: str = "") -> str:
    """四字段 SHA-256。字段顺序固定、sort_keys=True，确保跨进程稳定。

    spec_ref 为空字符串也参与计算（"补写引用" 也会触发 update）。
    """
    payload = {
        "what": what.strip(),
        "dod": dod.strip(),
        "deliverable": deliverable.strip(),
        "spec_ref": spec_ref.strip(),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_manifest(data: Any) -> list[str]:
    """手写 desired-tasks schema 校验（必填 + 类型 + 格式三层）。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest 不是 JSON 对象"]
    project = data.get("project")
    if not isinstance(project, str) or not project.strip():
        errors.append("缺少 project（非空字符串）")
    generated_at = data.get("generated_at")
    if not isinstance(generated_at, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", generated_at):
        errors.append(f"generated_at 非法：{generated_at!r}（需 YYYY-MM-DD）")
    if "source_story" in data and not isinstance(data["source_story"], str):
        errors.append("source_story 必须是字符串")
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        errors.append("tasks 字段不是数组")
        return errors
    required_fields = ("local_id", "tasklist", "parent_task", "what", "dod", "deliverable", "content_hash")
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"tasks[{idx}] 不是对象")
            continue
        for field in required_fields:
            value = task.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"tasks[{idx}].{field} 缺失或为空")
        if "spec_ref" in task and not isinstance(task["spec_ref"], str):
            errors.append(f"tasks[{idx}].spec_ref 必须是字符串")
        content_hash = task.get("content_hash")
        if isinstance(content_hash, str) and not re.match(r"^[a-f0-9]{64}$", content_hash):
            errors.append(f"tasks[{idx}].content_hash 非法：{content_hash!r}（需 64 位 hex）")
    return errors


def load_manifest(root: Path) -> tuple[dict[str, Any] | None, list[str], Path | None, str]:
    """读取 desired-tasks.json。

    返回 (data, errors, path, source)。data 为 None 时 errors 非空。
    """
    path, source = resolve_artifact(root, "desired-tasks.json")
    if path is None:
        return None, ["manifest 不存在"], None, "missing"
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (json.JSONDecodeError, OSError, UnicodeError) as exc:
        return None, [f"manifest 解析失败：{exc}"], path, source
    errors = _validate_manifest(data)
    return data, errors, path, source


def dry_run(root: Path) -> dict[str, Any]:
    """生成无副作用的飞书任务预览。

    基于 desired-tasks.json (manifest) × _映射表.json (mapping) 推导：
    - create: manifest 有，mapping 无该 local_id
    - create_with_review: mapping 有旧格式（裸 string）但无 synced.content_hash
    - skip: 双方都有且 content_hash 一致
    - update: 双方都有但 content_hash 不一致
    - orphan: mapping 有，manifest 没有该 local_id

    manifest 缺失时降级为 degraded-consistency-check：只输出 skip + orphan，不输出 create。
    sprint-status.yaml 退出 create/update 判定，仅作 feishu_status 附加信息。

    blocked_by 触发：① 客户确认非 pass；② 四层架构任一 unknown；③ readiness 非 pass；
    ④ progress.tech_readiness != done；⑤ Story 三要素不全；⑥ manifest 缺失（降级模式）；
    ⑦ 映射表缺失或结构错误。
    """
    mapping, mapping_error, mapping_path, mapping_source = load_mapping(root)
    manifest, manifest_errors, manifest_path, manifest_source = load_manifest(root)

    # —— 判定门禁（复用 check_project 的最小子集） ——
    blocked: list[str] = []
    confirmation = find_first(root, ("*客户确认*.md", "**/*客户确认*.md"))
    if confirmation and not parse_confirmation(confirmation).get("is_placeholder", True):
        if parse_confirmation(confirmation).get("decision") != "pass":
            blocked.append("客户确认非 pass")
    readiness = find_first(root, ("*readiness*.md", "**/*readiness*.md", "**/*技术就绪*.md"))
    if readiness and not parse_readiness(readiness).get("is_placeholder", True):
        if parse_readiness(readiness).get("conclusion") != "pass":
            blocked.append("技术就绪非 pass")
    # 四层架构：必须四份都存在
    arch_paths = [find_first(root, (f"*{n}架构*.md", f"**/*{n}架构*.md")) for n in ("业务", "产品", "技术", "数据")]
    if any(p is None for p in arch_paths):
        blocked.append("四层架构缺一份")
    # progress.tech_readiness
    progress_path, _ = resolve_artifact(root, "project-progress.yaml")
    if progress_path is not None:
        progress_data = read_progress(progress_path)
        if progress_data:
            tech_status = progress_data.get("stages", {}).get("tech_readiness", {}).get("status", "pending")
            if tech_status != "done":
                blocked.append(f"progress.tech_readiness={tech_status!r}（必须 done）")
    # Story 三要素
    story_files = find_all(root, ("stories/**/*.md", "**/*story*.md", "**/*stories*.md"))
    if story_files:
        for sp in story_files:
            info = parse_story(sp)
            if info["is_placeholder"] or not (info["has_goal"] and info["has_ac"] and info["has_deliverable"]):
                try:
                    rel = str(sp.relative_to(root))
                except ValueError:
                    rel = str(sp)
                blocked.append(f"Story 三要素不全：{rel}")

    if mapping_error == "文件不存在":
        blocked.append("映射表不存在：先创建 _映射表.json 或运行 feishu-sync 计划")
    elif mapping_error:
        blocked.append(f"映射表不可读取：{mapping_error}")
    if mapping is not None:
        _, id_errors = mapping_ids(mapping)
        blocked.extend(id_errors)

    mode = "manifest-driven" if manifest is not None and not manifest_errors else "degraded-consistency-check"
    if manifest is None or manifest_errors:
        blocked.append(f"manifest 不可用（{'; '.join(manifest_errors) or '不存在'}）")

    # —— 解析 sprint-status.yaml（只读附加信息） ——
    status_path, status_source = resolve_artifact(root, "sprint-status.yaml")
    status_rows: list[dict[str, str]] = []
    if status_path is not None:
        status_rows = read_simple_status(status_path)
    task_index: dict[str, dict[str, str]] = {row.get("task_id") or row.get("id") or "": row for row in status_rows if row.get("task_id") or row.get("id")}

    # —— 索引 manifest 和 mapping ——
    manifest_by_id: dict[str, dict[str, Any]] = {}
    if manifest is not None and not manifest_errors:
        for task in manifest.get("tasks", []):
            if isinstance(task, dict) and task.get("local_id"):
                manifest_by_id[task["local_id"]] = task

    mapping_by_id: dict[str, dict[str, Any]] = {}  # local_id -> {task_id, synced, list_name, parent_name}
    if isinstance(mapping, dict):
        for list_name, tasklist in mapping.get("tasklists", {}).items():
            if not isinstance(tasklist, dict):
                continue
            for parent_name, parent in tasklist.get("parent_tasks", {}).items():
                if not isinstance(parent, dict):
                    continue
                for local_id, value in parent.get("subtasks", {}).items():
                    tid, synced = parse_mapping_subtask(value)
                    if not tid:
                        continue
                    mapping_by_id[local_id] = {
                        "task_id": tid,
                        "synced": synced,
                        "list_name": list_name,
                        "parent_name": parent_name,
                    }

    operations: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _feishu_status(task_id: str) -> str:
        row = task_index.get(task_id)
        return row.get("status", "") if row else ""

    # 1. manifest 驱动的判定
    for local_id, mt in manifest_by_id.items():
        seen.add(local_id)
        what = mt.get("what", "")
        m_hash = mt.get("content_hash", "")
        mref = mapping_by_id.get(local_id)
        feishu_status = _feishu_status(mref["task_id"]) if mref else ""

        if mref is None:
            # manifest 有，mapping 无 → create
            if mode == "degraded-consistency-check":
                # 降级模式不输出 create（不假装知道远端是否存在）
                operations.append({
                    "action": "create_with_review",
                    "local_id": local_id,
                    "task_id": "",
                    "reason": "降级模式：未确认远端是否存在，需先跑 feishu-sync 生成 manifest",
                    "feishu_status": "",
                })
            else:
                operations.append({
                    "action": "create",
                    "local_id": local_id,
                    "task_id": "",
                    "reason": "首次推送",
                    "feishu_status": "",
                })
        else:
            synced = mref.get("synced") or {}
            s_hash = synced.get("content_hash") if isinstance(synced, dict) else None
            if not s_hash:
                # 旧格式 mapping（裸 string 或缺 synced）→ 建议人工确认
                operations.append({
                    "action": "create_with_review",
                    "local_id": local_id,
                    "task_id": mref["task_id"],
                    "reason": "mapping 为旧格式（无 synced.content_hash），建议人工确认是否需 update",
                    "feishu_status": feishu_status,
                })
            elif s_hash == m_hash:
                operations.append({
                    "action": "skip",
                    "local_id": local_id,
                    "task_id": mref["task_id"],
                    "reason": "三要素未变",
                    "feishu_status": feishu_status,
                })
            else:
                operations.append({
                    "action": "update",
                    "local_id": local_id,
                    "task_id": mref["task_id"],
                    "reason": f"三要素已变（旧 hash: {s_hash[:8]}…, 新 hash: {m_hash[:8]}…）",
                    "feishu_status": feishu_status,
                })

    # 2. mapping 有但 manifest 无 → orphan
    for local_id, mref in mapping_by_id.items():
        if local_id in seen:
            continue
        operations.append({
            "action": "orphan",
            "local_id": local_id,
            "task_id": mref["task_id"],
            "reason": "mapping 有但 manifest 无（远端残留）",
            "feishu_status": _feishu_status(mref["task_id"]),
        })

    summary = Counter(op["action"] for op in operations)
    try:
        mapping_path_str = str(mapping_path.relative_to(root)) if mapping_path else ""
    except ValueError:
        mapping_path_str = str(mapping_path) if mapping_path else ""
    try:
        manifest_path_str = str(manifest_path.relative_to(root)) if manifest_path else ""
    except ValueError:
        manifest_path_str = str(manifest_path) if manifest_path else ""
    status_path_str = ""
    if status_path is not None:
        try:
            status_path_str = str(status_path.relative_to(root))
        except ValueError:
            status_path_str = str(status_path)

    return {
        "mode": mode,
        "operations": operations,
        "summary": {
            "create": summary.get("create", 0),
            "update": summary.get("update", 0),
            "skip": summary.get("skip", 0),
            "orphan": summary.get("orphan", 0),
            "create_with_review": summary.get("create_with_review", 0),
            "blocked": len(blocked),
        },
        "blocked_by": blocked,
        "mapping_path": mapping_path_str,
        "mapping_source": mapping_source,
        "manifest_path": manifest_path_str,
        "manifest_source": manifest_source,
        "manifest_generated_at": manifest.get("generated_at", "") if isinstance(manifest, dict) else "",
        "manifest_task_count": len(manifest_by_id),
        "status_path": status_path_str,
        "status_source": status_source if status_path else "missing",
        "network": False,
        "side_effects": False,
        "mapped_subtask_count": len(mapping_by_id),
        "note": "dry-run：仅输出计划，不调用飞书、不写入映射表" if mode == "manifest-driven" else
                "dry-run 降级模式：manifest 缺失，只检查一致性不输出 create，请先跑 delivery-feishu-sync 生成 desired-tasks.json",
    }


# 每个 stage 对应的产物 glob patterns（用于 revert 时定位产物文件）。
# 匹配顺序按 tuple 顺序，第一个命中的产物会被处理。
STAGE_PRODUCTS: dict[str, tuple[str, ...]] = {
    "opportunity": ("*商机档案*.md", "**/*商机档案*.md"),
    "proposal": ("*报价单*.md", "**/*报价单*.md"),
    "deal_gate": ("立项包.md", "*合同签约确认*.md", "**/*合同签约确认*.md"),
    "requirements": ("project-context.md",),
    "analysis": (),  # analysis 阶段产物不固定（BMAD 产物），不主动撤回
    "prd": ("PRD.md",),
    "ux": ("UX.md",),
    "prototype": ("**/演示原型/index.html", "**/prototype/index.html"),
    "client_gate": ("*客户确认*.md", "**/*客户确认*.md"),
    "architecture": ("*业务架构*.md", "*产品架构*.md", "*技术架构*.md", "*数据架构*.md"),
    "tech_readiness": ("*readiness*.md", "*技术就绪*.md", "**/*readiness*.md", "**/*技术就绪*.md"),
    "story_breakdown": ("stories/**/*.md", "**/*story*.md", "**/*stories*.md"),
    "feishu_sync": ("_映射表.json", "desired-tasks.json"),
    "development": ("sprint-status.yaml",),
    "eval": ("*评测报告*.md", "**/*评测报告*.md"),
    "qa": (),
    "acceptance_gate": ("*验收报告*.md", "**/*验收报告*.md"),
}


def _has_draft_companion(root: Path, formal_path: Path) -> Path | None:
    """检查正式产物是否有同名 .draft.md 草稿同伴。返回草稿路径或 None。

    规则：同 stem + 同后缀替换为 .draft.md。若草稿存在则视为可还原点。
    """
    draft = formal_path.with_name(formal_path.stem + ".draft" + formal_path.suffix)
    if draft.is_file():
        return draft
    return None


def _archive_path(root: Path, formal_path: Path) -> Path:
    """生成归档路径：原名 + `.reverted-{YYYYMMDD-HHMMSS}` 后缀（避免覆盖历史归档）。

    时间戳来自系统时间，确保并发场景不冲突。
    """
    import datetime as _dt
    timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return formal_path.with_name(f"{formal_path.name}.reverted-{timestamp}")


def revert_step(root: Path, stage_id: str | None = None) -> dict[str, Any]:
    """撤回指定阶段的产物，恢复成可重做状态。

    默认（stage_id=None）：撤回 `project-progress.yaml` 中 current_stage 指向的阶段。
    显式指定：撤回指定 stage_id 对应的产物。

    返回字段：
    - reverted_stage: 被撤回的阶段名（None 表示未执行）
    - new_current_stage: 撤回后 project-progress.yaml 中的 current_stage
    - new_current_status: 撤回后 current_stage 的状态
    - files: [{path, action, new_path?}, ...]
        - action="restored_from_draft"：正式文件已删除，.draft.md 保留
        - action="archived"：正式文件已改名为 `.reverted-{timestamp}`
        - action="not_found"：该 stage 没有匹配到任何产物
    - progress_updated: bool，project-progress.yaml 是否被改写
    - error: 字符串（如果 stage 非法 / progress.yaml 缺失等）
    - warning: 提醒文本（撤回不可逆等）

    注意：
    - progress.yaml 不存在时退化为「仅撤回产物」模式（不报错）
    - 该函数会修改文件和 progress.yaml，是 CLI 唯一的写动作
    - 不删除任何文件（.reverted 归档 / 草稿保留）
    """
    result: dict[str, Any] = {
        "reverted_stage": None,
        "new_current_stage": None,
        "new_current_status": "",
        "files": [],
        "progress_updated": False,
        "error": "",
        "warning": "撤回动作不可逆——被归档的正式产物改名后不会自动删除。如需彻底删除请人工清理 .reverted-* 文件。",
    }

    if stage_id is not None and stage_id not in STAGE_PRODUCTS:
        result["error"] = f"非法 stage：{stage_id!r}（合法值见 STAGE_PRODUCTS 键）"
        return result

    # 读取 progress.yaml 定位 current_stage
    progress_path, _ = resolve_artifact(root, "project-progress.yaml")
    progress_data = read_progress(progress_path) if progress_path is not None else None

    target_stage = stage_id
    if target_stage is None:
        if progress_data is None:
            result["error"] = "未指定 stage 且未找到 project-progress.yaml——无法定位 current_stage。请用 --step 显式指定。"
            return result
        target_stage = progress_data.get("current_stage")
        if target_stage is None:
            result["error"] = "project-progress.yaml 中 current_stage 已为 null（验收完成态），无法再撤回。请用 --step 显式指定要撤回的阶段。"
            return result

    patterns = STAGE_PRODUCTS.get(target_stage, ())
    # 用 find_all 收集所有未被排除的真实产物
    candidates: list[Path] = []
    for pattern in patterns:
        for path in find_all(root, (pattern,)):
            if path not in candidates:
                candidates.append(path)

    if not candidates:
        result["reverted_stage"] = target_stage
        result["files"].append({
            "path": "",
            "action": "not_found",
            "reason": f"阶段 {target_stage} 未匹配到任何产物（可能本来就未产出）",
        })
    else:
        for formal in candidates:
            try:
                rel = str(formal.relative_to(root))
            except ValueError:
                rel = str(formal)
            draft = _has_draft_companion(root, formal)
            if draft is not None:
                # 有 draft 同伴：删正式文件，保留 draft
                try:
                    formal.unlink()
                    result["files"].append({
                        "path": rel,
                        "action": "restored_from_draft",
                        "draft_path": str(draft.relative_to(root)),
                    })
                except OSError as exc:
                    result["files"].append({
                        "path": rel,
                        "action": "error",
                        "reason": str(exc),
                    })
            else:
                # 无 draft：改名归档
                archived = _archive_path(root, formal)
                try:
                    formal.rename(archived)
                    try:
                        new_rel = str(archived.relative_to(root))
                    except ValueError:
                        new_rel = str(archived)
                    result["files"].append({
                        "path": rel,
                        "action": "archived",
                        "new_path": new_rel,
                    })
                except OSError as exc:
                    result["files"].append({
                        "path": rel,
                        "action": "error",
                        "reason": str(exc),
                    })

    result["reverted_stage"] = target_stage

    # 更新 progress.yaml：把该 stage 状态改回 pending
    if progress_path is not None and progress_data is not None:
        stages = progress_data.setdefault("stages", {})
        stage_entry = stages.get(target_stage)
        if isinstance(stage_entry, dict):
            stage_entry.pop("completed_at", None)
            stage_entry.pop("started_at", None)
            stage_entry.pop("gate_evidence", None)
            stage_entry["status"] = "pending"

        # 如果回退的是 current_stage，把 current_stage 改回上一个 done 的 stage
        current = progress_data.get("current_stage")
        if current == target_stage:
            new_current: str | None = None
            for sid in STAGES_ORDER:
                if sid == target_stage:
                    break
                if stages.get(sid, {}).get("status") == "done":
                    new_current = sid
            progress_data["current_stage"] = new_current
            # 把上一个 stage 标记为 in_progress（恢复成「正在进行」状态）
            if new_current is not None:
                new_entry = stages.setdefault(new_current, {})
                if isinstance(new_entry, dict):
                    new_entry["status"] = "in_progress"
                    new_entry.pop("completed_at", None)

        # 写回 progress.yaml（手写序列化，避免引入 yaml 依赖）
        try:
            _write_progress_yaml(progress_path, progress_data)
            result["progress_updated"] = True
            result["new_current_stage"] = progress_data.get("current_stage")
            if result["new_current_stage"]:
                nc = stages.get(result["new_current_stage"], {})
                result["new_current_status"] = nc.get("status", "") if isinstance(nc, dict) else ""
        except OSError as exc:
            result["error"] = f"progress.yaml 写入失败：{exc}"

    return result


def _write_progress_yaml(path: Path, data: dict[str, Any]) -> None:
    """手写 project-progress.yaml（最小化序列化器，复用 read_progress 的子集）。

    仅支持本工具读出来的数据格式：顶层 project/trace_id/current_stage/stages。
    stages 下每个阶段只保留 status 字段（started_at/completed_at/gate_evidence 在 revert 时已清掉）。
    """
    lines: list[str] = []
    project = data.get("project", "")
    trace_id = data.get("trace_id", "")
    current_stage = data.get("current_stage")
    if project:
        lines.append(f'project: "{project}"')
    if trace_id:
        lines.append(f'trace_id: "{trace_id}"')
    if current_stage is None:
        lines.append("current_stage: null")
    elif current_stage:
        lines.append(f'current_stage: "{current_stage}"')
    lines.append("stages:")
    for stage_id in STAGES_ORDER:
        entry = data.get("stages", {}).get(stage_id)
        if isinstance(entry, dict):
            status = entry.get("status", "pending")
            lines.append(f"  {stage_id}:")
            lines.append(f"    status: {status}")
    lines.append("")  # 末尾换行
    path.write_text("\n".join(lines), encoding="utf-8")


def next_action_suggestion(progress_data: dict[str, Any] | None, gate_statuses: dict[str, str] | None = None) -> dict[str, Any]:
    """根据 project-progress + 关卡状态生成「下一步请示建议」，给 AI 看现在该问用户什么。

    返回字段：
    - next_stage: 下一个 pending 阶段名（用于「接下来该干什么」类问题）
    - should_ask_user: bool，是否需要 AI 现在停下来问用户
    - suggested_question: 字符串，AI 可直接复述给用户的中文问句
    - blocking_gates: list[str]，未通过且阻断推进的关卡名
    - reason: 字符串，简短说明当前阻塞原因
    """
    gate_statuses = gate_statuses or {}
    blocking = [name for name, status in gate_statuses.items() if status in ("unknown", "fail")]

    if progress_data is None:
        return {
            "next_stage": None,
            "should_ask_user": True,
            "suggested_question": "我看不到 project-progress.yaml，你想做哪个阶段？告诉我角色（售前/PM/研发/AI工程师）我来路由。",
            "blocking_gates": blocking,
            "reason": "未找到 project-progress.yaml",
        }

    current = progress_data.get("current_stage")
    stages = progress_data.get("stages", {})

    # 找下一个 pending 阶段
    next_stage = None
    for stage_id in STAGES_ORDER:
        if stages.get(stage_id, {}).get("status") == "pending":
            next_stage = stage_id
            break

    if current is None and stages.get("acceptance_gate", {}).get("status") == "done":
        # 验收完成态
        return {
            "next_stage": None,
            "should_ask_user": True,
            "suggested_question": "当前是验收完成态（所有 17 个阶段已 done）。你想做复盘 / 立项新项目 / 还是验收归档？",
            "blocking_gates": blocking,
            "reason": "项目已完成",
        }

    if blocking:
        # 有阻断关卡：必须先消解
        names_zh = {
            "client": "客户签字",
            "readiness": "技术就绪",
            "eval": "AI 评测",
            "acceptance": "客户验收",
        }
        gate_names = "、".join(names_zh.get(g, g) for g in blocking)
        return {
            "next_stage": next_stage,
            "should_ask_user": True,
            "suggested_question": f"现在有 {gate_names} 关卡还没过（关卡状态 {blocking}），需要你先消解——是要补关卡产物，还是先撤回上一步重新做？",
            "blocking_gates": blocking,
            "reason": f"硬门禁未通过：{gate_names}",
        }

    if next_stage is None:
        return {
            "next_stage": None,
            "should_ask_user": True,
            "suggested_question": "所有 17 个阶段都已 done——你想做项目复盘吗？还是这条数据有问题？",
            "blocking_gates": blocking,
            "reason": "已完成全部阶段",
        }

    # 正常推进：告诉用户当前阶段 + 下一步建议
    current_label = current if current else "未启动"
    return {
        "next_stage": next_stage,
        "should_ask_user": True,
        "suggested_question": f"你现在在 {current_label} 阶段。下一步是 {next_stage}。要我开始推进吗？（说继续/OK 才动手）",
        "blocking_gates": blocking,
        "reason": "正常推进中",
    }
