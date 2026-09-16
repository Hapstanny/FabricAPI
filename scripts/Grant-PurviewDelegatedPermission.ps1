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

$clientServicePrincipal = az ad sp show --id $ClientId --output json 2>$null |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $clientServicePrincipal) {
    Write-Host "Creating the enterprise application for app registration $ClientId..."
    $clientServicePrincipal = az ad sp create --id $ClientId --output json |
        ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $clientServicePrincipal) {
        throw "Failed to create the enterprise application for '$ClientId'."
    }
}

Write-Host "Granting tenant-wide admin consent..."
az ad app permission admin-consent --id $ClientId --output none
if ($LASTEXITCODE -ne 0) {
    throw "Admin consent failed. Run this script while signed in as a Global Administrator."
}

$grants = az ad app permission list-grants --id $ClientId --output json |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Permission was configured, but its consent grant could not be verified."
}

$verifiedGrant = $grants |
    Where-Object {
        $_.resourceId -eq $graphServicePrincipal.id -and
        $_.consentType -eq "AllPrincipals" -and
        (($_.scope -split " ") -contains $scopeName)
    } |
    Select-Object -First 1

if (-not $verifiedGrant) {
    throw "Admin consent was not found for delegated scope '$scopeName'."
}

Write-Host ""
Write-Host "Verified:"
Write-Host "  App registration: $($application.displayName) ($ClientId)"
Write-Host "  Permission:       $scopeName"
Write-Host "  Permission type:  Delegated"
Write-Host "  Consent type:     AllPrincipals"
Write-Host ""
Write-Host "The signed-in audit user must also belong to the Purview Audit Reader or Audit Manager role group."
