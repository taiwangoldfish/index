$ErrorActionPreference = 'Stop'

$projectRoot = 'c:\Users\micha\OneDrive\Desktop\經驗群\goldfish ai'
$pythonExe = 'c:\Users\micha\OneDrive\Desktop\經驗群\goldfish ai\.venv\Scripts\python.exe'
$scriptPath = Join-Path $projectRoot 'train_learning_profile.py'
$logDir = Join-Path $projectRoot 'data\logs'
$logPath = Join-Path $logDir 'train_learning_profile.log'

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

try {
    Push-Location $projectRoot
    & $pythonExe $scriptPath 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        "[$timestamp] FAILED exit_code=$LASTEXITCODE" | Out-File -FilePath $logPath -Append -Encoding utf8
        exit $LASTEXITCODE
    }
    "[$timestamp] SUCCESS" | Out-File -FilePath $logPath -Append -Encoding utf8
}
catch {
    "[$timestamp] ERROR $($_.Exception.Message)" | Out-File -FilePath $logPath -Append -Encoding utf8
    exit 1
}
finally {
    Pop-Location
}
