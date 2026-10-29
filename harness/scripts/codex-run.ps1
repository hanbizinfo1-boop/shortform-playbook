<#
.SYNOPSIS
    CODEX 5.6 LUNA 브리지 - OpenAI Codex CLI 를 비대화형으로 1회 호출한다.
.DESCRIPTION
    Claude Code 의 codex-luna 서브에이전트가 이 스크립트만 통해 Codex 를 부른다.
    프롬프트는 stdin 으로 넘기고, 최종 답변만 --output-last-message 파일로 받아 출력한다.
    중간 로그는 작업 루트의 _tmp\codex\ 에 남는다.
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File %USERPROFILE%\.claude\scripts\codex-run.ps1 -Prompt "이 저장소 구조를 요약해줘"
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File %USERPROFILE%\.claude\scripts\codex-run.ps1 -PromptFile _tmp\codex\task.md -Sandbox workspace-write
#>
[CmdletBinding()]
param(
    # 인라인 프롬프트. 짧을 때만 사용한다.
    [string]$Prompt,

    # 긴 프롬프트는 파일로 넘긴다. UTF-8 로 저장할 것.
    [string]$PromptFile,

    # read-only: 읽고 분석만. workspace-write: WorkDir 안에서 파일 수정 허용.
    [ValidateSet('read-only', 'workspace-write')]
    [string]$Sandbox = 'read-only',

    [string]$Model = 'gpt-5.6-luna',

    [ValidateSet('low', 'medium', 'high', 'xhigh')]
    [string]$Effort = 'xhigh',

    # Codex 의 작업 루트. 기본값은 호출 시점의 현재 디렉터리.
    [string]$WorkDir,

    # 표준 지침(한국어 응답 / UTF-8 읽기 / 작업 범위) 자동 삽입을 끈다.
    [switch]$NoPreamble
)

$ErrorActionPreference = 'Stop'
try {
    # BOM 없는 UTF-8. [Text.Encoding]::UTF8 은 preamble(BOM)을 붙여서 프롬프트 앞이 더러워진다.
    # $global: 필수. 스크립트 스코프에만 잡으면 `& script.ps1` 로 직접 불렀을 때
    # 네이티브 명령으로 가는 파이프가 부모 세션 기본값(ASCII)을 써서 한글이 ? 로 깨진다.
    $utf8Pipe = New-Object Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $utf8Pipe
    $global:OutputEncoding = $utf8Pipe
} catch { }

# 이 스크립트는 ~/.claude/scripts/ 에 있어 특정 저장소에 묶이지 않는다.
# 작업 루트는 호출한 세션의 현재 디렉터리 = 지금 열려 있는 저장소.
if ([string]::IsNullOrWhiteSpace($WorkDir)) { $WorkDir = (Get-Location).Path }
$WorkDir = (Resolve-Path -LiteralPath $WorkDir).Path

# 로그도 그 저장소 안에 남긴다. 쓸 수 없으면 홈으로 물러난다.
$tmp = Join-Path $WorkDir '_tmp\codex'
try {
    if (-not (Test-Path -LiteralPath $tmp)) { New-Item -ItemType Directory -Force -Path $tmp | Out-Null }
} catch {
    $tmp = Join-Path $env:USERPROFILE '.claude\_tmp\codex'
    if (-not (Test-Path -LiteralPath $tmp)) { New-Item -ItemType Directory -Force -Path $tmp | Out-Null }
}

if (-not [string]::IsNullOrWhiteSpace($PromptFile)) {
    if (-not (Test-Path -LiteralPath $PromptFile)) {
        Write-Error ('프롬프트 파일을 찾지 못했다: {0}' -f $PromptFile)
        exit 2
    }
    $Prompt = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $PromptFile).Path, [Text.Encoding]::UTF8)
}
if ([string]::IsNullOrWhiteSpace($Prompt)) {
    Write-Error '프롬프트가 비어 있다. -Prompt 또는 -PromptFile 중 하나는 반드시 필요하다.'
    exit 2
}

# PATH 에 codex.cmd 와 확장자 없는 codex(셸 스크립트)가 같이 잡히므로 실행 가능한 쪽만 고른다.
$codexAll  = @(Get-Command codex -CommandType Application -ErrorAction SilentlyContinue)
$codexPath = ($codexAll | Where-Object { $_.Source -match '\.(cmd|bat|exe)$' } | Select-Object -First 1).Source
if (-not $codexPath) { $codexPath = ($codexAll | Select-Object -First 1).Source }
if (-not $codexPath) {
    Write-Error 'codex CLI 를 PATH 에서 찾지 못했다. `npm i -g @openai/codex` 로 설치했는지 확인할 것.'
    exit 3
}

$id         = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N').Substring(0, 6))
$promptPath = Join-Path $tmp ($id + '.prompt.md')
$lastPath   = Join-Path $tmp ($id + '.answer.md')
$logPath    = Join-Path $tmp ($id + '.log.txt')

if (-not $NoPreamble) {
    # 이 환경 고유의 함정을 매번 알려준다.
    #  - Windows PowerShell 5.1 은 BOM 없는 UTF-8 파일을 ANSI 로 읽어 한글이 깨진다.
    #  - 작업 범위는 저장소 루트 밖으로 나가면 안 된다.
    $preamble = @"
[운영 지침 — 호출자가 자동 삽입]
- 모든 답변은 한국어로 한다.
- 작업 루트는 $WorkDir 이다. 이 밖의 경로는 읽기만 하고, 쓰기는 절대 하지 않는다.
- 파일을 읽을 때는 반드시 UTF-8 로 읽어라. PowerShell 을 쓴다면
  ``Get-Content -LiteralPath <경로> -Raw -Encoding UTF8`` 처럼 -Encoding UTF8 을 명시할 것.
  (이 환경의 기본 인코딩은 ANSI(CP949)라 한글이 깨진다.)
- 파일을 새로 쓸 때는 UTF-8 (BOM 없음), 줄바꿈 LF 로 쓴다.
- 한글이나 `★` 가 들어간 경로는 항상 따옴표로 감싼다.
- 최종 답변은 자기완결적으로 쓴다. 호출자는 네 마지막 메시지만 읽는다.

[요청]
"@
    $Prompt = $preamble + "`n" + $Prompt
}

$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($promptPath, $Prompt, $utf8NoBom)

$argList = @(
    'exec'
    '--skip-git-repo-check'
    '--color', 'never'
    '-m', $Model
    '-s', $Sandbox
    '-C', $WorkDir
    '-c', ('model_reasoning_effort="{0}"' -f $Effort)
    '-o', $lastPath
)

$sw = [Diagnostics.Stopwatch]::StartNew()
$Prompt | & $codexPath @argList | Out-File -LiteralPath $logPath -Encoding utf8
$code = $LASTEXITCODE
$sw.Stop()

$answer = ''
if (Test-Path -LiteralPath $lastPath) {
    $answer = [IO.File]::ReadAllText($lastPath, [Text.Encoding]::UTF8)
}

Write-Output ('=== CODEX LUNA | model={0} | sandbox={1} | effort={2} | {3:n1}s | exit={4} ===' -f `
    $Model, $Sandbox, $Effort, $sw.Elapsed.TotalSeconds, $code)

if ([string]::IsNullOrWhiteSpace($answer)) {
    Write-Output '(최종 답변이 비어 있다. 아래는 실행 로그 마지막 40줄)'
    if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Tail 40 }
} else {
    Write-Output $answer
}

Write-Output ('=== END | prompt: {0} | log: {1} ===' -f $promptPath, $logPath)
exit $code
