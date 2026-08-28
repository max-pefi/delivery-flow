#!/usr/bin/env bash
# setup-verify.sh — delivery-flow 项目配置健康检查（Git Bash / macOS / Linux）
#
# 作用：
#   扫当前项目根，验证 delivery-flow 初始化是否完整。
#   用于排查"AI 找不到插件""onboarding 报错"等问题。
#
# 用法：
#   cd <你的项目>
#   bash <(curl -fsSL https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup-verify.sh)
#
# 可选参数：
#   --plugin-path PATH    期望的插件路径（默认从 AGENTS.md 推断，否则报错）
#   --json                输出 JSON 供 AI 解析
#   -h, --help            显示帮助
#
# 退出码：
#   0  全 OK 或仅 INFO
#   1  有 WARN（可继续，但有缺失）
#   2  有 ERROR（必须修复）

set -uo pipefail

PLUGIN_PATH=""
JSON_OUT=0

usage() {
  awk 'NR==1 || (/^[^#]/ && !done) {next} /^#/ {print; if(/^# -h, --help/) done=1; next} {exit}' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin-path) PLUGIN_PATH="$2"; shift 2;;
    --json)        JSON_OUT=1; shift;;
    -h|--help)     usage;;
    *) echo "未知参数：$1" >&2; exit 1;;
  esac
done

# 从 AGENTS.md 推断插件路径（如果用户没指定）
if [[ -z "$PLUGIN_PATH" && -f "AGENTS.md" ]]; then
  PLUGIN_PATH=$(awk '/^```$/{c++;next} c==1 && NF{print; exit}' AGENTS.md 2>/dev/null || true)
fi

# 检查结果数组
RESULTS=()        # "OK|WARN|ERROR|INFO message"
HAS_ERROR=0
HAS_WARN=0

ok()   { RESULTS+=("OK|$1"); }
warn() { RESULTS+=("WARN|$1"); HAS_WARN=1; }
err()  { RESULTS+=("ERROR|$1"); HAS_ERROR=1; }
info() { RESULTS+=("INFO|$1"); }

# ===== 检查项 =====

# 1. 软链接
# Windows 上 ln -s 创建的符号链接 Git Bash 看到的是「目录」或「符号链接」，
# 都视为可达；只有解析失败才报 ERROR
if [[ -e ".claude/plugins/delivery-flow/skills" ]]; then
  if [[ -L ".claude/plugins/delivery-flow" ]]; then
    TARGET=$(readlink ".claude/plugins/delivery-flow")
    # Windows / Git Bash 路径兼容
    TARGET_BASH=$(echo "$TARGET" | sed -E 's|^([A-Za-z]):|/\L\1|; s|\\|/|g' 2>/dev/null || echo "$TARGET")
    SKILL_COUNT=$(ls "$TARGET/skills" 2>/dev/null | wc -l || ls "$TARGET_BASH/skills" 2>/dev/null | wc -l)
    if [[ "$SKILL_COUNT" -ge 21 ]]; then
      ok "Claude Code 软链接正常（$SKILL_COUNT 个 skill）"
    else
      warn "Claude Code 软链接可达，但只检测到 $SKILL_COUNT 个 skill（期望 ≥21）"
    fi
  else
    info ".claude/plugins/delivery-flow 可达（非符号链接，更新插件需手动同步）"
  fi
else
  err "Claude Code 软链接不可达（.claude/plugins/delivery-flow/skills 缺失）"
fi

# 2. AGENTS.md
if [[ -f "AGENTS.md" ]]; then
  # 只检查开头 10 行的占位符（避免误报模板里"待填写"的 {{框架 + 版本}} 等）
  if head -10 AGENTS.md | grep -qE '\{\{[^}]+\}\}'; then
    warn "AGENTS.md 头部仍含占位符 {{...}}，未替换完"
  else
    ok "AGENTS.md 存在且无未替换占位符"
  fi
  # AGENTS.md 路径与 --plugin-path 一致性
  if [[ -n "$PLUGIN_PATH" ]]; then
    AGENTS_PATH=$(awk '/^```$/{c++;next} c==1 && NF{print; exit}' AGENTS.md 2>/dev/null || true)
    if [[ -n "$AGENTS_PATH" && "$AGENTS_PATH" != "$PLUGIN_PATH" ]]; then
      warn "AGENTS.md 写的插件路径（$AGENTS_PATH）与 --plugin-path（$PLUGIN_PATH）不一致"
    fi
  fi
