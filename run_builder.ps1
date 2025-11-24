# run_builder.ps1
# 启动 Serena Offline Builder GUI

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "      Serena Offline Builder Launcher     " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. 检查 Python 环境
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[Error] 未找到 Python。请确保 Python 已安装并添加到 PATH 环境变量中。" -ForegroundColor Red
    Read-Host "按回车键退出..."
    exit 1
}

# 2. 检查 uv 工具 (构建和下载依赖需要)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[Warning] 未找到 'uv' 工具。" -ForegroundColor Yellow
    Write-Host "    GUI 可以启动，但在构建或下载依赖时可能会失败。" -ForegroundColor Gray
    Write-Host "    请确保 'uv' 已安装 (pip install uv) 并添加到 PATH。" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "[OK] 检测到 Python 和 uv 工具。" -ForegroundColor Green
}

# 3. 启动 GUI
$GuiScript = Join-Path $ScriptDir "build_gui.py"
if (-not (Test-Path $GuiScript)) {
    Write-Host "[Error] 找不到脚本文件: $GuiScript" -ForegroundColor Red
    Read-Host "按回车键退出..."
    exit 1
}

Write-Host "正在启动 GUI..." -ForegroundColor Cyan
try {
    # 使用 python 运行脚本
    & python $GuiScript
}
catch {
    Write-Host "[Error] 运行过程中发生错误: $_" -ForegroundColor Red
}

Write-Host "程序已结束。" -ForegroundColor Gray
Read-Host "按回车键关闭窗口..."
