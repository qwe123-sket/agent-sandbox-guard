# 一键环境初始化（Windows PowerShell）
# 用法：在项目根目录执行  .\scripts\setup_env.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> 创建虚拟环境 .venv"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

Write-Host "==> 配置 pip 国内镜像（清华源）"
Copy-Item -Force "config\pip.ini" ".venv\pip.ini"

Write-Host "==> 安装依赖"
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\pip.exe" install -r requirements.txt

Write-Host ""
Write-Host "完成。接下来："
Write-Host "  copy .env.example .env"
Write-Host "  python scripts/run_agent_llm.py --role operator"
