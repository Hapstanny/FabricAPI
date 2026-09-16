# Microsoft Fabric, Power BI, and Purview Audit Python examples

A production-oriented, typed Python client and CLI for documented Microsoft Fabric REST
APIs, the separately governed Power BI REST APIs, and Microsoft Purview Audit Search
through Microsoft Graph v1.0.

The examples intentionally do not guess endpoint paths. Most Fabric workloads are accessed through the stable Core **Items** API (`/v1/workspaces/{workspaceId}/items`) with an official item type filter. Platform resources such as workspaces, capacities, deployment pipelines, and domains use their documented Fabric endpoints. Power BI gateways, dataset data sources, and tenant activity events use `api.powerbi.com` and a separate access token.

## Features

- Microsoft Entra authentication with `DefaultAzureCredential`, interactive browser authentication, or service-principal environment variables.
- Separate Fabric, Power BI, and Microsoft Graph token audiences.
- Typed reusable synchronous client with configurable base URLs and timeouts.
- Pagination through `continuationUri`, `continuationToken`, or Graph `@odata.nextLink`.
- HTTPS and trusted-host validation before bearer tokens are sent to absolute URLs.
- Retry/backoff for `429`, `500`, `502`, `503`, and `504`, including `Retry-After`.
- Explicit exceptions containing status, request ID, and service error details.
- Purview Audit query creation, status polling, record pagination, raw exports, and
  Copilot/Power BI governance summaries.
- Generic item listing/getting for new or less common Fabric item types.
- CLI shortcuts for common Fabric item types and Power BI administration examples.
- Unit tests with mocked HTTP and credentials; no tenant is required.

## Install

Python 3.10 or newer is required.

Open PowerShell, change to the cloned repository folder (the folder containing
`pyproject.toml`), and run the one-time setup:

```powershell
cd C:\path\to\FabricAPI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

`pip install -e .` registers the `fabric-api` command in the active virtual
environment. After installation, `fabric-api` works from any folder while that
environment is active; you do not have to remain in the repository folder.

In each new PowerShell window, either return to the repository and reactivate the
environment:

```powershell
cd C:\path\to\FabricAPI
.\.venv\Scripts\Activate.ps1
```

or call the executable by its full path:

```powershell
C:\path\to\FabricAPI\.venv\Scripts\fabric-api.exe workspaces
```

Copy `.env.example` values into your shell or preferred secret store. The CLI
does not load `.env` files automatically.

## Quick start

With an existing Azure CLI, Visual Studio Code, or other `DefaultAzureCredential`
sign-in, the smallest read-only example is:

```powershell
$env:FABRIC_AUTH_MODE = "default"
fabric-api workspaces
```

The same call is available as a directly runnable Python example:

```powershell
python .\examples\list_workspaces.py
```

It lists only workspaces the signed-in identity can access and does not modify tenant
resources.

### Export Purview audit and Copilot governance data

> **Required permissions:** An interactive Entra user must be a member of the
> Microsoft Purview **Audit Reader** or **Audit Manager** role group and must
> authenticate through an app registration with delegated Microsoft Graph
> `AuditLogsQuery.Read.All` permission and tenant admin consent. An app-only service
> principal requires the Microsoft Graph **application** permission
> `AuditLogsQuery.Read.All` with tenant admin consent.

Create a structured Microsoft Graph v1.0 Purview Audit query and write the complete raw
records plus flattened CSV summaries:

```powershell
fabric-api purview-audit export `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\purview-audit `
  --record-type powerBIAudit `
  --service PowerBI `
  --operation CopilotInteraction
```

Every supplied API filter is sent as a documented structured query property. Repeat
`--record-type`, `--operation`, `--user`, `--ip-address`, or `--object-id` to supply
multiple values. `--keyword` is available for the API's non-indexed-property search,
but it is not used as a substitute for structured filters.

Focused commands apply the exact primary API filters automatically:

```powershell
fabric-api copilot-usage `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\copilot-usage

fabric-api powerbi-usage `
  --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z `
  --output .\powerbi-usage
```

As described in the Copilot usage governance guidance, Copilot usage can be derived
from both the Power BI/Fabric Activity Events feed and Microsoft Purview Audit. They
provide related but different records.

Use the Power BI Admin Activity Events API to retrieve all five currently documented
Fabric Copilot session activities in one command:

```powershell
fabric-api activity-events `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-15T23:59:59Z `
  --fabric-copilot |
  Set-Content -Encoding utf8 .\fabric-copilot-activity.json
```

The preset makes one API request for each exact documented `Activity` value and
combines the returned events:

