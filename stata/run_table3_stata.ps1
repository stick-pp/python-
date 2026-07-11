param(
    [string]$PythonOut = "",
    [string]$StataOut = "",
    [string]$StataExe = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$checkoutRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
if ((Split-Path -Leaf (Split-Path -Parent $checkoutRoot)) -eq "worktrees") {
    $repoRoot = (Resolve-Path (Join-Path $checkoutRoot "..\..")).Path
} else {
    $repoRoot = $checkoutRoot
}
if ([string]::IsNullOrWhiteSpace($PythonOut)) {
    $PythonOut = Join-Path $repoRoot "shared_artifacts\python_out"
}
if ([string]::IsNullOrWhiteSpace($StataOut)) {
    $StataOut = Join-Path $repoRoot "shared_artifacts\stata_out"
}
$PythonOut = [System.IO.Path]::GetFullPath($PythonOut)
$StataOut = [System.IO.Path]::GetFullPath($StataOut)
$PythonStataIn = Join-Path $PythonOut "stata"
$PythonQaCounts = Join-Path $PythonOut "tables\qa_table3_regression_sample_counts.csv"
$ManifestPath = Join-Path $PythonOut "manifest.csv"

$doFile = Join-Path $scriptDir "table3_replication.do"
if (-not (Test-Path -LiteralPath $doFile)) {
    throw "Missing Stata do-file: $doFile"
}

New-Item -ItemType Directory -Force -Path $StataOut | Out-Null

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    $message = "Python manifest not found: $ManifestPath"
    $message | Set-Content -Path (Join-Path $StataOut "table3_stata_blocked.txt") -Encoding UTF8
    throw $message
}

$manifest = Import-Csv -LiteralPath $ManifestPath
$manifestFiles = @{}
foreach ($row in $manifest) {
    $manifestFiles[$row.file] = $true
}
$requiredManifestFiles = @(
    "stata/table3_regression_data.csv",
    "stata/table3_regression_data.dta",
    "stata/table3_replication.do"
)
foreach ($file in $requiredManifestFiles) {
    if (-not $manifestFiles.ContainsKey($file)) {
        $message = "Required Stata handoff file is not listed in manifest.csv: $file"
        $message | Set-Content -Path (Join-Path $StataOut "table3_stata_blocked.txt") -Encoding UTF8
        throw $message
    }
}

$pythonDo = Join-Path $PythonStataIn "table3_replication.do"
if (-not (Test-Path -LiteralPath $pythonDo)) {
    $message = "Python handoff Stata do-file not found: $pythonDo"
    $message | Set-Content -Path (Join-Path $StataOut "table3_stata_blocked.txt") -Encoding UTF8
    throw $message
}
if (-not (Test-Path -LiteralPath $PythonQaCounts)) {
    $message = "Python Table 3 QA sample-count file not found: $PythonQaCounts"
    $message | Set-Content -Path (Join-Path $StataOut "table3_stata_blocked.txt") -Encoding UTF8
    throw $message
}

$dtaInput = Join-Path $PythonStataIn "table3_regression_data.dta"
$csvInput = Join-Path $PythonStataIn "table3_regression_data.csv"
if (Test-Path -LiteralPath $dtaInput) {
    $inputPath = $dtaInput
    $inputKind = "dta"
} elseif (Test-Path -LiteralPath $csvInput) {
    $inputPath = $csvInput
    $inputKind = "csv"
} else {
    $message = "Python regression data not found. Expected table3_regression_data.dta or table3_regression_data.csv in $PythonStataIn"
    $message | Set-Content -Path (Join-Path $StataOut "table3_stata_blocked.txt") -Encoding UTF8
    throw $message
}

if ([string]::IsNullOrWhiteSpace($StataExe)) {
    $cmd = Get-Command StataMP-64 -ErrorAction SilentlyContinue
    if ($cmd) {
        $StataExe = $cmd.Source
    } else {
        $cmd = Get-Command StataSE-64 -ErrorAction SilentlyContinue
        if ($cmd) {
            $StataExe = $cmd.Source
        } else {
            $cmd = Get-Command StataBE-64 -ErrorAction SilentlyContinue
            if ($cmd) {
                $StataExe = $cmd.Source
            } else {
                $cmd = Get-Command stata -ErrorAction SilentlyContinue
                if ($cmd) {
                    $StataExe = $cmd.Source
                }
            }
        }
    }
}

