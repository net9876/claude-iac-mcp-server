#!/usr/bin/env bash
# Tear down the IaC MCP server — deletes the whole resource group.
# Usage:
#   ./deploy/destroy-azure.sh
#   RESOURCE_GROUP=rg-iac-mcp ./deploy/destroy-azure.sh
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-iac-mcp}"

echo "==> Deleting resource group '$RESOURCE_GROUP' and ALL resources in it..."
az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo "Delete initiated (running in background)."
echo "Check status with:  az group show -n $RESOURCE_GROUP"
