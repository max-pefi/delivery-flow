# setup-verify.ps1 — delivery-flow 项目配置健康检查（PowerShell / Windows）
#
# 作用：
#   扫当前项目根，验证 delivery-flow 初始化是否完整。
#   用于排查"AI 找不到插件""onboarding 报错"等问题。
#
# 用法：
#   cd <你的项目>
#   .\setup-verify.ps1
#   irm https://raw.githubusercontent.com/fredsimas782-jpg/delivery-flow/main/setup-verify.ps1 | iex
#
# 可选参数：
#   -PluginPath PATH    期望的插件路径（默认从 AGENTS.md 推断）
#   -Json               输出 JSON 供 AI 解析
#
# 退出码：
#   0  全 OK 或仅 INFO
#   1  有 WARN（可继续，但有缺失）
#   2  有 ERROR（必须修复）

param(
    [string]$PluginPath = "",
    [switch]$Json = $false
)

$ErrorActionPreference = "Stop"

# 从 AGENTS.md 推断插件路径
if (-not $PluginPath -and (Test-Path "AGENTS.md")) {
    $InCodeBlock = $false
    foreach ($Line in Get-Content "AGENTS.md") {
        if ($Line -match '^```$') {
            if ($InCodeBlock) { break }
            $InCodeBlock = $true
            continue
        }
        if ($InCodeBlock -and $Line.Trim()) {
            $PluginPath = $Line.Trim()
            break
        }
    }
}

# 结果数组
$Results = New-Object System.Collections.Generic.List[object]
$HasError = $false
$HasWarn = $false

function Add-Result {
    param([string]$Level, [string]$Message)
    $script:Results.Add(@{ level = $Level; message = $Message })
    switch ($Level) {
        "ERROR" { $script:HasError = $true }
        "WARN"  { $script:HasWarn  = $true }
    }
}

# ===== 检查项 =====

# 1. Claude Code 软链接
# Windows 上 ln -s / New-Item SymbolicLink 创建的符号链接，
# Test-Path -PathType Container 在某些 PowerShell 版本下也会判定为 True，
# 所以只看 skills/ 是否可达
$LinkPath = ".claude\plugins\delivery-flow"
$SkillsPath = Join-Path $LinkPath "skills"
if (Test-Path $SkillsPath) {
    $Item = Get-Item $LinkPath -Force -ErrorAction SilentlyContinue
    if ($Item -and $Item.LinkType -eq "SymbolicLink") {
        $Target = $Item.Target
        $SkillCount = (Get-ChildItem $SkillsPath -Directory -ErrorAction SilentlyContinue).Count
        if ($SkillCount -ge 21) {
            Add-Result "OK" "Claude Code 软链接正常（$SkillCount 个 skill）"
        } else {
            Add-Result "WARN" "Claude Code 软链接可达，但只检测到 $SkillCount 个 skill（期望 ≥21）"
        }
    } else {
        Add-Result "INFO" "$LinkPath 可达（非符号链接，更新插件需手动同步）"
    }
} else {
    Add-Result "ERROR" "Claude Code 软链接不可达（$SkillsPath 缺失）"
}

# 2. AGENTS.md
if (Test-Path "AGENTS.md") {
    # 只检查开头 10 行的占位符（避免误报模板里"待填写"的 {{框架 + 版本}} 等）
    $Head = Get-Content "AGENTS.md" -TotalCount 10 -Raw
    if ($Head -match '\{\{[^}]+\}\}') {
        Add-Result "WARN" "AGENTS.md 头部仍含占位符 {{...}}，未替换完"
    } else {
        Add-Result "OK" "AGENTS.md 存在且无未替换占位符"
    }
    if ($PluginPath) {
        $InCodeBlock = $false
        $AgentsPath = ""
        foreach ($Line in (Get-Content "AGENTS.md")) {
            if ($Line -match '^```$') {
                if ($InCodeBlock) { break }
                $InCodeBlock = $true
                continue
            }
            if ($InCodeBlock -and $Line.Trim()) {
                $AgentsPath = $Line.Trim()
                break
            }
        }
        if ($AgentsPath -and ($AgentsPath -ne $PluginPath)) {
            Add-Result "WARN" "AGENTS.md 写的插件路径（$AgentsPath）与 -PluginPath（$PluginPath）不一致"
        }
    }
} else {
    Add-Result "INFO" "AGENTS.md 不存在（Codex / 其他工具需要时启用 -Init 或 -InitForce）"
}

