<#
.SYNOPSIS
  Tear down the IaC MCP server — deletes the whole resource group.
.EXAMPLE
  .\deploy\destroy-azure.ps1
  .\deploy\destroy-azure.ps1 -ResourceGroup rg-iac-mcp
#>
param(
  [string]$ResourceGroup = "rg-iac-mcp"
)
$ErrorActionPreference = "Stop"

Write-Host "==> Deleting resource group '$ResourceGroup' and ALL resources in it..." -ForegroundColor Yellow
az group delete --name $ResourceGroup --yes --no-wait
Write-Host "Delete initiated (running in background)."
Write-Host "Check status with:  az group show -n $ResourceGroup"
