[CmdletBinding()]
param(
    [string]$Container = 'vasttrafik-ha',
    [int]$TimeoutSeconds = 150
)

# 'Continue' on purpose: `docker logs` writes container stderr, which would otherwise
# be turned into a terminating error by this script.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

# Readiness is taken from the container log, never by connecting to 5678: debugpy serves
# one debug session at a time, so probing it either steals the slot the debugger is about
# to use, or falsely reports "down" while a session is already attached.

# Only look at the current boot, so a previous run's listen line can't give a false pass.
$since = $null
$rawStart = (docker inspect -f '{{.State.StartedAt}}' $Container 2>$null)
if ($LASTEXITCODE -eq 0 -and $rawStart) {
    try { $since = ([datetimeoffset]::Parse($rawStart)).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') } catch { }
}

$logArgs = @('logs')
if ($since) { $logArgs += @('--since', $since) }
$logArgs += $Container

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    $log = (& docker @logArgs 2>&1 | Out-String)
    if ($log -match 'Listening for remote debug connection on') {
        Write-Host "debugpy is listening (per $Container logs)"
        exit 0
    }
    if ($log -match 'Error during setup of component debugpy') {
        Write-Error "debugpy failed to set up. Check 'docker logs $Container'."
        exit 1
    }
    Start-Sleep -Milliseconds 750
}

Write-Error "Timed out after ${TimeoutSeconds}s waiting for debugpy. Check 'docker logs $Container'."
exit 1
