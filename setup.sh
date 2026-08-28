#!/usr/bin/env bash
# setup.sh — delivery-flow 一键配置脚本（Git Bash / macOS / Linux）
#
# 作用：
#   1. 在当前目录生成精简版 AGENTS.md（自动填入插件路径）
#   2. 为 Claude Code 建 .claude/plugins/delivery-flow 软链接
#   3. 为 Codex / Cursor / Windsurf 生成对应规则文件
#   4. （可选 --bmad）调用 npx bmad-method 自动安装 BMAD
#
# 用法：
#   cd <你的项目>
#   bash <(curl -fsSL https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.sh) \
#     --plugin-path D:/tools/delivery-flow
#
# 可选参数：
#   --plugin-path PATH        插件本地路径（必填）
#   --no-claude               跳过 Claude Code 软链接配置
#   --no-codex                跳过 Codex AGENTS.md
#   --no-cursor               跳过 Cursor 规则
#   --no-windsurf             跳过 Windsurf 规则
#   --bmad                    启用 BMAD-METHOD 自动安装（默认关闭）
#   --bmad-tools <list>       BMAD 工具列表（默认 claude-code，多个用逗号）
#   --bmad-modules <list>     BMAD 模块列表（默认空，用 installer 默认）
#   --bmad-timeout <sec>      BMAD 安装超时秒数（默认 600）
#   --init                    启用项目模板初始化（复制 project-context.md /
#                             project-progress.yaml 到当前目录，默认关闭）
#   --init-name <name>        项目名（默认取当前目录名）
#   --init-user <name>        负责人名（默认 $USER）
#   --init-date <yyyy-mm-dd>  日期（默认今天）
#   --init-force              覆盖已存在的项目文件（默认 skip）
#   --no-init-progress        只复制 project-context.md，不复制 progress
#   --no-init-context         只复制 project-progress.yaml，不复制 context
#   --dry-run                 只打印将要做什么，不实际执行（不写文件、不建软链接、不调 npx）
#   -h, --help                显示帮助

set -euo pipefail

PLUGIN_PATH=""
DO_CLAUDE=1
DO_CODEX=1
DO_CURSOR=1
DO_WINDSURF=1
DO_BMAD=0
BMAD_TOOLS="claude-code"
BMAD_MODULES=""
BMAD_TIMEOUT=600

DO_INIT=0
DO_INIT_PROGRESS=1
DO_INIT_CONTEXT=1
INIT_NAME=""
INIT_USER="${USER:-unknown}"
INIT_DATE="$(date +%Y-%m-%d)"
INIT_FORCE=0
DRY_RUN=0

usage() {
  # 输出脚本头部到第一个空行（注释块结束）之间的内容作为帮助
  awk 'NR==1 || (/^[^#]/ && !done) {next} /^#/ {print; if(/^# -h/||/^# -h, --help/) done=1; next} {exit}' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin-path)    PLUGIN_PATH="$2"; shift 2;;
    --no-claude)      DO_CLAUDE=0; shift;;
    --no-codex)       DO_CODEX=0; shift;;
    --no-cursor)      DO_CURSOR=0; shift;;
    --no-windsurf)    DO_WINDSURF=0; shift;;
    --bmad)           DO_BMAD=1; shift;;
    --bmad-tools)     BMAD_TOOLS="$2"; shift 2;;
    --bmad-modules)   BMAD_MODULES="$2"; shift 2;;
    --bmad-timeout)   BMAD_TIMEOUT="$2"; shift 2;;
    --init)           DO_INIT=1; shift;;
    --init-name)      INIT_NAME="$2"; shift 2;;
    --init-user)      INIT_USER="$2"; shift 2;;
    --init-date)      INIT_DATE="$2"; shift 2;;
    --init-force)     INIT_FORCE=1; shift;;
    --no-init-progress) DO_INIT_PROGRESS=0; shift;;
    --no-init-context)  DO_INIT_CONTEXT=0; shift;;
    --dry-run)        DRY_RUN=1; shift;;
    -h|--help)        usage;;
    *) echo "未知参数：$1" >&2; exit 1;;
  esac
done

