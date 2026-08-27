#!/usr/bin/env python3
"""
delivery-flow「不重复造轮子」能力重叠校验脚本（stdlib only）。

判定规则：
  1. 解析新 SKILL.md 的 frontmatter description 字段
  2. 剥触发句（"当用户说...时使用"）
  3. 中文按字 bigram，英文按词；叠加 CAPABILITY_BOUNDARIES.md 的别名行扩展关键词集
  4. 与仓库内 21 个 SKILL.md 的 description 算 Overlap 系数 |A∩B| / min(|A|, |B|)
  5. 阈值：≥ 0.8 → FAIL；≥ 0.6 → WARN；< 0.6 → PASS
  6. FAIL 必须修复（重叠未在 CAPABILITY_BOUNDARIES.md 声明边界）才允许合并
  7. WARN 仅警告，重叠已在 CAPABILITY_BOUNDARIES.md 声明 BOUNDARY_DECLARED/OVERLAP_REMOVED 时不阻塞

退出码：PASS=0 / WARN=0 / FAIL=1（CI 阻塞 FAIL）

CLI：
  python scripts/check_capability_overlap.py --new-skill <path>           # 校验单文件
  python scripts/check_capability_overlap.py --all [--include-untracked]  # 本地全量回归
  python scripts/check_capability_overlap.py --diff <ref>                 # CI 用：比 <ref>..HEAD 改动的 SKILL.md
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
BOUNDARIES_FILE = ROOT / ".claude-plugin" / "CAPABILITY_BOUNDARIES.md"
EXTERNAL_FILE = ROOT / ".claude-plugin" / "external_skills.json"

THRESHOLD_FAIL = 0.8
THRESHOLD_WARN = 0.6
TRIGGER_PATTERN = re.compile(r"当用户说.*?时使用[。\.]?")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
DESC_FIELD_PATTERN = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)
ASCII_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]+")
CHINESE_CHAR_PATTERN = re.compile(r"[一-鿿]")


def parse_description(skill_path: pathlib.Path) -> Optional[str]:
    """从 SKILL.md frontmatter 抽出 description 字段；不存在则返回 None。"""
    try:
        text = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fm_match = FRONTMATTER_PATTERN.match(text)
    if not fm_match:
        return None
    desc_match = DESC_FIELD_PATTERN.search(fm_match.group(1))
    if not desc_match:
        return None
    return desc_match.group(1).strip()


def strip_trigger_phrase(description: str) -> str:
    """剥掉触发句 '当用户说"..."时使用'，避免污染关键词集合。"""
    return TRIGGER_PATTERN.sub("", description).strip()


def tokenize(description: str) -> Set[str]:
    """关键词集合：英文按词、中文按字 bigram。"""
    tokens: Set[str] = set()
    # 英文词（保留 SSOT / SPEC / DoD 等有意义缩写）
    for word in ASCII_WORD_PATTERN.findall(description):
        if len(word) >= 2:
            tokens.add(word.lower())
    # 中文按字 bigram（Plan agent 实测 Jaccard 不够；用 bigram 提升区分度）
    chinese_text = "".join(CHINESE_CHAR_PATTERN.findall(description))
    for i in range(len(chinese_text) - 1):
        tokens.add(chinese_text[i : i + 2])
    return tokens


def parse_boundaries() -> Dict[str, Dict[str, str]]:
    """
    解析 CAPABILITY_BOUNDARIES.md。
    返回 {skill_name: {"boundary": "...", "tag": "UNIQUE|BOUNDARY_DECLARED|OVERLAP_REMOVED", "aliases": "..."}}。
    格式：### delivery-xxx\n> 边界：...\n> 标签：...\n> 别名：...
    """
    if not BOUNDARIES_FILE.exists():
        return {}
    boundaries: Dict[str, Dict[str, str]] = {}
    current: Optional[str] = None
    field_map = {"边界": "boundary", "标签": "tag", "别名": "aliases"}
    for raw_line in BOUNDARIES_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        header_match = re.match(r"^### (delivery-[a-z-]+)\s*$", line)
        if header_match:
            current = header_match.group(1)
            boundaries[current] = {"boundary": "", "tag": "UNIQUE", "aliases": ""}
            continue
        if current and line.startswith("> "):
            for cn_label, en_key in field_map.items():
                prefix = f"> {cn_label}："
                if line.startswith(prefix):
                    boundaries[current][en_key] = line[len(prefix):].strip()
                    break
    return boundaries


def declared_aliases_for(boundaries: Dict[str, Dict[str, str]], skill_name: str) -> List[str]:
    """从 CAPABILITY_BOUNDARIES.md 取某个 skill 的声明别名（仅用于降级判定，不参与相似度计算）。"""
    info = boundaries.get(skill_name, {})
    aliases = info.get("aliases", "")
    return [a.strip().lower() for a in re.split(r"[,，、\s]+", aliases) if a.strip() and len(a.strip()) >= 2]


def overlap_coefficient(a: Set[str], b: Set[str]) -> float:
    """|A∩B| / min(|A|, |B|)；避免小集合稀释。"""
    if not a or not b:
        return 0.0
    intersection = a & b
    return len(intersection) / min(len(a), len(b))


def collect_existing_skills(include_untracked: bool = False) -> List[pathlib.Path]:
    """扫仓库 skills/ 下全部 SKILL.md；可选包含 git 未追踪文件。"""
    if not SKILLS_DIR.exists():
        return []
    paths = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if include_untracked:
        try:
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "skills/"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
            for rel in untracked:
                p = ROOT / rel
                if p.exists() and p not in paths:
                    paths.append(p)
        except subprocess.CalledProcessError:
            pass
    return paths


def check_one(
    new_skill_path: pathlib.Path,
    existing_paths: List[pathlib.Path],
    boundaries: Dict[str, Dict[str, str]],
) -> Tuple[str, List[Tuple[str, float]]]:
    """
    校验单个 SKILL.md 与现有所有 skill 的重叠度。
    返回 (verdict, [(existing_skill_name, overlap_score), ...])，verdict ∈ {PASS, WARN, FAIL}。
    """
    new_desc = parse_description(new_skill_path)
    if new_desc is None:
        return "FAIL", []  # 无 description 字段是结构性失败
    new_desc_clean = strip_trigger_phrase(new_desc)
    new_tokens = tokenize(new_desc_clean)

    # 新 skill 在边界文件里登记的标签（若有）
    new_skill_name = new_skill_path.parent.name
    new_tag = boundaries.get(new_skill_name, {}).get("tag", "")

    overlaps: List[Tuple[str, float]] = []
    max_score = 0.0
    max_skill = ""
    for existing in existing_paths:
        if existing.resolve() == new_skill_path.resolve():
            continue  # 跳过自身
        existing_desc = parse_description(existing)
        if existing_desc is None:
            continue
        existing_clean = strip_trigger_phrase(existing_desc)
        existing_tokens = tokenize(existing_clean)
        score = overlap_coefficient(new_tokens, existing_tokens)
        if score >= THRESHOLD_WARN:
            overlaps.append((existing.parent.name, score))
            if score > max_score:
                max_score = score
                max_skill = existing.parent.name

    overlaps.sort(key=lambda x: x[1], reverse=True)

    if max_score >= THRESHOLD_FAIL:
        return "FAIL", overlaps
    if max_score >= THRESHOLD_WARN:
        # WARN 判定：若重叠目标在 CAPABILITY_BOUNDARIES.md 声明了 BOUNDARY_DECLARED/OVERLAP_REMOVED 标签
        # 则降级为 PASS（已声明边界，不阻塞）
        target_tag = boundaries.get(max_skill, {}).get("tag", "")
        if target_tag in ("BOUNDARY_DECLARED", "OVERLAP_REMOVED"):
            return "PASS", overlaps
        return "WARN", overlaps
    return "PASS", overlaps


def cmd_new_skill(path: pathlib.Path, include_untracked: bool) -> int:
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    boundaries = parse_boundaries()
    existing = collect_existing_skills(include_untracked=include_untracked)
    verdict, overlaps = check_one(path, existing, boundaries)
    rel = path.relative_to(ROOT) if path.is_absolute() else path
    print(f"\n=== {rel} → {verdict} ===")
    if overlaps:
        print(f"Top overlaps (threshold WARN={THRESHOLD_WARN}, FAIL={THRESHOLD_FAIL}):")
        for name, score in overlaps[:5]:
            tag = boundaries.get(name, {}).get("tag", "UNREGISTERED")
            print(f"  {score:.3f}  {name}  [{tag}]")
    else:
        print("No significant overlaps detected.")
    if verdict == "FAIL":
        print("\n→ 修复指引：在 .claude-plugin/CAPABILITY_BOUNDARIES.md 给本 skill 加段落，"
              "或在 description 里减少与现有 skill 重叠的关键词。")
    elif verdict == "WARN":
        print("\n→ 警告：重叠未声明边界。请在 CAPABILITY_BOUNDARIES.md 给新 skill 或目标 skill 加 BOUNDARY_DECLARED 标签。")
    return 0 if verdict in ("PASS", "WARN") else 1


def cmd_all(include_untracked: bool) -> int:
    """全量回归：每个 skill 都跟其他 20 个比对。"""
    boundaries = parse_boundaries()
    existing = collect_existing_skills(include_untracked=include_untracked)
    if not existing:
        print("No SKILL.md found under skills/", file=sys.stderr)
        return 1
    any_fail = False
    any_warn = False
    print(f"=== 全量回归：{len(existing)} 个 SKILL.md ===\n")
    for skill in existing:
        verdict, overlaps = check_one(skill, existing, boundaries)
        marker = {"PASS": "+", "WARN": "!", "FAIL": "X"}[verdict]
        rel = skill.relative_to(ROOT)
        max_overlap = overlaps[0] if overlaps else None
        if max_overlap:
            print(f"  {marker} {verdict:4}  {rel}  (max {max_overlap[0]}={max_overlap[1]:.3f})")
        else:
            print(f"  {marker} {verdict:4}  {rel}")
        if verdict == "FAIL":
            any_fail = True
        elif verdict == "WARN":
            any_warn = True
    print(f"\n=== 总计：PASS={sum(1 for s in existing if check_one(s, existing, boundaries)[0]=='PASS')}, "
          f"WARN={any_warn}, FAIL={any_fail} ===")
    return 1 if any_fail else 0


def cmd_diff(ref: str, include_untracked: bool) -> int:
    """CI 用：列出 <ref>..HEAD 改动的 SKILL.md 并逐个校验。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=AM", f"{ref}..HEAD", "--", "skills/"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"git diff failed: {e.stderr}", file=sys.stderr)
        return 1
    changed = [ROOT / line for line in result.stdout.splitlines() if line.strip()]
    if not changed:
        print(f"No SKILL.md changes between {ref}..HEAD.")
        return 0
    boundaries = parse_boundaries()
    existing = collect_existing_skills(include_untracked=include_untracked)
    any_fail = False
    print(f"=== Diff mode: {len(changed)} SKILL.md changed since {ref} ===\n")
    for path in changed:
        verdict, overlaps = check_one(path, existing, boundaries)
        marker = {"PASS": "+", "WARN": "!", "FAIL": "X"}[verdict]
        print(f"  {marker} {verdict:4}  {path.relative_to(ROOT)}")
        for name, score in overlaps[:3]:
            print(f"           {score:.3f}  {name}")
        if verdict == "FAIL":
            any_fail = True
    return 1 if any_fail else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="delivery-flow capability overlap check (stdlib only)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--new-skill", type=pathlib.Path, help="校验单个 SKILL.md")
    group.add_argument("--all", action="store_true", help="全量回归所有 skill")
    group.add_argument("--diff", metavar="REF", help="CI 用：比对 <REF>..HEAD 改动的 SKILL.md")
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="包含 git 未追踪的 SKILL.md（防 skills/* 新建未提交时漏网）",
    )
    args = parser.parse_args()

    if args.new_skill is not None:
        return cmd_new_skill(args.new_skill, args.include_untracked)
    if args.all:
        return cmd_all(args.include_untracked)
    if args.diff is not None:
        return cmd_diff(args.diff, args.include_untracked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
