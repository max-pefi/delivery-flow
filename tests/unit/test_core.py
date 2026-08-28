import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.delivery_flow.core import (
    ProgressParseError,
    check_project,
    current_stage_summary,
    dry_run,
    find_first,
    layout_scan,
    next_action_suggestion,
    parse_acceptance,
    parse_confirmation,
    parse_evaluation,
    parse_readiness,
    parse_story,
    read_progress,
    read_trace_id,
    resolve_artifact,
    revert_step,
    status_summary,
    summarize_findings,
    stage_next_drafts,
    trace_project,
    validate_progress,
    _classify_filename,
    _is_excluded,
)


class DeliveryCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "SPEC.md").write_text(
            "# SPEC\n\n## Why\n问题\n## Capabilities\n能力\n## Constraints\n约束\n## Non-goals\n不做\n## Success signal\n成功\n",
            encoding="utf-8",
        )
        (self.root / "客户确认记录-2026-07-31.md").write_text("# 客户确认", encoding="utf-8")
        (self.root / "技术就绪-readiness.md").write_text("# readiness", encoding="utf-8")
        (self.root / "验收报告-2026-07-31.md").write_text("# 验收报告", encoding="utf-8")
        (self.root / "评测报告-2026-07-31.md").write_text("# 评测报告", encoding="utf-8")
        (self.root / "stories").mkdir()
        (self.root / "stories" / "story-a.md").write_text("# Story A\nAC", encoding="utf-8")
        (self.root / "_映射表.json").write_text(
            json.dumps({"tasklists": {"模块": {"guid": "list-1", "parent_tasks": {"Story A": {"guid": "parent-1", "subtasks": {"A-1": "task-1"}}}}}}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_check_passes_complete_fixture(self):
        # SPEC 五字段 + 映射表 GUID 完整能通过（关卡类条目在 placeholder 状态下应为 unknown）
        findings = check_project(self.root)
        # 结构性条目应 pass
        structural_pass = [f for f in findings if f["id"] in ("spec.fields", "mapping.valid")]
        self.assertTrue(all(f["status"] == "pass" for f in structural_pass))
        # 关卡类在 placeholder 状态下必须 unknown，不能 pass
        gate_unknown = [f for f in findings if f["id"].startswith("gate.")]
        self.assertTrue(all(f["status"] == "unknown" for f in gate_unknown))

    def test_trace_reports_complete_chain(self):
        (self.root / "[01] 业务架构.md").write_text("# 业务架构", encoding="utf-8")
        result = trace_project(self.root)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["mapped_subtask_count"], 1)

    def test_dry_run_has_no_side_effect(self):
        before = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        result = dry_run(self.root)
        after = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        self.assertFalse(result["side_effects"])
        self.assertEqual(before, after)
        self.assertFalse(result["network"])

    def test_status_marks_local_mirror(self):
        status = self.root / "sprint-status.yaml"
        status.write_text("- story: A-1\n  status: done\n", encoding="utf-8")
        result = status_summary(self.root)
        self.assertEqual(result["source"], "local-read-only-mirror")
        self.assertEqual(result["authority"], "feishu")
        self.assertEqual(result["status_counts"], {"done": 1})

    def test_read_progress_parses_yaml(self):
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "测试项目"\ncurrent_stage: "client_gate"\nstages:\n'
            '  requirements:\n    status: done\n    completed_at: "2026-07-20"\n'
            '  client_gate:\n    status: in_progress\n    started_at: "2026-07-30"\n'
            '  architecture:\n    status: pending\n',
            encoding="utf-8",
        )
        result = read_progress(progress_file)
        self.assertIsNotNone(result)
        self.assertEqual(result["project"], "测试项目")
        self.assertEqual(result["current_stage"], "client_gate")
        self.assertEqual(result["stages"]["requirements"]["status"], "done")
        self.assertEqual(result["stages"]["architecture"]["status"], "pending")

    def test_read_progress_returns_none_when_missing(self):
        result = read_progress(self.root / "nonexistent.yaml")
        self.assertIsNone(result)

    def test_progress_summary_from_file(self):
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "architecture"\nstages:\n'
            '  opportunity:\n    status: pending\n  proposal:\n    status: pending\n'
            '  deal_gate:\n    status: pending\n'
            '  requirements:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  analysis:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  prd:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  ux:\n    status: pending\n  prototype:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  client_gate:\n    status: done\n    completed_at: "2026-08-01"\n'
            '  architecture:\n    status: in_progress\n'
            '  tech_readiness:\n    status: pending\n'
            '  story_breakdown:\n    status: pending\n  feishu_sync:\n    status: pending\n'
            '  development:\n    status: pending\n  eval:\n    status: pending\n'
            '  qa:\n    status: pending\n  acceptance_gate:\n    status: pending\n',
            encoding="utf-8",
        )
        result = current_stage_summary(self.root)
        self.assertEqual(result["source"], "project-progress.yaml")
        self.assertEqual(result["current_stage"], "architecture")
        self.assertEqual(result["completed_count"], 5)
        self.assertEqual(result["next_stage"], "tech_readiness")

    def test_progress_summary_fallback_to_files(self):
        # 没有 progress.yaml 时回退到产物扫描
        result = current_stage_summary(self.root)
        self.assertEqual(result["source"], "inferred-from-files")
        self.assertIn("note", result)

    # —— 售前上游：Trace 根与上游链路 ——

    def test_read_trace_id_from_spec_header(self):
        # 商机编号写在 SPEC.md 头部引用行时优先读取
        (self.root / "SPEC.md").write_text(
            "> 商机编号: OPP-2026-007\n\n# SPEC\n\n## Why\n问题\n",
            encoding="utf-8",
        )
        self.assertEqual(read_trace_id(self.root), "OPP-2026-007")

    def test_read_trace_id_fallback_to_progress(self):
        # SPEC 无引用行时回退到 project-progress.yaml 顶层 trace_id
        (self.root / "project-progress.yaml").write_text(
            'project: "示例"\ntrace_id: "OPP-2026-009"\ncurrent_stage: "requirements"\nstages:\n'
            '  requirements:\n    status: in_progress\n',
            encoding="utf-8",
        )
        self.assertEqual(read_trace_id(self.root), "OPP-2026-009")

    def test_read_trace_id_absent(self):
        # 既无 SPEC 引用行也无 progress 时返回空串（不伪造）
        self.assertEqual(read_trace_id(self.root), "")

    def test_trace_includes_upstream_when_trace_id_present(self):
        # 存在商机编号 Trace 根时，链路向上游延伸到商机/签约
        (self.root / "SPEC.md").write_text(
            "> 商机编号: OPP-2026-001\n\n# SPEC\n\n## Why\n问题\n## Capabilities\n能力\n"
            "## Constraints\n约束\n## Non-goals\n不做\n## Success signal\n成功\n",
            encoding="utf-8",
        )
        (self.root / "商机档案-2026-07-10.md").write_text("# 商机档案", encoding="utf-8")
        (self.root / "立项包.md").write_text("# 立项包", encoding="utf-8")
        (self.root / "[01] 业务架构.md").write_text("# 业务架构", encoding="utf-8")
        result = trace_project(self.root)
        self.assertEqual(result["trace_id"], "OPP-2026-001")
        self.assertIn("opportunity", result["links"])
        self.assertIn("deal", result["links"])
        self.assertTrue(result["links"]["opportunity"])
        self.assertTrue(result["links"]["deal"])
        self.assertEqual(result["status"], "pass")

    def test_trace_reports_missing_upstream(self):
        # 有 Trace 根但缺立项包时，如实报告缺链而非隐藏
        (self.root / "SPEC.md").write_text(
            "> 商机编号: OPP-2026-002\n\n# SPEC\n\n## Why\n问题\n## Capabilities\n能力\n"
            "## Constraints\n约束\n## Non-goals\n不做\n## Success signal\n成功\n",
            encoding="utf-8",
        )
        (self.root / "商机档案-2026-07-10.md").write_text("# 商机档案", encoding="utf-8")
        result = trace_project(self.root)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("deal", result["missing"])

    def test_trace_omits_upstream_without_trace_id(self):
        # 无售前的存量项目（无商机编号）不应被判定缺上游链路
        result = trace_project(self.root)
        self.assertEqual(result["trace_id"], "")
        self.assertNotIn("opportunity", result["links"])
        self.assertNotIn("deal", result["links"])

    def test_progress_summary_recognizes_presales_stages(self):
        # project-progress.yaml 覆盖售前上游三阶段（带全部 17 阶段）
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ntrace_id: "OPP-2026-001"\ncurrent_stage: "proposal"\nstages:\n'
            '  opportunity:\n    status: done\n    completed_at: "2026-07-10"\n'
            '  proposal:\n    status: in_progress\n'
            '  deal_gate:\n    status: pending\n'
            '  requirements:\n    status: pending\n  analysis:\n    status: pending\n'
            '  prd:\n    status: pending\n  ux:\n    status: pending\n'
            '  prototype:\n    status: pending\n  client_gate:\n    status: pending\n'
            '  architecture:\n    status: pending\n  tech_readiness:\n    status: pending\n'
            '  story_breakdown:\n    status: pending\n  feishu_sync:\n    status: pending\n'
            '  development:\n    status: pending\n  eval:\n    status: pending\n'
            '  qa:\n    status: pending\n  acceptance_gate:\n    status: pending\n',
            encoding="utf-8",
        )
        result = current_stage_summary(self.root)
        self.assertEqual(result["trace_id"], "OPP-2026-001")
        self.assertEqual(result["current_stage"], "proposal")
        self.assertEqual(result["next_stage"], "deal_gate")
        self.assertEqual(result["total_stages"], 17)

    def test_progress_summary_fallback_recognizes_presales(self):
        # 无 progress.yaml 时，产物扫描能识别售前阶段产物
        (self.root / "商机档案-2026-07-10.md").write_text("# 商机档案", encoding="utf-8")
        (self.root / "报价单-2026-07-12.md").write_text("# 报价单", encoding="utf-8")
        # 移除下游产物，确保推断停在售前
        (self.root / "stories" / "story-a.md").unlink()
        (self.root / "stories").rmdir()
        (self.root / "_映射表.json").unlink()
        (self.root / "客户确认记录-2026-07-31.md").unlink()
        (self.root / "技术就绪-readiness.md").unlink()
        (self.root / "验收报告-2026-07-31.md").unlink()
        (self.root / "评测报告-2026-07-31.md").unlink()
        result = current_stage_summary(self.root)
        self.assertEqual(result["source"], "inferred-from-files")
        self.assertEqual(result["current_stage"], "proposal")

    # —— 四层架构文档识别 ——

    def _clear_downstream_products(self):
        """清理架构阶段之后的下游产物，用于隔离测试架构阶段推断"""
        for f in ("客户确认记录-2026-07-31.md", "技术就绪-readiness.md",
                  "验收报告-2026-07-31.md", "评测报告-2026-07-31.md"):
            p = self.root / f
            if p.exists():
                p.unlink()
        stories_dir = self.root / "stories"
        if stories_dir.exists():
            for f in stories_dir.iterdir():
                f.unlink()
            stories_dir.rmdir()
        mapping = self.root / "_映射表.json"
        if mapping.exists():
            mapping.unlink()

    def test_progress_summary_recognizes_four_layer_architecture(self):
        # 存在业务架构文档时，推断当前阶段为 architecture → tech_readiness
        self._clear_downstream_products()
        (self.root / "[01] 业务架构.md").write_text("# 业务架构", encoding="utf-8")
        (self.root / "readiness-report.md").write_text("# readiness", encoding="utf-8")
        result = current_stage_summary(self.root)
        self.assertEqual(result["source"], "inferred-from-files")
        self.assertEqual(result["current_stage"], "tech_readiness")

    def test_progress_summary_architecture_from_product_arch(self):
        # 仅有产品架构文档时，也能识别 architecture 阶段
        self._clear_downstream_products()
        (self.root / "[02] 产品架构.md").write_text("# 产品架构", encoding="utf-8")
        result = current_stage_summary(self.root)
        self.assertEqual(result["source"], "inferred-from-files")
        self.assertEqual(result["current_stage"], "architecture")

    def test_trace_includes_architecture_link(self):
        # 追溯链应包含 architecture 链接
        result = trace_project(self.root)
        self.assertIn("architecture", result["links"])
        # 无架构文档时，architecture 链接应为 False
        self.assertFalse(result["links"]["architecture"])

    def test_trace_architecture_present(self):
        # 存在四层架构文档时，追溯链中 architecture 应为 True
        (self.root / "[01] 业务架构.md").write_text("# 业务架构", encoding="utf-8")
        (self.root / "[02] 产品架构.md").write_text("# 产品架构", encoding="utf-8")
        (self.root / "[03] 技术架构.md").write_text("# 技术架构", encoding="utf-8")
        (self.root / "[04] 数据架构.md").write_text("# 数据架构", encoding="utf-8")
        result = trace_project(self.root)
        self.assertTrue(result["links"]["architecture"])

    def test_check_recognizes_business_architecture(self):
        # check_project 应能识别四层架构（业务/产品/技术/数据）
        (self.root / "[01] 业务架构.md").write_text("# 业务架构", encoding="utf-8")
        (self.root / "[02] 产品架构.md").write_text("# 产品架构", encoding="utf-8")
        (self.root / "[03] 技术架构.md").write_text("# 技术架构", encoding="utf-8")
        (self.root / "[04] 数据架构.md").write_text("# 数据架构", encoding="utf-8")
        findings = check_project(self.root)
        arch_findings = [f for f in findings if f["id"] == "arch.business"]
        self.assertEqual(len(arch_findings), 1)
        self.assertEqual(arch_findings[0]["status"], "pass")

    # —— 阶段二：统一机器文件路径 + 兼容旧目录 ——

    def test_is_excluded_blocks_skill_and_template_paths(self):
        # skills/、_bmad/、.claude/ 目录下的产物应被排除
        skills_dir = self.root / "skills"
        skills_dir.mkdir()
        fake = skills_dir / "demo.md"
        fake.write_text("# demo", encoding="utf-8")
        self.assertTrue(_is_excluded(fake))
        bmad_dir = self.root / "_bmad" / "core"
        bmad_dir.mkdir(parents=True)
        fake2 = bmad_dir / "agent.md"
        fake2.write_text("# agent", encoding="utf-8")
        self.assertTrue(_is_excluded(fake2))
        # 模板/示范文件也应被排除——用 unicode 转义避免 cp936 乱码
        tpl_name = "PRD" + "模板" + ".md"  # PRD模板.md
        tpl = self.root / tpl_name
        tpl.write_text("# tpl", encoding="utf-8")
        self.assertTrue(_is_excluded(tpl))
        demo_name = "示范子项目" + ".md"  # 示例子项目.md
        demo = self.root / demo_name
        demo.write_text("# demo", encoding="utf-8")
        self.assertTrue(_is_excluded(demo))

    def test_find_first_skills_directory_ignored(self):
        # skills/ 目录下的同名文件不应被误识别为业务产物
        # 先清理根目录的同名产物（setUp 已创建客户确认记录）
        (self.root / "客户确认记录-2026-07-31.md").unlink()
        skills_dir = self.root / "skills" / "delivery-check"
        skills_dir.mkdir(parents=True)
        (skills_dir / "客户确认记录.md").write_text("# fake", encoding="utf-8")
        result = find_first(self.root, ("*客户确认*.md", "**/*客户确认*.md"))
        self.assertIsNone(result)

    def test_resolve_artifact_root_layout(self):
        # 推荐布局：机器文件放项目根
        self.assertEqual(resolve_artifact(self.root, "SPEC.md"), (self.root / "SPEC.md", "root"))
        spec_only = self.root / "project-progress.yaml"
        spec_only.write_text("project: x\ncurrent_stage: requirements\n", encoding="utf-8")
        self.assertEqual(resolve_artifact(self.root, "project-progress.yaml"), (spec_only, "root"))

    def test_resolve_artifact_legacy_meta_layout(self):
        # 旧布局：项目根无文件，文件在 `_meta/` 下
        spec_in_meta = self.root / "_meta" / "project-progress.yaml"
        spec_in_meta.parent.mkdir()
        spec_in_meta.write_text("project: x\ncurrent_stage: requirements\n", encoding="utf-8")
        # 同时存在根版本时，根优先
        root_progress = self.root / "project-progress.yaml"
        root_progress.write_text("project: x\ncurrent_stage: requirements\n", encoding="utf-8")
        self.assertEqual(resolve_artifact(self.root, "project-progress.yaml"), (root_progress, "root"))
        # 删除根版本后才回退到 `_meta/`
        root_progress.unlink()
        self.assertEqual(resolve_artifact(self.root, "project-progress.yaml"), (spec_in_meta, "legacy"))

    def test_resolve_artifact_stage_dir_layout(self):
        # 阶段目录布局：SPEC.md 在 04-需求分析 下
        stage_dir = self.root / "04-需求分析"
        stage_dir.mkdir()
        spec_in_stage = stage_dir / "SPEC.md"
        spec_in_stage.write_text("# SPEC\n## Why\n## Capabilities\n## Constraints\n## Non-goals\n## Success signal\n", encoding="utf-8")
        # 项目根无 SPEC.md，应回退到阶段目录
        (self.root / "SPEC.md").unlink()
        self.assertEqual(resolve_artifact(self.root, "SPEC.md"), (spec_in_stage, "stage"))

    def test_resolve_artifact_missing(self):
        # 三处都没有时返回 (None, "missing")
        (self.root / "SPEC.md").unlink(missing_ok=True)
        self.assertEqual(resolve_artifact(self.root, "SPEC.md"), (None, "missing"))

    def test_check_uses_stage_layout_spec(self):
        # SPEC 在 04-需求分析 阶段目录时仍能识别五字段
        (self.root / "SPEC.md").unlink()
        stage_dir_name = "04-" + "需求分析"  # 04-需求分析
        stage_dir = self.root / stage_dir_name
        stage_dir.mkdir()
        (stage_dir / "SPEC.md").write_text(
            "# SPEC\n## Why\n问题\n## Capabilities\n能力\n## Constraints\n）"
            "约束\n## Non-goals\n不做\n## Success signal\n成功\n",
            encoding="utf-8",
        )
        findings = check_project(self.root)
        spec_findings = [f for f in findings if f["id"].startswith("spec.")]
        self.assertTrue(spec_findings)
        self.assertEqual(spec_findings[0]["status"], "pass")
        # Windows 路径分隔符统一用正斜杠校验
        evidence = spec_findings[0]["evidence"][0].replace("\\", "/")
        self.assertIn("04-需求分析/SPEC.md", evidence)

    def test_check_uses_legacy_meta_spec(self):
        # SPEC 在 `_meta/` 旧路径时仍能识别
        (self.root / "SPEC.md").unlink()
        meta = self.root / "_meta"
        meta.mkdir()
        (meta / "SPEC.md").write_text(
            "# SPEC\n## Why\n问题\n## Capabilities\n能力\n## Constraints\n约束"
            "\n## Non-goals\n不做\n## Success signal\n成功\n",
            encoding="utf-8",
        )
        findings = check_project(self.root)
        spec_findings = [f for f in findings if f["id"].startswith("spec.")]
        self.assertEqual(spec_findings[0]["status"], "pass")
        evidence = spec_findings[0]["evidence"][0].replace("\\", "/")
        self.assertIn("_meta/SPEC.md", evidence)

    def test_status_summary_uses_stage_layout(self):
        # sprint-status.yaml 在 07-开发 阶段目录时仍能读到
        stage_dir = self.root / "07-开发"
        stage_dir.mkdir()
        (stage_dir / "sprint-status.yaml").write_text("- story: A-1\n  status: done\n", encoding="utf-8")
        result = status_summary(self.root)
        self.assertEqual(result["path_source"], "stage")
        self.assertIn("07-开发", result["path"])
        self.assertEqual(result["status_counts"], {"done": 1})

    def test_current_stage_summary_uses_legacy_layout(self):
        # project-progress.yaml 在 `_meta/` 时仍能读到
        meta = self.root / "_meta"
        meta.mkdir()
        (meta / "project-progress.yaml").write_text(
            'project: "示例"\ntrace_id: "OPP-2026-007"\ncurrent_stage: "requirements"\nstages:\n'
            '  opportunity:\n    status: pending\n  proposal:\n    status: pending\n'
            '  deal_gate:\n    status: pending\n'
            '  requirements:\n    status: in_progress\n'
            '  analysis:\n    status: pending\n  prd:\n    status: pending\n'
            '  ux:\n    status: pending\n  prototype:\n    status: pending\n'
            '  client_gate:\n    status: pending\n  architecture:\n    status: pending\n'
            '  tech_readiness:\n    status: pending\n  story_breakdown:\n    status: pending\n'
            '  feishu_sync:\n    status: pending\n  development:\n    status: pending\n'
            '  eval:\n    status: pending\n  qa:\n    status: pending\n'
            '  acceptance_gate:\n    status: pending\n',
            encoding="utf-8",
        )
        result = current_stage_summary(self.root)
        self.assertEqual(result["source"], "project-progress.yaml")
        self.assertEqual(result["source_layout"], "legacy")
        self.assertEqual(result["current_stage"], "requirements")

    def test_current_stage_summary_rejects_invalid_stage(self):
        # 损坏 progress：current_stage 不在合法列表中时抛 ProgressParseError
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "totally_made_up"\nstages:\n'
            '  requirements:\n    status: pending\n',
            encoding="utf-8",
        )
        with self.assertRaises(ProgressParseError) as ctx:
            current_stage_summary(self.root)
        self.assertIn("totally_made_up", str(ctx.exception))

    def test_trace_reports_hit_paths(self):
        # trace_project 应返回每个 link 的实际命中路径
        result = trace_project(self.root)
        self.assertIn("paths", result)
        self.assertIn("mapping_source", result)
        self.assertTrue(result["paths"]["spec"])
        self.assertEqual(result["mapping_source"], "root")

    def test_trace_id_from_stage_layout_spec(self):
        # SPEC 在阶段目录时仍能读取商机编号
        (self.root / "SPEC.md").unlink()
        stage_dir = self.root / "04-需求分析"
        stage_dir.mkdir()
        (stage_dir / "SPEC.md").write_text(
            "> 商机编号: OPP-2026-077\n\n# SPEC\n\n## Why\n",
            encoding="utf-8",
        )
        self.assertEqual(read_trace_id(self.root), "OPP-2026-077")

    def test_dry_run_reports_mapping_source(self):
        # dry_run 应返回 mapping 实际来源
        result = dry_run(self.root)
        self.assertEqual(result["mapping_source"], "root")

    # —— 阶段三：project-progress 状态模型 ——

    def test_progress_template_is_all_pending(self):
        # 模板必须是全新项目状态：current_stage=requirements + 其他阶段 pending
        import yaml
        from pathlib import Path as _P
        tpl_path = _P("templates/project-progress模板.yaml")
        if not tpl_path.exists():
            self.skipTest("模板文件不存在")
        # 模板可能含 {{项目名}} 占位符，需替换
        text = tpl_path.read_text(encoding="utf-8").replace('"{{项目名}}"', '"测试"')
        data = yaml.safe_load(text)
        # 当前阶段应为 requirements
        self.assertEqual(data["current_stage"], "requirements")
        # trace_id 必须空字符串或不存在
        self.assertIn(data.get("trace_id", ""), ("", None))
        # current_stage 对应阶段必须 in_progress（validate_progress 拒绝 pending current）
        self.assertEqual(data["stages"]["requirements"]["status"], "in_progress",
                         "current_stage=requirements 的 status 必须 in_progress，否则 validate_progress 拒收")
        # 其他阶段必须 pending
        for stage_id, stage_data in data["stages"].items():
            if stage_id == "requirements":
                continue
            self.assertEqual(
                stage_data["status"], "pending",
                f"阶段 {stage_id} 应为 pending，实际为 {stage_data.get('status')}",
            )
        # 不能保留 completed_at / gate_evidence / started_at 示范数据
        for stage_data in data["stages"].values():
            self.assertNotIn("completed_at", stage_data)
            self.assertNotIn("started_at", stage_data)
            self.assertNotIn("gate_evidence", stage_data)

    def test_read_progress_accepts_null_current_stage(self):
        # current_stage: null 表示验收完成态
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: null\ntrace_id: "OPP-2026-099"\n'
            'stages:\n  acceptance_gate:\n    status: done\n    completed_at: "2026-08-04"\n'
            '  eval:\n    status: done\n    completed_at: "2026-08-03"\n',
            encoding="utf-8",
        )
        result = read_progress(progress_file)
        self.assertIsNotNone(result)
        self.assertIsNone(result["current_stage"])
        self.assertEqual(result["trace_id"], "OPP-2026-099")

    def test_read_progress_accepts_meta_segment(self):
        # meta 段是可选透传段（mode / modules / complexity / snapshot_at）
        # 解析器应接受 meta 顶层 key,不应污染 stages
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "development"\n'
            'meta:\n  mode: delivery\n  modules: ["第二课堂首期"]\n'
            '  complexity: medium\n  snapshot_at: "2026-08-21"\n'
            'stages:\n'
            '  opportunity: {status: pending}\n'
            '  proposal: {status: pending}\n'
            '  deal_gate: {status: pending}\n'
            '  requirements:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  analysis:\n    status: done\n    completed_at: "2026-08-11"\n'
            '  prd:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  ux:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  prototype:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  client_gate:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  architecture:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  tech_readiness:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  story_breakdown:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  feishu_sync:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  development:\n    status: in_progress\n    started_at: "2026-08-14"\n'
            '  eval: {status: pending}\n'
            '  qa: {status: pending}\n'
            '  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        result = read_progress(progress_file)
        self.assertIsNotNone(result)
        # meta 段被识别(简化解析器只做"key 出现"的事实记录)
        self.assertEqual(result["meta"], {"present": True})
        # stages 不应被 meta 子字段污染
        self.assertNotIn("mode", result["stages"])
        self.assertNotIn("modules", result["stages"])
        self.assertNotIn("complexity", result["stages"])
        self.assertNotIn("snapshot_at", result["stages"])
        # 正常 stage 仍在
        self.assertEqual(result["stages"]["development"]["status"], "in_progress")
        # validate_progress 也应通过
        errors = validate_progress(result)
        self.assertEqual(errors, [])

    def test_read_progress_without_meta_still_works(self):
        # 向后兼容:无 meta 段的项目文件仍能正常解析
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "development"\n'
            'stages:\n'
            '  opportunity: {status: pending}\n'
            '  proposal: {status: pending}\n'
            '  deal_gate: {status: pending}\n'
            '  requirements:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  analysis:\n    status: done\n    completed_at: "2026-08-11"\n'
            '  prd:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  ux:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  prototype:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  client_gate:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  architecture:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  tech_readiness:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  story_breakdown:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  feishu_sync:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  development:\n    status: in_progress\n    started_at: "2026-08-14"\n'
            '  eval: {status: pending}\n'
            '  qa: {status: pending}\n'
            '  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        result = read_progress(progress_file)
        self.assertIsNotNone(result)
        # meta 缺省时 result["meta"] = {}（初始化值）
        self.assertEqual(result["meta"], {})
        self.assertEqual(result["stages"]["development"]["status"], "in_progress")

    def test_read_progress_rejects_unknown_top_level_key(self):
        # 未知顶层字段（非白名单）必须抛错——保护 schema 演进
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "development"\n'
            'foo: bar\n'
            'stages:\n  requirements:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  client_gate:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  architecture:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  tech_readiness:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  story_breakdown:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  feishu_sync:\n    status: done\n    completed_at: "2026-08-14"\n'
            '  development:\n    status: in_progress\n    started_at: "2026-08-14"\n',
            encoding="utf-8",
        )
        with self.assertRaises(ProgressParseError):
            read_progress(progress_file)

    def test_read_progress_rejects_malformed_yaml(self):
        # 损坏的 YAML 必须抛 ProgressParseError，不能返回空对象
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text("not valid: yaml: : :", encoding="utf-8")
        with self.assertRaises(ProgressParseError):
            read_progress(progress_file)

    def test_read_progress_rejects_missing_required_fields(self):
        # 缺少 project 字段必须抛错
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            "current_stage: requirements\nstages:\n  requirements:\n    status: pending\n",
            encoding="utf-8",
        )
        with self.assertRaises(ProgressParseError) as ctx:
            read_progress(progress_file)
        self.assertIn("project", str(ctx.exception))

    def test_classify_filename_baseline(self):
        # 基线文件(prd/客户确认/招标参数)→ baseline
        self.assertEqual(_classify_filename("PRD.md"), "baseline")
        self.assertEqual(_classify_filename("客户确认记录-2026-08-13.md"), "baseline")
        self.assertEqual(_classify_filename("招标参数一致性审查报告.md"), "baseline")

    def test_classify_filename_drafts(self):
        # *.draft.* / 阶段性文件 → future_plan / first_phase
        self.assertEqual(
            _classify_filename("第二课堂完整模块PRD.draft.md"), "future_plan"
        )
        self.assertEqual(
            _classify_filename("第二课堂四层架构.draft.md"), "future_plan"
        )
        self.assertEqual(
            _classify_filename("开发排期-草案.md"), "first_phase"
        )
        self.assertEqual(
            _classify_filename("后续迭代需求池.md"), "first_phase"
        )

    def test_layout_scan_empty_project(self):
        # 空项目:无文件,loose_files 应空,机器文件 present=False
        empty = self.root / "empty_subdir"
        empty.mkdir()
        result = layout_scan(empty)
        self.assertEqual(result["root"], str(empty.resolve()))
        self.assertEqual(result["loose_files"], [])
        # 机器文件全部 present=False
        self.assertTrue(all(not m["present"] for m in result["machine_files"]))
        self.assertEqual(result["warnings"], [])

    def test_layout_scan_finds_loose_files(self):
        # 散落文件应被识别并分类(用独立子目录避免 setUp 残留)
        work = self.root / "loose_subdir"
        work.mkdir()
        (work / "PRD.md").write_text("# PRD", encoding="utf-8")
        (work / "第二课堂完整模块PRD.draft.md").write_text("# 完整 PRD", encoding="utf-8")
        (work / "README.md").write_text("# 杂乱文件", encoding="utf-8")
        result = layout_scan(work)
        names = [f["name"] for f in result["loose_files"]]
        self.assertIn("PRD.md", names)
        self.assertIn("第二课堂完整模块PRD.draft.md", names)
        self.assertIn("README.md", names)
        prd_entry = next(f for f in result["loose_files"] if f["name"] == "PRD.md")
        self.assertEqual(prd_entry["theme"], "baseline")
        self.assertEqual(prd_entry["suggested_dir"], "00-总览")
        draft_entry = next(f for f in result["loose_files"] if f["name"] == "第二课堂完整模块PRD.draft.md")
        self.assertEqual(draft_entry["theme"], "future_plan")
        self.assertEqual(draft_entry["suggested_dir"], "02-完整模块规划")

    def test_layout_scan_does_not_move_machine_files(self):
        # 机器文件应只在 machine_files 列出,不应进 loose_files
        work = self.root / "machine_subdir"
        work.mkdir()
        (work / "SPEC.md").write_text("# SPEC", encoding="utf-8")
        (work / "project-progress.yaml").write_text(
            'project: "x"\ncurrent_stage: null\nstages:\n',
            encoding="utf-8",
        )
        (work / "_映射表.json").write_text("{}", encoding="utf-8")
        result = layout_scan(work)
        machine_names = {m["name"] for m in result["machine_files"]}
        self.assertIn("SPEC.md", machine_names)
        self.assertIn("project-progress.yaml", machine_names)
        self.assertIn("_映射表.json", machine_names)
        loose_names = {f["name"] for f in result["loose_files"]}
        self.assertNotIn("SPEC.md", loose_names)
        self.assertNotIn("project-progress.yaml", loose_names)
        self.assertNotIn("_映射表.json", loose_names)

    def test_layout_scan_warns_theme_overflow(self):
        # 同一主题 >= 5 个散落文件时,应产 warning
        work = self.root / "overflow_subdir"
        work.mkdir()
        for i in range(6):
            (work / f"第二课堂完整模块PRD.draft.{i}.md").write_text("#", encoding="utf-8")
        result = layout_scan(work)
        warns = [w for w in result["warnings"] if w["id"] == "layout.theme-overflow"]
        self.assertEqual(len(warns), 1)
        self.assertIn("future_plan", warns[0]["message"])
        self.assertEqual(warns[0]["severity"], "info")

    def test_layout_scan_suggests_missing_stage_dirs(self):
        # progress 的 current_stage 对应目录若不存在,应建议创建
        progress_path = self.root / "project-progress.yaml"
        progress_path.write_text(
            'project: "示例"\ncurrent_stage: "development"\nstages:\n'
            '  requirements: {status: done, completed_at: "2026-08-14"}\n'
            '  analysis: {status: done, completed_at: "2026-08-11"}\n'
            '  prd: {status: done, completed_at: "2026-08-14"}\n'
            '  ux: {status: done, completed_at: "2026-08-14"}\n'
            '  prototype: {status: done, completed_at: "2026-08-14"}\n'
            '  client_gate: {status: done, completed_at: "2026-08-14"}\n'
            '  architecture: {status: done, completed_at: "2026-08-14"}\n'
            '  tech_readiness: {status: done, completed_at: "2026-08-14"}\n'
            '  story_breakdown: {status: done, completed_at: "2026-08-14"}\n'
            '  feishu_sync: {status: done, completed_at: "2026-08-14"}\n'
            '  development: {status: in_progress, started_at: "2026-08-14"}\n'
            '  opportunity: {status: pending}\n  proposal: {status: pending}\n'
            '  deal_gate: {status: pending}\n  eval: {status: pending}\n'
            '  qa: {status: pending}\n  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        # 删除所有阶段目录(确保都缺失)
        for entry in list(self.root.iterdir()):
            if entry.is_dir() and entry.name[:2].isdigit():
                import shutil
                shutil.rmtree(entry)
        result = layout_scan(self.root)
        # current_stage = development,STAGE_DIR_HINT["development"] = "07-开发"
        # 第一个未 done 阶段是 eval,所以建议的是 "08-测试验收"
        # (因为建议逻辑只到下一个 pending 阶段 break)
        # 实际逻辑是:遍历 STAGES_ORDER 直到第一个未 done 阶段
        # opportunity/proposal/deal_gate 是 pending,会被命中
        # STAGE_DIR_HINT["opportunity"] = "01-商机确认"
        suggestions = {s["name"] for s in result["suggested_dirs"]}
        self.assertIn("01-商机确认", suggestions)

    def test_stage_next_drafts_uses_current_stage(self):
        # 不传 stage_id 时,应读 project-progress 的 current_stage
        progress_path = self.root / "project-progress.yaml"
        progress_path.write_text(
            'project: "示例"\ncurrent_stage: "requirements"\nstages:\n'
            '  opportunity: {status: pending}\n  proposal: {status: pending}\n'
            '  deal_gate: {status: pending}\n  requirements: {status: in_progress}\n'
            '  analysis: {status: pending}\n  prd: {status: pending}\n'
            '  ux: {status: pending}\n  prototype: {status: pending}\n'
            '  client_gate: {status: pending}\n  architecture: {status: pending}\n'
            '  tech_readiness: {status: pending}\n  story_breakdown: {status: pending}\n'
            '  feishu_sync: {status: pending}\n  development: {status: pending}\n'
            '  eval: {status: pending}\n  qa: {status: pending}\n'
            '  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        result = stage_next_drafts(self.root)
        self.assertEqual(result["stage_id"], "requirements")
        self.assertEqual(result["stage_dir_hint"], "04-需求分析")
        # requirements 阶段应输出 PRD.draft.md + project-context.md.draft.md
        names = [d["filename_template"] for d in result["drafts"]]
        self.assertIn("PRD.draft.md", names)
        self.assertIn("project-context.md.draft.md", names)

    def test_stage_next_drafts_explicit_stage(self):
        # 显式传 stage_id 时,跳过 progress 读取
        result = stage_next_drafts(self.root, stage_id="tech_readiness")
        self.assertEqual(result["stage_id"], "tech_readiness")
        self.assertEqual(result["stage_dir_hint"], "06-架构")
        names = [d["filename_template"] for d in result["drafts"]]
        self.assertIn("技术就绪报告.draft.md", names)

    def test_stage_next_drafts_no_progress_no_stage(self):
        # 没 progress + 没 stage_id → 报错而非崩溃
        result = stage_next_drafts(self.root)
        self.assertIn("error", result)
        self.assertEqual(result["type"], "stage_next_drafts_error")

    def test_stage_next_drafts_invalid_stage(self):
        # 非法 stage_id → 报错并列出合法值
        result = stage_next_drafts(self.root, stage_id="bogus_stage")
        self.assertIn("error", result)
        self.assertIn("valid_stages", result)

    def test_stage_next_drafts_development_is_empty(self):
        # development 阶段 drafts 应为空(由各 Story 产出,不预生成)
        result = stage_next_drafts(self.root, stage_id="development")
        self.assertEqual(result["stage_id"], "development")
        self.assertEqual(result["drafts"], [])

    def test_validate_progress_passes_valid_state(self):
        # 正常状态应通过校验
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ntrace_id: "OPP-2026-001"\ncurrent_stage: "requirements"\nstages:\n'
            '  opportunity: {status: done, completed_at: "2026-07-15"}\n'
            '  proposal: {status: done, completed_at: "2026-07-17"}\n'
            '  deal_gate: {status: done, completed_at: "2026-07-18", gate_evidence: "x.md"}\n'
            '  requirements: {status: in_progress, started_at: "2026-07-20"}\n'
            '  analysis: {status: pending}\n'
            '  prd: {status: pending}\n  ux: {status: pending}\n  prototype: {status: pending}\n'
            '  client_gate: {status: pending}\n  architecture: {status: pending}\n'
            '  tech_readiness: {status: pending}\n  story_breakdown: {status: pending}\n'
            '  feishu_sync: {status: pending}\n  development: {status: pending}\n'
            '  eval: {status: pending}\n  qa: {status: pending}\n'
            '  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        data = read_progress(progress_file)
        errors = validate_progress(data)
        self.assertEqual(errors, [])

    def test_validate_progress_detects_multiple_in_progress(self):
        # 两个阶段同时 in_progress 必须报错
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "requirements"\nstages:\n'
            '  opportunity: {status: pending}\n'
            '  proposal: {status: pending}\n'
            '  deal_gate: {status: pending}\n'
            '  requirements: {status: in_progress}\n'
            '  analysis: {status: in_progress}\n'
            '  prd: {status: pending}\n  ux: {status: pending}\n  prototype: {status: pending}\n'
            '  client_gate: {status: pending}\n  architecture: {status: pending}\n'
            '  tech_readiness: {status: pending}\n  story_breakdown: {status: pending}\n'
            '  feishu_sync: {status: pending}\n  development: {status: pending}\n'
            '  eval: {status: pending}\n  qa: {status: pending}\n'
            '  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        data = read_progress(progress_file)
        errors = validate_progress(data)
        self.assertTrue(any("in_progress" in e for e in errors))

    def test_validate_progress_detects_done_without_completed_at(self):
        # done 阶段缺少 completed_at 必须报错
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "requirements"\nstages:\n'
            '  opportunity: {status: done}\n'
            '  proposal: {status: pending}\n  deal_gate: {status: pending}\n'
            '  requirements: {status: pending}\n  analysis: {status: pending}\n'
            '  prd: {status: pending}\n  ux: {status: pending}\n  prototype: {status: pending}\n'
            '  client_gate: {status: pending}\n  architecture: {status: pending}\n'
            '  tech_readiness: {status: pending}\n  story_breakdown: {status: pending}\n'
            '  feishu_sync: {status: pending}\n  development: {status: pending}\n'
            '  eval: {status: pending}\n  qa: {status: pending}\n'
            '  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        data = read_progress(progress_file)
        errors = validate_progress(data)
        self.assertTrue(any("completed_at" in e for e in errors))

    def test_validate_progress_detects_gate_evidence_on_non_gate_stage(self):
        # 非关卡阶段使用 gate_evidence 必须报错
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "requirements"\nstages:\n'
            '  opportunity: {status: pending}\n  proposal: {status: pending}\n'
            '  deal_gate: {status: pending}\n'
            '  requirements: {status: in_progress, gate_evidence: "fake.md"}\n'
            '  analysis: {status: pending}\n  prd: {status: pending}\n  ux: {status: pending}\n'
            '  prototype: {status: pending}\n  client_gate: {status: pending}\n'
            '  architecture: {status: pending}\n  tech_readiness: {status: pending}\n'
            '  story_breakdown: {status: pending}\n  feishu_sync: {status: pending}\n'
            '  development: {status: pending}\n  eval: {status: pending}\n'
            '  qa: {status: pending}\n  acceptance_gate: {status: pending}\n',
            encoding="utf-8",
        )
        data = read_progress(progress_file)
        errors = validate_progress(data)
        self.assertTrue(any("gate_evidence" in e for e in errors))

    def test_validate_progress_detects_acceptance_done_with_current(self):
        # acceptance_gate.done 但 current_stage 还指向它，应报"应置为 null"
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ncurrent_stage: "acceptance_gate"\nstages:\n'
            '  opportunity: {status: done, completed_at: "2026-07-15"}\n'
            '  proposal: {status: done, completed_at: "2026-07-17"}\n'
            '  deal_gate: {status: done, completed_at: "2026-07-18"}\n'
            '  requirements: {status: done, completed_at: "2026-07-20"}\n'
            '  analysis: {status: done, completed_at: "2026-07-22"}\n'
            '  prd: {status: done, completed_at: "2026-07-25"}\n'
            '  ux: {status: done, completed_at: "2026-07-27"}\n'
            '  prototype: {status: done, completed_at: "2026-07-28"}\n'
            '  client_gate: {status: done, completed_at: "2026-07-30"}\n'
            '  architecture: {status: done, completed_at: "2026-07-31"}\n'
            '  tech_readiness: {status: done, completed_at: "2026-08-01"}\n'
            '  story_breakdown: {status: done, completed_at: "2026-08-02"}\n'
            '  feishu_sync: {status: done, completed_at: "2026-08-02"}\n'
            '  development: {status: done, completed_at: "2026-08-03"}\n'
            '  eval: {status: done, completed_at: "2026-08-04"}\n'
            '  qa: {status: done, completed_at: "2026-08-04"}\n'
            '  acceptance_gate: {status: done, completed_at: "2026-08-04"}\n',
            encoding="utf-8",
        )
        data = read_progress(progress_file)
        errors = validate_progress(data)
        self.assertTrue(any("null" in e for e in errors))

    def test_current_stage_summary_handles_completed_state(self):
        # current_stage: null + acceptance_gate.done → 验收完成态
        progress_file = self.root / "project-progress.yaml"
        progress_file.write_text(
            'project: "示例"\ntrace_id: "OPP-2026-001"\ncurrent_stage: null\nstages:\n'
            '  opportunity: {status: done, completed_at: "2026-07-15"}\n'
            '  proposal: {status: done, completed_at: "2026-07-17"}\n'
            '  deal_gate: {status: done, completed_at: "2026-07-18"}\n'
            '  requirements: {status: done, completed_at: "2026-07-20"}\n'
            '  analysis: {status: done, completed_at: "2026-07-22"}\n'
            '  prd: {status: done, completed_at: "2026-07-25"}\n'
            '  ux: {status: done, completed_at: "2026-07-27"}\n'
            '  prototype: {status: done, completed_at: "2026-07-28"}\n'
            '  client_gate: {status: done, completed_at: "2026-07-30"}\n'
            '  architecture: {status: done, completed_at: "2026-07-31"}\n'
            '  tech_readiness: {status: done, completed_at: "2026-08-01"}\n'
            '  story_breakdown: {status: done, completed_at: "2026-08-02"}\n'
            '  feishu_sync: {status: done, completed_at: "2026-08-02"}\n'
            '  development: {status: done, completed_at: "2026-08-03"}\n'
            '  eval: {status: done, completed_at: "2026-08-04"}\n'
            '  qa: {status: done, completed_at: "2026-08-04"}\n'
            '  acceptance_gate: {status: done, completed_at: "2026-08-04"}\n',
            encoding="utf-8",
        )
        result = current_stage_summary(self.root)
        self.assertEqual(result["state"], "completed")
        self.assertIsNone(result["current_stage"])
        self.assertEqual(result["completed_count"], 17)

    # —— 阶段四：关卡最小证据 + 四态语义 ——

    def _write_full_confirmation(self) -> Path:
        """写入完整客户确认记录（含放行结论 + 三项最小证据）"""
        # 先清掉 setUp 创建的标题-only 文件，避免 find_first 抓到空模板
        for old in self.root.glob("*客户确认*.md"):
            old.unlink()
        path = self.root / "客户确认记录-2026-08-01.md"
        path.write_text(
            "# 客户确认记录\n\n"
            "## 6. 放行结论\n\n放行结论：放行\n\n"
            "## 7. 确认方式\n\n"
            "- 客户代表：王经理\n"
            "- 确认方式：邮件确认\n"
            "- 确认时间：2026-08-01\n",
            encoding="utf-8",
        )
        return path

    def test_parse_confirmation_placeholder(self):
        # 只有标题的模板 → placeholder
        info = parse_confirmation(self.root / "客户确认记录-2026-07-31.md")
        self.assertTrue(info["is_placeholder"])
        self.assertFalse(info["has_decision"])

    def test_parse_confirmation_with_placeholder_token(self):
        # 含 {{ }}/{占位} 的模板 → placeholder
        path = self.root / "客户确认记录-tpl.md"
        path.write_text("# 客户确认\n\n客户代表：{{客户代表}}\n", encoding="utf-8")
        info = parse_confirmation(path)
        self.assertTrue(info["is_placeholder"])

    def test_parse_confirmation_missing_required_fields(self):
        # 有放行结论但缺最小证据字段 → has_decision=True 但 method/confirmed_at/representative 为空
        path = self.root / "客户确认记录-partial.md"
        path.write_text(
            "# 客户确认\n\n## 6. 放行结论\n\n放行结论：放行\n\n"
            "## 7. 确认方式\n\n"
            "- 客户代表：王经理\n"
            "- 确认方式：邮件\n",
            encoding="utf-8",
        )
        info = parse_confirmation(path)
        self.assertFalse(info["is_placeholder"])
        self.assertTrue(info["has_decision"])
        self.assertEqual(info["decision"], "pass")
        self.assertEqual(info["representative"], "王经理")
        self.assertEqual(info["method"], "邮件")
        self.assertEqual(info["confirmed_at"], "")  # 缺失

    def test_parse_confirmation_full_evidence(self):
        # 放行结论 + 三项最小证据齐全 → decision=pass + 字段全有
        path = self._write_full_confirmation()
        info = parse_confirmation(path)
        self.assertFalse(info["is_placeholder"])
        self.assertEqual(info["decision"], "pass")
        self.assertEqual(info["representative"], "王经理")
        self.assertEqual(info["method"], "邮件确认")
        self.assertEqual(info["confirmed_at"], "2026-08-01")

    def test_parse_confirmation_negative_decision(self):
        # 含"不通过" → decision=fail
        path = self.root / "客户确认记录-fail.md"
        path.write_text(
            "# 客户确认\n\n## 6. 放行结论\n\n放行结论：不通过\n\n## 7. 确认方式\n\n原因：范围超出\n",
            encoding="utf-8",
        )
        info = parse_confirmation(path)
        self.assertEqual(info["decision"], "fail")
        self.assertFalse(info["has_decision"])

    def test_parse_readiness_placeholder(self):
        # 模板 → placeholder
        info = parse_readiness(self.root / "技术就绪-readiness.md")
        self.assertTrue(info["is_placeholder"])

    def test_parse_readiness_pass(self):
        path = self.root / "技术就绪-pass.md"
        path.write_text(
            "# readiness\n\n## 结论\n\n结论：通过\n\n## 说明\n所有评估项已确认通过\n",
            encoding="utf-8",
        )
        info = parse_readiness(path)
        self.assertFalse(info["is_placeholder"])
        self.assertEqual(info["conclusion"], "pass")

    def test_parse_readiness_pending(self):
        path = self.root / "技术就绪-pending.md"
        path.write_text(
            "# readiness\n\n## 结论\n\n结论：待确认\n\n## 说明\n尚有未决项\n",
            encoding="utf-8",
        )
        info = parse_readiness(path)
        self.assertEqual(info["conclusion"], "pending")

    def test_parse_readiness_fail(self):
        path = self.root / "技术就绪-fail.md"
        path.write_text(
            "# readiness\n\n## 结论\n\n结论：不通过\n\n## 说明\n存在阻断项\n",
            encoding="utf-8",
        )
        info = parse_readiness(path)
        self.assertEqual(info["conclusion"], "fail")

    def test_parse_acceptance_placeholder(self):
        info = parse_acceptance(self.root / "验收报告-2026-07-31.md")
        self.assertTrue(info["is_placeholder"])

    def test_parse_acceptance_full_evidence(self):
        path = self.root / "验收报告-full.md"
        path.write_text(
            "# 验收报告\n\n## 8. 验收结论\n\n验收结论：通过\n\n"
            "- 客户确认方式：签字盖章\n"
            "- 客户确认时间：2026-08-04\n",
            encoding="utf-8",
        )
        info = parse_acceptance(path)
        self.assertEqual(info["conclusion"], "pass")
        self.assertEqual(info["method"], "签字盖章")
        self.assertEqual(info["confirmed_at"], "2026-08-04")

    def test_parse_evaluation_placeholder(self):
        info = parse_evaluation(self.root / "评测报告-2026-07-31.md")
        self.assertTrue(info["is_placeholder"])

    def test_parse_evaluation_missing_tier1(self):
        # 有阈值有结论但无 Tier1 → incomplete
        path = self.root / "评测报告-notier1.md"
        path.write_text(
            "# 评测\n\n## 放行结论\n\n放行：放行\n\n阈值：>=0.85\n\n补充说明\n",
            encoding="utf-8",
        )
        info = parse_evaluation(path)
        self.assertFalse(info["is_placeholder"])
        self.assertEqual(info["conclusion"], "incomplete")
        self.assertFalse(info["has_tier1"])

    def test_parse_evaluation_missing_threshold(self):
        # 有 Tier1 有结论但无阈值 → incomplete
        path = self.root / "评测报告-nothr.md"
        path.write_text(
            "# 评测\n\n## 放行结论\n\n放行：放行\n\nTier1 实测：\n- 引用覆盖率 0.92\n\n补充说明\n",
            encoding="utf-8",
        )
        info = parse_evaluation(path)
        self.assertEqual(info["conclusion"], "incomplete")
        self.assertFalse(info["has_threshold"])

    def test_parse_evaluation_full_evidence(self):
        # Tier1 + 阈值 + 评测结论齐全 → pass
        path = self.root / "评测报告-pass.md"
        path.write_text(
            "# 评测\n\nTier1 实测：引用覆盖率 0.92\n\n阈值：>=0.85\n\n评测结论：放行\n",
            encoding="utf-8",
        )
        info = parse_evaluation(path)
        self.assertEqual(info["conclusion"], "pass")
        self.assertTrue(info["has_tier1"])
        self.assertTrue(info["has_threshold"])

    def test_parse_story_placeholder(self):
        info = parse_story(self.root / "stories" / "story-a.md")
        self.assertTrue(info["is_placeholder"])

    def test_parse_story_missing_goal(self):
        path = self.root / "stories" / "story-nogoal.md"
        path.write_text(
            "# Story\n\n## DoD\nsome ac\n\n## 交付物\nfoo\n\n## 补充\n补充说明\n",
            encoding="utf-8",
        )
        info = parse_story(path)
        self.assertFalse(info["is_placeholder"])
        self.assertFalse(info["has_goal"])
        self.assertTrue(info["has_ac"])
        self.assertTrue(info["has_deliverable"])

    def test_parse_story_full_three_elements(self):
        path = self.root / "stories" / "story-good.md"
        path.write_text(
            "# Story\n\n## 目标\n做某个功能\n\n## DoD / 验收标准\nAC1: 通过\n\n## 交付物\nAPI 文档\n",
            encoding="utf-8",
        )
        info = parse_story(path)
        self.assertTrue(info["has_goal"])
        self.assertTrue(info["has_ac"])
        self.assertTrue(info["has_deliverable"])

    def test_check_template_is_not_pass(self):
        # setUp 创建的文件都是只有标题的模板：关卡检查必须 unknown，不能 pass
        findings = check_project(self.root)
        gate_findings = {f["id"]: f for f in findings if f["id"].startswith("gate.")}
        self.assertEqual(gate_findings["gate.client"]["status"], "unknown")
        self.assertEqual(gate_findings["gate.readiness"]["status"], "unknown")
        self.assertEqual(gate_findings["gate.acceptance"]["status"], "unknown")
        self.assertEqual(gate_findings["gate.eval"]["status"], "unknown")

    def test_check_client_gate_passes_with_full_evidence(self):
        # 完整证据 → pass
        self._write_full_confirmation()
        # 其它关卡也补全；先清理 setUp 的标题-only 文件
        for old in self.root.glob("*技术就绪*.md"):
            old.unlink()
        readiness = self.root / "技术就绪-pass.md"
        readiness.write_text(
            "# readiness\n\n## 结论\n\n结论：通过\n\n## 说明\n所有评估项已确认通过\n",
            encoding="utf-8",
        )
        for old in self.root.glob("*评测报告*.md"):
            old.unlink()
        eval_path = self.root / "评测报告-full.md"
        eval_path.write_text(
            "# 评测\n\nTier1 实测：引用覆盖率 0.92\n\n阈值：>=0.85\n\n评测结论：放行\n\n补充说明\n",
            encoding="utf-8",
        )
        for old in self.root.glob("*验收报告*.md"):
            old.unlink()
        accept = self.root / "验收报告-full.md"
        accept.write_text(
            "# 验收\n\n## 8. 验收结论\n\n验收结论：通过\n"
            "- 客户确认方式：签字盖章\n- 客户确认时间：2026-08-04\n",
            encoding="utf-8",
        )
        findings = check_project(self.root)
        gate_findings = {f["id"]: f for f in findings if f["id"].startswith("gate.")}
        self.assertEqual(gate_findings["gate.client"]["status"], "pass")
        self.assertEqual(gate_findings["gate.readiness"]["status"], "pass")
        self.assertEqual(gate_findings["gate.eval"]["status"], "pass")
        self.assertEqual(gate_findings["gate.acceptance"]["status"], "pass")

    def test_check_mapping_fails_when_guids_missing(self):
        # 映射表有结构但缺 GUID → fail
        (self.root / "_映射表.json").write_text(
            json.dumps({"tasklists": {"模块": {"parent_tasks": {"Story A": {"subtasks": {"A-1": "task-1"}}}}}}),
            encoding="utf-8",
        )
        findings = check_project(self.root)
        mapping_findings = [f for f in findings if f["id"] == "mapping.valid"]
        self.assertEqual(mapping_findings[0]["status"], "fail")

    def test_check_mapping_passes_when_guids_complete(self):
        # 完整 GUID + 子任务 ID → pass
        (self.root / "_映射表.json").write_text(
            json.dumps({
                "tasklists": {
                    "模块": {
                        "guid": "list-1",
                        "parent_tasks": {
                            "Story A": {
                                "guid": "parent-1",
                                "subtasks": {"A-1": "task-1"},
                            }
                        },
                    }
                }
            }),
            encoding="utf-8",
        )
        findings = check_project(self.root)
        mapping_findings = [f for f in findings if f["id"] == "mapping.valid"]
        self.assertEqual(mapping_findings[0]["status"], "pass")

    def test_summarize_findings_blocks_on_unknown(self):
        # 模板状态下必须有 unknown 且 blocked=true
        findings = check_project(self.root)
        summary = summarize_findings(findings)
        self.assertGreater(summary["unknown" if "unknown" in summary else "warn"], 0)
        self.assertTrue(summary["blocked"])

    # —— 阶段五：关卡顺序纪律 ——

    def _write_full_evidence(self) -> None:
        """构造全套完整证据，让 client_gate/tech_readiness 关卡 pass。"""
        # 先清掉 setUp 的标题-only 文件
        for old in self.root.glob("*客户确认*.md"):
            old.unlink()
        (self.root / "客户确认记录-full.md").write_text(
            "# 客户确认\n\n放行结论：放行\n"
            "- 客户代表：王经理\n- 确认方式：邮件确认\n- 确认时间：2026-08-01\n"
            "补充说明\n",
            encoding="utf-8",
        )
        for old in self.root.glob("*技术就绪*.md"):
            old.unlink()
        (self.root / "技术就绪-full.md").write_text(
            "# readiness\n\n## 结论\n\n结论：通过\n\n## 说明\n所有项已确认\n",
            encoding="utf-8",
        )
        # 四层架构齐全
        (self.root / "业务架构.md").write_text("# 业务架构", encoding="utf-8")
        (self.root / "产品架构.md").write_text("# 产品架构", encoding="utf-8")
        (self.root / "技术架构.md").write_text("# 技术架构", encoding="utf-8")
        (self.root / "数据架构.md").write_text("# 数据架构", encoding="utf-8")
        # project-progress.tech_readiness=done
        (self.root / "project-progress.yaml").write_text(
            'project: "示例"\ncurrent_stage: "feishu_sync"\nstages:\n'
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
        # Story 三要素齐全
        stories_dir = self.root / "stories"
        stories_dir.mkdir(exist_ok=True)
        (stories_dir / "story-a.md").write_text(
            "# Story A\n\n## 做什么\n\nA 的目标\n\n## DoD/AC\n\n- AC1\n\n## 交付物\n\nA 的交付物\n",
            encoding="utf-8",
        )

    def test_order_fail_when_story_without_client(self):
        # 没有客户确认但有 Story → order.client-before-story fail
        for old in self.root.glob("*客户确认*.md"):
            old.unlink()
        findings = check_project(self.root)
        order_findings = {f["id"]: f for f in findings if f["id"].startswith("order.")}
        self.assertIn("order.client-before-story", order_findings)
        self.assertEqual(order_findings["order.client-before-story"]["status"], "fail")

    def test_order_fail_when_mapping_without_readiness(self):
        # readiness 占位符（setUp 默认） + 有映射 → readiness-before-feishu fail
        # setUp 已有 _映射表.json 和 标题-only 技术就绪报告
        findings = check_project(self.root)
        order_findings = {f["id"]: f for f in findings if f["id"].startswith("order.")}
        self.assertIn("order.readiness-before-feishu", order_findings)
        self.assertEqual(order_findings["order.readiness-before-feishu"]["status"], "fail")

    def test_order_fail_when_story_without_readiness(self):
        # readiness 未通过 + 有 Story → readiness-before-story fail
        findings = check_project(self.root)
        order_findings = {f["id"]: f for f in findings if f["id"].startswith("order.")}
        self.assertIn("order.readiness-before-story", order_findings)
        self.assertEqual(order_findings["order.readiness-before-story"]["status"], "fail")

    def test_order_fail_when_dev_status_without_readiness(self):
        # readiness 未通过 + 有 sprint-status.yaml → readiness-before-dev fail
        (self.root / "sprint-status.yaml").write_text("- story: A-1\n  status: done\n", encoding="utf-8")
        findings = check_project(self.root)
        order_findings = {f["id"]: f for f in findings if f["id"].startswith("order.")}
        self.assertIn("order.readiness-before-dev", order_findings)
        self.assertEqual(order_findings["order.readiness-before-dev"]["status"], "fail")

    def test_order_pass_with_full_gate_chain(self):
        # 客户确认 + readiness 都通过 + 下游产物齐全 → 没有 order fail
        self._write_full_evidence()
        # 给 mapping 加 GUID，让 mapping.valid pass
        (self.root / "_映射表.json").write_text(
            json.dumps({
                "tasklists": {"模块": {
                    "guid": "list-1",
                    "parent_tasks": {"Story A": {"guid": "parent-1", "subtasks": {"A-1": "task-1"}}},
                }}
            }),
            encoding="utf-8",
        )
        findings = check_project(self.root)
        order_findings = [f for f in findings if f["id"].startswith("order.")]
        self.assertFalse(any(f["status"] == "fail" for f in order_findings))

    def test_order_fail_when_readiness_passed_but_client_not(self):
        # readiness 通过但客户签字关卡未通过 → order.client-before-readiness fail
        for old in self.root.glob("*客户确认*.md"):
            old.unlink()
        for old in self.root.glob("*技术就绪*.md"):
            old.unlink()
        # readiness 完整通过
        (self.root / "技术就绪-pass.md").write_text(
            "# readiness\n\n## 结论\n\n结论：通过\n\n## 说明\n所有项已确认\n",
            encoding="utf-8",
        )
        # 客户确认是空标题 → placeholder，不算 pass
        (self.root / "客户确认记录-empty.md").write_text("# 客户确认\n", encoding="utf-8")
        findings = check_project(self.root)
        order_findings = {f["id"]: f for f in findings if f["id"].startswith("order.")}
        self.assertEqual(order_findings["order.client-before-readiness"]["status"], "fail")

    # —— 阶段六：dry-run create/update/skip/orphan ——

    def _write_manifest(self, tasks: list[dict[str, str]]) -> None:
        """构造 desired-tasks.json。tasks 每项含 local_id/tasklist/parent_task/what/dod/deliverable，content_hash 自动计算。"""
        import sys
        sys.path.insert(0, str(self.root.parent))
        from scripts.delivery_flow.core import compute_content_hash
        manifest_tasks: list[dict[str, Any]] = []
        for t in tasks:
            spec_ref = t.get("spec_ref", "")
            content_hash = compute_content_hash(
                t["what"], t["dod"], t["deliverable"], spec_ref,
            )
            entry: dict[str, Any] = {
                "local_id": t["local_id"],
                "tasklist": t.get("tasklist", "模块"),
                "parent_task": t.get("parent_task", "Story"),
                "what": t["what"],
                "dod": t["dod"],
                "deliverable": t["deliverable"],
                "content_hash": content_hash,
            }
            if spec_ref:
                entry["spec_ref"] = spec_ref
            manifest_tasks.append(entry)
        manifest = {
            "project": "测试项目",
            "generated_at": "2026-08-01",
            "tasks": manifest_tasks,
        }
        (self.root / "desired-tasks.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_mapping_with_synced(self, items: dict[tuple[str, str], dict[str, Any]]) -> None:
        """构造新格式映射表：items[(parent, local_id)] = {task_id, synced?}。"""
        tasklists: dict = {}
        for (parent, local_id), info in items.items():
            parent_block = tasklists.setdefault("模块", {
                "guid": "list-1",
                "parent_tasks": {},
            })
            pb = parent_block["parent_tasks"].setdefault(parent, {"guid": f"p-{parent}", "subtasks": {}})
            pb["subtasks"][local_id] = info
        (self.root / "_映射表.json").write_text(
            json.dumps({"tasklists": tasklists}), encoding="utf-8",
        )

    def _write_mapping(self, items: dict[tuple[str, str], str]) -> None:
        """构造映射表（兼容旧格式，value 为裸字符串）。"""
        tasklists: dict = {}
        for (parent, local_id), task_id in items.items():
            parent_block = tasklists.setdefault("模块", {
                "guid": "list-1",
                "parent_tasks": {},
            })
            pb = parent_block["parent_tasks"].setdefault(parent, {"guid": f"p-{parent}", "subtasks": {}})
            pb["subtasks"][local_id] = task_id
        (self.root / "_映射表.json").write_text(
            json.dumps({"tasklists": tasklists}), encoding="utf-8",
        )

    def _write_status(self, rows: list[dict[str, str]]) -> None:
        """构造 sprint-status.yaml。"""
        lines = []
        for row in rows:
            lines.append(f"- story: {row['story']}")
            if "task_id" in row:
                lines.append(f"  task_id: {row['task_id']}")
            if "status" in row:
                lines.append(f"  status: {row['status']}")
        (self.root / "sprint-status.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _full_gate_chain(self) -> None:
        """满足 dry-run 所有门禁的最小产物集（只设置文件，不过解析）。"""
        (self.root / "客户确认记录-full.md").write_text(
            "# 客户确认\n\n放行结论：放行\n"
            "- 客户代表：王经理\n- 确认方式：邮件\n- 确认时间：2026-08-01\n",
            encoding="utf-8",
        )
        (self.root / "技术就绪-full.md").write_text(
            "# readiness\n\n## 结论\n\n结论：通过\n\n## 说明\nok\n",
            encoding="utf-8",
        )
        (self.root / "业务架构.md").write_text("# 业务架构", encoding="utf-8")
        (self.root / "产品架构.md").write_text("# 产品架构", encoding="utf-8")
        (self.root / "技术架构.md").write_text("# 技术架构", encoding="utf-8")
        (self.root / "数据架构.md").write_text("# 数据架构", encoding="utf-8")
        (self.root / "project-progress.yaml").write_text(
            'project: "测试项目"\ncurrent_stage: "feishu_sync"\nstages:\n'
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
        stories_dir = self.root / "stories"
        stories_dir.mkdir(exist_ok=True)
        (stories_dir / "story-a.md").write_text(
            "# Story A\n\n## 做什么\n\nA\n\n## DoD/AC\n\n- AC1\n\n## 交付物\n\nA 交付\n",
            encoding="utf-8",
        )

    def test_dry_run_creates_when_no_status(self):
        # manifest 有 2 条 + 映射表无该 local_id → 全部 create（前提：所有门禁通过）
        self._full_gate_chain()
        (self.root / "_映射表.json").write_text(
            json.dumps({"tasklists": {}}), encoding="utf-8",
        )
        self._write_manifest([
            {"local_id": "A-1", "what": "W1", "dod": "D1", "deliverable": "X1"},
            {"local_id": "A-2", "what": "W2", "dod": "D2", "deliverable": "X2"},
        ])
        result = dry_run(self.root)
        self.assertEqual(result["mode"], "manifest-driven")
        self.assertEqual(result["summary"]["create"], 2)
        self.assertEqual(result["summary"]["update"], 0)
        self.assertEqual(result["summary"]["skip"], 0)
        actions = [op["action"] for op in result["operations"]]
        self.assertEqual(actions, ["create", "create"])
        self.assertFalse(result["network"])

    def test_dry_run_skips_when_content_hash_matches(self):
        # manifest 和 mapping 都齐全且 content_hash 一致 → skip
        self._full_gate_chain()
        import sys
        sys.path.insert(0, str(self.root.parent))
        from scripts.delivery_flow.core import compute_content_hash
        h = compute_content_hash("W1", "D1", "X1")
        self._write_manifest([{"local_id": "A-1", "what": "W1", "dod": "D1", "deliverable": "X1"}])
        self._write_mapping_with_synced({("Story A", "A-1"): {
            "task_id": "task-1",
            "synced": {"content_hash": h, "synced_at": "2026-08-01",
                       "what": "W1", "dod": "D1", "deliverable": "X1"},
        }})
        result = dry_run(self.root)
        self.assertEqual(result["summary"]["skip"], 1)
        self.assertEqual(result["summary"]["create"], 0)
        self.assertEqual(result["operations"][0]["action"], "skip")

    def test_dry_run_updates_when_content_hash_changed(self):
        # manifest 内容已变但 mapping 的 synced.content_hash 未变 → update
        self._full_gate_chain()
        self._write_manifest([{"local_id": "A-1", "what": "W1-new", "dod": "D1-new", "deliverable": "X1-new"}])
        self._write_mapping_with_synced({("Story A", "A-1"): {
            "task_id": "task-1",
            "synced": {"content_hash": "0" * 64, "synced_at": "2026-07-01",
                       "what": "W1-old", "dod": "D1-old", "deliverable": "X1-old"},
        }})
        result = dry_run(self.root)
        self.assertEqual(result["summary"]["update"], 1)
        op = result["operations"][0]
        self.assertEqual(op["action"], "update")

    def test_dry_run_detects_orphans(self):
        # mapping 有 local_id 但 manifest 无 → orphan
        self._full_gate_chain()
        # 完整重置映射表，避免 setUp 默认的 A-1 干扰
        self._write_manifest([{"local_id": "A-1", "what": "W1", "dod": "D1", "deliverable": "X1"}])
        self._write_mapping_with_synced({("Story A", "A-1"): {"task_id": "task-1"},
                                          ("Story A", "A-2"): {"task_id": "task-2"}})
        result = dry_run(self.root)
        # A-1 mapping 缺 synced.content_hash（old format 残留）→ create_with_review 而非 skip
        self.assertEqual(result["summary"]["create_with_review"], 1)
        self.assertEqual(result["summary"]["orphan"], 1)
        orphan_ops = [op for op in result["operations"] if op["action"] == "orphan"]
        self.assertEqual(orphan_ops[0]["local_id"], "A-2")

    def test_dry_run_detects_orphans_with_synced(self):
        # mapping 有 synced.content_hash 且与 manifest 一致 → skip；A-2 不在 manifest → orphan
        import sys
        sys.path.insert(0, str(self.root.parent))
        from scripts.delivery_flow.core import compute_content_hash
        self._full_gate_chain()
        h = compute_content_hash("W1", "D1", "X1")
        self._write_manifest([{"local_id": "A-1", "what": "W1", "dod": "D1", "deliverable": "X1"}])
        self._write_mapping_with_synced({
            ("Story A", "A-1"): {"task_id": "task-1", "synced": {
                "content_hash": h, "synced_at": "2026-08-01",
                "what": "W1", "dod": "D1", "deliverable": "X1"}},
            ("Story A", "A-2"): {"task_id": "task-2"},
        })
        result = dry_run(self.root)
        self.assertEqual(result["summary"]["skip"], 1)
        self.assertEqual(result["summary"]["orphan"], 1)

    def test_dry_run_blocks_when_mapping_missing(self):
        # 映射表不存在 → blocked
        self._full_gate_chain()
        (self.root / "_映射表.json").unlink()
        self._write_manifest([{"local_id": "A-1", "what": "W1", "dod": "D1", "deliverable": "X1"}])
        result = dry_run(self.root)
        self.assertGreater(result["summary"]["blocked"], 0)
        self.assertIn("映射表不存在", " ".join(result["blocked_by"]))

    def test_dry_run_blocks_when_mapping_invalid(self):
        # 映射表结构错误 → blocked
        self._full_gate_chain()
        self._write_manifest([{"local_id": "A-1", "what": "W1", "dod": "D1", "deliverable": "X1"}])
        (self.root / "_映射表.json").write_text(json.dumps({"tasklists": {"模块": {"parent_tasks": {}}}}), encoding="utf-8")
        result = dry_run(self.root)
        self.assertGreater(result["summary"]["blocked"], 0)

    def test_dry_run_mixed_scenario(self):
        # 混合：1 skip（hash 一致）+ 1 update（hash 变）+ 1 create（mapping 无）
        self._full_gate_chain()
        import sys
        sys.path.insert(0, str(self.root.parent))
        from scripts.delivery_flow.core import compute_content_hash
        h_unchanged = compute_content_hash("W1", "D1", "X1")
        self._write_manifest([
            {"local_id": "A-1", "what": "W1", "dod": "D1", "deliverable": "X1"},  # skip
            {"local_id": "A-2", "what": "W2-new", "dod": "D2-new", "deliverable": "X2-new"},  # update
            {"local_id": "B-1", "what": "W3", "dod": "D3", "deliverable": "X3"},  # create
        ])
        self._write_mapping_with_synced({
            ("Story A", "A-1"): {"task_id": "task-1", "synced": {
                "content_hash": h_unchanged, "synced_at": "2026-08-01",
                "what": "W1", "dod": "D1", "deliverable": "X1"}},
            ("Story A", "A-2"): {"task_id": "task-2", "synced": {
                "content_hash": "0" * 64, "synced_at": "2026-07-01",
                "what": "W2-old", "dod": "D2-old", "deliverable": "X2-old"}},
            # B-1 不在 mapping 里 → create
        })
        result = dry_run(self.root)
        self.assertEqual(result["summary"]["skip"], 1)
        self.assertEqual(result["summary"]["update"], 1)
        self.assertEqual(result["summary"]["create"], 1)
        self.assertEqual(result["summary"]["orphan"], 0)
        self.assertEqual(result["summary"]["blocked"], 0)

    # —— 批次一：关卡结论契约（用真实模板回归） ——

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _load_template(self, *parts: str) -> str:
        """从仓库 skills 目录加载真实模板原文。"""
        path = self._repo_root().joinpath("skills", *parts)
        if not path.exists():
            self.skipTest(f"模板不存在: {path}")
        return path.read_text(encoding="utf-8")

    def _fill_template(self, text: str, **kw: str) -> str:
        """把模板里所有 <...> 占位符替换成合理值，确保 _is_placeholder_file 返回 False。

        显式替换按字段名（不带尖括号），剩余 <...> 兜底替换为 'x'。
        """
        explicit: dict[str, str] = {
            "填写项目名称": "星辰科技",
            "填写客户单位或联系人": "星辰科技",
            "填写 PM / 项目负责人": "张明",
            "YYYY-MM-DD": "2026-08-01",
            "填写 放行 / 有条件放行 / 不放行": kw.get("decision", "放行"),
            "填写 通过 / 有条件通过 / 不通过": kw.get("decision", "通过"),
            "填写 放行 / 不放行": kw.get("decision", "放行"),
            "填写客户方代表姓名": kw.get("representative", "李振宇"),
            "填写 签字 / 邮件 / IM / 会议纪要 等": kw.get("method", "邮件"),
            "填写 签字 / 盖章 / 邮件 / IM 等": kw.get("method", "签字盖章"),
            "客户代表": kw.get("representative", "李振宇"),
            "确认方式": kw.get("method", "邮件"),
            "签字/邮件/IM消息/会议纪要": kw.get("method", "邮件"),
            "签字/盖章/邮件/IM 等": kw.get("method", "签字盖章"),
            "签字方式": kw.get("method", "邮件"),
            "时间": kw.get("date", "2026-08-01"),
            "日期": kw.get("date", "2026-08-01"),
            "备注": "",
            "负责人": "张明",
            "任务清单/看板": "飞书",
            "数据包/登记表": "数据",
            "如：种子数据未到位": "种子数据",
            "如：同步任务系统": "同步任务",
            "如：准备 PoC 数据": "PoC 数据",
            "未满足/进行中/已满足": "已满足",
            "阻断研发/有条件放行/调整范围": "放行",
            "用 3-5 句话说明为什么放行/不放行，必须写清楚研发下一步能做什么、不能做什么。": "说明",
            "用 3-5 句话说明验收理由、遗留问题和后续安排。": "说明",
            "系统版本/交付版本": "v1.0.0",
            "客户确认记录 v__": "客户确认记录 v0.1",
        }
        for k, v in explicit.items():
            text = text.replace(f"<{k}>", v)
        text = re.sub(r"<[^>\n]+>", "x", text)
        text = text.replace("≥____", "≥ 0.90")
        text = text.replace("≥__", "≥ 0.90")
        text = text.replace("____", "0.90")
        text = text.replace("☐", "☑")
        return text

    # —— 客户确认：5 个真实模板回归 ——

    def test_parse_confirmation_real_template_blank(self):
        """真实客户确认模板 + 不替换占位符 → placeholder。"""
        text = self._load_template("delivery-client-gate", "templates", "客户确认记录模板.md")
        path = self.root / "客户确认-real-blank.md"
        path.write_text(text, encoding="utf-8")
        info = parse_confirmation(path)
        self.assertTrue(info["is_placeholder"])

    def test_parse_confirmation_real_template_pass(self):
        """真实客户确认模板 + 放行 + 最小证据齐全 → pass。"""
        text = self._load_template("delivery-client-gate", "templates", "客户确认记录模板.md")
        text = self._fill_template(text, decision="放行", representative="李振宇", method="邮件")
        path = self.root / "客户确认-real-pass.md"
        path.write_text(text, encoding="utf-8")
        info = parse_confirmation(path)
        self.assertFalse(info["is_placeholder"])
        self.assertEqual(info["decision"], "pass")
        self.assertEqual(info["representative"], "李振宇")
        self.assertEqual(info["method"], "邮件")
        self.assertEqual(info["confirmed_at"], "2026-08-01")

    def test_parse_confirmation_real_template_fail(self):
        """真实模板 + 不放行 → fail。"""
        text = self._load_template("delivery-client-gate", "templates", "客户确认记录模板.md")
        text = self._fill_template(text, decision="不放行", representative="李振宇", method="邮件")
        path = self.root / "客户确认-real-fail.md"
        path.write_text(text, encoding="utf-8")
        info = parse_confirmation(path)
        self.assertFalse(info["is_placeholder"])
        self.assertEqual(info["decision"], "fail")
        self.assertFalse(info["has_decision"])

    def test_parse_confirmation_real_template_conditional(self):
        """真实模板 + 有条件放行 → conditional（不能再误判为 pass）。"""
        text = self._load_template("delivery-client-gate", "templates", "客户确认记录模板.md")
        text = self._fill_template(text, decision="有条件放行", representative="李振宇", method="邮件")
        path = self.root / "客户确认-real-conditional.md"
        path.write_text(text, encoding="utf-8")
        info = parse_confirmation(path)
        self.assertFalse(info["is_placeholder"])
        self.assertEqual(info["decision"], "conditional")
        self.assertFalse(info["has_decision"])  # conditional 不算已放行

    def test_parse_confirmation_real_template_pass_with_reverse_mention(self):
        """codex 明确要求：正文说明段含「不放行」字样，但结论行填「放行」→ pass。"""
        text = self._load_template("delivery-client-gate", "templates", "客户确认记录模板.md")
        text = self._fill_template(text, decision="放行", representative="李振宇", method="邮件")
        # 在结论说明段强插「不放行」字样
        text = text.replace(
            "说明",
            "说明：范围已澄清。先前担心不放行的部分已消解，研发可启动。",
        )
        path = self.root / "客户确认-real-reverse.md"
        path.write_text(text, encoding="utf-8")
        info = parse_confirmation(path)
        self.assertEqual(info["decision"], "pass")  # 不能因正文反向词误判

    # —— 验收：3 个真实模板回归 ——

    def test_parse_acceptance_real_template_pass(self):
        text = self._load_template("delivery-acceptance-gate", "templates", "验收报告模板.md")
        text = self._fill_template(text, decision="通过", method="签字盖章")
        path = self.root / "验收-real-pass.md"
        path.write_text(text, encoding="utf-8")
        info = parse_acceptance(path)
        self.assertEqual(info["conclusion"], "pass")
        self.assertEqual(info["method"], "签字盖章")
        self.assertEqual(info["confirmed_at"], "2026-08-01")

    def test_parse_acceptance_real_template_fail(self):
        text = self._load_template("delivery-acceptance-gate", "templates", "验收报告模板.md")
        text = self._fill_template(text, decision="不通过", method="签字盖章")
        path = self.root / "验收-real-fail.md"
        path.write_text(text, encoding="utf-8")
        info = parse_acceptance(path)
        self.assertEqual(info["conclusion"], "fail")

    def test_parse_acceptance_real_template_pass_with_reverse_mention(self):
        """验收：正文提到「不通过」但结论行填「通过」→ 仍 pass。"""
        text = self._load_template("delivery-acceptance-gate", "templates", "验收报告模板.md")
        text = self._fill_template(text, decision="通过", method="签字盖章")
        text = text.replace("说明", "说明：原标记不通过的两项已修复并重测，本次通过。")
        path = self.root / "验收-real-reverse.md"
        path.write_text(text, encoding="utf-8")
        info = parse_acceptance(path)
        self.assertEqual(info["conclusion"], "pass")

    # —— 评测：3 个真实模板回归 ——

    def test_parse_evaluation_real_template_pass(self):
        text = self._load_template("delivery-eval-loop", "templates", "评测报告模板.md")
        text = self._fill_template(text, decision="放行")
        path = self.root / "评测-real-pass.md"
        path.write_text(text, encoding="utf-8")
        info = parse_evaluation(path)
        self.assertTrue(info["has_tier1"])
        self.assertTrue(info["has_threshold"])
        self.assertEqual(info["conclusion"], "pass")

    def test_parse_evaluation_real_template_fail(self):
        text = self._load_template("delivery-eval-loop", "templates", "评测报告模板.md")
        text = self._fill_template(text, decision="不放行")
        path = self.root / "评测-real-fail.md"
        path.write_text(text, encoding="utf-8")
        info = parse_evaluation(path)
        self.assertEqual(info["conclusion"], "fail")

    def test_parse_evaluation_real_template_pass_with_reverse_mention(self):
        """评测：正文提「阻断」但结论行「放行」→ 仍 pass。"""
        text = self._load_template("delivery-eval-loop", "templates", "评测报告模板.md")
        text = self._fill_template(text, decision="放行")
        # 替换阻断原因行
        text = text.replace("阻断原因：__________", "阻断原因：原阻断项已修复。")
        path = self.root / "评测-real-reverse.md"
        path.write_text(text, encoding="utf-8")
        info = parse_evaluation(path)
        self.assertEqual(info["conclusion"], "pass")

    # —— 阶段七：revert 撤回 + next_action_suggestion ——

    def _write_progress_with_stage(self, current_stage: str, done_stages: list[str] | None = None) -> Path:
        """构造 project-progress.yaml：current_stage 指向指定阶段，前面阶段标 done。"""
        done_stages = done_stages or []
        all_stages = (
            "opportunity", "proposal", "deal_gate",
            "requirements", "analysis", "prd", "ux", "prototype",
            "client_gate", "architecture", "tech_readiness",
            "story_breakdown", "feishu_sync", "development",
            "eval", "qa", "acceptance_gate",
        )
        lines = ['project: "示例"', 'current_stage: "{}"'.format(current_stage), "stages:"]
        for sid in all_stages:
            if sid in done_stages:
                lines.append(f"  {sid}: {{status: done, completed_at: \"2026-08-01\"}}")
            elif sid == current_stage:
                lines.append(f"  {sid}: {{status: in_progress, started_at: \"2026-08-01\"}}")
            else:
                lines.append(f"  {sid}: {{status: pending}}")
        path = self.root / "project-progress.yaml"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_revert_archives_formal_when_no_draft(self):
        """无 draft 草稿同伴时：正式文件改名归档为 .reverted-{timestamp}。"""
        self._write_progress_with_stage("deal_gate", done_stages=["opportunity", "proposal"])
        formal = self.root / "立项包.md"
        formal.write_text("# 立项包\n合同范围...", encoding="utf-8")
        result = revert_step(self.root)
        self.assertEqual(result["reverted_stage"], "deal_gate")
        # 原文件不存在
        self.assertFalse(formal.exists())
        # 归档文件存在，文件名含 reverted-
        archived = list(self.root.glob("立项包.md.reverted-*"))
        self.assertEqual(len(archived), 1)
        actions = [f["action"] for f in result["files"]]
        self.assertIn("archived", actions)

    def test_revert_restores_from_draft_when_companion_exists(self):
        """有 draft 草稿同伴时：删正式文件，保留 draft。"""
        self._write_progress_with_stage("prd", done_stages=["opportunity", "proposal", "deal_gate", "requirements", "analysis"])
        formal = self.root / "PRD.md"
        formal.write_text("# PRD\n正式版本", encoding="utf-8")
        draft = self.root / "PRD.draft.md"
        draft.write_text("# PRD\n草稿版本", encoding="utf-8")
        result = revert_step(self.root)
        # 正式文件被删，draft 保留
        self.assertFalse(formal.exists())
        self.assertTrue(draft.exists())
        # result 里 action 是 restored_from_draft
        actions = [f["action"] for f in result["files"]]
        self.assertIn("restored_from_draft", actions)

    def test_revert_returns_not_found_when_no_artifacts(self):
        """无产物时：返回 not_found 但不报错。"""
        self._write_progress_with_stage("analysis", done_stages=["opportunity", "proposal", "deal_gate", "requirements"])
        result = revert_step(self.root)
        self.assertEqual(result["reverted_stage"], "analysis")
        self.assertEqual(result["files"][0]["action"], "not_found")
        self.assertEqual(result["error"], "")

    def test_revert_rejects_invalid_stage(self):
        """非法 stage：返回 error，不写任何文件。"""
        formal = self.root / "PRD.md"
        formal.write_text("# PRD", encoding="utf-8")
        result = revert_step(self.root, stage_id="totally_made_up")
        self.assertIn("非法 stage", result["error"])
        # 正式文件没被动
        self.assertTrue(formal.exists())

    def test_revert_updates_progress_to_pending(self):
        """撤回后 progress.yaml 中该 stage 状态变 pending，清掉 completed_at。"""
        self._write_progress_with_stage("deal_gate", done_stages=["opportunity", "proposal"])
        formal = self.root / "立项包.md"
        formal.write_text("# 立项包", encoding="utf-8")
        revert_step(self.root)
        progress_path = self.root / "project-progress.yaml"
        data = read_progress(progress_path)
        self.assertEqual(data["stages"]["deal_gate"]["status"], "pending")
        self.assertNotIn("completed_at", data["stages"]["deal_gate"])

    def test_revert_moves_current_stage_backward(self):
        """撤回 current_stage 时：current_stage 回退到上一个 done的阶段。"""
        self._write_progress_with_stage("deal_gate", done_stages=["opportunity", "proposal"])
        formal = self.root / "立项包.md"
        formal.write_text("# 立项包", encoding="utf-8")
        result = revert_step(self.root)
        # deal_gate 是 current，回退后 current 应该变成 proposal（上一个 done）
        self.assertEqual(result["new_current_stage"], "proposal")
        self.assertEqual(result["new_current_status"], "in_progress")
        progress_path = self.root / "project-progress.yaml"
        data = read_progress(progress_path)
        self.assertEqual(data["current_stage"], "proposal")
        self.assertEqual(data["stages"]["proposal"]["status"], "in_progress")

    def test_revert_explicit_step(self):
        """--step 精确指定 stage：忽略 current_stage，回退指定 stage。"""
        self._write_progress_with_stage("architecture", done_stages=["opportunity", "proposal", "deal_gate"])
        biz = self.root / "业务架构.md"
        biz.write_text("# 业务架构", encoding="utf-8")
        result = revert_step(self.root, stage_id="architecture")
        self.assertEqual(result["reverted_stage"], "architecture")
        self.assertFalse(biz.exists())

    def test_revert_without_progress_yaml(self):
        """无 progress.yaml 时：必须 --step，否则报错。"""
        # 无 progress.yaml 时不指定 stage → 报错
        result = revert_step(self.root, stage_id=None)
        self.assertIn("project-progress.yaml", result["error"])

    def test_next_action_suggestion_normal_progress(self):
        """正常推进中：给出 next_stage + 建议问句。"""
        progress_data = {
            "project": "测试",
            "current_stage": "deal_gate",
            "stages": {
                "opportunity": {"status": "done"},
                "proposal": {"status": "done"},
                "deal_gate": {"status": "in_progress"},
                "requirements": {"status": "pending"},
            },
        }
        result = next_action_suggestion(progress_data, gate_statuses={})
        self.assertTrue(result["should_ask_user"])
        self.assertEqual(result["next_stage"], "requirements")
        self.assertIn("deal_gate", result["suggested_question"])
        self.assertIn("requirements", result["suggested_question"])
        self.assertEqual(result["blocking_gates"], [])

    def test_next_action_suggestion_blocks_when_gates_unknown(self):
        """关卡状态 unknown/fail：返回阻断建议，问用户是否补/撤回。"""
        progress_data = {
            "project": "测试",
            "current_stage": "architecture",
            "stages": {
                "opportunity": {"status": "done"},
                "proposal": {"status": "done"},
                "deal_gate": {"status": "done"},
                "requirements": {"status": "done"},
                "analysis": {"status": "done"},
                "prd": {"status": "done"},
                "ux": {"status": "done"},
                "prototype": {"status": "done"},
                "client_gate": {"status": "in_progress"},
                "architecture": {"status": "in_progress"},
            },
        }
        result = next_action_suggestion(
            progress_data,
            gate_statuses={"client": "unknown", "readiness": "fail", "eval": "pass", "acceptance": "pass"},
        )
        self.assertIn("client", result["blocking_gates"])
        self.assertIn("readiness", result["blocking_gates"])
        self.assertIn("客户签字", result["suggested_question"])
        self.assertIn("技术就绪", result["suggested_question"])

    def test_next_action_suggestion_completed_state(self):
        """验收完成态（current_stage=null + acceptance_gate=done）：询问用户复盘/立项。"""
        progress_data = {
            "project": "测试",
            "current_stage": None,
            "stages": {
                "acceptance_gate": {"status": "done"},
            },
        }
        result = next_action_suggestion(progress_data, gate_statuses={})
        self.assertTrue(result["should_ask_user"])
        self.assertIn("复盘", result["suggested_question"])

    def test_next_action_suggestion_without_progress(self):
        """无 progress_data：返回引导性问句。"""
        result = next_action_suggestion(None, gate_statuses={})
        self.assertTrue(result["should_ask_user"])
        self.assertIn("project-progress.yaml", result["suggested_question"])


if __name__ == "__main__":
    unittest.main()
