"""
IaC MCP Server — Azure / Terraform self-service platform.

Exposes the org's *approved* Terraform module registry and IaC standards to AI
coding agents (Claude Code, GitHub Copilot) over the Model Context Protocol.

Agents use these tools to query approved modules and generate compliant
infrastructure instead of authoring ad-hoc Terraform.

Run (stdio, for Claude Code / Copilot):
    python server/iac_mcp_server.py

Dependencies: see requirements.txt  (mcp, pyyaml)
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Paths — resolved relative to this file so the server works from any cwd.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "registry"
MODULES_DIR = REGISTRY_DIR / "modules"
CATALOG_FILE = REGISTRY_DIR / "catalog.yaml"
STANDARDS_FILE = ROOT / "standards" / "standards.yaml"

mcp = FastMCP("acme-iac-platform")


# ---------------------------------------------------------------------------
# Registry / standards loading (cached; call refresh_registry to reload).
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _standards() -> dict[str, Any]:
    return yaml.safe_load(STANDARDS_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _modules() -> dict[str, dict[str, Any]]:
    """Load every approved module spec, keyed by module name."""
    catalog = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for name in catalog.get("modules", []):
        spec_path = MODULES_DIR / f"{name}.yaml"
        if not spec_path.exists():
            continue
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if spec.get("status") == "approved":
            out[spec["name"]] = spec
    return out


def _abbr_for(module: dict[str, Any]) -> str | None:
    """Org resource abbreviation: the module spec's own `abbr` field wins,
    falling back to a name-keyword heuristic for older specs."""
    if module.get("abbr"):
        return module["abbr"]
    abbrs = _standards()["naming"]["resource_abbreviations"]
    name = module["name"]
    # Heuristic: match on a keyword in the module name.
    keymap = {
        "resource-group": "resource_group",
        "virtual-network": "virtual_network",
        "storage-account": "storage_account",
        "postgresql": "postgresql_flexible_server",
        "aks": "kubernetes_cluster",
        "key-vault": "key_vault",
    }
    for needle, key in keymap.items():
        if needle in name:
            return abbrs.get(key)
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def list_modules(category: str = "") -> list[dict[str, str]]:
    """List approved Terraform modules in the registry.

    Args:
        category: Optional filter (e.g. "networking", "database", "storage",
                  "compute", "security", "foundation"). Empty = all.

    Returns a list of {name, display_name, category, description}.
    """
    result = []
    for m in _modules().values():
        if category and m.get("category") != category:
            continue
        result.append(
            {
                "name": m["name"],
                "display_name": m["display_name"],
                "category": m.get("category", ""),
                "description": " ".join(m.get("description", "").split()),
            }
        )
    return result


@mcp.tool()
def search_modules(query: str) -> list[dict[str, str]]:
    """Free-text search across module name, description, category, and tags.

    Args:
        query: Keywords, e.g. "postgres database" or "private network".
    """
    terms = [t.lower() for t in query.split() if t]
    scored: list[tuple[int, dict[str, str]]] = []
    for m in _modules().values():
        haystack = " ".join(
            [
                m["name"],
                m["display_name"],
                m.get("category", ""),
                m.get("description", ""),
                " ".join(m.get("tags", [])),
            ]
        ).lower()
        score = sum(haystack.count(t) for t in terms)
        if score:
            scored.append(
                (
                    score,
                    {
                        "name": m["name"],
                        "display_name": m["display_name"],
                        "category": m.get("category", ""),
                        "description": " ".join(m.get("description", "").split()),
                    },
                )
            )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


@mcp.tool()
def get_module(name: str) -> dict[str, Any]:
    """Get the full spec of an approved module: source, version, inputs, outputs,
    and a compliant usage example.

    Args:
        name: Module name, e.g. "azure-storage-account".
    """
    mod = _modules().get(name)
    if not mod:
        return {
            "error": f"Module '{name}' is not in the approved registry.",
            "available": sorted(_modules().keys()),
        }
    return mod


@mcp.tool()
def list_standards() -> dict[str, Any]:
    """Return the org IaC standards: naming pattern, allowed regions, required
    tags, environments, registry source allowlist, and the security baseline.

    Agents MUST consult this before generating infrastructure.
    """
    return _standards()


@mcp.tool()
def generate_module_usage(
    module_name: str,
    workload: str,
    environment: str,
    location: str = "westeurope",
    instance: int = 1,
    extra_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a compliant Terraform module block + locals tags, wired with the
    org naming standard and mandatory tags.

    Args:
        module_name: Approved module, e.g. "azure-storage-account".
        workload:    Short workload/app name, e.g. "payments".
        environment: One of the approved environments (dev|test|prod).
        location:    Approved Azure region (default westeurope).
        instance:    Instance number for the resource name suffix (default 1).
        extra_inputs: Optional extra HCL input assignments, e.g.
                      {"address_space": '["10.20.0.0/16"]'}.

    Returns {hcl, resource_name, warnings}. Always run validate_config on the
    result before applying.
    """
    std = _standards()
    warnings: list[str] = []

    mod = _modules().get(module_name)
    if not mod:
        return {
            "error": f"Module '{module_name}' is not approved.",
            "available": sorted(_modules().keys()),
        }

    if environment not in std["environments"]:
        warnings.append(
            f"environment '{environment}' is not in approved set {std['environments']}."
        )
    if location not in std["allowed_regions"]:
        warnings.append(
            f"location '{location}' is not in approved regions {std['allowed_regions']}."
        )

    org = std["organization"]
    abbr = _abbr_for(mod) or "res"
    resource_name = f"{org}-{environment}-{workload}-{abbr}{instance:02d}"

    # Some Azure names forbid hyphens/uppercase (e.g. storage accounts). Specs
    # opt in via `flatten_name: true`.
    name_value = resource_name
    if mod.get("flatten_name"):
        name_value = re.sub(r"[^a-z0-9]", "", resource_name.lower())[:24]
        warnings.append(
            "Name was flattened to satisfy Azure's 3-24 lowercase-alnum rule."
        )

    # Mandatory tags block.
    tag_lines = "\n".join(
        f'    {k:<13} = "{_tag_placeholder(k, environment, workload)}"'
        for k in std["required_tags"]
    )

    # Build the module block.
    local_ref = module_name.split("-", 1)[-1].replace("-", "_")
    source = mod["source"]
    version = mod.get("version", "")
    rg_ref = mod.get("rg_ref", "resource_group_name")
    supports_tags = mod.get("supports_tags", True)

    lines = [f'module "{local_ref}" {{', f'  source  = "{source}"']
    if version:  # git:: sources pin via ?ref= in the source, so version may be empty.
        lines.append(f'  version = "{version}"')
    lines += ["", f'  name     = "{name_value}"', f'  location = "{location}"']

    # Resource-group wiring differs per AVM module (some take parent_id, some a name).
    if rg_ref == "parent_id":
        lines.append("  parent_id = module.resource_group.resource_id")
    elif rg_ref == "resource_group_name":
        lines.append("  resource_group_name = module.resource_group.name")
    # rg_ref == "none" → this module IS the resource group; emit nothing.

    if supports_tags:
        lines.append("  tags     = local.common_tags")
    for k, v in (extra_inputs or {}).items():
        lines.append(f"  {k} = {v}")
    lines.append("}")
    module_block = "\n".join(lines)

    locals_block = f"locals {{\n  common_tags = {{\n{tag_lines}\n  }}\n}}"
    hcl = f"{locals_block}\n\n{module_block}\n"

    # Required inputs the agent must still fill in (beyond what we auto-wired).
    handled = {"name", "location", "tags", rg_ref}
    todo = [i for i in mod.get("required_inputs", []) if i not in handled]

    return {
        "resource_name": name_value,
        "source": source,
        "hcl": hcl,
        "todo_inputs": todo,
        "warnings": warnings,
        "next_step": "Fill any todo_inputs from get_module, then run validate_config(hcl).",
    }


