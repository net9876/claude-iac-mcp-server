"""Smoke test — exercises the tool functions directly (no MCP transport needed).

    python tests/smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import iac_mcp_server as s  # noqa: E402


def run() -> int:
    failures = 0

    def check(label: str, cond: bool) -> None:
        nonlocal failures
        status = "PASS" if cond else "FAIL"
        if not cond:
            failures += 1
        print(f"[{status}] {label}")

    mods = s.list_modules()
    check("list_modules returns 8 approved modules (6 AVM + 2 custom)", len(mods) == 8)

    db = s.search_modules("postgres database")
    check("search finds postgres first", db and db[0]["name"] == "azure-postgresql-flexible")

    spec = s.get_module("azure-storage-account")
    check("storage module points at real AVM source",
          spec["source"] == "Azure/avm-res-storage-storageaccount/azurerm")
    check("storage module pins a version", spec["version"] == "0.7.2")

    missing = s.get_module("aws-s3-bucket")
    check("get_module rejects non-approved module", "error" in missing)

    std = s.list_standards()
    check("standards expose allowed_regions", "westeurope" in std["allowed_regions"])
    check("AVM sources are allowlisted", "Azure/avm-*" in std["registry"]["allowed_sources"])

    # Storage uses parent_id wiring; flattened name.
    gen = s.generate_module_usage("azure-storage-account", "payments", "prod")
    check("generate flattens storage name", gen["resource_name"] == "acmeprodpaymentsst01")
    check("storage wired via parent_id",
          "parent_id = module.resource_group.resource_id" in gen["hcl"])
    check("generated HCL uses real AVM source",
          "Azure/avm-res-storage-storageaccount/azurerm" in gen["hcl"])

    # Key Vault uses resource_group_name wiring.
    kv = s.generate_module_usage("azure-key-vault", "payments", "prod")
    check("key vault wired via resource_group_name",
          "resource_group_name = module.resource_group.name" in kv["hcl"])
    check("key vault todo_inputs flags tenant_id", "tenant_id" in kv["todo_inputs"])

    # Resource group is the RG → no parent_id / resource_group_name line.
    rg = s.generate_module_usage("azure-resource-group", "payments", "prod")
    check("resource group has no rg wiring line",
          "parent_id" not in rg["hcl"] and "resource_group_name" not in rg["hcl"])

    good = s.validate_config(gen["hcl"])
    check("generated config has no source/region errors",
          not any(f["rule"] in ("REG-SRC", "REGION") for f in good["findings"]))

    # ── Hybrid registry: our own git-sourced modules ──────────────────────────
    law = s.get_module("azure-log-analytics")
    check("custom module served with git:: source",
          law["source"].startswith("git::https://github.com/net9876/terraform-azure-modules"))

    g_law = s.generate_module_usage("azure-log-analytics", "payments", "prod")
    check("custom module uses spec abbr (law)",
          g_law["resource_name"] == "acme-prod-payments-law01")
    check("git module emits no version line", "version =" not in g_law["hcl"])
    check("log-analytics wired via resource_group_name",
          "resource_group_name = module.resource_group.name" in g_law["hcl"])

    g_hard = s.generate_module_usage("azure-storage-hardened", "payments", "prod")
    check("hardened storage flattens name via spec flag",
          g_hard["resource_name"] == "acmeprodpaymentsst01")
    check("hardened storage wired via parent_id",
          "parent_id = module.resource_group.resource_id" in g_hard["hcl"])

    v_law = s.validate_config(g_law["hcl"])
    check("git:: source passes the allowlist",
          not any(f["rule"] == "REG-SRC" for f in v_law["findings"]))

    # Regression: a full file with required_providers must NOT trip REG-SRC.
    full = '''
        terraform {
          required_providers {
            azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
            random  = { source = "hashicorp/random",  version = "~> 3.0" }
          }
        }
        module "resource_group" {
          source  = "Azure/avm-res-resources-resourcegroup/azurerm"
          version = "0.4.0"
          name     = "acme-prod-payments-rg01"
          location = "westeurope"
          tags = { environment = "prod", owner = "x", cost_center = "y",
                   project = "payments", managed_by = "terraform" }
        }
    '''
    fok = s.validate_config(full)
    check("provider sources do NOT trip REG-SRC (false-positive fix)",
          not any(f["rule"] == "REG-SRC" for f in fok["findings"]))

    bad = s.validate_config('''
        module "x" {
          source   = "github.com/random/module"
          location = "eastus"
          name     = "myresource"
          password = "hunter2"
        }
    ''')
    check("validate flags bad source", any(f["rule"] == "REG-SRC" for f in bad["findings"]))
    check("validate flags bad region", any(f["rule"] == "REGION" for f in bad["findings"]))
    check("validate flags hardcoded secret", any(f["rule"] == "SEC-SECRET-001" for f in bad["findings"]))
    check("validate marks bad config non-compliant", bad["compliant"] is False)

    print(f"\n{'ALL PASSED' if not failures else str(failures) + ' FAILED'}")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
