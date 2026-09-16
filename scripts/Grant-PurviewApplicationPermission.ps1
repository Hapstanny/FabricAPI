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

$assignmentResponse = az rest `
    --method get `
    --url "https://graph.microsoft.com/v1.0/servicePrincipals/$($clientServicePrincipal.id)/appRoleAssignments" `
    --output json |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Permission was configured, but its app-role assignment could not be verified."
}

$verifiedAssignment = $assignmentResponse.value |
    Where-Object {
        $_.resourceId -eq $graphServicePrincipal.id -and
        $_.appRoleId -eq $appRole.id
    } |
    Select-Object -First 1

if (-not $verifiedAssignment) {
    throw "Admin consent was not found for application permission '$permissionName'."
}

Write-Host ""
Write-Host "Verified:"
Write-Host "  App registration: $($application.displayName) ($ClientId)"
Write-Host "  Permission:       $permissionName"
Write-Host "  Permission type:  Application"
Write-Host "  Admin consent:    Granted"
