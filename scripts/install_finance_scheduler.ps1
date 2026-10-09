param(
    [string]$TaskName = "WealthAudit Finance Sync",
    [string]$WslDistro = "Ubuntu-22.04",
    [Parameter(Mandatory = $true)]
    [string]$RepoPath,
    [string]$At = "07:00"
)

$ErrorActionPreference = "Stop"

if ($RepoPath -notmatch '^/') {
    throw "RepoPath must be a WSL/Linux absolute path such as /home/kafka/WealthAudit"
}

try {
    $triggerTime = [DateTime]::ParseExact($At, "HH:mm", $null)
} catch {
    throw "At must use HH:mm, for example 07:00"
}

$quotedRepo = $RepoPath.Replace("'", "'\''")
$bash = "cd '$quotedRepo' && mkdir -p data/logs && uv run python -m src.infrastructure.finance_sync_cli run >> data/logs/finance-sync.log 2>&1"
$q = [char]34
$arguments = "-d $q$WslDistro$q -- bash -lc $q$bash$q"

$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Retention-aware WealthAudit finance acquisition. Authentication boundaries are handled per provider." -Force | Out-Null

Write-Output "Registered: $TaskName"
Write-Output "Daily: $At"
Write-Output "WSL distro: $WslDistro"
Write-Output "Repo: $RepoPath"
