# Microsoft Fabric, Power BI, and Purview Audit Python Examples

A production-oriented, typed Python client and CLI for documented Microsoft Fabric
REST APIs, separately governed Power BI REST APIs, and Microsoft Purview Audit Search
through Microsoft Graph v1.0.

This repository never guesses endpoint paths. Fabric workloads are discovered through
the stable Core Items API where supported. Platform resources use their documented
Fabric endpoints, while Power BI administration and Purview Audit use separate APIs,
permissions, and token audiences.

## Contents

- [What is included](#what-is-included)
- [Requirements](#requirements)
- [Install](#install)
- [Authentication](#authentication)
- [Quick start](#quick-start)
- [CLI command reference](#cli-command-reference)
- [Audit and governance workflows](#audit-and-governance-workflows)
- [Workspace inventory exports](#workspace-inventory-exports)
- [API boundaries and prerequisites](#api-boundaries-and-prerequisites)
- [Coverage and limitations](#coverage-and-limitations)
- [Security and data handling](#security-and-data-handling)
- [Troubleshooting](#troubleshooting)
- [Official documentation](#official-documentation)
- [Development](#development)

## What is included

- Microsoft Entra authentication with `DefaultAzureCredential`, interactive browser
  authentication, or service-principal environment variables.
- Separate access tokens for Fabric, Power BI, and Microsoft Graph.
- A typed synchronous client with configurable base URLs and request timeouts.
- Pagination through `continuationUri`, `continuationToken`, and Graph
  `@odata.nextLink`.
- Retry and backoff for `429`, `500`, `502`, `503`, and `504`, including
  `Retry-After`.
- HTTPS and trusted-host validation before bearer tokens are sent to absolute URLs.
- Explicit exceptions containing status, request ID, and service error details.
- Generic Fabric item listing and retrieval for new or less common item types.
- CLI shortcuts for common Fabric items and platform resources.
- Power BI gateway, data source, and tenant activity-event examples.
- Purview Audit query creation, polling, pagination, raw exports, and Copilot/Power BI
  governance summaries.
- Unit tests using mocked HTTP and credentials; no live tenant is required.

## Requirements

- Python 3.10 or newer.
- A Microsoft Entra identity with access appropriate to each API operation.
- Azure CLI only when using the included app-registration setup scripts.
- Tenant administrator assistance for admin consent, Fabric/Power BI tenant settings,
  or Purview role-group assignments when required.

## Install

Open PowerShell in the cloned repository folder:

```powershell
cd C:\path\to\FabricAPI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

`pip install -e .` registers the `fabric-api` command in the active virtual
environment. The command works from any folder while that environment remains
active.

In a new PowerShell window, reactivate the environment:

```powershell
cd C:\path\to\FabricAPI
.\.venv\Scripts\Activate.ps1
```

Alternatively, invoke the executable directly:

```powershell
C:\path\to\FabricAPI\.venv\Scripts\fabric-api.exe workspaces
```

Copy values from `.env.example` into your shell or preferred secret store. The CLI
does not automatically load `.env` files.

## Authentication

Choose an authentication mode based on who should perform the operation:

| Mode | Identity used | Recommended use |
|---|---|---|
| `default` | Azure CLI, developer tool, managed identity, or another credential in `DefaultAzureCredential` | Local development and Azure-hosted workloads |
| `interactive` | Signed-in Entra user through a public-client app registration | Delegated user access and local Purview testing |
| `client_secret` | Service principal | Non-interactive automation |

For Purview Audit extraction, the two supported authorization paths are:

| Path | App permission | Human/resource authorization | CLI mode |
|---|---|---|---|
| Entra user | Delegated Graph `AuditLogsQuery.Read.All` with admin consent | Signed-in user is in Purview **Audit Reader** or **Audit Manager** | `interactive` |
| Service principal | Application Graph `AuditLogsQuery.Read.All` with admin consent | Service principal and tenant must satisfy the API's app-only requirements | `client_secret` |

> [!IMPORTANT]
> Do not mix the rows. A delegated permission does not authorize an app-only token,
> and an application permission does not authorize an interactive user token.
> Separate app registrations for interactive users and automation are recommended
> for clearer ownership and least privilege.

### Default credential chain

```powershell
$env:FABRIC_AUTH_MODE = "default"
fabric-api workspaces
```

### Interactive Entra user

Interactive OAuth access combines two identities:

- the **app registration**, which requests delegated API permissions; and
- the **signed-in Entra user**, whose roles and resource access are enforced.

Delegated permissions are not assigned directly to a user object.

#### Create interactive and service-principal apps

Run the included setup script as a Global Administrator:

```powershell
.\scripts\New-FabricApiInteractiveApp.ps1 `
  -TenantId "<tenant-id>" `
  -DisplayName "Fabric API Interactive CLI"
```

To create both a delegated interactive app and a separate app-only service principal:

```powershell
.\scripts\New-FabricApiInteractiveApp.ps1 `
  -TenantId "<tenant-id>" `
  -DisplayName "Fabric API Interactive CLI" `
  -CreateServicePrincipal `
  -ServicePrincipalDisplayName "Fabric API Automation" `
  -CreateClientSecret
```

> [!IMPORTANT]
> Run the script with `.\` or PowerShell's call operator `&`. Do not prefix it with
> `cd`; `cd` changes directories and cannot accept `-TenantId`.

The script:

1. Creates a single-tenant public-client app registration.
2. Configures the `http://localhost` redirect URI.
3. Creates the associated enterprise application.
4. Adds delegated Microsoft Graph `AuditLogsQuery.Read.All`.
5. Grants and verifies tenant-wide admin consent.
6. Optionally creates a separate confidential app and service principal.
7. Adds application Microsoft Graph `AuditLogsQuery.Read.All` to that automation
   identity and verifies admin consent.
8. Optionally creates a one-year client secret and prints both authentication
   configurations.

The interactive public client never receives a secret. `-CreateClientSecret` applies
only to the separate automation app and requires `-CreateServicePrincipal`.

> [!CAUTION]
> A generated client secret is displayed once. Store it immediately in an approved
> secret store, do not paste it into source files, and clear terminal transcripts or
> logs that may have captured it. Omit `-CreateClientSecret` when using a certificate
> or federated credential instead.

Then configure the CLI with the values printed by the script:

```powershell
$env:FABRIC_AUTH_MODE = "interactive"
$env:AZURE_TENANT_ID = "<tenant-id>"
$env:AZURE_CLIENT_ID = "<interactive-app-registration-client-id>"
Remove-Item Env:AZURE_CLIENT_SECRET -ErrorAction SilentlyContinue
```

After assigning the signed-in user to the Purview role group, verify delegated
extraction:

```powershell
fabric-api copilot-usage `
  --start 2026-09-07T00:00:00Z `
  --end 2026-09-08T00:00:00Z `
  --output .\entra-copilot-usage
```

The browser sign-in must use the same Entra user that was assigned to **Audit
Reader** or **Audit Manager**.

#### Configure an existing interactive app

To add the delegated Purview permission to an existing app registration:

```powershell
.\scripts\Grant-PurviewDelegatedPermission.ps1 `
  -TenantId "<tenant-id>" `
  -ClientId "<interactive-app-registration-client-id>"
```

The script resolves the current Microsoft Graph scope ID rather than hard-coding it,
adds `AuditLogsQuery.Read.All` as a delegated `Scope`, grants tenant-wide admin
consent, and verifies the resulting OAuth permission grant.

#### Assign the Purview user role

For Purview Audit Search, the signed-in user must also be assigned to **Audit
Reader** or **Audit Manager**:

1. Sign in to [Microsoft Purview](https://purview.microsoft.com) with an account that
   has the Purview **Role Management** role.
2. Go to **Settings** > **Roles and scopes** > **Role groups**.
3. Select **Audit Reader** for read/export access, or **Audit Manager** when audit
   management access is also required.
4. Select **Edit** > **Choose users** or **Choose groups**.
5. Add the user, then select **Next** > **Save** > **Done**.

> [!NOTE]
> `Add-RoleGroupMember -Identity "Audit Reader"` can return
> `ManagementObjectNotFoundException` because this Purview portal role group might
> not be exposed as an Exchange or Security and Compliance PowerShell `RoleGroup`.
> Use the Purview portal workflow above.

### Service principal

The combined setup command above can create a separate service principal, grant
application `AuditLogsQuery.Read.All`, and optionally create a one-year client
secret. To grant the application permission to an existing service-principal app:

```powershell
.\scripts\Grant-PurviewApplicationPermission.ps1 `
  -TenantId "<tenant-id>" `
  -ClientId "<service-principal-application-id>"
```

Store any credential outside source control, then configure the CLI:

```powershell
$env:FABRIC_AUTH_MODE = "client_secret"
$env:AZURE_TENANT_ID = "<tenant-id>"
$env:AZURE_CLIENT_ID = "<application-id>"
$env:AZURE_CLIENT_SECRET = Read-Host "Client secret" -MaskInput
```

For Purview Audit Search, grant the service principal the Microsoft Graph
**application** permission `AuditLogsQuery.Read.All` and tenant admin consent. The
permission must show **Type: Application** and **Status: Granted for
&lt;tenant&gt;**.

Azure subscription RBAC roles such as Reader or Contributor do not grant Microsoft
365 unified audit-log access. Delegated `AuditLog.Read.All` is also a different
permission and does not replace `AuditLogsQuery.Read.All`.

Verify app-only extraction in the same PowerShell session:

```powershell
fabric-api copilot-usage `
  --start 2026-09-07T00:00:00Z `
  --end 2026-09-08T00:00:00Z `
  --output .\spn-copilot-usage
```

If an error names `User:<UPN>`, the CLI did not use the service principal. Confirm
that `FABRIC_AUTH_MODE=client_secret` and all three Azure credential variables are
set in the terminal that runs `fabric-api`.

### Token audiences

| API | Scope |
|---|---|
| Microsoft Fabric | `https://api.fabric.microsoft.com/.default` |
| Power BI | `https://analysis.windows.net/powerbi/api/.default` |
| Microsoft Graph | `https://graph.microsoft.com/.default` |

## Quick start

List the Fabric workspaces available to the current identity:

```powershell
fabric-api workspaces
```

The same operation is available as a runnable Python example:

```powershell
python .\examples\list_workspaces.py
```

Select a workspace and list all its items:

```powershell
$workspace = fabric-api workspaces | ConvertFrom-Json | Select-Object -First 1
fabric-api items $workspace.id
```

Filter by an official Fabric item type:

```powershell
fabric-api items $workspace.id --type Lakehouse
```

Get one item:

```powershell
fabric-api item <workspace-id> <item-id>
```

## CLI command reference

Values in angle brackets are placeholders. Do not type the angle brackets.

### Fabric Core APIs

```powershell
# Workspaces and generic items
fabric-api workspaces
fabric-api items <workspace-id>
fabric-api items <workspace-id> --type <official-item-type>
fabric-api item <workspace-id> <item-id>

# Convenience commands backed by the generic Items API
fabric-api lakehouses <workspace-id>
fabric-api warehouses <workspace-id>
fabric-api semantic-models <workspace-id>
fabric-api dataflows <workspace-id>
fabric-api eventhouses <workspace-id>
fabric-api eventstreams <workspace-id>
fabric-api kql-databases <workspace-id>
fabric-api kql-querysets <workspace-id>
fabric-api environments <workspace-id>
fabric-api dashboards <workspace-id>

# Platform resources
fabric-api capacities
fabric-api deployment-pipelines
fabric-api domains

# Data Factory pipeline activity runs
fabric-api activity-runs <workspace-id> <job-instance-id> `
  --updated-after 2026-09-14T00:00:00Z `
  --updated-before 2026-09-15T00:00:00Z
```

### Power BI REST and Admin APIs

```powershell
fabric-api gateways
fabric-api datasources <workspace-id> <semantic-model-id>

fabric-api activity-events `
  --start 2026-09-14T00:00:00Z `
  --end 2026-09-14T23:59:59Z
```

### Microsoft Graph Purview Audit Search

```powershell
fabric-api purview-audit export `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\purview-audit

fabric-api copilot-usage `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\copilot-usage

fabric-api powerbi-usage `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\powerbi-usage
```

All commands print JSON unless the command writes a documented export directory.

## Audit and governance workflows

Power BI/Fabric Activity Events and Purview Audit provide related but different
records:

| Surface | Best suited for |
|---|---|
| Power BI Activity Events | Operational Fabric and Power BI tenant activity in daily windows |
| Purview Audit Search | Cross-service governance and compliance metadata |
| DSPM for AI / Activity Explorer | Portal insights, policies, and risky or sensitive interaction investigation |
| Capacity Metrics app | Capacity utilization, compute trends, and chargeback analysis |
| eDiscovery | Preservation, search, review, and export of collected Copilot content |

### Fabric Copilot activity events

Retrieve all five currently documented Fabric Copilot session operations:

```powershell
fabric-api activity-events `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-15T23:59:59Z `
  --fabric-copilot |
  Set-Content -Encoding utf8 .\fabric-copilot-activity.json
```

The preset requests these exact `Activity` values and combines the results:

- `FabricCopilotSessionCreated`
- `FabricCopilotSessionDeleted`
- `FabricCopilotSessionMessageSent`
- `FabricCopilotSessionUpdated`
- `FabricCopilotSessionStateUpdated`

Retrieve only message events, optionally for one user:

```powershell
fabric-api activity-events `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-15T23:59:59Z `
  --activity FabricCopilotSessionMessageSent `
  --user analyst@contoso.com
```

The API supports server-side equality filters for `Activity`, `UserId`, or both.
Counting `FabricCopilotSessionMessageSent` by `UserId` provides observed active-user
and interaction-volume reporting. It does not measure productivity impact.

### Purview Copilot and Power BI usage

Create a structured Purview Audit query with explicit filters:

```powershell
fabric-api purview-audit export `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\purview-audit `
  --record-type powerBIAudit `
  --service PowerBI `
  --operation CopilotInteraction
```

Repeat `--record-type`, `--operation`, `--user`, `--ip-address`, or `--object-id`
to supply multiple values. `--keyword` maps to the API's non-indexed-property search;
it is not a substitute for structured filters.

Focused reports apply their primary filters automatically:

```powershell
fabric-api copilot-usage `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-16T00:00:00Z `
  --output .\copilot-usage

fabric-api powerbi-usage `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-16T00:00:00Z `
  --output .\powerbi-usage
```

Purview results can include `AppIdentity`, `AppHost`, message IDs and counts,
contexts, accessed resources, and sensitivity-label identifiers. They do not
necessarily include prompt or response text.

Equivalent Python examples:

```powershell
python .\examples\export_purview_audit.py `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\purview-audit `
  --operation CopilotInteraction

python .\examples\analyze_purview_usage.py copilot `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\copilot-usage
```

### Fabric Data Agent audit coverage

The `--fabric-copilot` Activity Events preset covers the five documented Fabric
Copilot session operations. It does not claim general Fabric Data Agent coverage.
Microsoft currently documents Data Agent interaction auditing through Purview.

Fabric Data Agent auditing is in preview. When the prerequisites are enabled,
Purview creates `CopilotInteraction` records for Data Agent requests and responses:

```powershell
fabric-api copilot-usage `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-16T00:00:00Z `
  --output .\data-agent-audit
```

Create a Data Agent-focused CSV using the documented Purview application label:

```powershell
Import-Csv .\data-agent-audit\audit-records.csv |
  Where-Object { $_.auditData -match "Fabric-Data Agent" } |
  Export-Csv .\data-agent-audit\fabric-data-agent-interactions.csv -NoTypeInformation
```

Data Agent logging requires:

- Microsoft Purview Audit;
- the **DSPM for AI - Capture interactions for Copilot experiences** policy; and
- the Fabric tenant setting **Allow Microsoft Purview to secure AI interactions**.

Prompt and response content availability remains subject to Purview roles, policy
configuration, licensing, and preview behavior.

### Export contents

Purview export directories contain:

- `audit-records.json` with query state, collection errors, and all original records;
- `audit-records.jsonl` with one unchanged original record per line;
- `audit-records.csv` with flattened fields and serialized full audit data;
- daily active-user and interaction counts for Copilot reports;
- counts by user, workload, operation, activity, object, service, and `AppHost`;
- prompt/response message counts from `CopilotEventData.Messages/isPrompt`;
- context, accessed-resource, and sensitivity-label summaries; and
- `manifest.json` with status, errors, record count, and completion state.

The exporter retains partial records if a later page fails. A failed, cancelled,
timed-out, or partially collected query is marked `complete: false`; the command
writes available artifacts and exits nonzero.

## Workspace inventory exports

Export every accessible workspace and every item in each workspace:

```powershell
python .\examples\export_workspace_inventory.py
```

The output contains:

- the complete Workspaces API payload;
- the complete Items API payload for every readable workspace;
- flattened workspace, capacity, and item rows; and
- explicit per-workspace errors.

Limit the export to selected workspaces:

```powershell
python .\examples\export_workspace_inventory.py `
  --workspace-id <workspace-id-1> `
  --workspace-id <workspace-id-2> `
  --output selected-workspaces.json
```

Include capacities, domains, and deployment pipelines only when the identity has
their additional permissions:

```powershell
python .\examples\export_workspace_inventory.py --include-platform-resources
```

Include Power BI Admin activity events in the same file:

```powershell
python .\examples\export_workspace_inventory.py `
  --activity-start 2026-09-14T00:00:00Z `
  --activity-end 2026-09-14T23:59:59Z `
  --output workspace-items-and-activities.json
```

The activity window must be within one UTC day and within the preceding 28 days.
When `--workspace-id` is supplied, only matching `WorkspaceId` events are retained.
If the Power BI token or admin API call fails, the workspace inventory is still
written and the failure is included in `activityEvents.error` and the top-level
`errors` collection.

## API boundaries and prerequisites

### Microsoft Fabric REST APIs

| Capability | Official call shape used | Typical requirement |
|---|---|---|
| Workspaces | `GET https://api.fabric.microsoft.com/v1/workspaces` | `Workspace.Read.All` or `Workspace.ReadWrite.All` |
| Workspace items | `GET .../v1/workspaces/{workspaceId}/items?type={type}` | Viewer workspace role and workspace read scope |
| Item details | `GET .../v1/workspaces/{workspaceId}/items/{itemId}` | Viewer workspace role and item read scope |
| Capacities | `GET .../v1/capacities` | Capacity visibility and operation-specific permissions |
| Deployment pipelines | `GET .../v1/deploymentPipelines` | Access to the returned pipelines |
| Domains | `GET .../v1/domains` | `Domain.Read.All`; returns tenant domains |
| Pipeline activity runs | `POST .../v1/workspaces/{workspaceId}/datapipelines/pipelineruns/{jobInstanceId}/queryactivityruns` | Pipeline access and applicable workspace/item scopes |

Service principals and managed identities are supported only where the operation's
**Microsoft Entra supported identities** table says so. Tenant administrators may
also need to enable the Fabric setting that allows service principals to use Fabric
APIs and scope it to an appropriate security group.

Convenience item commands are aliases for the generic Items API, not fabricated
workload endpoints. If a tenant does not recognize a type, use
`fabric-api items <workspace-id>` to inspect the types returned by that tenant.

### Power BI REST and Admin APIs

| Capability | Official call shape used | Important limitation |
|---|---|---|
| Gateways | `GET https://api.powerbi.com/v1.0/myorg/gateways` | Caller must be a gateway administrator |
| Dataset data sources | `GET .../v1.0/myorg/groups/{groupId}/datasets/{datasetId}/datasources` | Workspace and semantic-model permissions apply |
| Activity events | `GET .../v1.0/myorg/admin/activityevents` | Fabric/Power BI administrator or allowed service principal; one UTC day per request |

Delegated activity-event access requires Power BI `Tenant.Read.All` or
`Tenant.ReadWrite.All`. For service-principal access, enable the tenant setting for
read-only admin APIs and place the principal in the allowed security group. Do not
add admin-consent-required Power BI application permissions unless an operation's
documentation explicitly requires them.

There is no Fabric `/activities` collection in this repository. Power BI Activity
Events are tenant audit events. Data Factory activity runs are separately queried
for a known pipeline job instance.

### Microsoft Purview Audit Search through Graph

The client uses these Microsoft Graph v1.0 endpoints:

| Operation | Endpoint |
|---|---|
| Create query | `POST https://graph.microsoft.com/v1.0/security/auditLog/queries` |
| Poll status | `GET https://graph.microsoft.com/v1.0/security/auditLog/queries/{id}` |
| List records | `GET https://graph.microsoft.com/v1.0/security/auditLog/queries/{id}/records` |

For broad Microsoft 365 audit workloads:

- **Interactive:** delegated Graph `AuditLogsQuery.Read.All`, tenant admin consent,
  and Purview **Audit Reader** or **Audit Manager** for the signed-in user.
- **Service principal:** application Graph `AuditLogsQuery.Read.All` and tenant admin
  consent.

The client supports the v1.0 create contract's `filterStartDateTime`,
`filterEndDateTime`, `recordTypeFilters`, `serviceFilter`, `operationFilters`,
`userPrincipalNameFilters`, `ipAddressFilters`, `objectIdFilters`, and
`keywordFilter`. Timestamps must include an offset, and the end must be later than
the start. The client does not impose an undocumented maximum query span.

### Copilot in Fabric prerequisites

- Enable **Allow Microsoft Purview to secure AI interactions** in the Fabric admin
  portal. Microsoft documents this setting as enabled by default.
- Confirm applicable Purview availability, licensing, and pay-as-you-go requirements.
- Use a DSPM for AI capture policy when prompt/response collection is required.
- Viewing content in Activity Explorer requires applicable Content Explorer Content
  Viewer permissions.
- Use eDiscovery for preservation, search, review, and export of collected Copilot
  content. The documented item-class pattern is
  `IPM.SkypeTeams.Message.Copilot.Fabric.*`.

DSPM for AI is primarily a portal, report, recommendation, policy, and Activity
Explorer experience. This repository does not invent a DSPM bulk-export API.

For scheduled or bulk ingestion, consider the separately documented Office 365
Management Activity API. It uses the `ActivityFeed.Read` application permission,
subscriptions, and downloadable content blobs. Do not confuse its feed model with
Graph Audit Search.

## Coverage and limitations

- Lakehouses, warehouses, semantic models, dataflows, eventhouses, eventstreams, KQL
  databases, KQL querysets, environments, and dashboards are demonstrated through
  the Fabric Items API.
- `items --type` supports additional official item types without requiring a new CLI
  command.
- Datamarts are not demonstrated because they are not consistently supported by the
  Fabric Items API across tenants.
- The Capacities API exposes capacity metadata, not detailed utilization metrics.
  Use the Fabric Capacity Metrics app or other documented monitoring experiences.
- Data sources and gateways are Power BI resources, not Fabric Core item endpoints.
- Some item types have workload-specific create, update, definition, or job APIs.
  This repository focuses on safe discovery and retrieval.
- Activity and audit counts represent observed events; they do not by themselves
  establish productivity impact.

## Security and data handling

- No credentials or tenant-specific identifiers are committed.
- Authenticated continuation URLs are restricted to configured HTTPS API hosts.
- Power BI regional continuation hosts under `analysis.windows.net` are allowed;
  arbitrary hosts, user-information URLs, and unexpected ports are rejected before
  token acquisition or forwarding.
- JSON and JSONL exports preserve original records and should be treated as sensitive
  governance data.
- CSV exports prefix formula-like strings with a literal apostrophe to prevent
  spreadsheet formula execution.
- Common audit-output directories are ignored by Git. Protect custom output paths
  and never commit audit exports.
- Base URL overrides are intended for testing or sovereign-cloud routing and must be
  absolute HTTPS URLs:

```powershell
$env:FABRIC_API_BASE_URL = "https://api.fabric.microsoft.com"
$env:POWER_BI_API_BASE_URL = "https://api.powerbi.com"
$env:PURVIEW_GRAPH_BASE_URL = "https://graph.microsoft.com"
```

## Troubleshooting

### `Set-Location` rejects `-TenantId`

The script was invoked with `cd`. Run it directly:

```powershell
& ".\scripts\New-FabricApiInteractiveApp.ps1" `
  -TenantId "<tenant-id>" `
  -DisplayName "Fabric API Interactive CLI"
```

### Purview returns `403 ... User:<UPN> dont have any permissions`

The request used delegated authentication. Verify all of the following:

1. `FABRIC_AUTH_MODE` is `interactive`.
2. `AZURE_CLIENT_ID` identifies the intended public-client app registration.
3. That app has **delegated** `AuditLogsQuery.Read.All`, not only
   `AuditLog.Read.All` or an application permission.
4. Tenant admin consent is granted.
5. The named user belongs to Purview **Audit Reader** or **Audit Manager**.
6. The user signs in again after permission changes have propagated.

If the request should use the service principal instead, set
`FABRIC_AUTH_MODE=client_secret` in the same terminal and provide all three Azure
credential environment variables.

### Power BI activity events return `400 Bad Request`

Use ISO 8601 UTC timestamps with `Z`, keep the start and end within the same UTC day,
and request a date within the API's 28-day retention window:

```powershell
fabric-api activity-events `
  --start 2026-09-14T00:00:00Z `
  --end 2026-09-14T23:59:59Z
```

Quote timestamp values if shell parsing or copied formatting alters them.

### `Add-RoleGroupMember` cannot find `Audit Reader`

Assign the role through the Microsoft Purview portal under **Settings** > **Roles
and scopes** > **Role groups**. The Purview role group might not be exposed through
the connected Exchange PowerShell endpoint.

## Official documentation

- [Fabric REST API overview](https://learn.microsoft.com/rest/api/fabric/articles/)
- [Fabric API identity support](https://learn.microsoft.com/rest/api/fabric/articles/identity-support)
- [Fabric API pagination](https://learn.microsoft.com/rest/api/fabric/articles/pagination)
- [Workspaces - List Workspaces](https://learn.microsoft.com/rest/api/fabric/core/workspaces/list-workspaces)
- [Items - List Items](https://learn.microsoft.com/rest/api/fabric/core/items/list-items)
- [Items - Get Item](https://learn.microsoft.com/rest/api/fabric/core/items/get-item)
- [Capacities - List Capacities](https://learn.microsoft.com/rest/api/fabric/core/capacities/list-capacities)
- [Deployment Pipelines - List Deployment Pipelines](https://learn.microsoft.com/rest/api/fabric/core/deployment-pipelines/list-deployment-pipelines)
- [Domains - List Domains](https://learn.microsoft.com/rest/api/fabric/core/domains/list-domains)
- [Fabric Data Factory pipeline REST capabilities](https://learn.microsoft.com/fabric/data-factory/pipeline-rest-api-capabilities)
- [Power BI Activity Events - Get Activity Events](https://learn.microsoft.com/rest/api/power-bi/admin/get-activity-events)
- [Power BI Gateways - Get Gateways](https://learn.microsoft.com/rest/api/power-bi/gateways/get-gateways)
- [Power BI Datasets - Get Datasources In Group](https://learn.microsoft.com/rest/api/power-bi/datasets/get-datasources-in-group)
- [Graph v1.0 - Create auditLogQuery](https://learn.microsoft.com/graph/api/security-auditcoreroot-post-auditlogqueries?view=graph-rest-1.0)
- [Graph v1.0 - List auditLogRecords](https://learn.microsoft.com/graph/api/security-auditlogquery-list-records?view=graph-rest-1.0)
- [CopilotInteraction audit schema](https://learn.microsoft.com/office/office-365-management-api/copilot-schema)
- [Use Microsoft Purview with Copilot in Fabric](https://learn.microsoft.com/purview/ai-copilot-fabric)
- [Office 365 Management Activity API reference](https://learn.microsoft.com/office/office-365-management-api/office-365-management-activity-api-reference)

## Development

Install development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Run the repository checks:

```powershell
ruff format --check .
ruff check .
mypy src
pytest
```
