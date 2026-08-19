"""delivery-flow 本地只读自动化命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    ProgressParseError,
    check_project,
    current_stage_summary,
    dry_run,
    governance_summary,
    next_action_suggestion,
    plan_summary,
    project_health_report,
    revert_step,
    status_summary,
    summarize_findings,
    trace_project,
)

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INPUT = 2
EXIT_POLICY = 3
EXIT_INTERNAL = 4


def emit(payload: object, as_json: bool) -> None:
    """统一输出人读摘要或稳定 JSON。"""
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            print(f"{key}: {value}")
    else:
        print(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="delivery-flow 本地只读一致性检查工具")
    parser.add_argument(
        "command",
        choices=("check", "trace", "status", "dry-run", "progress", "plan", "governance", "report", "revert"),
    )
    parser.add_argument("--root", default=".", help="消费方项目根目录")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--status-file", help="status 命令指定本地镜像路径")
    parser.add_argument(
        "--step",
        dest="step",
        help="revert 命令：精确指定要回退的阶段（如 deal_gate）。不指定则回退 project-progress.yaml 的 current_stage。",
    )
    return parser


def emit_dry_run(payload: dict[str, object], as_json: bool) -> None:
    """dry-run 的人读摘要：列出每个操作的 local_id/task/原因 + 模式/mode。"""
    if as_json:
        emit(payload, True)
        return
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    mode = payload.get("mode", "manifest-driven")
    print(f"dry-run [{mode}]：{payload.get('note', '')}")
    print(f"映射表：{payload.get('mapping_path', '')}（来源 {payload.get('mapping_source', '')}）")
    manifest_path = payload.get("manifest_path", "")
    if manifest_path:
        print(f"manifest：{manifest_path}（{payload.get('manifest_generated_at', '')}, "
              f"{payload.get('manifest_task_count', 0)} 任务）")
    status_path = payload.get("status_path", "")
    if status_path:
        print(f"本地镜像：{status_path}（来源 {payload.get('status_source', '')}）")
    print(f"操作统计：create={summary.get('create', 0)} "
          f"update={summary.get('update', 0)} "
          f"skip={summary.get('skip', 0)} "
          f"orphan={summary.get('orphan', 0)} "
          f"create_with_review={summary.get('create_with_review', 0)} "
          f"blocked={summary.get('blocked', 0)}")
    for op in payload.get("operations", []):
        if not isinstance(op, dict):
            continue
        feishu_status = op.get("feishu_status", "")
        suffix = f" [飞书:{feishu_status}]" if feishu_status else ""
        print(f"  [{op.get('action', '?')}] {op.get('local_id', '')} → {op.get('task_id', '')}（{op.get('reason', '')}）{suffix}")
    blocked_by = payload.get("blocked_by", [])
    if isinstance(blocked_by, list) and blocked_by:
        print("阻断：")
        for item in blocked_by:
            print(f"  - {item}")


def _collect_gate_statuses(payload: dict[str, object], root) -> dict[str, str]:
    """从 progress payload 提取关卡阶段的状态，映射成四态之一（pass/unknown/fail）。

    四个关卡：client_gate (→ client) / tech_readiness (→ readiness) / eval (→ eval) / acceptance_gate (→ acceptance)。
    project-progress.yaml 中 status=done 视为 pass；其他视为 unknown。
    """
    stages = payload.get("stages") if isinstance(payload.get("stages"), dict) else {}
    if not stages:
        return {}

    def _status(stage_id: str) -> str:
        entry = stages.get(stage_id, {})
        if not isinstance(entry, dict):
            return "unknown"
        s = entry.get("status", "")
        return "pass" if s == "done" else "unknown"

    return {
        "client": _status("client_gate"),
        "readiness": _status("tech_readiness"),
        "eval": _status("eval"),
        "acceptance": _status("acceptance_gate"),
    }


def _payload_to_progress_data(payload: dict[str, object]):
    """把 current_stage_summary 的 payload 反向构造成 progress_data dict（供 next_action_suggestion 用）。

    无 stages 字段（inferred-from-files 模式）时返回 None。
    """
    stages = payload.get("stages")
    if not isinstance(stages, dict) or not stages:
        return None
    return {
        "project": payload.get("project", ""),
        "trace_id": payload.get("trace_id", ""),
        "current_stage": payload.get("current_stage"),
        "stages": {
            stage_id: {"status": status}
            for stage_id, status in stages.items()
            if isinstance(status, str)
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "check":
            findings = check_project(root)
            payload = {"findings": findings, "summary": summarize_findings(findings)}
            emit(payload, args.json)
            return EXIT_BLOCKED if payload["summary"]["blocked"] else EXIT_OK
        if args.command == "trace":
            payload = trace_project(root)
            emit(payload, args.json)
            return EXIT_BLOCKED if payload["status"] != "pass" else EXIT_OK
        if args.command == "status":
            status_path = Path(args.status_file).resolve() if args.status_file else None
            payload = status_summary(root, status_path)
            emit(payload, args.json)
            return EXIT_OK
        if args.command == "dry-run":
            payload = dry_run(root)
            emit_dry_run(payload, args.json)
            summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
            return EXIT_BLOCKED if summary.get("blocked", 0) else EXIT_OK
        if args.command == "progress":
            payload = current_stage_summary(root)
            # 注入 next_action_suggestion：让 AI 知道现在该请示用户什么
            gate_statuses = _collect_gate_statuses(payload, root)
            payload["next_action_suggestion"] = next_action_suggestion(
                _payload_to_progress_data(payload),
                gate_statuses,
            )
            emit(payload, args.json)
            return EXIT_OK
        if args.command == "plan":
            payload = plan_summary(root)
            emit(payload, args.json)
            return EXIT_INPUT if payload.get("status") == "invalid" else EXIT_OK
        if args.command == "governance":
            payload = governance_summary(root)
            emit(payload, args.json)
            return EXIT_INPUT if payload.get("status") == "invalid" else EXIT_OK
        if args.command == "report":
            payload = project_health_report(root)
            emit(payload, args.json)
            return EXIT_BLOCKED if payload.get("health") == "blocked" else EXIT_OK
        if args.command == "revert":
            payload = revert_step(root, args.step)
            emit(payload, args.json)
            return EXIT_OK if not payload.get("error") else EXIT_INPUT
        return EXIT_INPUT
    except ProgressParseError as exc:
        # project-progress.yaml 结构错误：退出码 2（输入错误）
        emit({"error": str(exc), "type": "progress_parse_error"}, args.json)
        return EXIT_INPUT
    except (OSError, UnicodeError, ValueError) as exc:
        emit({"error": str(exc)}, args.json)
        return EXIT_INPUT
    except Exception as exc:  # pragma: no cover - 防止 CLI 泄漏堆栈
        emit({"error": str(exc)}, args.json)
        return EXIT_INTERNAL


if __name__ == "__main__":
    sys.exit(main())
