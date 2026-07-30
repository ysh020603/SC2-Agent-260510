# Temporary serial full-match runner for kimi_nothink regression.
# Uses short batch/match names to stay under Windows MAX_PATH (~260).

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Batch = "kn30"
$Model = "Kimi-k2.5"
$Interval = 60
$Limit = 1200
$EnemyRace = "terran"
$EnemyDiff = "easy"

# Prefix kept short: race1 + strategy~6 + map~4
$Jobs = @(
    @{ Strategy = "marine_rush";           BotRace = "terran";  Map = "KairosJunctionLE"; Index = 0; Prefix = "t_mrush_kj" },
    @{ Strategy = "bio";                   BotRace = "terran";  Map = "AutomatonLE";      Index = 1; Prefix = "t_bio_au" },
    @{ Strategy = "two_base_matrix_tanks"; BotRace = "terran";  Map = "AbyssalReefLE";    Index = 2; Prefix = "t_2bmt_ab" },
    @{ Strategy = "four_gate";             BotRace = "protoss"; Map = "AutomatonLE";      Index = 3; Prefix = "p_4gate_au" },
    @{ Strategy = "voidray";               BotRace = "protoss"; Map = "AbyssalReefLE";    Index = 4; Prefix = "p_void_ab" },
    @{ Strategy = "lings";                 BotRace = "zerg";    Map = "KairosJunctionLE"; Index = 5; Prefix = "z_lings_kj" },
    @{ Strategy = "roach_hydra";           BotRace = "zerg";    Map = "AutomatonLE";      Index = 6; Prefix = "z_rh_au" }
)

$SessionId = "$(Get-Date -Format 'yyyyMMdd_HHmmss')_$PID"
$LogDir = Join-Path $Root "game_records\$Batch\runner_logs\$SessionId"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Summary = Join-Path $LogDir "matrix_summary.txt"
"batch=$Batch model=$Model started=$(Get-Date -Format o)" | Tee-Object -FilePath $Summary

foreach ($job in $Jobs) {
    $idx = $job.Index
    $tag = "$($job.BotRace)_$($job.Strategy)_$($job.Map)"
    $log = Join-Path $LogDir ("{0:D2}_{1}.log" -f $idx, $tag)
    $line = "[$idx] START $tag $(Get-Date -Format o)"
    $line | Tee-Object -FilePath $Summary -Append
    Write-Host $line

    $pyArgs = @(
        "tools\run_experiment.py",
        "--strategy", $job.Strategy,
        "--bot-race", $job.BotRace,
        "--enemy-race", $EnemyRace,
        "--enemy-difficulty", $EnemyDiff,
        "--decision-model", $Model,
        "--decision-interval", "$Interval",
        "--game-time-limit", "$Limit",
        "--map-name", $job.Map,
        "--batch-name", $Batch,
        "--match-prefix", $job.Prefix,
        "--run-index", "$idx"
    )

    $sw = [Diagnostics.Stopwatch]::StartNew()
    & python @pyArgs *>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
    $sw.Stop()
    $done = "[$idx] DONE exit=$code elapsed_sec=$([int]$sw.Elapsed.TotalSeconds) $tag $(Get-Date -Format o)"
    $done | Tee-Object -FilePath $Summary -Append
    Write-Host $done
}

"finished=$(Get-Date -Format o)" | Tee-Object -FilePath $Summary -Append
