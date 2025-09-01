param(
  [ValidateSet('patch','minor','major')] [string]$Type = 'patch',
  [string]$Branch = 'main'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Write-Warn($msg)  { Write-Host $msg -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host $msg -ForegroundColor Red }

# Ensure GitHub CLI is available and authenticated
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  Write-Err 'GitHub CLI (gh) not found. Install: https://cli.github.com/'
  exit 1
}
& gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Err 'GitHub CLI not authenticated. Run: gh auth login'
  exit 1
}

# Determine if this is the first release (no v* tags yet)
$hasTags = (& git tag --list 'v*')
$isFirstRelease = -not $hasTags

# Read current VERSION (if present)
$currentVersion = if (Test-Path 'VERSION') { (Get-Content 'VERSION' -Raw).Trim() } else { '' }

function Get-NextVersion([string]$current, [string]$bump) {
  if (-not $current -or ($current -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$')) { $current = '0.0.0' }
  $parts = $current.Split('.') | ForEach-Object { [int]$_ }
  $major,$minor,$patch = $parts
  switch ($bump) {
    'major' { $major++; $minor=0; $patch=0 }
    'minor' { $minor++; $patch=0 }
    default { $patch++ }
  }
  return "$major.$minor.$patch"
}

# Enforce first release to v1.0.0 regardless of selection
if ($isFirstRelease) {
  if ($Type -ne 'major') { Write-Warn "First release detected: overriding bump '$Type' -> 'major' for v1.0.0" }
  $Type = 'major'
}

$predicted = if ($isFirstRelease) { '1.0.0' } else { Get-NextVersion -current $currentVersion -bump $Type }

Write-Info "Releasing BindKit"
Write-Host "  Current VERSION: $([string]::IsNullOrEmpty($currentVersion) ? '(none)' : $currentVersion)"
Write-Host "  Bump type      : $Type"
Write-Host "  Next version   : v$predicted"
Write-Host "  Branch         : $Branch"

# Trigger the GitHub Actions workflow
Write-Info "Triggering GitHub Actions workflow 'release.yml'..."
& gh workflow run release.yml -r $Branch -f release_type=$Type
if ($LASTEXITCODE -ne 0) {
  Write-Err 'Failed to dispatch workflow.'
  exit 1
}

Write-Host "Workflow dispatched. This will:"
Write-Host "  - Commit: chore(release): v$predicted"
Write-Host "  - Tag: v$predicted"
Write-Host "  - Build and publish installer + portable EXE"

# Optionally watch the latest run for this branch
try {
  Write-Info "Waiting for workflow completion (Ctrl+C to stop)..."
  Start-Sleep -Seconds 5
  & gh run watch --exit-status *> $null
} catch {
  Write-Warn 'Could not watch run; check Actions tab for progress.'
}

Write-Info "Done. View the release when it finishes:"
Write-Host "  gh release view v$predicted --web"

