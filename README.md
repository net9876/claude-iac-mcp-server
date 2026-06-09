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
| `.mcp.json` | Claude Code MCP wiring |
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

Mirror the rules from `SKILL.md` into `.github/copilot-instructions.md` so Copilot Chat
applies them.

## Deploying the example

The generated example lives in `environments/prod/payments/`. To deploy it against
**your** Azure state account without editing committed files:

```powershell
cd environments/prod/payments
Copy-Item backend.local.hcl.example backend.local.hcl   # edit values if needed
terraform init -backend-config=backend.local.hcl
terraform plan
terraform apply
```

The example uses real AVM modules, so `terraform init` actually downloads them. The
state backend account (e.g. `myterrasa`) must already exist — `backend.local.hcl` is
gitignored, so your real account names never get published.

## Add one of YOUR own modules

1. Copy `registry/modules/TEMPLATE-custom-git-module.yaml` to `registry/modules/<name>.yaml`.
2. Set `source` to a `git::https://github.com/<you>/...//modules/<name>?ref=v1.0.0`,
   `rg_ref` to match how your module takes its resource group, and `status: approved`.
3. Add `<name>` to `registry/catalog.yaml`.
4. `refresh_registry()` (or restart). The AI now self-serves your module too.

## Production hardening (next steps)

- Replace the heuristic `validate_config` with **OPA/Conftest** policies, run both here
  and in CI (the heuristic is a fast pre-flight, not the enforcement gate).
- Pin AVM versions centrally and add a renovate/dependabot job to bump them.
- Add auth + run the server over HTTP (streamable-http) for a shared team instance
  instead of per-developer stdio.
- Emit telemetry on which modules are generated to measure adoption.