- `FabricCopilotSessionCreated`
- `FabricCopilotSessionDeleted`
- `FabricCopilotSessionMessageSent`
- `FabricCopilotSessionUpdated`
- `FabricCopilotSessionStateUpdated`

To retrieve only messages, or only one user's messages:

```powershell
fabric-api activity-events `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-15T23:59:59Z `
  --activity FabricCopilotSessionMessageSent

fabric-api activity-events `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-15T23:59:59Z `
  --activity FabricCopilotSessionMessageSent `
  --user analyst@contoso.com
```

The Activity Events API supports server-side equality filters for `Activity`,
`UserId`, or both. Counting `FabricCopilotSessionMessageSent` by `UserId` provides
active-user and interaction-volume reporting from Fabric activity logs. The command
returns the complete event objects supplied by the API; available properties can
vary by activity.

Use Purview Audit separately for the cross-service `CopilotInteraction` records and
governance metadata:

```powershell
fabric-api copilot-usage `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-16T00:00:00Z `
  --output .\copilot-usage
```

Purview results can include `AppIdentity`
`Copilot.Fabric.CopilotforPowerBI`, `AppHost`, message IDs/counts, contexts,
accessed resources, and sensitivity-label identifiers. They don't necessarily
contain prompt or response text. Use Activity Events for Fabric operational usage
tracking and Purview for cross-service compliance and governance analysis.

#### Fabric Data Agent audit coverage

The `--fabric-copilot` Activity Events preset covers the five documented Fabric
Copilot session operations listed above. It does **not** claim Fabric Data Agent
coverage because Microsoft currently documents Data Agent interaction auditing
through Microsoft Purview rather than as a corresponding set of Power BI Admin
Activity Events operations.

Fabric Data Agent audit logging is currently in preview. When the prerequisites are
enabled, Purview creates `CopilotInteraction` audit records for Data Agent requests
and responses. Collect those records with:

```powershell
fabric-api copilot-usage `
  --start 2026-09-15T00:00:00Z `
  --end 2026-09-16T00:00:00Z `
  --output .\data-agent-audit
```

The command collects all Copilot interaction records. To create a Data Agent-focused
CSV using the documented Purview application label:

```powershell
Import-Csv .\data-agent-audit\audit-records.csv |
  Where-Object { $_.auditData -match "Fabric-Data Agent" } |
  Export-Csv .\data-agent-audit\fabric-data-agent-interactions.csv -NoTypeInformation
```

Data Agent logging requires Purview Audit, the **DSPM for AI - Capture interactions
for Copilot experiences** policy, and the Fabric tenant setting **Allow Microsoft
Purview to secure AI interactions**. The raw export preserves every property
returned by Microsoft Graph. Access to displayed prompt and response content remains
subject to Purview roles, policy configuration, licensing, and the preview service's
API behavior.

The equivalent directly runnable examples are:

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

Each output directory contains:

- `audit-records.json` with query state, collection errors, and every original record;
- `audit-records.jsonl` with one unchanged original record per line;
- `audit-records.csv` with selected flattened fields, `AppIdentity`/`AppHost`, and
  serialized full audit data;
- Copilot daily active-user and interaction counts;
- counts by user, service/workload, operation, and `CopilotEventData.AppHost`;
- prompt/response **message counts** from `CopilotEventData.Messages/isPrompt`;
- context, accessed-resource, and sensitivity-label identifier summaries;
- Power BI/Fabric day, operation, activity, user, object, and service trends; and
- `manifest.json`, which explicitly reports query status, errors, record count, and
  whether collection completed.

JSON and JSONL files retain the unchanged API records and should be treated as
sensitive governance data. CSV exports prefix spreadsheet formula-like string values
with a literal apostrophe to prevent formula execution when opened in Excel. The
documented output directories are ignored by Git; protect any custom output path and
do not commit audit exports.

The exporter retains partial records if a later page fails. A failed, cancelled, timed
out, or partially collected query is marked `complete: false` and the command exits
nonzero after writing the available artifacts.

To capture a consolidated inventory of every accessible workspace and every item in
each workspace:

```powershell
python .\examples\export_workspace_inventory.py
```

The command writes `fabric-workspace-inventory.json` with:

- the complete workspace payload returned by the Workspaces API;
- the complete item payload returned for every workspace;
- a flattened `rows` collection with workspace, capacity, and item fields; and
- an explicit `errors` collection if an individual workspace cannot be read.

Limit the export to a selected list of workspaces by repeating `--workspace-id`:

```powershell
python .\examples\export_workspace_inventory.py `
  --workspace-id <workspace-id-1> `
  --workspace-id <workspace-id-2> `
  --output selected-workspaces.json