if [[ -z "$PLUGIN_PATH" ]]; then
  echo "❌ 缺少 --plugin-path 参数" >&2
  echo "示例：bash setup.sh --plugin-path D:/tools/delivery-flow" >&2
  exit 1
fi

# 把 Windows 路径 D:\tools\xxx 转成 Git Bash 可识别的 /d/tools/xxx
PLUGIN_PATH_BASH=$(echo "$PLUGIN_PATH" | sed -E 's|^([A-Za-z]):|/\L\1|; s|\\|/|g')
PLUGIN_PATH_ESCAPED=$(echo "$PLUGIN_PATH" | sed 's|\\|\\\\|g')

# 校验插件路径
if [[ ! -d "$PLUGIN_PATH_BASH" && ! -d "$PLUGIN_PATH" ]]; then
  echo "❌ 插件路径不存在：$PLUGIN_PATH" >&2
  echo "   请先 git clone delivery-flow 到该路径" >&2
  exit 1
fi

if [[ ! -d "$PLUGIN_PATH_BASH/skills" && ! -d "$PLUGIN_PATH/skills" ]]; then
  echo "❌ 路径下找不到 skills/ 目录，确认是 delivery-flow 仓库" >&2
  exit 1
fi

echo "✅ 检测到 delivery-flow 插件：$PLUGIN_PATH"
echo "📍 当前目录：$(pwd)"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "🧪 DRY-RUN 模式：只打印将要做什么，不实际执行"
fi
echo ""

# ===== 1. 生成 AGENTS.md（Codex / 其他工具共用）=====
if [[ "$DO_CODEX" == "1" ]]; then
  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -f "AGENTS.md" ]]; then
      echo "🧪 [dry-run] AGENTS.md 已存在，将跳过（用 --init-force 覆盖）"
    else
      echo "🧪 [dry-run] 将生成 AGENTS.md（Codex / 其他工具）"
    fi
  elif [[ -f "AGENTS.md" ]]; then
    echo "⏭️  AGENTS.md 已存在，跳过生成（如需重新生成请手动删除）"
  else
    cat > AGENTS.md <<'EOF'
# AGENTS.md — 项目 AI 工作指令

> delivery-flow 入口。新对话开始自动读取。

## 1. 插件路径

```
${PLUGIN_PATH_ESCAPED}
```

## 2. 启动动作（每个新对话必做）

按顺序：
1. 调 `python "${PLUGIN_PATH//\\/\\\\}delivery.py" progress --root . --json` 读当前阶段
2. 读 `project-context.md`（项目宪法，不存在则提示生成）
3. 扫项目根所有文档（不要求用户整理）

## 3. 阶段路由（不要靠记忆判断）

- "现在到哪了" → 调 `progress`，复述 `next_action_suggestion.suggested_question`
- "下一步" → 调 `dry-run`，列出操作清单等我确认
- "撤回" → 调 `delivery revert --step <stage_id>`
- "我是 XX 角色，做 XX" → 读 progress + 角色路由表决定 skill

**角色 → skill 路由**：
- 商务/售前 → `delivery-presales` / `delivery-deal-gate`
- PM → BMAD `brainstorm` / `write-prd` / `delivery-client-gate`
- 项目经理 → `delivery-plan` / `delivery-feishu-sync` / `delivery-acceptance-gate`
- 研发 → Superpowers `tdd` / `writing-plans`
- AI 工程师 → `delivery-eval-loop` / `pm-ai-shipping:ship-check`

## 4. 三个纪律（违反即报错）

1. **逐步确认**：每 step 前告诉我"要做 X、产出 Y"，等我说"继续"再执行
2. **不确定就问**：不替我拍板
3. **草稿态**：先写 `.draft.`，确认后才 mv

## 5. 详细规则查这里

- 21 个 skill 清单：`${PLUGIN_PATH_ESCAPED}\README.md` 第 40-48 行
- 三步循环：README 第 458-465 行
- 状态机：`project-progress.yaml`

## 6. 自检（出问题先跑这个）

脚本：`bash ${PLUGIN_PATH_BASH}/setup-verify.sh --json`

