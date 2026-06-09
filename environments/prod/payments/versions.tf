terraform {
  required_version = ">= 1.11" # administrator_password_wo (write-only args) need 1.11+

  # Remote state on an Azure Storage backend (SEC-STATE-001). The values below are
  # illustrative defaults for the published template. To use YOUR real state account
  # WITHOUT editing this file, override at init time:
  #
  #   terraform init -backend-config=backend.local.hcl
  #
  # (See backend.local.hcl.example — copy it to backend.local.hcl; it is gitignored.)
  # The backing storage account is bootstrap infra that must already exist with blob
  # versioning + soft-delete enabled; use_azuread_auth avoids shared-key (SEC-STORAGE-002).
  backend "azurerm" {
    resource_group_name  = "acme-prod-tfstate-rg01"
    storage_account_name = "acmeprodtfstatest01"
    container_name       = "tfstate"
    key                  = "payments/prod/terraform.tfstate"
    use_azuread_auth     = true
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
}