```

Capacities, domains, and deployment pipelines require additional scopes. Include
them only when the signed-in identity has those permissions:

```powershell
python .\examples\export_workspace_inventory.py --include-platform-resources
```

This inventory captures the complete metadata exposed by the documented APIs. It
does not represent capacity utilization metrics, gateway data sources, or pipeline
activity runs, which use separate APIs, permissions, and query parameters.

### Include tenant audit/activity events

Add a UTC time window to include Power BI Admin activity events in the same JSON
file:

```powershell
python .\examples\export_workspace_inventory.py `
  --activity-start 2026-09-14T00:00:00Z `
  --activity-end 2026-09-14T23:59:59Z `
  --output workspace-items-and-activities.json
```

The activity window must be within one UTC day and within the preceding 28 days.
The signed-in identity must be a Fabric administrator with `Tenant.Read.All` or
`Tenant.ReadWrite.All`, or a service principal enabled for read-only admin APIs.
When `--workspace-id` is supplied, the exporter keeps only activity events whose
`WorkspaceId` matches the selected workspaces. Without `--workspace-id`, it
captures all activity events returned for the tenant and time window.
If the separate Power BI token or admin API call fails, the exporter still writes
the workspace/item inventory and records the activity failure in both
`activityEvents.error` and the top-level `errors` collection.

Pipeline activity runs are not tenant-wide audit events. They require a known
pipeline job instance ID and remain available through:

```powershell
fabric-api activity-runs <workspace-id> <job-instance-id> `
  --updated-after 2026-09-14T00:00:00Z `
  --updated-before 2026-09-15T00:00:00Z
```

Install development tools with `python -m pip install -e ".[dev]"` when running
the checks below.

## Authentication

The default mode uses Azure Identity's credential chain and allows interactive browser fallback:

```powershell
$env:FABRIC_AUTH_MODE = "default"
fabric-api workspaces
```

To force an interactive browser:

```powershell
$env:FABRIC_AUTH_MODE = "interactive"
$env:AZURE_TENANT_ID = "<tenant-id>"
$env:AZURE_CLIENT_ID = "<app-registration-client-id>"
fabric-api workspaces
```

For Purview Audit commands, the custom app registration must have delegated
`AuditLogsQuery.Read.All` with tenant admin consent. The signed-in user must also be
assigned to the Purview **Audit Reader** role group, which includes **View-Only Audit
Logs**, or **Audit Manager**, which includes **Audit Logs** and audit-management
permissions.

For a service principal, store credentials outside source control:

```powershell
$env:FABRIC_AUTH_MODE = "client_secret"
$env:AZURE_TENANT_ID = "<tenant-id>"
$env:AZURE_CLIENT_ID = "<application-id>"
$env:AZURE_CLIENT_SECRET = Read-Host "Client secret" -MaskInput
fabric-api workspaces
```

For Purview Audit commands, grant this service principal the Microsoft Graph
**application** permission `AuditLogsQuery.Read.All` and tenant admin consent. Azure
subscription RBAC roles such as Reader or Contributor do not grant access to the
Microsoft 365 unified audit log.

Fabric tokens use `https://api.fabric.microsoft.com/.default`. Power BI tokens use
`https://analysis.windows.net/powerbi/api/.default`. Purview Audit Search uses the
Microsoft Graph audience and scope `https://graph.microsoft.com/.default`.

## CLI examples

Values in angle brackets are placeholders. Do not type the angle brackets. First
list workspaces and copy the `id` value you want:

```powershell
# Fabric Core APIs
fabric-api workspaces
```

For example, select the first returned workspace and pass its ID to the item command:

```powershell
$workspace = fabric-api workspaces | ConvertFrom-Json | Select-Object -First 1
fabric-api items $workspace.id
```

The command calls
`GET https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items`,
automatically follows all continuation pages, and prints the combined JSON
results. The signed-in identity must have access to that workspace.

Additional examples:

```powershell
fabric-api items <workspace-id> --type Lakehouse
fabric-api item <workspace-id> <item-id>

# Convenience commands backed by the generic Fabric Items API
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

# Fabric platform resources
fabric-api capacities
fabric-api deployment-pipelines
fabric-api domains
fabric-api activity-runs <workspace-id> <job-instance-id> `
  --updated-after 2026-09-14T00:00:00Z `
  --updated-before 2026-09-15T00:00:00Z

# Power BI REST APIs
fabric-api gateways
fabric-api datasources <workspace-id> <semantic-model-id>
fabric-api activity-events --start 2026-09-14T00:00:00Z --end 2026-09-14T23:59:59Z

# Microsoft Graph v1.0 Purview Audit Search
fabric-api purview-audit export --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z --output .\purview-audit
fabric-api copilot-usage --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z --output .\copilot-usage
fabric-api powerbi-usage --start 2026-09-01T00:00:00Z `
  --end 2026-09-02T00:00:00Z --output .\powerbi-usage
