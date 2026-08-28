# setup.ps1 — delivery-flow 一键配置脚本（PowerShell / Windows）
#
# 作用：
#   1. 在当前目录生成精简版 AGENTS.md
#   2. 为 Claude Code 建 .claude\plugins\delivery-flow 软链接
#   3. 为 Cursor / Windsurf 生成对应规则文件
#   4. （可选 -Bmad）调用 npx bmad-method 自动安装 BMAD
#
# 用法：
#   cd <你的项目>
#   irm https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup.ps1 | iex `
#     -PluginPath D:\tools\delivery-flow
#
# 或下载后：
#   .\setup.ps1 -PluginPath D:\tools\delivery-flow
#
# 可选参数（所有开关默认关闭）：
#   -NoClaude           跳过 Claude Code 软链接
#   -NoCodex            跳过 Codex AGENTS.md
#   -NoCursor           跳过 Cursor 规则
#   -NoWindsurf         跳过 Windsurf 规则
#   -Bmad               启用 BMAD-METHOD 自动安装
#   -BmadTools <list>   BMAD 工具列表（默认 claude-code，多个用逗号）
#   -BmadModules <list> BMAD 模块列表（默认空，用 installer 默认）
#   -BmadTimeout <sec>  BMAD 安装超时秒数（默认 600）
#   -Init               启用项目模板初始化（复制 project-context.md /
#                       project-progress.yaml，默认关闭）
#   -InitName <name>    项目名（默认取当前目录名）
#   -InitUser <name>    负责人名（默认 $env:USERNAME）
#   -InitDate <date>    日期（默认今天 yyyy-MM-dd）
#   -InitForce          覆盖已存在的项目文件（默认 skip）
#   -NoInitProgress     只复制 project-context.md，不复制 progress
#   -NoInitContext      只复制 project-progress.yaml，不复制 context
#   -DryRun             只打印将要做什么，不实际执行（不写文件、不建软链接、不调 npx）