if ([string]::IsNullOrWhiteSpace($StataExe) -or -not (Test-Path -LiteralPath $StataExe)) {
    throw "Stata executable not found. Pass -StataExe with the full path."
}

$runDir = Join-Path ([System.IO.Path]::GetTempPath()) ("skinner_table3_stata_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$tempDo = Join-Path $runDir "table3_replication.do"
$tempInput = Join-Path $runDir ("table3_regression_data." + $inputKind)
Copy-Item -LiteralPath $doFile -Destination $tempDo -Force
Copy-Item -LiteralPath $inputPath -Destination $tempInput -Force

$env:SKINNER_TABLE3_DTA = ""
$env:SKINNER_TABLE3_CSV = ""
if ($inputKind -eq "dta") {
    $env:SKINNER_TABLE3_DTA = ($tempInput -replace "\\", "/")
} else {
    $env:SKINNER_TABLE3_CSV = ($tempInput -replace "\\", "/")
}
$env:SKINNER_STATA_OUT = ($runDir -replace "\\", "/")

$process = Start-Process -FilePath $StataExe -ArgumentList @("/b", "do", "`"$tempDo`"") -WorkingDirectory $runDir -PassThru -WindowStyle Hidden
$deadline = (Get-Date).AddMinutes(5)
$resultCsv = Join-Path $runDir "table3_stata_results.csv"

while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $resultCsv) {
        break
    }
    if ($process.HasExited -and -not (Test-Path -LiteralPath $resultCsv)) {
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
}

if (-not (Test-Path -LiteralPath $resultCsv)) {
    $logFile = Join-Path $runDir "table3_stata.log"
    if (Test-Path -LiteralPath $logFile) {
        Copy-Item -LiteralPath $logFile -Destination (Join-Path $StataOut "table3_stata.log") -Force
    }
    $batchLogFile = Join-Path $runDir "table3_replication.log"
    if (Test-Path -LiteralPath $batchLogFile) {
        Copy-Item -LiteralPath $batchLogFile -Destination (Join-Path $StataOut "table3_replication.log") -Force
    }
    throw "Stata did not create table3_stata_results.csv. See table3_stata.log if it was copied."
}

foreach ($name in @(
    "table3_stata_results.csv",
    "table3_stata_results.dta",
    "table3_stata_sample_counts.csv",
    "table3_stata_sample_counts.dta",
    "table3_stata.log"
)) {
    $src = Join-Path $runDir $name
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $StataOut $name) -Force
    }
}

$stataCountsPath = Join-Path $StataOut "table3_stata_sample_counts.csv"
$stataCounts = Import-Csv -LiteralPath $stataCountsPath
$pythonCounts = Import-Csv -LiteralPath $PythonQaCounts
$pythonByModel = @{}
foreach ($row in $pythonCounts) {
    $pythonByModel["$($row.panel)||$($row.model)"] = [int]$row.current_N
}

$checkRows = New-Object System.Collections.Generic.List[object]
$mismatches = New-Object System.Collections.Generic.List[string]
foreach ($row in $stataCounts) {
    $key = "$($row.panel)||$($row.model)"
    if (-not $pythonByModel.ContainsKey($key)) {
        $mismatches.Add("Missing Python QA row for $($row.panel) $($row.model)")
        continue
    }
    $stataN = [int]$row.N
    $pythonN = $pythonByModel[$key]
    $match = ($stataN -eq $pythonN)
    $checkRows.Add([pscustomobject]@{
        panel = $row.panel
        model = $row.model
        stata_N = $stataN
        python_N = $pythonN
        N_match = $match
    })
    if (-not $match) {
        $mismatches.Add("$($row.panel) $($row.model): Stata N=$stataN, Python N=$pythonN")
    }
}

$checkPath = Join-Path $StataOut "table3_stata_python_sample_check.csv"
$checkRows | Export-Csv -LiteralPath $checkPath -NoTypeInformation -Encoding UTF8
if ($mismatches.Count -gt 0) {
    $message = "Stata/Python Table 3 sample-count mismatch: " + ($mismatches -join "; ")
    $message | Set-Content -Path (Join-Path $StataOut "table3_stata_blocked.txt") -Encoding UTF8
    throw $message
}

"Stata Table 3 run completed at $(Get-Date -Format s). Input=$inputPath. Sample counts matched $PythonQaCounts." | Set-Content -Path (Join-Path $StataOut "table3_stata_run_summary.txt") -Encoding UTF8
Write-Output "Wrote Table 3 Stata outputs to $StataOut"
