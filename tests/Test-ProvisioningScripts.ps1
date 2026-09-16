$ErrorActionPreference = "Stop"

function Assert-True {
    param(
        [Parameter(Mandatory)]
        [bool] $Condition,

        [Parameter(Mandatory)]
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$scriptDirectory = Join-Path $repositoryRoot "scripts"
$scriptPaths = Get-ChildItem $scriptDirectory -Filter "*.ps1"

Assert-True ($scriptPaths.Count -ge 3) "Expected all provisioning scripts to be present."

foreach ($scriptPath in $scriptPaths) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $scriptPath.FullName,
        [ref] $tokens,
        [ref] $errors
    ) | Out-Null
    Assert-True ($errors.Count -eq 0) "$($scriptPath.Name) contains PowerShell syntax errors."
}

$allScripts = ($scriptPaths | ForEach-Object {
        Get-Content $_.FullName -Raw
    }) -join "`n"
$delegatedScript = Get-Content (
    Join-Path $scriptDirectory "Grant-PurviewDelegatedPermission.ps1"
) -Raw
$applicationScript = Get-Content (
    Join-Path $scriptDirectory "Grant-PurviewApplicationPermission.ps1"
) -Raw
$combinedScript = Get-Content (
    Join-Path $scriptDirectory "New-FabricApiInteractiveApp.ps1"
) -Raw

Assert-True (
    $allScripts -notmatch "az ad app permission admin-consent"
) "Provisioning must not grant blanket consent to every permission requested by an app."
Assert-True (
    $allScripts -notmatch "az ad app credential reset"
) "Provisioning must not create a plaintext client secret."
Assert-True (
    $allScripts -notmatch "Write-Host.*(?:password|secret):"
) "Provisioning must not write credentials to terminal output."

Assert-True (
    $delegatedScript -match "oauth2PermissionGrants"
) "Delegated consent must use an exact Microsoft Graph OAuth grant."
Assert-True (
    $delegatedScript -match "--method patch"
) "Delegated consent must update an existing grant without replacing its other scopes."
Assert-True (
    $delegatedScript -match "Sort-Object -Unique"
) "Delegated consent must preserve the union of existing and required scopes."
Assert-True (
    $delegatedScript -match "Wait-ForDelegatedScope"
) "Delegated consent visibility must use bounded polling."

Assert-True (
    $applicationScript -match "appRoleAssignments"
) "Application consent must create the exact Microsoft Graph app-role assignment."
Assert-True (
    $applicationScript -match "Wait-ForAppRoleAssignment"
) "Application permission visibility must use bounded polling."
Assert-True (
    $combinedScript -notmatch "CreateClientSecret"
) "The combined setup script must not offer plaintext secret generation."

Write-Host "Provisioning script syntax and security contracts passed."
