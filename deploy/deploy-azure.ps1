<#
.SYNOPSIS
  Deploy the IaC MCP server to Azure Container Apps (HTTP/streamable-http).

.DESCRIPTION
  Builds the image from the repo Dockerfile in the cloud (no local Docker needed)
  and deploys it as a Container App with external ingress on /mcp. Run `az login`
  first. Idempotent: re-running updates the existing app.

.EXAMPLE
  .\deploy\deploy-azure.ps1
  .\deploy\deploy-azure.ps1 -ResourceGroup rg-iac-mcp -Location westeurope -AppName iac-mcp
#>
param(
  [string]$ResourceGroup = "rg-iac-mcp",
  [string]$Location      = "eastus",
  [string]$AppName       = "iac-mcp-server",
  [string]$EnvName       = "iac-mcp-env"
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent

Write-Host "==> Checking Azure login..." -ForegroundColor Cyan
az account show --only-show-errors | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Not logged in. Run 'az login' first." }

Write-Host "==> Ensuring Container Apps extension + providers..." -ForegroundColor Cyan
az extension add --name containerapp --upgrade --only-show-errors | Out-Null
az provider register -n Microsoft.App --wait --only-show-errors | Out-Null
az provider register -n Microsoft.OperationalInsights --wait --only-show-errors | Out-Null

Write-Host "==> Deploying '$AppName' to '$ResourceGroup' ($Location). This builds the image in Azure..." -ForegroundColor Cyan
az containerapp up `
  --name $AppName `
  --resource-group $ResourceGroup `
  --location $Location `
  --environment $EnvName `
  --source $repoRoot `
  --target-port 8000 `
  --ingress external `
  --env-vars MCP_TRANSPORT=http PORT=8000

$fqdn = az containerapp show -n $AppName -g $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Green
Write-Host " Deployed. MCP endpoint:  https://$fqdn/mcp" -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Connect Claude Code (user scope, available in every project):"
Write-Host "  claude mcp add --transport http --scope user acme-iac-platform https://$fqdn/mcp"
Write-Host ""
Write-Host "GitHub Copilot (.vscode/mcp.json):"
Write-Host '  { "servers": { "acme-iac-platform": { "type": "http", "url": "https://' + $fqdn + '/mcp" } } }'
Write-Host ""
Write-Host "WARNING: ingress is public and UNAUTHENTICATED — fine for a short test," -ForegroundColor Yellow
Write-Host "         add auth before any real org use (see deploy/README.md)." -ForegroundColor Yellow
Write-Host ""
Write-Host "Tear everything down:  .\deploy\destroy-azure.ps1 -ResourceGroup $ResourceGroup"
