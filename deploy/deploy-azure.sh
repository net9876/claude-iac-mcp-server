#!/usr/bin/env bash
# Deploy the IaC MCP server to Azure Container Apps (HTTP/streamable-http).
# Builds the image from the repo Dockerfile in the cloud (no local Docker needed).
# Run `az login` first. Idempotent: re-running updates the existing app.
#
# Usage:
#   ./deploy/deploy-azure.sh
#   RESOURCE_GROUP=rg-iac-mcp LOCATION=westeurope APP_NAME=iac-mcp ./deploy/deploy-azure.sh
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-iac-mcp}"
LOCATION="${LOCATION:-eastus}"
APP_NAME="${APP_NAME:-iac-mcp-server}"
ENV_NAME="${ENV_NAME:-iac-mcp-env}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Checking Azure login..."
az account show --only-show-errors >/dev/null

echo "==> Ensuring Container Apps extension + providers..."
az extension add --name containerapp --upgrade --only-show-errors >/dev/null
az provider register -n Microsoft.App --wait --only-show-errors >/dev/null
az provider register -n Microsoft.OperationalInsights --wait --only-show-errors >/dev/null

echo "==> Deploying '$APP_NAME' to '$RESOURCE_GROUP' ($LOCATION). This builds the image in Azure..."
az containerapp up \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --environment "$ENV_NAME" \
  --source "$REPO_ROOT" \
  --target-port 8000 \
  --ingress external \
  --env-vars MCP_TRANSPORT=http PORT=8000

FQDN="$(az containerapp show -n "$APP_NAME" -g "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)"
echo
echo "==================================================================="
echo " Deployed. MCP endpoint:  https://${FQDN}/mcp"
echo "==================================================================="
echo
echo "Connect Claude Code (user scope):"
echo "  claude mcp add --transport http --scope user acme-iac-platform https://${FQDN}/mcp"
echo
echo "WARNING: ingress is public and UNAUTHENTICATED — fine for a short test,"
echo "         add auth before any real org use (see deploy/README.md)."
echo
echo "Tear everything down:  ./deploy/destroy-azure.sh"
