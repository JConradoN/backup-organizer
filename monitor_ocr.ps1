param(
    [string]$JobLike = "ocr_dir_%",
    [int]$IntervalSec = 5,
    [string]$DbPath = "backup_organizer.db",
    [string]$PythonExe = "",
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

function Resolve-PythonExe {
    param([string]$Preferred)

    if ($Preferred -and (Test-Path $Preferred)) {
        return $Preferred
    }

    $venvPy = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        return $venvPy
    }

    $cmd = Get-Command python
    if ($cmd) {
        return $cmd.Source
    }

    throw "Nao foi possivel encontrar python.exe. Passe -PythonExe explicitamente."
}

function Get-OcrProcesses {
    $procs = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match "indexacao_texto.py" } |
        Sort-Object ProcessId -Unique

    if (-not $procs) {
        return @()
    }

    $perfProc = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process
    $gpuEng = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine |
        Where-Object { $_.UtilizationPercentage -gt 0 }

    $rows = @()
    foreach ($p in $procs) {
        $pid = [int]$p.ProcessId
        $perf = $perfProc | Where-Object { [int]$_.IDProcess -eq $pid } | Select-Object -First 1

        $gpuPct = 0
        $pidPattern = "pid_${pid}_"
        foreach ($g in $gpuEng) {
            if ($g.Name -like "*$pidPattern*") {
                $gpuPct += [double]$g.UtilizationPercentage
            }
        }

        $job = ""
        $source = ""
        if ($p.CommandLine -match "--job-id\s+([^\s]+)") {
            $job = $Matches[1]
        }
        if ($p.CommandLine -match "--fonte\s+([^\s]+)") {
            $source = $Matches[1]
        }

        $rows += [PSCustomObject]@{
            PID    = $pid
            CPUPct = [int]($perf.PercentProcessorTime)
            RAMMB  = [math]::Round(([double]$perf.WorkingSetPrivate / 1MB), 1)
            GPUPct = [int]([math]::Round($gpuPct, 0))
            JobId  = $job
            Fonte  = $source
        }
    }

    # Defensive dedupe by PID in case CIM returns duplicated entries.
    return (
        $rows |
            Group-Object -Property PID |
            ForEach-Object { $_.Group | Select-Object -First 1 } |
            Sort-Object CPUPct -Descending
    )
}

function Get-JobProgress {
    param(
        [string]$PythonPath,
        [string]$DatabasePath,
        [string]$LikePattern
    )

    $pyCode = @'
import json
import pathlib
import sqlite3
import sys

db = pathlib.Path(sys.argv[1])
like = sys.argv[2]

if not db.exists():
    print(json.dumps({"error": f"db nao encontrado: {db}"}))
    raise SystemExit(0)

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
    SELECT job_id, fonte, status, processed_count, total_count, updated_em
    FROM text_index_jobs
    WHERE job_id LIKE ?
    ORDER BY updated_em DESC
    """,
    (like,)
).fetchall()

out = []
for r in rows:
    processed = int(r["processed_count"] or 0)
    total = int(r["total_count"] or 0)
    pct = (processed * 100.0 / total) if total > 0 else 0.0
    out.append(
        {
            "job_id": r["job_id"],
            "fonte": r["fonte"],
            "status": r["status"],
            "processed": processed,
            "total": total,
            "percent": round(pct, 2),
            "updated_em": r["updated_em"],
        }
    )

print(json.dumps({"jobs": out}, ensure_ascii=False))
'@

    $raw = & $PythonPath -c $pyCode $DatabasePath $LikePattern 2>$null
    if (-not $raw) {
        return @()
    }

    $parsed = $raw | ConvertFrom-Json
    if ($parsed.error) {
        return @([PSCustomObject]@{ Error = $parsed.error })
    }

    return $parsed.jobs
}

function Show-Snapshot {
    param(
        [string]$PythonPath,
        [string]$DatabasePath,
        [string]$LikePattern,
        [bool]$ClearScreen = $true
    )

    if ($ClearScreen) {
        Clear-Host
    }
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "Monitor OCR/Ollama  |  $now"
    Write-Host "Db: $DatabasePath  |  Filtro job: $LikePattern"
    Write-Host ("=" * 90)

    $ocr = Get-OcrProcesses
    if ($ocr.Count -eq 0) {
        Write-Host "OCR: nenhum processo indexacao_texto.py ativo."
    }
    else {
        Write-Host "OCR processos ativos:"
        $ocr | Format-Table PID, CPUPct, RAMMB, GPUPct, JobId, Fonte -AutoSize

        $sumCpu = ($ocr | Measure-Object -Property CPUPct -Sum).Sum
        $sumRam = ($ocr | Measure-Object -Property RAMMB -Sum).Sum
        $sumGpu = ($ocr | Measure-Object -Property GPUPct -Sum).Sum
        Write-Host ("Totais OCR -> CPU%: {0} | RAM(MB): {1} | GPU%: {2}" -f $sumCpu, [int]$sumRam, $sumGpu)
    }

    Write-Host ("-" * 90)

    if (Get-Command ollama) {
        $ops = ollama ps
        if ($ops) {
            Write-Host "Ollama:"
            $ops
        }
        else {
            Write-Host "Ollama: sem modelos ativos."
        }
    }
    else {
        Write-Host "Ollama: CLI nao encontrado no PATH."
    }

    Write-Host ("-" * 90)

    $jobs = Get-JobProgress -PythonPath $PythonPath -DatabasePath $DatabasePath -LikePattern $LikePattern
    if ($jobs.Count -eq 0) {
        Write-Host "Jobs: nenhum registro encontrado no banco para o filtro informado."
    }
    elseif ($jobs[0].PSObject.Properties.Name -contains "Error") {
        Write-Host ("Jobs: {0}" -f $jobs[0].Error)
    }
    else {
        Write-Host "Progresso de jobs OCR:"
        $jobs |
            Select-Object job_id, status, processed, total, percent, updated_em, fonte |
            Format-Table -AutoSize

        $totP = ($jobs | Measure-Object -Property processed -Sum).Sum
        $totT = ($jobs | Measure-Object -Property total -Sum).Sum
        $pct = if ($totT -gt 0) { [math]::Round(($totP * 100.0 / $totT), 2) } else { 0 }
        Write-Host ("Resumo jobs -> {0}/{1} ({2}%)" -f $totP, $totT, $pct)
    }

    Write-Host ("=" * 90)
    Write-Host "Ctrl+C para parar."
}

$resolvedPy = Resolve-PythonExe -Preferred $PythonExe

do {
    Show-Snapshot -PythonPath $resolvedPy -DatabasePath $DbPath -LikePattern $JobLike -ClearScreen:(-not $Once)
    if (-not $Once) {
        Start-Sleep -Seconds $IntervalSec
    }
}
while (-not $Once)
