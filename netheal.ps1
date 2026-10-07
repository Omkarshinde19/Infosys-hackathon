param([ValidateSet('start','stop','status','test','eval')][string]$Command = 'start')
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$runRoot = Join-Path $projectRoot '.cache/runtime'
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install Python dependencies into .venv first (see README).' }
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodePath = if ($nodeCommand) { $nodeCommand.Source } else {
    Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
}
$nextPath = Join-Path $projectRoot 'frontend/node_modules/next/dist/bin/next'
if ($Command -eq 'test') { & $pythonPath -m pytest -q; exit $LASTEXITCODE }
if ($Command -eq 'eval') { & $pythonPath -m services.evaluator.harness @args; exit $LASTEXITCODE }

function Stop-OwnedProcesses {
    $recordPath = Join-Path $runRoot 'processes.json'
    if (-not (Test-Path -LiteralPath $recordPath)) { return }
    $records = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    foreach ($record in $records) {
        $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
        $expectedStart = if ($record.started -is [datetime]) { $record.started.ToUniversalTime() }
        else { [datetime]::Parse([string]$record.started, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime() }
        if ($process -and [Math]::Abs(($process.StartTime.ToUniversalTime() - $expectedStart).TotalSeconds) -lt 1) {
            # PID and creation time guard against stopping an unrelated reused PID.
            & taskkill.exe /PID $record.id /T /F | Out-Null
        }
        # A Python venv launcher may exit while its interpreter child keeps serving.
        $children = Get-CimInstance Win32_Process | Where-Object {
            $_.ParentProcessId -eq $record.id -and $_.CommandLine -and
            $_.CommandLine.Contains($projectRoot) -and $_.CreationDate.ToUniversalTime() -ge $expectedStart
        }
        foreach ($child in $children) { & taskkill.exe /PID $child.ProcessId /T /F | Out-Null }
    }
    $stillRunning = @($records | Where-Object { Get-Process -Id $_.id -ErrorAction SilentlyContinue })
    if ($stillRunning.Count -eq 0) { Remove-Item -LiteralPath $recordPath }
    else { throw 'A recorded process remains running; its identity did not match the saved creation time.' }
}

function Show-Status {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8001/health' -TimeoutSec 3
        Write-Host ('Engine: running; detector ready={0}; telemetry age={1}s' -f $health.detector_ready,$health.telemetry_age_s)
    } catch { Write-Host 'Engine: unavailable' }
    Write-Host 'Dashboard: http://localhost:3000'
    Write-Host 'API: http://localhost:8001/docs'
    Write-Host ('Logs: {0}' -f $runRoot)
}

if ($Command -eq 'stop') { Stop-OwnedProcesses; Write-Host 'NetHeal processes stopped.'; exit }
if ($Command -eq 'status') { Show-Status; exit }
if (-not (Test-Path -LiteralPath $nodePath) -or -not (Test-Path -LiteralPath $nextPath)) {
    throw 'Install frontend dependencies (npm ci --prefix frontend) and make Node available.'
}
foreach ($port in 8001,3000) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Run .\netheal.ps1 status or stop your existing service."
    }
}
# A stable private signing key is created locally; its value is never printed.
$envPath = Join-Path $projectRoot '.env'
$envText = if (Test-Path -LiteralPath $envPath) { Get-Content -LiteralPath $envPath -Raw } else { '' }
$match = [regex]::Match($envText,'(?m)^JWT_SECRET\s*=\s*([^\r\n]+)')
if (-not $match.Success -or $match.Groups[1].Value.Trim(' ','"',"'").Length -lt 32) {
    $keyBytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($keyBytes)
    $key = [BitConverter]::ToString($keyBytes).Replace('-','').ToLowerInvariant()
    $envText = [regex]::Replace($envText,'(?m)^JWT_SECRET[^\r\n]*(?:\r?\n)?','')
    [System.IO.File]::WriteAllText($envPath,$envText.TrimEnd()+[Environment]::NewLine+'JWT_SECRET='+$key+[Environment]::NewLine)
}
$env:NETHEAL_STATE_PATH = Join-Path $runRoot 'controller.sqlite3'
$env:GATEWAY_URL = 'http://127.0.0.1:8001'
$env:NEXT_PUBLIC_GATEWAY_WS = 'ws://localhost:8001/ws/live'
$env:PYTHONUNBUFFERED = '1'
# Native mode uses direct WebSockets. Docker mode has its own broker/archive profile.
Remove-Item Env:KAFKA_BOOTSTRAP -ErrorAction SilentlyContinue
$records = @()
try {
    $engine = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','services.gateway.main:app','--host','127.0.0.1','--port','8001') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot 'engine.log') -RedirectStandardError (Join-Path $runRoot 'engine-error.log')
    $records += @{id=$engine.Id; started=$engine.StartTime.ToUniversalTime().ToString('o'); name='engine'}
    $nextMode = if (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend/.next/BUILD_ID')) { 'start' } else { 'dev' }
    $frontend = Start-Process -FilePath $nodePath -ArgumentList @(('"'+$nextPath+'"'),$nextMode,'--hostname','127.0.0.1','--port','3000') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot 'frontend.log') -RedirectStandardError (Join-Path $runRoot 'frontend-error.log')
    $records += @{id=$frontend.Id; started=$frontend.StartTime.ToUniversalTime().ToString('o'); name='frontend'}
    $records | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runRoot 'processes.json')
    # Save the actual listener identities as well as launchers, including venv children.
    $deadline = (Get-Date).AddSeconds(55)
    do {
        $listeners = @(Get-NetTCPConnection -LocalPort 8001,3000 -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count -ge 2) { break }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    if (@($listeners.LocalPort | Sort-Object -Unique).Count -lt 2) {
        throw 'Engine or frontend did not start within 55 seconds. Inspect .cache/runtime logs.'
    }
    foreach ($listener in $listeners) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($owner.CommandLine -and $owner.CommandLine.Contains($projectRoot)) {
            $actual = Get-Process -Id $owner.ProcessId
            if ($owner.ProcessId -notin $records.id) {
                $records += @{id=$actual.Id; started=$actual.StartTime.ToUniversalTime().ToString('o'); name='listener'}
            }
        }
    }
    $records | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runRoot 'processes.json')
} catch {
    $records | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runRoot 'processes.json')
    Stop-OwnedProcesses
    throw
}
Write-Host 'NetHeal started. The detector learns for about30 seconds before ordinary anomaly scoring.'
Show-Status
