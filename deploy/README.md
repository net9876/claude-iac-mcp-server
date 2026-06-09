# Deploying the IaC MCP server to Azure

Run the platform as a **shared, always-on instance** so a whole team connects their
Claude Code / GitHub Copilot to one URL — instead of each developer running it
locally. This deploys the server (HTTP/streamable-http) to **Azure Container Apps**.

> Local use needs none of this. Locally, Claude Code auto-spawns the server over
> stdio (see the root `.mcp.json`). This is only for a hosted/org instance — or a
> one-time test that the remote scheme works.

## What gets deployed

```
  developers ──HTTPS──▶  Azure Container App  ──▶  iac_mcp_server (HTTP, /mcp)
                         (scale-to-zero, public ingress)
```

- An **Azure Container Apps environment** + one **Container App** running this repo's
  Dockerfile, serving the MCP endpoint at `https://<app>.<region>.azurecontainerapps.io/mcp`.
- The image is built **in Azure** from the Dockerfile (via `az containerapp up`), so
  you do **not** need Docker installed locally.

## Prerequisites

- Azure CLI (`az`) and an Azure subscription.
- `az login` completed.
- That's it — the deploy script installs the `containerapp` extension and registers
  the required resource providers for you.

## Deploy (one command)

PowerShell:
```powershell
az login
.\deploy\deploy-azure.ps1                       # defaults: rg-iac-mcp / eastus / iac-mcp-server
# or customize:
.\deploy\deploy-azure.ps1 -ResourceGroup rg-iac-mcp -Location westeurope -AppName iac-mcp
```

bash:
```bash
az login
./deploy/deploy-azure.sh
# or:  RESOURCE_GROUP=rg-iac-mcp LOCATION=westeurope APP_NAME=iac-mcp ./deploy/deploy-azure.sh
```

The script prints the MCP endpoint URL and the exact connect commands when it finishes.

## Connect your AI client to the hosted server

**Claude Code** (user scope = available in every project on your machine):
```powershell
claude mcp add --transport http --scope user acme-iac-platform https://<fqdn>/mcp
```

**GitHub Copilot** (`.vscode/mcp.json` in a project):
```json
{
  "servers": {
    "acme-iac-platform": {
      "type": "http",
      "url": "https://<fqdn>/mcp"
    }
  }
}
```

Verify in Claude Code with `/mcp` — you should see `acme-iac-platform` connected with
its 7 tools, exactly as in local mode.

## One-time test flow (then clean up)

```powershell
az login
.\deploy\deploy-azure.ps1                        # ~3-5 min (cloud build + deploy)
claude mcp add --transport http --scope user acme-iac-test https://<fqdn>/mcp
#   open claude, run /mcp, confirm 7 tools, try: "list the approved modules"
claude mcp remove acme-iac-test                  # disconnect
.\deploy\destroy-azure.ps1                        # deletes the whole resource group
```

## Cost

Azure Container Apps **scales to zero** when idle, so a short test costs cents. The
`destroy` script removes everything. Still, don't leave an unauthenticated instance
running.

## ⚠️ Security — read before any real org use

The deploy uses **public, unauthenticated ingress** so the test is friction-free.
**Do not expose a real internal registry this way.** Before org rollout, add at least
one of:

- A reverse proxy / API gateway requiring an API key or **Entra ID (OAuth)** token.
- Container Apps auth (`az containerapp auth`) with your identity provider.
- Private ingress + VNet, reachable only from the corporate network.

The registry/standards served here are not secrets, but an open write-capable MCP
endpoint is still something you want behind auth.

## Updating the hosted instance

Re-run `deploy-azure.ps1` — `az containerapp up` rebuilds from the current source and
rolls out a new revision. (When you change `registry/` or `standards/`, that's how the
hosted copy picks them up; locally you'd just call `refresh_registry`.)
