[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $TenantId,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $ClientId,

    [switch] $SkipLogin
)

$ErrorActionPreference = "Stop"

$graphAppId = "00000003-0000-0000-c000-000000000000"
$permissionName = "AuditLogsQuery.Read.All"
$visibilityAttempts = 6

function Wait-ForServicePrincipal {
    param(
        [Parameter(Mandatory)]
        [string] $ApplicationId,

        [int] $MaxAttempts = $visibilityAttempts
    )

    for ($attempt = 0; $attempt -lt $MaxAttempts; $attempt++) {
        $servicePrincipal = az ad sp show --id $ApplicationId --output json 2>$null |
            ConvertFrom-Json
        if ($LASTEXITCODE -eq 0 -and $servicePrincipal) {
            return $servicePrincipal
        }
        if ($attempt -lt $MaxAttempts - 1) {
            Start-Sleep -Seconds ([Math]::Pow(2, $attempt))
        }
    }
    return $null
}

function Get-AppRoleAssignment {
    param(
        [Parameter(Mandatory)]
        [string] $ClientServicePrincipalId,

        [Parameter(Mandatory)]
        [string] $ResourceServicePrincipalId,

        [Parameter(Mandatory)]
        [string] $AppRoleId
    )

    $response = az rest `
        --method get `
        --url "https://graph.microsoft.com/v1.0/servicePrincipals/$ClientServicePrincipalId/appRoleAssignments" `
        --output json |
        ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) {
        throw "Application role assignments could not be inspected."
    }
    return $response.value |
        Where-Object {
            $_.resourceId -eq $ResourceServicePrincipalId -and
            $_.appRoleId -eq $AppRoleId
        } |
        Select-Object -First 1
}

function Wait-ForAppRoleAssignment {
    param(
        [Parameter(Mandatory)]
        [string] $ClientServicePrincipalId,

        [Parameter(Mandatory)]
        [string] $ResourceServicePrincipalId,

        [Parameter(Mandatory)]
        [string] $AppRoleId
    )

    for ($attempt = 0; $attempt -lt $visibilityAttempts; $attempt++) {
        try {
            $assignment = Get-AppRoleAssignment `
                -ClientServicePrincipalId $ClientServicePrincipalId `
                -ResourceServicePrincipalId $ResourceServicePrincipalId `
                -AppRoleId $AppRoleId
        }
        catch {
            if ($attempt -eq $visibilityAttempts - 1) {
                throw
            }
            Start-Sleep -Seconds ([Math]::Pow(2, $attempt))
            continue
        }
        if ($assignment) {
            return $assignment
        }
        if ($attempt -lt $visibilityAttempts - 1) {
            Start-Sleep -Seconds ([Math]::Pow(2, $attempt))
        }
    }
    return $null
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI (az) is required. Install it from https://aka.ms/installazurecliwindows."
}

if (-not $SkipLogin) {
    Write-Host "Signing in to tenant $TenantId..."
    az login --tenant $TenantId --allow-no-subscriptions --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI sign-in failed."
    }
}

$signedInTenant = az account show --query tenantId --output tsv
if ($LASTEXITCODE -ne 0 -or $signedInTenant -ne $TenantId) {
    throw "Azure CLI is signed in to tenant '$signedInTenant', not '$TenantId'."
}

$application = az ad app show --id $ClientId --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $application) {
    throw "App registration '$ClientId' was not found in tenant '$TenantId'."
}

$graphServicePrincipal = az ad sp show --id $graphAppId --output json |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $graphServicePrincipal) {
    throw "The Microsoft Graph service principal was not found in tenant '$TenantId'."
}

$appRole = $graphServicePrincipal.appRoles |
    Where-Object {
        $_.value -eq $permissionName -and
        $_.isEnabled -and
        $_.allowedMemberTypes -contains "Application"
    } |
    Select-Object -First 1

if (-not $appRole) {
    throw "Microsoft Graph does not expose application permission '$permissionName'."
}

$graphAccess = $application.requiredResourceAccess |
    Where-Object { $_.resourceAppId -eq $graphAppId } |
    Select-Object -First 1
$alreadyRequested = $graphAccess.resourceAccess |
    Where-Object { $_.id -eq $appRole.id -and $_.type -eq "Role" } |
    Select-Object -First 1

if ($alreadyRequested) {
    Write-Host "$permissionName is already requested by app registration $ClientId."
}
else {
    Write-Host "Adding Microsoft Graph application permission $permissionName..."
    az ad app permission add `
        --id $ClientId `
        --api $graphAppId `
        --api-permissions "$($appRole.id)=Role" `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to add application permission '$permissionName'."
    }
}

$clientServicePrincipal = Wait-ForServicePrincipal -ApplicationId $ClientId -MaxAttempts 1
if (-not $clientServicePrincipal) {
    Write-Host "Creating the enterprise application for app registration $ClientId..."
    az ad sp create --id $ClientId --output none
    $createExitCode = $LASTEXITCODE
    $clientServicePrincipal = Wait-ForServicePrincipal -ApplicationId $ClientId
    if (-not $clientServicePrincipal) {
        if ($createExitCode -ne 0) {
            throw "Failed to create the enterprise application for '$ClientId'."
        }
        throw "The enterprise application for '$ClientId' was not visible after bounded polling."
    }
}

$verifiedAssignment = Get-AppRoleAssignment `
    -ClientServicePrincipalId $clientServicePrincipal.id `
    -ResourceServicePrincipalId $graphServicePrincipal.id `
    -AppRoleId $appRole.id

if (-not $verifiedAssignment) {
    Write-Host "Granting the exact Microsoft Graph application role $permissionName..."
    $assignmentBody = @{
        principalId = $clientServicePrincipal.id
        resourceId = $graphServicePrincipal.id
        appRoleId = $appRole.id
    } | ConvertTo-Json -Compress

    az rest `
        --method post `
        --url "https://graph.microsoft.com/v1.0/servicePrincipals/$($clientServicePrincipal.id)/appRoleAssignments" `
        --headers "Content-Type=application/json" `
        --body $assignmentBody `
        --output none
    if ($LASTEXITCODE -ne 0) {
        $grantExitCode = $LASTEXITCODE
    }
    else {
        $grantExitCode = 0
    }

    $verifiedAssignment = Wait-ForAppRoleAssignment `
        -ClientServicePrincipalId $clientServicePrincipal.id `
        -ResourceServicePrincipalId $graphServicePrincipal.id `
        -AppRoleId $appRole.id

    if (-not $verifiedAssignment) {
        if ($grantExitCode -ne 0) {
            throw "Application permission grant failed. Run this script while signed in as a Global Administrator."
        }
        throw "The application role assignment was not visible for '$permissionName' after bounded polling."
    }
}

Write-Host ""
Write-Host "Verified:"
Write-Host "  App registration: $($application.displayName) ($ClientId)"
Write-Host "  Permission:       $permissionName"
Write-Host "  Permission type:  Application"
Write-Host "  Admin consent:    Granted"