```

All commands print JSON. Override service roots only for testing or sovereign-cloud routing:

```powershell
$env:FABRIC_API_BASE_URL = "https://api.fabric.microsoft.com"
$env:POWER_BI_API_BASE_URL = "https://api.powerbi.com"
$env:PURVIEW_GRAPH_BASE_URL = "https://graph.microsoft.com"
```

Endpoint overrides must be absolute HTTPS URLs. Authenticated absolute continuation
URLs are accepted only for the configured API host. Power BI additionally accepts
documented regional continuation hosts under `analysis.windows.net`; arbitrary hosts,
non-HTTPS URLs, user-information URLs, and unexpected ports are rejected before a
token is acquired or forwarded.

## API boundaries and prerequisites

### Microsoft Fabric REST APIs

| Capability | Official call shape used | Typical requirement |
|---|---|---|
| Workspaces | `GET https://api.fabric.microsoft.com/v1/workspaces` | `Workspace.Read.All` or `Workspace.ReadWrite.All` |
| Workspace items | `GET .../v1/workspaces/{workspaceId}/items?type={type}` | Viewer workspace role and `Workspace.Read.All` or `Workspace.ReadWrite.All` |
| Item details | `GET .../v1/workspaces/{workspaceId}/items/{itemId}` | Viewer workspace role and `Item.Read.All` or `Item.ReadWrite.All` |
| Capacities | `GET .../v1/capacities` | Fabric capacity visibility and the permissions stated by the operation |
| Deployment pipelines | `GET .../v1/deploymentPipelines` | Access to the returned deployment pipelines |
| Domains | `GET .../v1/domains` | `Domain.Read.All`; returns all tenant domains |
| Pipeline activity runs | `POST .../v1/workspaces/{workspaceId}/datapipelines/pipelineruns/{jobInstanceId}/queryactivityruns` | Pipeline access; examples use `Workspace.ReadWrite.All` and `Item.ReadWrite.All` |

Service principals and managed identities are supported only where each operation's **Microsoft Entra supported identities** table says so. Tenant administrators may also need to enable the Fabric tenant setting that allows service principals to use Fabric APIs and scope it to an appropriate security group.

The convenience item commands are aliases for the generic Items API, not invented workload endpoints. If a tenant does not recognize a type, the service returns `InvalidItemType`; use `fabric-api items <workspace-id>` to inspect the exact types present in that tenant.

### Power BI REST and Admin APIs

| Capability | Official call shape used | Important limitation |
|---|---|---|
| Gateways | `GET https://api.powerbi.com/v1.0/myorg/gateways` | Caller must be a gateway administrator |
| Dataset data sources | `GET .../v1.0/myorg/groups/{groupId}/datasets/{datasetId}/datasources` | Workspace and semantic model permissions apply |
| Activity/audit events | `GET .../v1.0/myorg/admin/activityevents` | Fabric/Power BI administrator or an allowed service principal; time range must be within one UTC day and within the retention window |

For delegated activity-event access, the documented Power BI permission is `Tenant.Read.All` or `Tenant.ReadWrite.All`. For service-principal access, enable the Power BI/Fabric tenant setting allowing service principals to use read-only admin APIs, place the principal in the allowed security group, and do **not** add admin-consent-required Power BI application permissions unless the operation's documentation explicitly requires them.

Activity events are the supported audit/activity API represented by this repository. There is no fabricated Fabric `/activities` collection.
Fabric Data Factory activity runs are separately available only in the context of a specific pipeline job instance, through the `activity-runs` command.

### Microsoft Purview Audit Search through Graph

`PurviewAuditClient` uses only the current Microsoft Graph v1.0 endpoints:

| Operation | Endpoint |
|---|---|
| Create query | `POST https://graph.microsoft.com/v1.0/security/auditLog/queries` |
| Poll status | `GET https://graph.microsoft.com/v1.0/security/auditLog/queries/{id}` |
| List records | `GET https://graph.microsoft.com/v1.0/security/auditLog/queries/{id}/records` |

For broad Microsoft 365 audit workloads:

- **Interactive/delegated authentication:** Add delegated Microsoft Graph
  `AuditLogsQuery.Read.All` to the custom app registration, grant tenant admin
  consent, and add the signed-in user to the Purview **Audit Reader** or **Audit
  Manager** role group.
