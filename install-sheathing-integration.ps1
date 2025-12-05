<#
Installs a simple `sheath` function into the user's PowerShell profile that invokes the local sheathing-cli.ps1 wrapper.
This is non-destructive: it appends the function only if it does not already exist in the profile.
Run with PowerShell (may prompt to create profile):
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
  .\install-sheathing-integration.ps1
#>
$wrapper = Join-Path $PSScriptRoot "sheathing-cli.ps1"
$profilePath = $PROFILE

if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

$profileText = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
if ($profileText -match "function\s+sheath\b") {
    Write-Output "A 'sheath' function already exists in your PowerShell profile. No changes made."
    return
}

$functionBlock = @"
function sheath {
    param(
        [Parameter(Mandatory=$true, ValueFromPipeline=$true)][string[]]$Path,
        [switch]$Mirror,
        [ValidateSet('horizontal','vertical')][string]$Orientation = 'horizontal',
        [string]$Lengths
    )
    $scriptDir = '${PSScriptRoot}'
    $wrapper = Join-Path $scriptDir 'sheathing-cli.ps1'
    foreach ($p in $Path) {
        & $wrapper -Path $p -Mirror:$Mirror -Orientation $Orientation -Lengths $Lengths
    }
}
"@

Add-Content -Path $profilePath -Value "`n# Added by Sheathing tool integration`n$functionBlock"
Write-Output "Added 'sheath' function to your PowerShell profile at $profilePath. Close and reopen PowerShell to use it."