[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $TenantId,

    [ValidateNotNullOrEmpty()]
    [string] $DisplayName = "Fabric API Interactive CLI",

    [switch] $CreateServicePrincipal,

    [ValidateNotNullOrEmpty()]
    [string] $ServicePrincipalDisplayName = "Fabric API Automation"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI (az) is required. Install it from https://aka.ms/installazurecliwindows."
}

Write-Host "Signing in to tenant $TenantId..."
az login --tenant $TenantId --allow-no-subscriptions --output none
if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI sign-in failed."
}

$signedInTenant = az account show --query tenantId --output tsv
if ($LASTEXITCODE -ne 0 -or $signedInTenant -ne $TenantId) {
    throw "Azure CLI is signed in to tenant '$signedInTenant', not '$TenantId'."
}

Write-Host "Creating single-tenant public-client app registration '$DisplayName'..."
$application = az ad app create `
    --display-name $DisplayName `
    --sign-in-audience AzureADMyOrg `
    --is-fallback-public-client true `
    --public-client-redirect-uris "http://localhost" `
    --output json |
    ConvertFrom-Json

if ($LASTEXITCODE -ne 0 -or -not $application.appId) {
    throw "Failed to create the interactive app registration."
}

$clientId = $application.appId

Write-Host "Creating its enterprise application..."
$servicePrincipal = az ad sp create --id $clientId --output json |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $servicePrincipal.id) {
    throw "App registration '$clientId' was created, but its enterprise application could not be created."
}

$permissionScript = Join-Path $PSScriptRoot "Grant-PurviewDelegatedPermission.ps1"
& $permissionScript -TenantId $TenantId -ClientId $clientId -SkipLogin

if ($CreateServicePrincipal) {
    Write-Host ""
    Write-Host "Creating confidential app registration '$ServicePrincipalDisplayName'..."
    $automationApplication = az ad app create `
        --display-name $ServicePrincipalDisplayName `
        --sign-in-audience AzureADMyOrg `
        --output json |
        ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $automationApplication.appId) {
        throw "Failed to create the service-principal app registration."
    }

    $automationClientId = $automationApplication.appId

    Write-Host "Creating its enterprise application (service principal)..."
    $automationServicePrincipal = az ad sp create `
        --id $automationClientId `
        --output json |
        ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $automationServicePrincipal.id) {
        throw "App registration '$automationClientId' was created, but its service principal could not be created."
    }

    $applicationPermissionScript = Join-Path `
        $PSScriptRoot `
        "Grant-PurviewApplicationPermission.ps1"
    & $applicationPermissionScript `
        -TenantId $TenantId `
        -ClientId $automationClientId `
        -SkipLogin
}

Write-Host ""
Write-Host "Interactive app setup is complete. Use these values in the current PowerShell session:"
Write-Host ""
Write-Host "`$env:FABRIC_AUTH_MODE = `"interactive`""
Write-Host "`$env:AZURE_TENANT_ID = `"$TenantId`""
Write-Host "`$env:AZURE_CLIENT_ID = `"$clientId`""
Write-Host "Remove-Item Env:AZURE_CLIENT_SECRET -ErrorAction SilentlyContinue"
Write-Host ""
Write-Host "Then run fabric-api and sign in with a user assigned to the Purview Audit Reader or Audit Manager role group."

if ($CreateServicePrincipal) {
    Write-Host ""
    Write-Host "Service-principal setup is complete:"
    Write-Host "  Tenant ID:  $TenantId"
    Write-Host "  Client ID:  $automationClientId"
    Write-Host "No credential was created or displayed. Configure a certificate, federated credential, managed identity, or separately managed client secret."
}
