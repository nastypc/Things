<#
Simple PowerShell wrapper to call the CDT Sheathing Adjuster in CLI mode.
Usage examples:
  .\sheathing-cli.ps1 -Path "C:\path\to\psfly.cdt" -Mirror
  .\sheathing-cli.ps1 -Path "C:\path\to\P1.CDT" -Mirror -Orientation horizontal
#>
param(
    [Parameter(Mandatory=$true)][string[]]$Path,
    [switch]$Mirror,
    [ValidateSet("horizontal","vertical")][string]$Orientation = "horizontal",
    [string]$Lengths
)

$python = "python"
$script = Join-Path $PSScriptRoot "src\main.py"

foreach ($p in $Path) {
    if (-not (Test-Path $p)) {
        Write-Error "File not found: $p"
        continue
    }
    $cmd = "$python `"$script`" --process `"$p`""
    if ($Mirror) { $cmd += " --mirror" }
    $cmd += " --orientation $Orientation"
    if ($Lengths) { $cmd += " --lengths `"$Lengths`"" }
    Write-Output "Running: $cmd"
    iex $cmd
}