AI 触发词："verify 一下" / "setup 出问题了" / "AI 找不到插件" → 跑上面脚本，按 `has_error` 决定修复策略。

## 7. 模型分层（让大模型思考，小模型执行）

读 `project-context.md` 的「模型分层策略」节。**支持两种协作模式**：

### A. 同工具内分层（如都在 Claude Code / 都在 Codex CLI）

- "出方案" / "想一下" / "列计划" → 当前阶段的**思考模型**
  - Claude Code：Opus（`/think hard` 或 Task tool 调度）
  - Codex CLI：SOL（`/plan` 模式或 "think deep"）
- "按方案执行" / "写代码" / "改这个" → 当前阶段的**执行模型**
  - Claude Code：Sonnet / Haiku
  - Codex CLI：mini / `/code` 模式
- 切换：直接说"切到执行" / "切到思考"

### B. 跨工具交接（思考工具 ≠ 执行工具）⭐常见

- **思考模型**在工具 A 出方案 → **必须写到「交接文件」**（默认 `<阶段目录>/[NN] <产物>.draft.md`，跨工具时由 `project-context.md` 指定）
- **关闭工具 A** → **打开工具 B**（执行模型所在工具）→ **第一句话：`读 <交接文件>，按方案执行`**
- 执行工具读到的方案**必须是 `.draft.` 已 review 态**——不允许读未确认草稿

反模式（出现就停下来问人）：
- 跨工具交接时思考模型没落文件（执行工具找不到依据）
- 执行工具读了未 `.draft.` 的方案（违反 SSOT 纪律）
- 思考 / 执行工具在不同项目目录（上下文丢失）
EOF
    echo "✅ 已生成 AGENTS.md（Codex / 其他工具）"
  fi
fi

# ===== 2. Claude Code 软链接 =====
if [[ "$DO_CLAUDE" == "1" ]]; then
  mkdir -p .claude/plugins

  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -L ".claude/plugins/delivery-flow" || -d ".claude/plugins/delivery-flow" ]]; then
      echo "🧪 [dry-run] .claude/plugins/delivery-flow 已存在"
    else
      echo "🧪 [dry-run] 将建软链接：.claude/plugins/delivery-flow → $PLUGIN_PATH_BASH"
    fi
  elif [[ -L ".claude/plugins/delivery-flow" || -d ".claude/plugins/delivery-flow" ]]; then
    echo "⏭️  .claude/plugins/delivery-flow 已存在"
  else
    ln -s "$PLUGIN_PATH_BASH" .claude/plugins/delivery-flow
    echo "✅ 已建 Claude Code 软链接：.claude/plugins/delivery-flow → $PLUGIN_PATH"
  fi

  # 验证（非 dry-run 才执行）
  if [[ "$DRY_RUN" != "1" ]]; then
    if [[ -d ".claude/plugins/delivery-flow/skills" ]]; then
      SKILL_COUNT=$(ls .claude/plugins/delivery-flow/skills | wc -l)
      echo "✅ 验证通过，检测到 $SKILL_COUNT 个 skill"
    else
      echo "⚠️  警告：软链接建好但看不到 skills/，请检查路径"
    fi
  fi
fi

# ===== 3. Cursor 规则 =====
if [[ "$DO_CURSOR" == "1" ]]; then
  mkdir -p .cursor/rules
  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -f ".cursor/rules/delivery-flow.mdc" ]]; then
      echo "🧪 [dry-run] .cursor/rules/delivery-flow.mdc 已存在"
    else
      echo "🧪 [dry-run] 将生成 .cursor/rules/delivery-flow.mdc"
    fi
  elif [[ -f ".cursor/rules/delivery-flow.mdc" ]]; then
    echo "⏭️  .cursor/rules/delivery-flow.mdc 已存在"
  else
    cat > .cursor/rules/delivery-flow.mdc <<EOF
---
description: delivery-flow 交付工作流指令
globs: ["**/*.md", "**/*.yaml"]
---

# delivery-flow 交付工作流

插件路径：${PLUGIN_PATH}