@mcp.tool()
def validate_config(config: str) -> dict[str, Any]:
    """Validate a Terraform snippet against org standards. Heuristic, fast,
    pre-plan guardrail — not a substitute for `terraform validate` or OPA/Conftest
    in CI, but catches the common policy violations early.

    Checks: approved module sources, allowed regions, required tags, naming
    standard, and a few security baseline rules.

    Args:
        config: Raw Terraform/HCL text.
    """
    std = _standards()
    findings: list[dict[str, str]] = []

    def add(level: str, rule: str, message: str) -> None:
        findings.append({"level": level, "rule": rule, "message": message})

    # 1. Module source allowlist. Provider sources (e.g. hashicorp/azurerm in a
    #    required_providers block) are NOT module sources and are exempt.
    for src in re.findall(r'source\s*=\s*"([^"]+)"', config):
        if _is_provider_source(src):
            continue
        if not any(_glob_match(p, src) for p in std["registry"]["allowed_sources"]):
            add("error", "REG-SRC", f"Module source '{src}' is not in the approved registry.")

    # 2. Allowed regions.
    for loc in re.findall(r'location\s*=\s*"([^"]+)"', config):
        if loc not in std["allowed_regions"]:
            add("error", "REGION", f"location '{loc}' is not approved {std['allowed_regions']}.")

    # 3. Required tags present (look inside a common_tags / tags block).
    for tag in std["required_tags"]:
        if not re.search(rf'\b{re.escape(tag)}\b\s*=', config):
            add("error", "TAGS", f"Required tag '{tag}' is missing.")

    # 4. Naming standard — only applies to names that claim to be org resource names
    #    (start with the org prefix). Subnet keys, secret names, etc. are exempt, and
    #    storage names are flattened (no hyphens) so they never match here.
    org = std.get("organization", "")
    name_re = re.compile(std["naming"]["regex"])
    for nm in re.findall(r'\bname\s*=\s*"([^"]+)"', config):
        if org and nm.startswith(f"{org}-") and not name_re.match(nm):
            add("warning", "NAMING", f"Name '{nm}' does not match {std['naming']['regex']}.")

    # 5. Security baseline heuristics.
    if "0.0.0.0/0" in config:
        add("error", "SEC-NET-001", "Public 0.0.0.0/0 exposure detected.")
    if re.search(r'public_network_access\s*=\s*"?(true|Enabled)"?', config, re.I):
        add("error", "SEC-DATA-001", "public_network_access must be disabled.")
    if re.search(r'(password|secret)\s*=\s*"(?!@Microsoft\.KeyVault)[^"]+"', config, re.I):
        add("error", "SEC-SECRET-001", "Hardcoded secret detected; use a Key Vault reference.")

    errors = [f for f in findings if f["level"] == "error"]
    return {
        "compliant": not errors,
        "error_count": len(errors),
        "warning_count": len(findings) - len(errors),
        "findings": findings or [{"level": "info", "rule": "OK", "message": "No issues found."}],
    }


