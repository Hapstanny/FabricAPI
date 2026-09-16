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
$scopeName = "AuditLogsQuery.Read.All"
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

function Get-DelegatedGrant {
    param(
        [Parameter(Mandatory)]
        [string] $ClientServicePrincipalId,

        [Parameter(Mandatory)]
        [string] $ResourceServicePrincipalId
    )

    $filter = [Uri]::EscapeDataString(
        "clientId eq '$ClientServicePrincipalId' and " +
        "resourceId eq '$ResourceServicePrincipalId' and " +
        "consentType eq 'AllPrincipals'"
    )
    $response = az rest `
        --method get `
        --url "https://graph.microsoft.com/v1.0/oauth2PermissionGrants?`$filter=$filter" `
        --output json |
        ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) {
        throw "Delegated permission grants could not be inspected."
    }
    return $response.value | Select-Object -First 1
}

function Wait-ForDelegatedScope {
    param(
        [Parameter(Mandatory)]
        [string] $ClientServicePrincipalId,

        [Parameter(Mandatory)]
        [string] $ResourceServicePrincipalId,

        [Parameter(Mandatory)]
        [string] $RequiredScope
    )

    for ($attempt = 0; $attempt -lt $visibilityAttempts; $attempt++) {
        try {
            $grant = Get-DelegatedGrant `
                -ClientServicePrincipalId $ClientServicePrincipalId `
                -ResourceServicePrincipalId $ResourceServicePrincipalId
        }
        catch {
            if ($attempt -eq $visibilityAttempts - 1) {
                throw
            }
            Start-Sleep -Seconds ([Math]::Pow(2, $attempt))
            continue
        }
        if ($grant -and (($grant.scope -split " ") -contains $RequiredScope)) {
            return $grant
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

$graphServicePrincipal = az ad sp show --id $graphAppId --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $graphServicePrincipal) {
    throw "The Microsoft Graph service principal was not found in tenant '$TenantId'."
}

$scope = $graphServicePrincipal.oauth2PermissionScopes |
    Where-Object { $_.value -eq $scopeName -and $_.isEnabled } |
    Select-Object -First 1

if (-not $scope) {
    throw "Microsoft Graph does not expose the delegated scope '$scopeName' in this tenant."
}

$graphAccess = $application.requiredResourceAccess |
    Where-Object { $_.resourceAppId -eq $graphAppId } |
    Select-Object -First 1
$alreadyRequested = $graphAccess.resourceAccess |
    Where-Object { $_.id -eq $scope.id -and $_.type -eq "Scope" } |
    Select-Object -First 1

if ($alreadyRequested) {
    Write-Host "$scopeName is already requested by app registration $ClientId."
}
else {
    Write-Host "Adding delegated Microsoft Graph permission $scopeName..."
    az ad app permission add `
        --id $ClientId `
        --api $graphAppId `
        --api-permissions "$($scope.id)=Scope" `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to add delegated permission '$scopeName'."
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

$grant = Get-DelegatedGrant `
    -ClientServicePrincipalId $clientServicePrincipal.id `
    -ResourceServicePrincipalId $graphServicePrincipal.id
$verifiedGrant = $grant -and (($grant.scope -split " ") -contains $scopeName)

if (-not $verifiedGrant) {
    Write-Host "Granting tenant-wide consent for delegated scope $scopeName..."
    if ($grant) {
        $updatedScopes = @($grant.scope -split " ") + $scopeName |
            Where-Object { $_ } |
            Sort-Object -Unique
        $grantBody = @{
            scope = $updatedScopes -join " "
        } | ConvertTo-Json -Compress
        az rest `
            --method patch `
            --url "https://graph.microsoft.com/v1.0/oauth2PermissionGrants/$($grant.id)" `
            --headers "Content-Type=application/json" `
            --body $grantBody `
            --output none
    }
    else {
        $grantBody = @{
            clientId = $clientServicePrincipal.id
            consentType = "AllPrincipals"
            principalId = $null
            resourceId = $graphServicePrincipal.id
            scope = $scopeName
        } | ConvertTo-Json -Compress
        az rest `
            --method post `
            --url "https://graph.microsoft.com/v1.0/oauth2PermissionGrants" `
            --headers "Content-Type=application/json" `
            --body $grantBody `
            --output none
    }
    $grantExitCode = $LASTEXITCODE

    $verifiedGrant = Wait-ForDelegatedScope `
        -ClientServicePrincipalId $clientServicePrincipal.id `
        -ResourceServicePrincipalId $graphServicePrincipal.id `
        -RequiredScope $scopeName
    if (-not $verifiedGrant) {
        if ($grantExitCode -ne 0) {
            throw "Delegated consent failed. Run this script while signed in as a Global Administrator."
        }
        throw "Tenant-wide consent was not visible for delegated scope '$scopeName' after bounded polling."
    }
}

Write-Host ""
Write-Host "Verified:"
Write-Host "  App registration: $($application.displayName) ($ClientId)"
Write-Host "  Permission:       $scopeName"
Write-Host "  Permission type:  Delegated"
Write-Host "  Consent type:     AllPrincipals"
Write-Host ""
Write-Host "The signed-in audit user must also belong to the Purview Audit Reader or Audit Manager role group."