新对话开始时：
1. 调 \`python "${PLUGIN_PATH//\\/\\\\}delivery.py" progress --root . --json\` 读当前阶段
2. 读 \`project-context.md\` 和 \`AGENTS.md\`
3. 按阶段路由决定调哪个 skill

详细规则见 \`${PLUGIN_PATH}\skills/\` 下各 SKILL.md。
EOF
    echo "✅ 已生成 .cursor/rules/delivery-flow.mdc"
  fi
fi

# ===== 4. Windsurf 规则 =====
if [[ "$DO_WINDSURF" == "1" ]]; then
  mkdir -p .windsurf/rules
  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -f ".windsurf/rules/delivery-flow.md" ]]; then
      echo "🧪 [dry-run] .windsurf/rules/delivery-flow.md 已存在"
    else
      echo "🧪 [dry-run] 将生成 .windsurf/rules/delivery-flow.md"
    fi
  elif [[ -f ".windsurf/rules/delivery-flow.md" ]]; then
    echo "⏭️  .windsurf/rules/delivery-flow.md 已存在"
  else
    cat > .windsurf/rules/delivery-flow.md <<EOF
# delivery-flow 交付工作流

插件路径：${PLUGIN_PATH}

新对话开始时：
1. 调 \`python "${PLUGIN_PATH//\\/\\\\}delivery.py" progress --root . --json\` 读当前阶段
2. 读 \`project-context.md\` 和 \`AGENTS.md\`
3. 按阶段路由决定调哪个 skill
EOF
    echo "✅ 已生成 .windsurf/rules/delivery-flow.md"
  fi
fi

# ===== 5. BMAD-METHOD 自动安装（可选）=====
if [[ "$DO_BMAD" == "1" ]]; then
  echo ""
  echo "==== BMAD-METHOD 安装 ===="

  # 前置检查：node + npx（dry-run 模式仍检查，但不强制 exit）
  if ! command -v node >/dev/null 2>&1; then
    echo "❌ 未检测到 node，请先安装 Node.js 18+：https://nodejs.org" >&2
    [[ "$DRY_RUN" != "1" ]] && { echo "   安装后重跑：bash setup.sh --plugin-path $PLUGIN_PATH --bmad" >&2; exit 1; }
  elif ! command -v npx >/dev/null 2>&1; then
    echo "❌ 未检测到 npx（通常随 Node.js 一同安装），跳过 BMAD 安装" >&2
  else
    NODE_MAJOR=$(node -v | sed -E 's/^v([0-9]+).*/\1/')
    if [[ "$NODE_MAJOR" -lt 18 ]]; then
      echo "⚠️  Node.js 版本为 $(node -v)，BMAD 要求 18+，尝试继续..." >&2
    fi

    BMAD_CMD=(npx -y bmad-method install --directory . --tools "$BMAD_TOOLS" --yes)
    if [[ -n "$BMAD_MODULES" ]]; then
      BMAD_CMD+=(--modules "$BMAD_MODULES")
    fi

    echo "📦 执行：${BMAD_CMD[*]}"
    echo "   （首次运行会下载 bmad-method 包，可能耗时 1-3 分钟；超时 ${BMAD_TIMEOUT}s）"
    echo ""

    # dry-run 模式：只打印命令就跳过执行
    if [[ "$DRY_RUN" == "1" ]]; then
      echo "🧪 [dry-run] 跳过执行"
      echo ""
    else
      # set +e：BMAD 失败不阻塞后续步骤（软链接等已经做完）
      set +e
      if command -v timeout >/dev/null 2>&1; then
        timeout "$BMAD_TIMEOUT" "${BMAD_CMD[@]}"
        BMAD_RC=$?
      else
        # macOS 默认没 timeout，用 perl 模拟
        perl -e "alarm $BMAD_TIMEOUT; exec @ARGV" "${BMAD_CMD[@]}"
        BMAD_RC=$?
      fi
      set -e

      if [[ "$BMAD_RC" -eq 0 ]]; then
        if [[ -d "_bmad" ]]; then
          echo ""
          echo "✅ BMAD 安装完成（_bmad/ 目录已创建）"
        else
          echo ""
          echo "⚠️  BMAD 安装命令返回成功但未发现 _bmad/ 目录，请检查" >&2
        fi
      elif [[ "$BMAD_RC" -eq 124 ]]; then
        echo ""
        echo "❌ BMAD 安装超时（>${BMAD_TIMEOUT}s），已自动中断" >&2
        echo "   可手动重跑：npx -y bmad-method install --directory . --tools $BMAD_TOOLS --yes" >&2
      else
        echo ""
        echo "❌ BMAD 安装失败（退出码 $BMAD_RC）" >&2
        echo "   可手动重跑：npx -y bmad-method install --directory . --tools $BMAD_TOOLS --yes" >&2
        echo "   其他配置（AGENTS.md / 软链接 / Cursor / Windsurf）已就绪，不影响使用" >&2
      fi
    fi
  fi
fi

# ===== 6. 项目模板初始化（可选）=====
if [[ "$DO_INIT" == "1" ]]; then
  echo ""
  echo "==== 项目模板初始化 ===="

  # 默认项目名 = 当前目录 basename
  if [[ -z "$INIT_NAME" ]]; then
    INIT_NAME=$(basename "$(pwd)")
  fi

  TEMPLATES_DIR="$PLUGIN_PATH_BASH/templates"
  if [[ ! -d "$TEMPLATES_DIR" ]]; then
    echo "❌ 模板目录不存在：$TEMPLATES_DIR" >&2
    echo "   请确认插件路径正确（--plugin-path）" >&2
    exit 1
  fi

  # 复制 + 占位符替换（与 BMAD mustache 约定一致：{{name}} / {{user_name}} / {{date}}）
  copy_template() {
    local src="$1"
    local dst="$2"
    local label="$3"

    if [[ -f "$dst" && "$INIT_FORCE" -ne 1 ]]; then
      if [[ "$DRY_RUN" == "1" ]]; then
        echo "🧪 [dry-run] $dst 已存在，将跳过（用 --init-force 覆盖）"
      else
        echo "⏭️  $label 已存在（$dst），跳过（用 --init-force 覆盖）"
      fi
      return 0
    fi

    if [[ ! -f "$src" ]]; then
      echo "❌ 模板文件不存在：$src" >&2
      return 1
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
      echo "🧪 [dry-run] 将生成 $dst（项目名：$INIT_NAME）"
      return 0
    fi

    # 用 awk 做占位符替换（避免 sed 在 Windows / macOS 上的差异）
    awk -v name="$INIT_NAME" -v user="$INIT_USER" -v date="$INIT_DATE" '
      {
        gsub(/\{\{项目名\}\}/, name);
        gsub(/\{\{project_name\}\}/, name);
        gsub(/\{\{负责人\}\}/, user);
        gsub(/\{\{user_name\}\}/, user);
        gsub(/\{\{日期\}\}/, date);
        gsub(/\{\{date\}\}/, date);
        print
      }
    ' "$src" > "$dst"

    echo "✅ 已生成 $dst（项目名：$INIT_NAME）"
  }

  if [[ "$DO_INIT_PROGRESS" == "1" ]]; then
    copy_template "$TEMPLATES_DIR/project-progress模板.yaml" "project-progress.yaml" "进度文件"
  fi
  if [[ "$DO_INIT_CONTEXT" == "1" ]]; then
    copy_template "$TEMPLATES_DIR/project-context模板.md" "project-context.md" "项目上下文"
  fi

  if [[ "$DRY_RUN" != "1" ]]; then
    echo ""
    echo "📝 模板已就位，下一步："
    echo "   - 编辑 project-context.md 填入项目红线/验收线（AI 必读）"
    echo "   - 编辑 project-progress.yaml 顶部 project / trace_id 字段"
  fi
fi

echo ""
echo "🎉 配置完成！"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "（DRY-RUN 模式未实际改动文件，去掉 --dry-run 真跑一次）"
fi
echo ""
echo "下一步："
echo "  1. 把学校/客户资料扔进当前目录"
echo "  2. 打开 AI 工具（Claude Code / Codex / Cursor / Windsurf）"
echo "  3. 第一句话：\"按 AGENTS.md 走，现在到哪了\""
echo ""
echo "💡 最常用一行命令："
echo "   bash setup.sh --plugin-path $PLUGIN_PATH --bmad --init"