# 이 폴더의 Claude Code 세션을 이어서 연다.
#
#   .\이어하기.ps1          # 가장 최근 대화를 잇는다 (없으면 새 세션)
#   .\이어하기.ps1 -New     # 새 세션으로 시작
#   .\이어하기.ps1 -Pick    # 세션 목록에서 고른다
param([switch]$New, [switch]$Pick)
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot

if ($New)  { claude;            exit $LASTEXITCODE }
if ($Pick) { claude --resume;   exit $LASTEXITCODE }

claude --continue
if ($LASTEXITCODE -ne 0) { claude }
exit $LASTEXITCODE
