param(
    [int]$Seconds = 25,
    [string]$DistDir = (Join-Path $PWD 'dist')
)
$exe = Join-Path $DistDir 'IPC-Monitor.exe'
$stdoutLog = Join-Path $DistDir 'selftest_stdout.log'
$stderrLog = Join-Path $DistDir 'selftest_stderr.log'

function Stop-ProcessTree([int]$RootId) {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $children = @{}
    foreach ($item in $all) {
        $parent = [int]$item.ParentProcessId
        if (-not $children.ContainsKey($parent)) { $children[$parent] = @() }
        $children[$parent] += [int]$item.ProcessId
    }
    $ordered = [System.Collections.Generic.List[int]]::new()
    function Add-Descendants([int]$Id) {
        if ($children.ContainsKey($Id)) {
            foreach ($childId in $children[$Id]) {
                Add-Descendants $childId
                $ordered.Add($childId)
            }
        }
    }
    Add-Descendants $RootId
    foreach ($id in $ordered) {
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
    Stop-Process -Id $RootId -Force -ErrorAction SilentlyContinue
}

function Wait-FileUnlocked([string]$Path, [int]$TimeoutSeconds = 15) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $stream = [System.IO.File]::Open($Path, 'Open', 'ReadWrite', 'None')
            $stream.Dispose()
            return $true
        } catch {
            Start-Sleep -Milliseconds 250
        }
    } while ((Get-Date) -lt $deadline)
    return $false
}

$p = Start-Process -FilePath $exe -PassThru -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
Start-Sleep -Seconds $Seconds
if (-not $p.HasExited) {
    Stop-ProcessTree $p.Id
    if (-not (Wait-FileUnlocked $exe)) {
        Write-Error '[SELFTEST] executable remained locked after stopping its process tree'
        exit 4
    }
    Write-Host '[SELFTEST] application stayed alive for the test window'
} else {
    Write-Host ("[SELFTEST] exited code " + $p.ExitCode)
    exit 1
}

$combined = @()
if (Test-Path -LiteralPath $stdoutLog) { $combined += Get-Content -Raw -Encoding UTF8 -LiteralPath $stdoutLog }
if (Test-Path -LiteralPath $stderrLog) { $combined += Get-Content -Raw -Encoding UTF8 -LiteralPath $stderrLog }
$text = $combined -join "`n"
if ($text -match 'Traceback|ModuleNotFoundError|STARTUP FAILED') {
    Write-Error '[SELFTEST] fatal error signature found in logs'
    exit 2
}
if ($text -notmatch 'YOLO loaded via ONNX') {
    Write-Error '[SELFTEST] ONNX face engine success marker not found'
    exit 3
}
Write-Host '[SELFTEST] ONNX engine marker found; no fatal signature detected'
exit 0
