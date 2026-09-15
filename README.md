# Fabric REST API examples

Reusable Python clients for the [Microsoft Fabric REST API](https://learn.microsoft.com/rest/api/fabric/)
and [Power BI REST API](https://learn.microsoft.com/rest/api/power-bi/). They intentionally keep the
two endpoint families and token audiences separate: Fabric uses
`https://api.fabric.microsoft.com/.default`; Power BI uses
`https://analysis.windows.net/powerbi/api/.default`.

## Run

```bash
pip install -e '.[dev]'
export AZURE_TENANT_ID=... AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=...
fabric-api workspaces
fabric-api items <workspace-id> Lakehouse
fabric-api pipeline-runs <workspace-id> <pipeline-id>
fabric-api gateways
fabric-api data-sources <gateway-id>
fabric-api activity-events '2025-01-01T00:00:00.000Z' '2025-01-01T01:00:00.000Z'
```

`--interactive` uses `InteractiveBrowserCredential`; otherwise a complete service-principal
environment configuration uses `ClientSecretCredential`, and `DefaultAzureCredential` is used for
local development, managed identities, and workload identity. Never place secrets in source or CLI
arguments. `--fabric-url` and `--powerbi-url` allow sovereign-cloud or test endpoints.

The commands also cover `capacities`, `domains`, and `deployment-pipelines`. The client follows
Fabric continuation URIs and Power BI OData next links, sets a 30-second timeout, and retries
transient transport failures and 429/5xx responses at most three times.

## Platform boundaries

Use the official API documentation above to select an endpoint and its required delegated scope,
application permission, workspace role, capacity role, or tenant setting. Admin activity events
require the applicable Power BI tenant admin role and tenant setting. Service principals are not
supported by every Fabric or Power BI endpoint: verify the endpoint-specific documentation and
enable the relevant tenant setting before using one. Datamart and Capacity Metrics surfaces are not
general-purpose REST APIs and are deliberately not represented here. These examples do not bypass
Fabric, Power BI, Entra ID, workspace, capacity, domain, or tenant authorization.
