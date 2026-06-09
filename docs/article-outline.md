# Article outline — "Self-Service Infrastructure, Driven by AI: An IaC MCP Server for Azure"

Working title options:
- *Teaching Claude Code to Provision Compliant Azure Infra (with an MCP Server + AVM)*
- *The Golden Path, Automated: AI Self-Service IaC on Azure Verified Modules*
- *From Ticket to Terraform: An MCP Server That Lets AI Generate Only Approved Infra*

## 1. The hook (the problem)
- Developers want infra *now*; platform teams want infra *compliant*. The usual
  resolution is tickets, wikis, and copy-pasted Terraform that drifts from standard.
- AI coding agents (Claude Code, Copilot) will happily generate Terraform — but left
  alone they invent resources, skip tags, and pull random modules. That's a liability.
- Thesis: don't fight the AI — **constrain** it. Give it a tool that only exposes
  *approved* modules and *encodes* your standards.

## 2. The idea: MCP as the guardrail
- One paragraph on what MCP is (a standard way to give an AI agent tools/context).
- The two halves: an **IaC MCP server** (the guardrail) + an **agent skill** (the
  knowledge). Diagram from the README.

## 3. What the server exposes (the tools)
- `list_modules`, `search_modules`, `get_module` — query the approved registry.
- `list_standards` — naming, regions, mandatory tags, security baseline.
- `generate_module_usage` — scaffolds a compliant block (naming + RG wiring + tags).
- `validate_config` — a fast policy pre-flight before `terraform plan`.
- Screenshot: `/mcp` in Claude Code showing the server connected with its tools.

## 4. The registry is hybrid (and free)
- Baseline = **Azure Verified Modules** — Microsoft's own compliance-grade modules,
  on the public Terraform Registry. No paid registry needed.
- Plus **your own modules** via `git::` GitHub sources. Same UX to the agent.
- Callout: a "module registry" is just *where versioned module code lives* — it does
  not have to be a product.

## 5. The money shot: a real run
- Paste the actual Claude Code transcript: one English sentence →
  `list_standards` → `search_modules` → `get_module` → `generate_module_usage` →
  `validate_config` → a compliant `main.tf`.
- Show the generated `main.tf` (AVM modules, correct `parent_id` vs
  `resource_group_name` wiring, mandatory tags, write-only Postgres password).

## 6. The part nobody expects: the AI audited my platform
- Honest beat. On the first run (against placeholder modules), the agent found two
  real defects in MY registry: a Key Vault module that couldn't actually hold a
  secret, and a validator false-positive on provider sources.
- Lesson: the agent isn't just a consumer of the platform — it's a fuzzer for it.
  Fixing those made the platform genuinely better.

## 7. Compliance baked in
- Naming standard + regex, allowed regions, mandatory tags, security baseline
  (TLS, no public access, secrets via Key Vault/write-only, remote state).
- `validate_config` as a guardrail; OPA/Conftest in CI as the real gate.

## 8. Try it yourself
- Link the GitHub repo. `pip install`, `python tests/smoke_test.py`, wire `.mcp.json`,
  ask Claude Code for infra.
- Note: `acme` is a placeholder — rename to your org; swap in your own git modules.

## 9. Where this goes next (production hardening)
- HTTP transport + auth for a shared team server; telemetry on module adoption;
  Renovate to bump AVM versions; OPA policy gate in CI.

## Assets to capture for the post
- [ ] Screenshot: `/mcp` panel (server connected, 7 tools)
- [ ] Screenshot: `/skills` panel (iac-self-service on)
- [ ] Transcript: the full provision run
- [ ] Snippet: the generated `main.tf`
- [ ] Snippet: `validate_config` catching a bad source / hardcoded secret
- [ ] Diagram: the README architecture box
