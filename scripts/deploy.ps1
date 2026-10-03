# 一键发布：构建 + 提交 + 推送（Vercel 自动部署）
# 用法： powershell -ExecutionPolicy Bypass -File scripts/deploy.ps1 -Message "KW43/44 更新"

param([string]$Message = "update flyer data")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== 1/3 构建站点 ==" -ForegroundColor Cyan
python "scripts\build.py"

Write-Host "== 2/3 提交改动 ==" -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
    git init | Out-Null
    git branch -M main
}
git add -A
git commit -m $Message

Write-Host "== 3/3 推送到远端（Vercel 自动部署）==" -ForegroundColor Cyan
git push

Write-Host "完成。若尚未绑定 Vercel，请到 vercel.com 导入该仓库，Output Directory 填 dist。" -ForegroundColor Green
