"""CLI 合约测试：progress 命令遇到损坏文件退出码 2。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ProgressCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        # 通过模块入口运行，避免依赖系统 PATH 中的 delivery 命令
        cmd = [sys.executable, "-m", "scripts.delivery_flow.cli", *args, "--json"]
        return subprocess.run(cmd, cwd="D:/code/delivery-flow", capture_output=True, text=True)

    def test_progress_exit_code_on_malformed_yaml(self):
        # 损坏 YAML → 退出码 2（输入错误），不是 0
        (self.root / "project-progress.yaml").write_text(
            "not valid: yaml: : :",
            encoding="utf-8",
        )
        proc = self._run("progress", "--root", str(self.root))
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload.get("type"), "progress_parse_error")

    def test_progress_exit_code_on_missing_required_fields(self):
        # 缺少 project 字段 → 退出码 2
        (self.root / "project-progress.yaml").write_text(
            "current_stage: requirements\nstages:\n  requirements:\n    status: pending\n",
            encoding="utf-8",
        )
        proc = self._run("progress", "--root", str(self.root))
        self.assertEqual(proc.returncode, 2)

    def test_progress_exit_code_zero_when_missing_file(self):
        # 文件不存在（全新项目）应回退到产物扫描，正常退出码 0
        proc = self._run("progress", "--root", str(self.root))
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["source"], "inferred-from-files")


class DryRunCliTests(unittest.TestCase):
    """dry-run 命令的 CLI 合约：create/update/skip/orphan 输出 + 退出码。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", "scripts.delivery_flow.cli", *args, "--json"]
        return subprocess.run(cmd, cwd="D:/code/delivery-flow", capture_output=True, text=True)

    def test_dry_run_exit_zero_when_no_blockers(self):
        # manifest + mapping 齐全 + 所有门禁通过 → exit 0
        (self.root / "_映射表.json").write_text(
            json.dumps({"tasklists": {"模块": {
                "guid": "list-1",
                "parent_tasks": {"Story A": {"guid": "p1", "subtasks": {"A-1": "task-1"}}},
            }}}),
            encoding="utf-8",
        )
        # 提供全套门禁产物
        (self.root / "客户确认记录-full.md").write_text(
            "# 客户确认\n\n放行结论：放行\n- 客户代表：王经理\n- 确认方式：邮件\n- 确认时间：2026-08-01\n",
            encoding="utf-8",
        )
        (self.root / "技术就绪-full.md").write_text(
            "# readiness\n\n## 结论\n\n结论：通过\n",
            encoding="utf-8",
        )
        for n in ("业务", "产品", "技术", "数据"):
            (self.root / f"{n}架构.md").write_text(f"# {n}架构", encoding="utf-8")
        (self.root / "project-progress.yaml").write_text(
            'project: "测试"\ncurrent_stage: "feishu_sync"\nstages:\n'
            '  opportunity:\n    status: pending\n  proposal:\n    status: pending\n'
            '  deal_gate:\n    status: pending\n'
            '  requirements:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  analysis:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  prd:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  ux:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  prototype:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  client_gate:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  architecture:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  tech_readiness:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  story_breakdown:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  feishu_sync:\n    status: in_progress\n'
            '  development:\n    status: pending\n  eval:\n    status: pending\n'
            '  qa:\n    status: pending\n  acceptance_gate:\n    status: pending\n',
            encoding="utf-8",
        )
        (self.root / "stories").mkdir(exist_ok=True)
        (self.root / "stories" / "story-a.md").write_text(
            "# Story A\n\n## 做什么\n\nA\n\n## DoD/AC\n\n- AC1\n\n## 交付物\n\nA 交付\n",
            encoding="utf-8",
        )
        # manifest 含 A-1，mapping 旧格式缺 synced → create_with_review（不计入 blocked）
        import hashlib, json as _j
        h = hashlib.sha256(_j.dumps({"what": "W1", "dod": "D1", "deliverable": "X1", "spec_ref": ""},
                                    ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        (self.root / "desired-tasks.json").write_text(_j.dumps({
            "project": "测试",
            "generated_at": "2026-08-01",
            "tasks": [{"local_id": "A-1", "tasklist": "模块", "parent_task": "Story A",
                        "what": "W1", "dod": "D1", "deliverable": "X1", "content_hash": h}],
        }, ensure_ascii=False), encoding="utf-8")
        proc = self._run("dry-run", "--root", str(self.root))
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertIn("operations", payload)
        self.assertIn("summary", payload)
        self.assertEqual(payload["network"], False)

    def test_dry_run_exit_one_when_blocked(self):
        # 映射表缺失 → exit 1 (BLOCKED)
        proc = self._run("dry-run", "--root", str(self.root))
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertGreater(payload["summary"]["blocked"], 0)

    def test_dry_run_exit_one_when_mapping_invalid(self):
        # 映射表结构错误 → exit 1
        (self.root / "_映射表.json").write_text(
            json.dumps({"tasklists": {"模块": {"parent_tasks": {}}}}),
            encoding="utf-8",
        )
        proc = self._run("dry-run", "--root", str(self.root))
        self.assertEqual(proc.returncode, 1)


class LauncherEntrypointTests(unittest.TestCase):
    """delivery.py 启动器：在插件仓库外的临时目录调用，验证路径独立性。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo_root = Path(__file__).resolve().parents[2]
        self.launcher = self.repo_root / "delivery.py"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        # 在临时目录跑 launcher，模拟 Skill 内 ${CLAUDE_PLUGIN_ROOT} 调用
        return subprocess.run(
            [sys.executable, str(self.launcher), *args, "--json"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )

    def test_launcher_help_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(self.launcher), "--help"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("delivery-flow", proc.stdout)

    def test_launcher_check_blocks_empty_project(self):
        # 空项目目录无任何产物 → 阻断，退出码 1
        proc = self._run("check", "--root", str(self.root))
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["summary"]["blocked"])

    def test_launcher_progress_falls_back_when_missing(self):
        # 无 project-progress.yaml → 回退到推断，退出码 0
        proc = self._run("progress", "--root", str(self.root))
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["source"], "inferred-from-files")


if __name__ == "__main__":
    unittest.main()