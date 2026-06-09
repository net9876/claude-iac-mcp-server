# AI-Assisted IaC Self-Service Platform (Azure + Terraform)

An **AI-assisted self-service platform** for infrastructure. Developers use Claude
Code or GitHub Copilot to query an **approved Terraform module registry** and generate
**compliant** Azure infrastructure — without hand-rolling Terraform or pulling random
modules off the internet.

The approved registry is **hybrid**:
- **Azure Verified Modules (AVM)** — Microsoft's curated, compliance-grade modules from
  the public Terraform Registry (the baseline).
- **Your own modules** — hosted in a GitHub repo and referenced via a `git::` source.
  No registry product required. See `registry/modules/TEMPLATE-custom-git-module.yaml`.

It has two halves:

1. **An IaC MCP server** (`server/iac_mcp_server.py`) — exposes the approved module
   registry + standards as [MCP](https://modelcontextprotocol.io) tools.
2. **Agent skill / context** (`skills/iac-self-service/SKILL.md`) — encodes *how* the
   agent must use those tools to stay compliant.

```
developer ──▶ Claude Code / Copilot ──MCP──▶ iac_mcp_server ──▶ registry/ + standards/
                     │                                           (AVM + your git modules)
                     └── guided by skills/iac-self-service/SKILL.md
```

> **Note on names:** `acme` is a placeholder org name and the `app.terraform.io/acme/*`
> entry is an *optional* private-registry example. Replace `acme` with your own short
> name to brand it. The real, working modules are the AVM ones.

## Layout

| Path | Purpose |
|---|---|
| `server/iac_mcp_server.py` | FastMCP server (7 tools) |
| `registry/catalog.yaml` | The allowlist of approved modules |
| `registry/modules/*.yaml` | Per-module spec: source, version, `rg_ref`, inputs, outputs, example |
| `registry/modules/TEMPLATE-custom-git-module.yaml` | How to register your own git module |
| `standards/standards.yaml` | Naming, regions, required tags, source allowlist, security baseline |
| `skills/iac-self-service/SKILL.md` | The agent skill encoding the standards |
| `environments/prod/payments/` | Example output: a compliant, AVM-based `main.tf` |
| `.mcp.json` | Claude Code MCP wiring (local stdio) |
| `Dockerfile` | Container image for a hosted (HTTP) instance |
| `deploy/` | One-command Azure deploy + teardown scripts and docs |
| `tests/smoke_test.py` | Fast smoke test of the tools (19 checks) |

## MCP tools

| Tool | What it does |
|---|---|
| `list_modules(category?)` | List approved modules (optionally by category) |
| `search_modules(query)` | Free-text search the registry |
| `get_module(name)` | Full spec: source, version, `rg_ref`, inputs, outputs, example |
| `list_standards()` | The org standards the agent must honor |
| `generate_module_usage(module, workload, environment, …)` | Scaffold a compliant block (naming, RG wiring, tags) + `todo_inputs` |
| `validate_config(hcl)` | Heuristic policy check before `terraform plan` |
| `refresh_registry()` | Hot-reload registry/standards after edits |

## Setup

```powershell
pip install -r requirements.txt
python tests/smoke_test.py          # expect: ALL PASSED (19 checks)
```

## Use with Claude Code

`.mcp.json` is already provided. From the repo root:

```powershell
claude            # auto-discovers .mcp.json and starts the server
```

Load the skill once:

```powershell
New-Item -ItemType Directory -Force .claude\skills\iac-self-service | Out-Null
Copy-Item skills\iac-self-service\SKILL.md .claude\skills\iac-self-service\
```

Then ask: *"Provision a storage account and a Postgres database for the payments app
in prod."* The agent runs `list_standards` → `search_modules` → `get_module` →
`generate_module_usage` → `validate_config` and writes a compliant `main.tf`.

## Use with GitHub Copilot

Copilot (VS Code) reads MCP servers from `.vscode/mcp.json`:

```json
{
  "servers": {
    "acme-iac-platform": {
      "type": "stdio",
      "command": "python",
      "args": ["${workspaceFolder}/server/iac_mcp_server.py"]
    }
  }
}
```

For a **hosted** instance, point Copilot at the URL instead:
`{ "servers": { "acme-iac-platform": { "type": "http", "url": "https://<fqdn>/mcp" } } }`.
Mirror the rules from `SKILL.md` into `.github/copilot-instructions.md` so Copilot Chat
applies them.

## Two run modes: local (stdio) vs hosted (HTTP)

| | Local | Hosted (org) |
|---|---|---|
| Transport | stdio (default) | HTTP / streamable-http |
| Who starts it | Claude Code / Copilot auto-spawn it per session | Always-on Azure Container App |
| Setup | none — `.mcp.json` already wires it | `deploy/deploy-azure.ps1` (one command) |
| Connect | `.mcp.json` (project) or `claude mcp add` | `claude mcp add --transport http … https://<fqdn>/mcp` |

Switch a process to HTTP mode with `MCP_TRANSPORT=http` (the `Dockerfile` sets this).

### Deploy a shared instance to Azure

So a whole team points at one URL instead of running it locally:

```powershell
az login
.\deploy\deploy-azure.ps1     # builds the image in Azure + deploys to Container Apps
```

It prints the MCP URL and the connect command. Tear down with
`.\deploy\destroy-azure.ps1`. Full guide (connection, one-time test, **auth before
real use**, cost): [deploy/README.md](deploy/README.md).

## Deploying the example

The generated example lives in `environments/prod/payments/`. To deploy it against
**your** Azure state account without editing committed files:

```powershell
cd environments/prod/payments
Copy-Item backend.local.hcl.example backend.local.hcl   # edit values for your state account

# azurerm v4 needs a subscription id; the azurerm backend needs auth to your state account
$env:ARM_SUBSCRIPTION_ID = (az account show --query id -o tsv)
# state auth: either set use_azuread_auth in backend.local.hcl (needs Blob Data Contributor),
# or supply the key:  $env:ARM_ACCESS_KEY = (az storage account keys list -g <rg> -n <sa> --query "[0].value" -o tsv)

terraform init "-backend-config=backend.local.hcl"   # NOTE: quotes are required in PowerShell
terraform plan
terraform apply
```

The example uses real AVM modules, so `terraform init` actually downloads them (needs
Terraform >= 1.11 for the write-only Postgres password). The state backend account
(e.g. `myterrasa`) must already exist — `backend.local.hcl` is gitignored, so your real
account names never get published.

## Add one of YOUR own modules

1. Copy `registry/modules/TEMPLATE-custom-git-module.yaml` to `registry/modules/<name>.yaml`.
2. Set `source` to a `git::https://github.com/<you>/...//modules/<name>?ref=v1.0.0`,
   `rg_ref` to match how your module takes its resource group, and `status: approved`.
3. Add `<name>` to `registry/catalog.yaml`.
4. `refresh_registry()` (or restart). The AI now self-serves your module too.

## Production hardening (next steps)

- **Add authentication** to the hosted instance (the `deploy/` HTTP server ships open by
  default). Put it behind Entra ID / an API gateway before any real org use — see the
  Security section of [deploy/README.md](deploy/README.md).
- Replace the heuristic `validate_config` with **OPA/Conftest** policies, run both here
  and in CI (the heuristic is a fast pre-flight, not the enforcement gate).
- Pin AVM versions centrally and add a renovate/dependabot job to bump them.
- Emit telemetry on which modules are generated to measure adoption.
