import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.delivery_flow.core import (
    check_project,
    governance_summary,
    plan_summary,
    project_health_report,
    validate_project_governance,
    validate_project_plan,
)


class PlanGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_plan(self):
        (self.root / "project-plan.json").write_text(json.dumps({
            "project": "二课",
            "version": "v0.1",
            "team_size": 2,
            "current_phase": "phase-01",
            "phases": [
                {
                    "id": "phase-01",
                    "name": "底座",
                    "status": "in_progress",
                    "dependencies": [],
                    "parallel_with": ["phase-02"],
                    "completion_criteria": ["通过阶段验收"],
                },
                {
                    "id": "phase-02",
                    "name": "设置",
                    "status": "pending",
                    "dependencies": [],
                    "completion_criteria": ["通过阶段验收"],
                },
                {
                    "id": "phase-03",
                    "name": "活动",
                    "status": "pending",
                    "dependencies": ["phase-01"],
                    "completion_criteria": ["通过阶段验收"],
                },
            ],
        }, ensure_ascii=False), encoding="utf-8")

    def test_plan_summary_reports_ready_and_dependency_blocked(self):
        self._write_plan()
        result = plan_summary(self.root)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["team_size"], 2)
        self.assertIn("phase-02", result["ready_phases"])
        self.assertEqual(result["dependency_blocked"]["phase-03"], ["phase-01"])

    def test_invalid_plan_rejects_missing_criteria(self):
        self.assertTrue(validate_project_plan({
            "project": "测试", "version": "v0.1", "team_size": 2,
            "phases": [{"id": "p1", "name": "阶段", "status": "pending", "dependencies": []}],
        }))

    def test_governance_summary_exposes_blockers(self):
        (self.root / "project-governance.json").write_text(json.dumps({
            "version": "v0.1",
            "risks": [{"id": "R-001", "priority": "P0", "title": "目录冲突", "status": "open",
                       "impact": "返工", "evidence": ["确认清单"]}],
            "issues": [{"id": "I-001", "title": "接口未定", "status": "blocked",
                        "impact": "阻塞", "evidence": ["会议纪要"], "resolution_condition": "完成确认"}],
            "changes": [{"id": "C-001", "title": "范围变更", "status": "open", "approval": "pending",
                         "impact": "影响计划", "evidence": ["邮件"], "affected_artifacts": ["SPEC.md"]}],
            "decisions": [],
        }, ensure_ascii=False), encoding="utf-8")
        result = governance_summary(self.root)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["open_p0_risks"][0]["id"], "R-001")
        self.assertEqual(result["blocked_issues"][0]["id"], "I-001")
        self.assertEqual(result["pending_change_count"], 1)

    def test_check_blocks_governance_items_when_file_is_enabled(self):
        (self.root / "project-governance.json").write_text(json.dumps({
            "version": "v0.1", "risks": [{"id": "R-001", "priority": "P0", "title": "风险",
            "status": "open", "impact": "高", "evidence": ["risk.md"]}],
            "issues": [], "changes": [], "decisions": [],
        }, ensure_ascii=False), encoding="utf-8")
        findings = check_project(self.root)
        ids = {item["id"] for item in findings}
        self.assertIn("governance.p0-risk", ids)
        self.assertTrue(any(item["status"] == "fail" for item in findings if item["id"] == "governance.p0-risk"))

    def test_report_cli_returns_blocked_health(self):
        (self.root / "project-governance.json").write_text(json.dumps({
            "version": "v0.1", "risks": [{"id": "R-001", "priority": "P0", "title": "风险",
            "status": "open", "impact": "高", "evidence": ["risk.md"]}],
            "issues": [], "changes": [], "decisions": [],
        }, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.delivery_flow.cli", "report", "--root", str(self.root), "--json"],
            cwd="D:/code/delivery-flow", capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["health"], "blocked")


if __name__ == "__main__":
    unittest.main()
