# Microsoft Fabric REST API Python examples

A production-oriented, typed Python client and CLI for documented Microsoft Fabric REST APIs and the separately governed Power BI REST APIs.

The examples intentionally do not guess endpoint paths. Most Fabric workloads are accessed through the stable Core **Items** API (`/v1/workspaces/{workspaceId}/items`) with an official item type filter. Platform resources such as workspaces, capacities, deployment pipelines, and domains use their documented Fabric endpoints. Power BI gateways, dataset data sources, and tenant activity events use `api.powerbi.com` and a separate access token.

## Features

- Microsoft Entra authentication with `DefaultAzureCredential`, interactive browser authentication, or service-principal environment variables.
- Separate Fabric and Power BI token audiences.
- Typed reusable synchronous client with configurable base URLs and timeouts.
- Pagination through `continuationUri` or `continuationToken`.
- Retry/backoff for `429`, `500`, `502`, `503`, and `504`, including `Retry-After`.
- Explicit exceptions containing status, request ID, and service error details.
- Generic item listing/getting for new or less common Fabric item types.
- CLI shortcuts for common Fabric item types and Power BI administration examples.
- Unit tests with mocked HTTP and credentials; no tenant is required.

## Install

Python 3.10 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Copy `.env.example` values into your shell or preferred secret store. The CLI does not load `.env` files automatically.

## Authentication

The default mode uses Azure Identity's credential chain and allows interactive browser fallback:

```powershell
$env:FABRIC_AUTH_MODE = "default"
fabric-api workspaces
```

To force an interactive browser:

```powershell
$env:FABRIC_AUTH_MODE = "interactive"
fabric-api workspaces
```

For a service principal, store credentials outside source control:

```powershell
$env:FABRIC_AUTH_MODE = "client_secret"
$env:AZURE_TENANT_ID = "<tenant-id>"
$env:AZURE_CLIENT_ID = "<application-id>"
$env:AZURE_CLIENT_SECRET = "<secret>"
fabric-api workspaces
```

Fabric tokens use `https://api.fabric.microsoft.com/.default`. Power BI tokens use `https://analysis.windows.net/powerbi/api/.default`.

## CLI examples

```powershell
# Fabric Core APIs
fabric-api workspaces
fabric-api items <workspace-id>
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
fabric-api datamarts <workspace-id>

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
```

All commands print JSON. Override service roots only for testing or sovereign-cloud routing:

```powershell
$env:FABRIC_API_BASE_URL = "https://api.fabric.microsoft.com"
$env:POWER_BI_API_BASE_URL = "https://api.powerbi.com"
```

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

## Coverage and limitations

- Lakehouses, warehouses, semantic models, dataflows, eventhouses, eventstreams, KQL databases, KQL querysets, environments, dashboards, and datamarts are demonstrated through the Fabric Items API. The CLI passes the item type exactly as documented/configured and the generic `items --type` option supports additional current and future item types.
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

## Development

```powershell
ruff format --check .
ruff check .
mypy src
pytest
```