- **Service-principal/application authentication:** Add Microsoft Graph application
  `AuditLogsQuery.Read.All` to the app registration and grant tenant admin consent.

More narrowly scoped `AuditLogsQuery-*` permissions exist, but may not cover the
workloads selected by these governance exports. The tenant must have Microsoft
Purview Audit available and meet the applicable licensing and data-access
requirements.

A response such as:

```text
403 ... User:<user-principal-name> dont have any permissions
```

means the request reached Graph but the delegated user/app combination lacks the
required Graph consent, Purview audit role, or both. It is not caused by the query
dates. Verify the custom app's delegated permission and admin consent, assign the user
to Audit Reader or Audit Manager, sign in again, and retry. If the error names a user,
the CLI used delegated authentication rather than the service principal.

The client supports the v1.0 create contract's `filterStartDateTime`,
`filterEndDateTime`, `recordTypeFilters` (including `powerBIAudit`), `serviceFilter`,
`operationFilters` (including `CopilotInteraction`), `userPrincipalNameFilters`,
`ipAddressFilters`, `objectIdFilters`, and `keywordFilter`. Timestamps must include an
offset and the end must be later than the start. The client does not impose an
undocumented maximum query span.

### Copilot in Fabric governance prerequisites and interpretation

- In the Fabric admin portal, enable **Allow Microsoft Purview to secure AI
  interactions**. Microsoft documents this as enabled by default.
- Purview management of these interactions requires the applicable Purview
  availability/licensing and pay-as-you-go billing. Confirm current tenant eligibility
  before relying on collection.
- Prompt and response content in Purview security/compliance experiences requires a
  collection policy, such as the DSPM for AI recommendation that captures Copilot
  interactions. Viewing that content in Activity Explorer also requires the applicable
  Content Explorer Content Viewer permissions.
- Audit records can expose `CopilotInteraction` metadata, message identifiers and
  prompt/response counts, `AppHost`, contexts, accessed resources, and sensitivity-label
  identifiers. They do **not** necessarily expose prompt or response text. This exporter
  never labels message IDs or counts as content.
- Interaction and active-user counts describe observed usage. Productivity impact
  cannot be inferred reliably from audit counts alone.
- DSPM for AI remains a Microsoft Purview portal, report, recommendation, policy, and
  Activity Explorer workflow. This repository does not invent a DSPM export API.
- For preserved Copilot in Fabric content, Microsoft documents eDiscovery as the
  supported search/review/export workflow. The verified item-class search pattern is
  `IPM.SkypeTeams.Message.Copilot.Fabric.*`.

### Choosing the right monitoring surface

| Surface | Use it for | Do not treat it as |
|---|---|---|
| Power BI Activity Events | Power BI tenant administration/activity events in short daily windows | A complete cross-service Copilot compliance record |
| Purview Audit Search API | On-demand structured queries across the unified audit log and raw record export | Prompt-content preservation or a productivity score |
| DSPM for AI / Activity Explorer | Portal insights, recommendations, policies, risky/sensitive interaction investigation | A public bulk export API |
| Capacity Metrics app / chargeback guidance | Capacity utilization, compute trends, and cost allocation | User-level compliance auditing |
| eDiscovery | Preservation, search, review, and export of collected Copilot content | A replacement for operational audit analytics |

For a second phase of scheduled or bulk ingestion, consider the Office 365 Management
Activity API rather than confusing its feed model with Graph Audit Search. It uses the
`ActivityFeed.Read` application permission, subscriptions, and downloadable content
blobs. Supported content types include `Audit.General`. When listing available content,
query intervals should be no more than 24 hours and the start can be no more than seven
days in the past. After a subscription is created, first blobs can take up to 12 hours
to appear.

## Coverage and limitations

- Lakehouses, warehouses, semantic models, dataflows, eventhouses, eventstreams, KQL databases, KQL querysets, environments, and dashboards are demonstrated through the Fabric Items API. The CLI passes the item type exactly as documented/configured and the generic `items --type` option supports additional current and future item types.
- Datamart surfaces are not demonstrated because they are not supported by the Fabric Items API across tenants.
- Capacity metadata is exposed by the Fabric Capacities API. Detailed capacity utilization metrics are not exposed by that endpoint. Use the officially supported Microsoft Fabric Capacity Metrics app or documented monitoring experiences; this repository does not invent a capacity-metrics REST path.
- Datasources and gateways are Power BI REST resources, not Fabric Core item endpoints.
- Some item types have additional workload-specific create/update/definition/job APIs. This example focuses on safe discovery and retrieval and leaves those operations to their individual official contracts.

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

```powershell
ruff format --check .
ruff check .
mypy src
pytest
```