else
  info "AGENTS.md 不存在（Codex / 其他工具需要时启用 --init 或 --init-force）"
fi

# 3. Cursor
if [[ -f ".cursor/rules/delivery-flow.mdc" ]]; then
  ok "Cursor 规则文件存在"
elif [[ -d ".cursor" ]]; then
  info "使用 Cursor 但未发现 delivery-flow 规则文件"
else
  info "未使用 Cursor（.cursor/ 不存在）"
fi

# 4. Windsurf
if [[ -f ".windsurf/rules/delivery-flow.md" ]]; then
  ok "Windsurf 规则文件存在"
elif [[ -d ".windsurf" ]]; then
  info "使用 Windsurf 但未发现 delivery-flow 规则文件"
else
  info "未使用 Windsurf（.windsurf/ 不存在）"
fi

# 5. BMAD
if [[ -d "_bmad" ]]; then
  ok "BMAD 已安装（_bmad/ 存在）"
else
  info "BMAD 未安装（_bmad/ 不存在）；需要时手动跑 npx -y bmad-method install"
fi

# 6. project-context.md
if [[ -f "project-context.md" ]]; then
  # 只检查 frontmatter（开头 10 行）的占位符，不误报模板里的"待填写"
  if head -10 project-context.md | grep -qE '\{\{[^}]+\}\}'; then
    warn "project-context.md 头部仍含占位符 {{...}}，未替换完"
  else
    ok "project-context.md 存在"
  fi
else
  warn "project-context.md 不存在（onboarding 会提示生成）"
fi

# 7. project-progress.yaml
if [[ -f "project-progress.yaml" ]]; then
  if grep -q '^current_stage:' project-progress.yaml; then
    STAGE=$(grep '^current_stage:' project-progress.yaml | sed 's/.*: *//; s/"//g')
    ok "project-progress.yaml 存在，current_stage=$STAGE"
  else
    warn "project-progress.yaml 存在但无 current_stage 字段"
  fi
else
  warn "project-progress.yaml 不存在（onboarding 会提示生成）"
fi

# ===== 输出 =====

if [[ "$JSON_OUT" == "1" ]]; then
  echo "{"
  echo "  \"results\": ["
  FIRST=1
  for r in "${RESULTS[@]}"; do
    LEVEL="${r%%|*}"
    MSG="${r#*|}"
    # JSON 转义
    MSG_ESC=$(echo "$MSG" | sed 's/\\/\\\\/g; s/"/\\"/g')
    if [[ "$FIRST" -eq 1 ]]; then FIRST=0; else echo ","; fi
    printf '    {"level": "%s", "message": "%s"}' "$LEVEL" "$MSG_ESC"
  done
  echo ""
  echo "  ],"
  echo "  \"has_error\": $HAS_ERROR,"
  echo "  \"has_warn\": $HAS_WARN"
  echo "}"
  if [[ "$HAS_ERROR" -eq 1 ]]; then exit 2
  elif [[ "$HAS_WARN" -eq 1 ]]; then exit 1
  else exit 0
  fi
else
  echo ""
  echo "==== delivery-flow 配置健康检查 ===="
  echo ""
  for r in "${RESULTS[@]}"; do
    LEVEL="${r%%|*}"
    MSG="${r#*|}"
    case "$LEVEL" in
      OK)    printf "  \033[32m✅\033[0m %s\n" "$MSG";;
      WARN)  printf "  \033[33m⚠️ \033[0m %s\n" "$MSG";;
      ERROR) printf "  \033[31m❌\033[0m %s\n" "$MSG";;
      INFO)  printf "  \033[36mℹ️ \033[0m %s\n" "$MSG";;
    esac
  done
  echo ""
  if [[ "$HAS_ERROR" -eq 1 ]]; then
    echo "❌ 存在 ERROR，建议重新跑 setup.sh（bash setup.sh --plugin-path ... --init --bmad）"
    exit 2
  elif [[ "$HAS_WARN" -eq 1 ]]; then
    echo "⚠️  存在 WARN，功能可用但建议补齐缺失项"
    exit 1
  else
    echo "🎉 全部 OK，AI 可直接接管项目"
    exit 0
  fi
fi