@mcp.tool()
def refresh_registry() -> dict[str, Any]:
    """Reload the module registry and standards from disk (after a catalog update)."""
    _standards.cache_clear()
    _modules.cache_clear()
    return {"reloaded": True, "module_count": len(_modules())}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tag_placeholder(key: str, environment: str, workload: str) -> str:
    return {
        "environment": environment,
        "project": workload,
        "managed_by": "terraform",
    }.get(key, f"<{key}>")


def _is_provider_source(src: str) -> bool:
    """True for Terraform PROVIDER sources (namespace/name), which are exempt from
    the module allowlist. Module registry sources have three segments
    (Azure/avm-res-x/azurerm); git/local sources contain '::' or start with . or /."""
    if "::" in src or src.startswith((".", "/")):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", src))


def _glob_match(pattern: str, value: str) -> bool:
    """Tiny glob: only '*' wildcard, anchored."""
    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(regex, value) is not None


if __name__ == "__main__":
    import os

    # Default = stdio (local): Claude Code / Copilot auto-spawn this per session.
    # Set MCP_TRANSPORT=http to serve over HTTP for a shared/hosted (org) instance;
    # the MCP endpoint is then available at  http://<host>:<port>/mcp
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http"):
        from mcp.server.transport_security import TransportSecuritySettings

        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", "8000")))

        # MCP's DNS-rebinding protection validates the Host header against an
        # allow-list (default: localhost only). Behind a platform ingress (e.g.
        # Azure Container Apps) the Host is the ingress FQDN, which would 421.
        # Set MCP_ALLOWED_HOSTS to lock to specific hosts; otherwise disable the
        # check (the ingress + any auth in front are the real boundary).
        allowed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
        if allowed:
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=allowed,
                allowed_origins=allowed,
            )
        else:
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=False
            )

        mcp.run(transport="streamable-http")
    else:
        mcp.run()
