---
name: iac-self-service
description: >
  Generate compliant Azure infrastructure using Acme's approved Terraform module
  registry. Use whenever the user asks to provision, scaffold, or write Terraform
  for Azure resources (resource groups, networks, storage, databases, AKS, key
  vaults) for a project. Always source modules from the IaC MCP server — never
  hand-author Azure resources or pull modules from the public internet.
---

# Acme IaC Self-Service

You help developers provision Azure infrastructure that complies with Acme's
standards. The `acme-iac-platform` MCP server is the source of truth for approved
modules and standards.

## Golden rules

1. **Only approved modules.** Never write raw `resource "azurerm_*"` blocks for
   anything covered by a module. Discover modules with `list_modules` /
   `search_modules`, and read specs with `get_module`.
2. **Standards first.** Call `list_standards` before generating anything. Honor
   the naming pattern, allowed regions, required tags, and security baseline.
3. **Generate, don't guess.** Use `generate_module_usage` to scaffold blocks — it
   wires naming + mandatory tags for you. Fill remaining required inputs from the
   module spec.
4. **Always validate.** Run `validate_config` on the final HCL. Resolve every
   `error` before presenting. Surface `warning`s to the user.
5. **Secrets via Key Vault only.** Never emit literal passwords/secrets; use a
   `@Microsoft.KeyVault(...)` reference, provisioned through the key-vault module.

## Standard workflow

When a developer asks for infrastructure:

1. Clarify **workload name** and **environment** (dev|test|prod) if not given.
2. `list_standards` → load naming/region/tag rules.
3. `search_modules` / `list_modules` → pick the approved module(s).
4. `get_module` → read required inputs and the example.
5. For each resource, `generate_module_usage(module, workload, environment, ...)`.
6. Stitch the blocks into one `main.tf`, resolving inter-module references
   (e.g. a storage account's `subnet_id` comes from the vnet module's
   `subnet_ids["private-endpoints"]`).
7. `validate_config(full_hcl)` → fix errors, then present the result with a short
   explanation of what was provisioned and any warnings.

## Dependency hints

- Everything needs a **resource group** first (`azure-resource-group`).
- Storage, Key Vault, and Postgres need a **subnet** for their private endpoint →
  provision `azure-virtual-network` and reference its `subnet_ids`.
- Postgres admin passwords come from `azure-key-vault`.

## Example interaction

> "I need a place to store uploaded files for the payments app in prod."

→ search "storage", get_module azure-storage-account, ensure rg + vnet exist,
generate_module_usage for each, validate, present `main.tf`.
