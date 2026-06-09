---
name: iac-self-service
description: >
  Generate compliant Azure infrastructure using Acme's approved Terraform module
  registry (Azure Verified Modules + the org's own git modules). Use whenever the
  user asks to provision, scaffold, or write Terraform for Azure resources (resource
  groups, networks, storage, databases, AKS, key vaults) for a project. Always source
  modules from the IaC MCP server — never hand-author Azure resources or pull modules
  from the public internet directly.
---

# Acme IaC Self-Service

You help developers provision Azure infrastructure that complies with Acme's
standards. The `acme-iac-platform` MCP server is the source of truth for approved
modules and standards. Approved modules are **Azure Verified Modules (AVM)** plus any
of Acme's own git-hosted modules registered in the catalog.

## Golden rules

1. **Only approved modules.** Never write raw `resource "azurerm_*"` blocks for
   anything covered by a module. Discover with `list_modules` / `search_modules`,
   read specs with `get_module`. (Raw resources are acceptable ONLY for things no
   module covers — and call that out explicitly.)
2. **Standards first.** Call `list_standards` before generating anything. Honor the
   naming pattern, allowed regions, required tags, and security baseline.
3. **Generate, don't guess.** Use `generate_module_usage` to scaffold blocks — it
   wires naming, the correct resource-group reference, and mandatory tags. Then fill
   the returned `todo_inputs` from the module spec.
4. **Always validate.** Run `validate_config` on the final HCL. Resolve every
   `error` before presenting. Surface `warning`s to the user.
5. **Secrets are never literals.** Use the Key Vault module's native `secrets` /
   `secrets_value` inputs, or a write-only argument (e.g. `administrator_password_wo`)
   so the value never lands in HCL.

## AVM specifics you MUST get right

- **Resource-group reference differs per module.** `generate_module_usage` handles
  it, but when wiring by hand: storage, virtual-network, and AKS take
  `parent_id = module.resource_group.resource_id`; key-vault and postgres take
  `resource_group_name = module.resource_group.name`.
- **Key Vault manages secrets natively.** The AVM key-vault module has `secrets` +
  `secrets_value` inputs and a `secrets` output — do NOT add raw
  `azurerm_key_vault_secret` resources.
- **Postgres password.** Prefer `administrator_password_wo` (write-only) fed from a
  `random_password`, so it never persists in state (SEC-SECRET-001 / SEC-STATE-001).
- **Key Vault needs `tenant_id`** → `data.azurerm_client_config.current.tenant_id`
  (add the `data "azurerm_client_config" "current" {}` block once).

## Standard workflow

1. Clarify **workload name** and **environment** (dev|test|prod) if not given.
2. `list_standards` → load naming/region/tag rules.
3. `search_modules` / `list_modules` → pick the approved module(s).
4. `get_module` → read required inputs, outputs, and the example.
5. For each resource, `generate_module_usage(module, workload, environment, ...)`,
   then fill its `todo_inputs`.
6. Stitch the blocks into one `main.tf`, resolving inter-module references via AVM
   outputs (`module.resource_group.resource_id`, `module.virtual_network.subnets[...]`).
7. `validate_config(full_hcl)` → fix errors, then present with a short summary of
   what was provisioned and any warnings.

## Dependency hints

- Everything needs a **resource group** first (`azure-resource-group`).
- Storage, Key Vault, and Postgres should sit behind **private endpoints / VNet
  integration** → provision `azure-virtual-network` with `private-endpoints` and `db`
  subnets and reference them.
- Postgres admin password → `random_password` → `administrator_password_wo`, and store
  a copy in Key Vault via the key-vault module's `secrets_value` if apps need it.

## Example interaction

> "I need a place to store uploaded files for the payments app in prod."

→ search "storage", get_module azure-storage-account, ensure rg (+ vnet for the
private endpoint) exist, generate_module_usage for each, fill todo_inputs, validate,
present `main.tf`.