param(
    [Parameter(Mandatory=$true)]
    [string]$PluginPath,

    [switch]$NoClaude = $false,
    [switch]$NoCodex = $false,
    [switch]$NoCursor = $false,
    [switch]$NoWindsurf = $false,

    [switch]$Bmad = $false,
    [string]$BmadTools = "claude-code",
    [string]$BmadModules = "",
    [int]$BmadTimeout = 600,

    [switch]$Init = $false,
    [string]$InitName = "",
    [string]$InitUser = $env:USERNAME,
    [string]$InitDate = (Get-Date -Format "yyyy-MM-dd"),
    [switch]$InitForce = $false,
    [switch]$NoInitProgress = $false,
    [switch]$NoInitContext = $false,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

# 校验插件路径
if (-not (Test-Path $PluginPath)) {
    Write-Host "❌ 插件路径不存在：$PluginPath" -ForegroundColor Red
    Write-Host "   请先 git clone delivery-flow 到该路径" -ForegroundColor Red
    exit 1
}

$SkillsPath = Join-Path $PluginPath "skills"
if (-not (Test-Path $SkillsPath)) {
    Write-Host "❌ 路径下找不到 skills/ 目录，确认是 delivery-flow 仓库" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 检测到 delivery-flow 插件：$PluginPath" -ForegroundColor Green
Write-Host "📍 当前目录：$(Get-Location)" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "🧪 DRY-RUN 模式：只打印将要做什么，不实际执行" -ForegroundColor Magenta
}
Write-Host ""

# 转义反斜杠（用于 Markdown 代码块）
$PluginPathEscaped = $PluginPath -replace '\\', '\\'
$DeliveryPy = Join-Path $PluginPath "delivery.py"

# ===== 1. 生成 AGENTS.md =====
if (-not $NoCodex) {
    if ($DryRun) {
        if (Test-Path "AGENTS.md") {
            Write-Host "🧪 [dry-run] AGENTS.md 已存在，将跳过" -ForegroundColor Magenta
        } else {
            Write-Host "🧪 [dry-run] 将生成 AGENTS.md" -ForegroundColor Magenta
        }
    } elseif (Test-Path "AGENTS.md") {
        Write-Host "⏭️  AGENTS.md 已存在，跳过生成" -ForegroundColor Yellow
    } else {
        $AgentsContent = @"
# AGENTS.md — 项目 AI 工作指令

> delivery-flow 入口。新对话开始自动读取。

## 1. 插件路径

\`\`\`
$PluginPathEscaped
\`\`\`

## 2. 启动动作（每个新对话必做）

按顺序：
1. 调 \`python "$DeliveryPy" progress --root . --json\` 读当前阶段
2. 读 \`project-context.md\`（项目宪法，不存在则提示生成）
3. 扫项目根所有文档（不要求用户整理）

## 3. 阶段路由（不要靠记忆判断）

- "现在到哪了" → 调 \`progress\`，复述 \`next_action_suggestion.suggested_question\`
- "下一步" → 调 \`dry-run\`，列出操作清单等我确认
- "撤回" → 调 \`delivery revert --step <stage_id>\`
- "我是 XX 角色，做 XX" → 读 progress + 角色路由表决定 skill

**角色 → skill 路由**：
- 商务/售前 → \`delivery-presales\` / \`delivery-deal-gate\`
- PM → BMAD \`brainstorm\` / \`write-prd\` / \`delivery-client-gate\`
- 项目经理 → \`delivery-plan\` / \`delivery-feishu-sync\` / \`delivery-acceptance-gate\`
- 研发 → Superpowers \`tdd\` / \`writing-plans\`
- AI 工程师 → \`delivery-eval-loop\` / \`pm-ai-shipping:ship-check\`

## 4. 三个纪律（违反即报错）

1. **逐步确认**：每 step 前告诉我"要做 X、产出 Y"，等我说"继续"再执行
2. **不确定就问**：不替我拍板
3. **草稿态**：先写 \`.draft.\`，确认后才 mv

## 5. 详细规则查这里

- 21 个 skill 清单：\`$PluginPathEscaped\README.md\` 第 40-48 行
- 三步循环：README 第 458-465 行
- 状态机：\`project-progress.yaml\`

## 6. 自检（出问题先跑这个）

脚本：\`powershell -ExecutionPolicy Bypass -File "$PluginPath\setup-verify.ps1" -Json\`

AI 触发词："verify 一下" / "setup 出问题了" / "AI 找不到插件" → 跑上面脚本，按 \`has_error\` 决定修复策略。

## 7. 模型分层（让大模型思考，小模型执行）

读 \`project-context.md\` 的「模型分层策略」节。**支持两种协作模式**：

### A. 同工具内分层（如都在 Claude Code / 都在 Codex CLI）

- "出方案" / "想一下" / "列计划" → 当前阶段的**思考模型**
  - Claude Code：Opus（\`/think hard\` 或 Task tool 调度）
  - Codex CLI：SOL（\`/plan\` 模式或 "think deep"）
- "按方案执行" / "写代码" / "改这个" → 当前阶段的**执行模型**
  - Claude Code：Sonnet / Haiku
  - Codex CLI：mini / \`/code\` 模式
- 切换：直接说"切到执行" / "切到思考"

### B. 跨工具交接（思考工具 ≠ 执行工具）⭐常见

- **思考模型**在工具 A 出方案 → **必须写到「交接文件」**（默认 \`<阶段目录>/[NN] <产物>.draft.md\`，跨工具时由 \`project-context.md\` 指定）
- **关闭工具 A** → **打开工具 B**（执行模型所在工具）→ **第一句话：\`读 <交接文件>，按方案执行\`**
- 执行工具读到的方案**必须是 \`.draft.\` 已 review 态**——不允许读未确认草稿

反模式（出现就停下来问人）：
- 跨工具交接时思考模型没落文件（执行工具找不到依据）
- 执行工具读了未 \`.draft.\` 的方案（违反 SSOT 纪律）
- 思考 / 执行工具在不同项目目录（上下文丢失）
"@
        Set-Content -Path "AGENTS.md" -Value $AgentsContent -Encoding UTF8
        Write-Host "✅ 已生成 AGENTS.md" -ForegroundColor Green
    }
}

# ===== 2. Claude Code 软链接 =====
if (-not $NoClaude) {
    $ClaudePluginsDir = ".claude\plugins"
    $LinkPath = Join-Path $ClaudePluginsDir "delivery-flow"

    if (-not (Test-Path $ClaudePluginsDir)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $ClaudePluginsDir -Force | Out-Null
        }
    }

    if ($DryRun) {
        if (Test-Path $LinkPath) {
            Write-Host "🧪 [dry-run] $LinkPath 已存在" -ForegroundColor Magenta
        } else {
            Write-Host "🧪 [dry-run] 将建软链接：$LinkPath → $PluginPath" -ForegroundColor Magenta
        }
    } elseif (Test-Path $LinkPath) {
        Write-Host "⏭️  $LinkPath 已存在" -ForegroundColor Yellow
    } else {
        # 需要管理员权限建符号链接
        try {
            New-Item -ItemType SymbolicLink -Path $LinkPath -Target $PluginPath -ErrorAction Stop | Out-Null
            Write-Host "✅ 已建 Claude Code 软链接：$LinkPath → $PluginPath" -ForegroundColor Green
        } catch {
            Write-Host "❌ 建符号链接失败（需要管理员权限或开发者模式）：" -ForegroundColor Red
            Write-Host "   $_" -ForegroundColor Red
            Write-Host ""
            Write-Host "   替代方案 1：以管理员身份重跑此脚本" -ForegroundColor Yellow
            Write-Host "   替代方案 2：开启 Windows 开发者模式（设置 → 更新和安全 → 开发者选项）" -ForegroundColor Yellow
            Write-Host "   替代方案 3：手动复制整个 delivery-flow 到 .claude\plugins\delivery-flow" -ForegroundColor Yellow
            exit 1
        }
    }

    # 验证（非 dry-run 才执行）
    if (-not $DryRun) {
        $VerifyPath = Join-Path $LinkPath "skills"
        if (Test-Path $VerifyPath) {
            $SkillCount = (Get-ChildItem $VerifyPath -Directory).Count
            Write-Host "✅ 验证通过，检测到 $SkillCount 个 skill" -ForegroundColor Green
        } else {
            Write-Host "⚠️  警告：软链接建好但看不到 skills/，请检查路径" -ForegroundColor Yellow
        }
    }
}

# ===== 3. Cursor 规则 =====
if (-not $NoCursor) {
    $CursorDir = ".cursor\rules"
    $CursorFile = Join-Path $CursorDir "delivery-flow.mdc"

    if (-not (Test-Path $CursorDir) -and -not $DryRun) {
        New-Item -ItemType Directory -Path $CursorDir -Force | Out-Null
    }

    if ($DryRun) {
        if (Test-Path $CursorFile) {
            Write-Host "🧪 [dry-run] $CursorFile 已存在" -ForegroundColor Magenta
        } else {
            Write-Host "🧪 [dry-run] 将生成 $CursorFile" -ForegroundColor Magenta
        }
    } elseif (Test-Path $CursorFile) {
        Write-Host "⏭️  $CursorFile 已存在" -ForegroundColor Yellow
    } else {
        $CursorContent = @"
---
description: delivery-flow 交付工作流指令
globs: ["**/*.md", "**/*.yaml"]
---

# delivery-flow 交付工作流

插件路径：$PluginPath

新对话开始时：
1. 调 \`python "$DeliveryPy" progress --root . --json\` 读当前阶段
2. 读 \`project-context.md\` 和 \`AGENTS.md\`
3. 按阶段路由决定调哪个 skill

详细规则见 \`$PluginPath\skills\` 下各 SKILL.md。
"@
        Set-Content -Path $CursorFile -Value $CursorContent -Encoding UTF8
        Write-Host "✅ 已生成 $CursorFile" -ForegroundColor Green
    }
}

# ===== 4. Windsurf 规则 =====
if (-not $NoWindsurf) {
    $WindsurfDir = ".windsurf\rules"
    $WindsurfFile = Join-Path $WindsurfDir "delivery-flow.md"

    if (-not (Test-Path $WindsurfDir) -and -not $DryRun) {
        New-Item -ItemType Directory -Path $WindsurfDir -Force | Out-Null
    }

    if ($DryRun) {
        if (Test-Path $WindsurfFile) {
            Write-Host "🧪 [dry-run] $WindsurfFile 已存在" -ForegroundColor Magenta
        } else {
            Write-Host "🧪 [dry-run] 将生成 $WindsurfFile" -ForegroundColor Magenta
        }
    } elseif (Test-Path $WindsurfFile) {
        Write-Host "⏭️  $WindsurfFile 已存在" -ForegroundColor Yellow
    } else {
        $WindsurfContent = @"
# delivery-flow 交付工作流

插件路径：$PluginPath

新对话开始时：
1. 调 \`python "$DeliveryPy" progress --root . --json\` 读当前阶段
2. 读 \`project-context.md\` 和 \`AGENTS.md\`
3. 按阶段路由决定调哪个 skill
"@
        Set-Content -Path $WindsurfFile -Value $WindsurfContent -Encoding UTF8
        Write-Host "✅ 已生成 $WindsurfFile" -ForegroundColor Green
    }
}

# ===== 5. BMAD-METHOD 自动安装（可选）=====
if ($Bmad) {
    Write-Host ""
    Write-Host "==== BMAD-METHOD 安装 ====" -ForegroundColor Cyan

    # 前置检查：node + npx
    $NodeCmd = Get-Command node -ErrorAction SilentlyContinue
    $NpxCmd  = Get-Command npx  -ErrorAction SilentlyContinue

    if (-not $NodeCmd) {
        Write-Host "❌ 未检测到 node，请先安装 Node.js 18+：https://nodejs.org" -ForegroundColor Red
        if (-not $DryRun) {
            Write-Host "   安装后重跑：.\setup.ps1 -PluginPath $PluginPath -Bmad" -ForegroundColor Red
            exit 1
        }
    }
    if (-not $NpxCmd) {
        Write-Host "❌ 未检测到 npx（通常随 Node.js 一同安装），跳过 BMAD 安装" -ForegroundColor Red
    } else {
        # Node 版本检查
        $NodeVersion = & node -v 2>$null
        if ($NodeVersion -match '^v(\d+)') {
            $NodeMajor = [int]$Matches[1]
            if ($NodeMajor -lt 18) {
                Write-Host "⚠️  Node.js 版本为 $NodeVersion，BMAD 要求 18+，尝试继续..." -ForegroundColor Yellow
            }
        }

        # 组装命令
        $BmadArgs = @(
            "-y", "bmad-method", "install",
            "--directory", ".",
            "--tools", $BmadTools,
            "--yes"
        )
        if ($BmadModules) {
            $BmadArgs += @("--modules", $BmadModules)
        }

        Write-Host "📦 执行：npx $($BmadArgs -join ' ')" -ForegroundColor Cyan
        Write-Host "   （首次运行会下载 bmad-method 包，可能耗时 1-3 分钟；超时 ${BmadTimeout}s）" -ForegroundColor Cyan
        Write-Host ""

        # dry-run 模式：只打印命令就跳过执行
        if ($DryRun) {
            Write-Host "🧪 [dry-run] 跳过执行" -ForegroundColor Magenta
            Write-Host ""
        } else {
            # 执行 npx（流式输出；不阻塞其他已完成步骤）
            $BmadRC = 0
            try {
                # 使用 Start-Process 拿 PID，再以 Job 跑以支持超时
                $Job = Start-Job -ScriptBlock {
                    param($cmd, $args)
                    & $cmd @args
                } -ArgumentList "npx", $BmadArgs

                if (Wait-Job $Job -Timeout $BmadTimeout) {
                    $BmadRC = Receive-Job $Job -Keep -ErrorAction SilentlyContinue
                    # PowerShell 里 Receive-Job 返回的不是简单 RC；改用 $Job.State 判断
                } else {
                    Stop-Job $Job
                    Remove-Job $Job -Force
                    $BmadRC = 124  # 超时标记
                }

                if ($Job.State -in @('Completed', 'Stopped')) {
                    # 从 ExitCode 取（PowerShell 7+ 支持，旧版 PS 5.1 不支持）
                    if ($Job.PSVersionTable.PSVersion.Major -ge 7) {
                        $BmadRC = $Job.ChildJobs[0].ExitCode
                    } else {
                        # PS 5.1 兼容：没有 _bmad 就算失败
                        if (Test-Path "_bmad") { $BmadRC = 0 } else { $BmadRC = 1 }
                    }
                }
                Remove-Job $Job -Force -ErrorAction SilentlyContinue
            } catch {
                Write-Host "❌ BMAD 安装异常：$_" -ForegroundColor Red
                $BmadRC = 1
            }

            if ($BmadRC -eq 0 -and (Test-Path "_bmad")) {
                Write-Host ""
                Write-Host "✅ BMAD 安装完成（_bmad/ 目录已创建）" -ForegroundColor Green
            } elseif ($BmadRC -eq 124) {
                Write-Host ""
                Write-Host "❌ BMAD 安装超时（>${BmadTimeout}s），已自动中断" -ForegroundColor Red
                Write-Host "   可手动重跑：npx -y bmad-method install --directory . --tools $BmadTools --yes" -ForegroundColor Yellow
            } else {
                Write-Host ""
                Write-Host "❌ BMAD 安装失败（退出码 $BmadRC）" -ForegroundColor Red
                Write-Host "   可手动重跑：npx -y bmad-method install --directory . --tools $BmadTools --yes" -ForegroundColor Yellow
                Write-Host "   其他配置（AGENTS.md / 软链接 / Cursor / Windsurf）已就绪，不影响使用" -ForegroundColor Yellow
            }
        }
    }
}

# ===== 6. 项目模板初始化（可选）=====
if ($Init) {
    Write-Host ""
    Write-Host "==== 项目模板初始化 ====" -ForegroundColor Cyan

    # 默认项目名 = 当前目录 basename
    if (-not $InitName) {
        $InitName = (Get-Item .).Name
    }

    $TemplatesDir = Join-Path $PluginPath "templates"
    if (-not (Test-Path $TemplatesDir)) {
        Write-Host "❌ 模板目录不存在：$TemplatesDir" -ForegroundColor Red
        Write-Host "   请确认插件路径正确（-PluginPath）" -ForegroundColor Red
        exit 1
    }

    # 复制 + 占位符替换（与 BMAD mustache 约定一致）
    function Copy-Template {
        param(
            [string]$Src,
            [string]$Dst,
            [string]$Label
        )

        if ((Test-Path $Dst) -and -not $InitForce) {
            if ($DryRun) {
                Write-Host "🧪 [dry-run] $Dst 已存在，将跳过（用 -InitForce 覆盖）" -ForegroundColor Magenta
            } else {
                Write-Host "⏭️  $Label 已存在（$Dst），跳过（用 -InitForce 覆盖）" -ForegroundColor Yellow
            }
            return
        }
        if (-not (Test-Path $Src)) {
            Write-Host "❌ 模板文件不存在：$Src" -ForegroundColor Red
            return
        }

        if ($DryRun) {
            Write-Host "🧪 [dry-run] 将生成 $Dst（项目名：$InitName）" -ForegroundColor Magenta
            return
        }

        $Content = Get-Content $Src -Raw -Encoding UTF8
        $Content = $Content -replace '\{\{项目名\}\}',        $InitName
        $Content = $Content -replace '\{\{project_name\}\}', $InitName
        $Content = $Content -replace '\{\{负责人\}\}',        $InitUser
        $Content = $Content -replace '\{\{user_name\}\}',    $InitUser
        $Content = $Content -replace '\{\{日期\}\}',          $InitDate
        $Content = $Content -replace '\{\{date\}\}',          $InitDate

        Set-Content -Path $Dst -Value $Content -Encoding UTF8
        Write-Host "✅ 已生成 $Dst（项目名：$InitName）" -ForegroundColor Green
    }

    if (-not $NoInitProgress) {
        Copy-Template -Src (Join-Path $TemplatesDir "project-progress模板.yaml") `
                      -Dst "project-progress.yaml" `
                      -Label "进度文件"
    }
    if (-not $NoInitContext) {
        Copy-Template -Src (Join-Path $TemplatesDir "project-context模板.md") `
                      -Dst "project-context.md" `
                      -Label "项目上下文"
    }

    if (-not $DryRun) {
        Write-Host ""
        Write-Host "📝 模板已就位，下一步：" -ForegroundColor Cyan
        Write-Host "   - 编辑 project-context.md 填入项目红线/验收线（AI 必读）" -ForegroundColor Cyan
        Write-Host "   - 编辑 project-progress.yaml 顶部 project / trace_id 字段" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "🎉 配置完成！" -ForegroundColor Green
if ($DryRun) {
    Write-Host "（DRY-RUN 模式未实际改动文件，去掉 -DryRun 真跑一次）" -ForegroundColor Magenta
}
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  1. 把学校/客户资料扔进当前目录"
Write-Host "  2. 打开 AI 工具（Claude Code / Codex / Cursor / Windsurf）"
Write-Host "  3. 第一句话：'按 AGENTS.md 走，现在到哪了'"
Write-Host ""
Write-Host "💡 最常用一行命令：" -ForegroundColor Cyan
Write-Host "   .\setup.ps1 -PluginPath $PluginPath -Bmad -Init" -ForegroundColor Cyan