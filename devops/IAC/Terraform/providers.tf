terraform {
  backend "azurerm" {}
  # backend "local" { path = "./states/terraform.tfstate" }
  required_version = ">=1.5.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.72.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 2.45.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = ">= 1.12.1"
    }
    azuredevops = {
      source  = "microsoft/azuredevops"
      version = ">=0.4.0"
    }
  }
}


provider "azurerm" {
  skip_provider_registration = true
  storage_use_azuread        = true
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
    app_configuration {
      purge_soft_delete_on_destroy = false
      recover_soft_deleted         = false
    }
  }
}


provider "azurerm" {
  features {}
  skip_provider_registration = true
  // resource_provider_registrations = none
  alias           = "dns"
  subscription_id = "966fb436-5647-427d-bc27-44d3be41dbb8"
}

provider "azurerm" {
  features {}
  skip_provider_registration = true
  alias                      = "law"
  subscription_id            = "ee604705-a4ac-4132-8ef4-d69c441d9038"
}



provider "azuredevops" {
  # Remember to specify the org service url and personal access token details below
  org_service_url       = "https://bupaaunz.visualstudio.com/"
  personal_access_token = var.PAT
}

# provider "kubernetes" {
#   config_path    = "~/.kube/config"
#   config_context = format("%s-%s", var.AKSClusterName, "admin")
# }
