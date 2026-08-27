"""
check_capability_overlap.py 的单元测试（stdlib only）。

覆盖场景：
  - PASS：全新能力的 description，与现有 skill 不重叠
  - FAIL：与现有 description 完全复制，重叠度 1.0
  - FAIL：缺少 frontmatter description 字段（结构性失败）
  - 触发句剥离：包含「当用户说...时使用」应被剥离
  - 边界文件解析：21 个 skill 全部登记
"""

import sys
import pathlib
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_capability_overlap import (  # noqa: E402
    parse_description,
    strip_trigger_phrase,
    tokenize,
    overlap_coefficient,
    parse_boundaries,
    check_one,
)


class TestDescriptionParsing(unittest.TestCase):
    def test_parse_real_skill(self):
        desc = parse_description(REPO_ROOT / "skills" / "delivery-bootstrap" / "SKILL.md")
        self.assertIsNotNone(desc)
        self.assertIn("delivery-flow", desc)

    def test_parse_missing_description(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("---\nname: foo\n---\n# body\n")
            path = pathlib.Path(f.name)
        try:
            self.assertIsNone(parse_description(path))
        finally:
            path.unlink()

    def test_parse_no_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# no frontmatter\nbody\n")
            path = pathlib.Path(f.name)
        try:
            self.assertIsNone(parse_description(path))
        finally:
            path.unlink()


class TestTriggerPhraseStrip(unittest.TestCase):
    def test_strip_when_user_says(self):
        text = "这是描述当用户说\"装插件\"或\"初始化\"时使用。后面是核心。"
        result = strip_trigger_phrase(text)
        self.assertNotIn("当用户说", result)
        self.assertIn("这是描述", result)
        self.assertIn("核心", result)

    def test_no_trigger_phrase(self):
        text = "纯描述无触发句。"
        self.assertEqual(strip_trigger_phrase(text), text)


class TestTokenize(unittest.TestCase):
    def test_chinese_bigrams(self):
        tokens = tokenize("检查交付项目")
        self.assertIn("检查", tokens)
        self.assertIn("查交", tokens)
        self.assertIn("交付", tokens)
        self.assertIn("付项", tokens)
        self.assertIn("项目", tokens)

    def test_english_words(self):
        tokens = tokenize("SPEC.md and SSOT truth")
        self.assertIn("spec", tokens)
        self.assertIn("ssot", tokens)
        self.assertIn("truth", tokens)

    def test_short_words_filtered(self):
        tokens = tokenize("a bb ccc")
        self.assertNotIn("a", tokens)
        self.assertIn("bb", tokens)
        self.assertIn("ccc", tokens)


class TestOverlapCoefficient(unittest.TestCase):
    def test_identical(self):
        a = {"x", "y", "z"}
        self.assertEqual(overlap_coefficient(a, a), 1.0)

    def test_disjoint(self):
        self.assertEqual(overlap_coefficient({"x"}, {"y"}), 0.0)

    def test_empty(self):
        self.assertEqual(overlap_coefficient(set(), {"x"}), 0.0)

    def test_overlap_uses_min_not_avg(self):
        """Overlap 系数 = |A∩B| / min(|A|, |B|)，不是 Jaccard。"""
        a = {"x", "y", "z", "w"}  # 4
        b = {"x", "y"}            # 2
        # Overlap = 2 / min(4, 2) = 1.0
        # Jaccard = 2 / 4 = 0.5
        self.assertEqual(overlap_coefficient(a, b), 1.0)


class TestBoundariesParsing(unittest.TestCase):
    def test_parses_all_21_skills(self):
        boundaries = parse_boundaries()
        self.assertGreaterEqual(len(boundaries), 21, f"only {len(boundaries)} parsed")
        # 每个 skill 必须有 tag 字段
        for name, info in boundaries.items():
            self.assertIn("tag", info, f"{name} missing tag")
            self.assertIn(info["tag"], ("UNIQUE", "BOUNDARY_DECLARED", "OVERLAP_REMOVED"))


class TestCheckOne(unittest.TestCase):
    """端到端：用一个临时 SKILL.md 跟真实 21 个 skill 比对。"""

    def test_pass_brand_new_capability(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(
                "---\n"
                "name: brand-new\n"
                "description: 一个全新能力，管理客户付款发票与税务对账，"
                "在合同签约后触发。当用户说\"开发票\"时使用。\n"
                "---\n"
                "# body\n"
            )
            path = pathlib.Path(f.name)
        try:
            existing = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
            boundaries = parse_boundaries()
            verdict, overlaps = check_one(path, existing, boundaries)
            self.assertEqual(verdict, "PASS", f"got {verdict}, overlaps={overlaps}")
        finally:
            path.unlink()

    def test_fail_exact_duplicate(self):
        """复制 delivery-trace 的 description 应触发 FAIL。"""
        original_desc = parse_description(REPO_ROOT / "skills" / "delivery-trace" / "SKILL.md")
        self.assertIsNotNone(original_desc)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(
                "---\n"
                "name: fake-trace\n"
                f"description: {original_desc}\n"
                "---\n"
                "# body\n"
            )
            path = pathlib.Path(f.name)
        try:
            existing = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
            boundaries = parse_boundaries()
            verdict, overlaps = check_one(path, existing, boundaries)
            self.assertEqual(verdict, "FAIL")
            self.assertGreater(len(overlaps), 0)
            top_name, top_score = overlaps[0]
            self.assertEqual(top_name, "delivery-trace")
            self.assertGreater(top_score, 0.8)
        finally:
            path.unlink()

    def test_fail_missing_description(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("---\nname: no-desc\n---\n# body\n")
            path = pathlib.Path(f.name)
        try:
            existing = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
            boundaries = parse_boundaries()
            verdict, _ = check_one(path, existing, boundaries)
            self.assertEqual(verdict, "FAIL")
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