# 3. Cursor
if (Test-Path ".cursor\rules/delivery-flow.mdc") {
    Add-Result "OK" "Cursor 规则文件存在"
} elseif (Test-Path ".cursor") {
    Add-Result "INFO" "使用 Cursor 但未发现 delivery-flow 规则文件"
} else {
    Add-Result "INFO" "未使用 Cursor（.cursor/ 不存在）"
}

# 4. Windsurf
if (Test-Path ".windsurf\rules/delivery-flow.md") {
    Add-Result "OK" "Windsurf 规则文件存在"
} elseif (Test-Path ".windsurf") {
    Add-Result "INFO" "使用 Windsurf 但未发现 delivery-flow 规则文件"
} else {
    Add-Result "INFO" "未使用 Windsurf（.windsurf/ 不存在）"
}

# 5. BMAD
if (Test-Path "_bmad") {
    Add-Result "OK" "BMAD 已安装（_bmad/ 存在）"
} else {
    Add-Result "INFO" "BMAD 未安装（_bmad/ 不存在）；需要时手动跑 npx -y bmad-method install"
}

# 6. project-context.md
if (Test-Path "project-context.md") {
    # 只检查 frontmatter（开头 10 行）的占位符
    $Head = Get-Content "project-context.md" -TotalCount 10 -Raw
    if ($Head -match '\{\{[^}]+\}\}') {
        Add-Result "WARN" "project-context.md 头部仍含占位符 {{...}}，未替换完"
    } else {
        Add-Result "OK" "project-context.md 存在"
    }
} else {
    Add-Result "WARN" "project-context.md 不存在（onboarding 会提示生成）"
}

# 7. project-progress.yaml
if (Test-Path "project-progress.yaml") {
    $InProgress = $false
    $CurrentStage = ""
    foreach ($Line in (Get-Content "project-progress.yaml")) {
        if ($Line -match '^current_stage:\s*"?([^"]*)"?') {
            $CurrentStage = $Matches[1]
            $InProgress = $true
            break
        }
    }
    if ($InProgress) {
        Add-Result "OK" "project-progress.yaml 存在，current_stage=$CurrentStage"
    } else {
        Add-Result "WARN" "project-progress.yaml 存在但无 current_stage 字段"
    }
} else {
    Add-Result "WARN" "project-progress.yaml 不存在（onboarding 会提示生成）"
}

# ===== 输出 =====

if ($Json) {
    $Output = @{
        results   = $Results
        has_error = $HasError
        has_warn  = $HasWarn
    }
    $Output | ConvertTo-Json -Depth 3
} else {
    Write-Host ""
    Write-Host "==== delivery-flow 配置健康检查 ====" -ForegroundColor Cyan
    Write-Host ""
    foreach ($r in $Results) {
        switch ($r.level) {
            "OK"    { Write-Host "  [OK]    $($r.message)" -ForegroundColor Green }
            "WARN"  { Write-Host "  [WARN]  $($r.message)" -ForegroundColor Yellow }
            "ERROR" { Write-Host "  [ERROR] $($r.message)" -ForegroundColor Red }
            "INFO"  { Write-Host "  [INFO]  $($r.message)" -ForegroundColor Cyan }
        }
    }
    Write-Host ""
    if ($HasError) {
        Write-Host "ERROR 存在，建议重新跑 setup.ps1（.\setup.ps1 -PluginPath ... -Init -Bmad）" -ForegroundColor Red
        exit 2
    } elseif ($HasWarn) {
        Write-Host "WARN 存在，功能可用但建议补齐缺失项" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "全部 OK，AI 可直接接管项目" -ForegroundColor Green
        exit 0
    }
}