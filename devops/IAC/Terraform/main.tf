
data "azuredevops_project" "teamproject" {
  name = var.TeamProjectName
}

locals {
  static_secrets = [
    {
      key   = "APPLICATIONINSIGHTS-CONNECTION-STRING"
      value = try(module.appinsights[0].connection_string, "")
    },
    {
      key   = "AzureWebJobsStorage--accountName"
      value = try(module.storage_account[0].name, "")
    },
  ]

  ado_vars = [
    {
      key   = "keyvault_url"
      value = try(module.keyvault[0].vault_uri, "")
    },
    {
      key   = "APPLICATIONINSIGHTS_CONNECTION_STRING"
      value = try(module.appinsights[0].connection_string, "")
    },
    {
      key   = "APPLICATIONINSIGHTS_AUTHENTICATION_STRING"
      value = try(format("Authorization=AAD;ClientId=%s", var.managed_identity_sp_client_id), "")
    },
    {
      key   = "appinsights_key"
      value = try(module.appinsights[0].instrumentation_key, "")
    },
    {
      key   = "AzureWebJobsStorage--accountName"
      value = try(module.storage_account[0].name, "")
    },
    {
      key   = "namespace_name"
      value = try(var.namespace_name, "")
    },
    {
      key   = "k8s_namespace_account_name"
      value = try(var.k8s_namespace_account_name, "")
    },
    {
      key       = "app-secret-1"
      value     = "secret-value-1"
      is_secret = true
    }
  ]

}


module "ado_environment" {
  source           = "git::https://dev.azure.com/bupaaunz/Internal%20Developer%20Portal/_git/IDP-terraform-patterns//ado_environment?ref=matt"
  app_name         = var.app_name
  environment_name = var.environment_name
  TeamProjectName  = var.TeamProjectName

  providers = { azuredevops = azuredevops }
}

resource "azuredevops_pipeline_authorization" "adoenv_auth" {
  project_id  = data.azuredevops_project.teamproject.id
  resource_id = module.ado_environment.id
  type        = "environment"
  depends_on  = [time_sleep.wait_a_minute, module.ado_environment]
}

module "keyvault" {
  count                           = var.keyvault_enabled == true ? 1 : 0
  source                          = "git::https://dev.azure.com/bupaaunz/Internal%20Developer%20Portal/_git/IDP-terraform-patterns//keyvault?ref=matt"
  app_short_name                  = var.app_short_name
  environment_name                = var.environment_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  endpoint_subnet_name            = var.endpoint_subnet_name
  endpoint_vnet_name              = var.endpoint_vnet_name
  endpoint_vnet_resource_group    = var.endpoint_vnet_resource_group
  writer_keyvault_object_ids      = var.writer_keyvault_object_ids
  reader_keyvault_object_ids      = var.reader_keyvault_object_ids
  service_connection_sp_object_id = var.service_connection_sp_object_id

  providers = { azurerm.dns = azurerm.dns }
}


module "appinsights" {
  count                   = var.appinsights_enabled == true ? 1 : 0
  source                  = "git::https://dev.azure.com/bupaaunz/Internal%20Developer%20Portal/_git/IDP-terraform-patterns//appinsights?ref=matt"
  app_name                = var.app_name
  environment_name        = var.environment_name
  resource_group_name     = var.resource_group_name
  location                = var.location
  law_name                = var.law_name
  law_resource_group_name = var.law_resource_group_name

  providers = { azurerm.law = azurerm.law }
}


module "storage_account" {
  count                         = var.storage_account_enabled == true ? 1 : 0
  source                        = "git::https://dev.azure.com/bupaaunz/Internal%20Developer%20Portal/_git/IDP-terraform-patterns//storage_account?ref=matt"
  app_short_name                = var.app_short_name
  environment_name              = var.environment_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  endpoint_subnet_name          = var.endpoint_subnet_name
  endpoint_vnet_name            = var.endpoint_vnet_name
  endpoint_vnet_resource_group  = var.endpoint_vnet_resource_group
  blob_privateendpoint_enabled  = true
  queue_privateendpoint_enabled = false
  table_privateendpoint_enabled = false

  providers = { azurerm.dns = azurerm.dns }
}

resource "time_sleep" "wait_a_minute" {
  depends_on      = [module.keyvault, module.appinsights, module.storage_account]
  create_duration = "60s"
}

module "keyvault_secrets" {
  count          = var.keyvault_enabled == true ? 1 : 0
  source         = "git::https://dev.azure.com/bupaaunz/Internal%20Developer%20Portal/_git/IDP-terraform-patterns//keyvault_secrets?ref=matt"
  keyvault_id    = module.keyvault[0].id
  static_secrets = local.static_secrets
  depends_on     = [time_sleep.wait_a_minute, module.keyvault, module.appinsights, module.storage_account]
}

module "cosmosdb_documentdb" {
  count                        = var.cosmos_documentdb_enabled == true ? 1 : 0
  source                       = "git::https://dev.azure.com/bupaaunz/Internal%20Developer%20Portal/_git/IDP-terraform-patterns//cosmos-documentdb?ref=matt"
  app_name                     = var.app_name
  environment_name             = var.environment_name
  resource_group_name          = var.resource_group_name
  location                     = var.location
  endpoint_subnet_name         = var.endpoint_subnet_name
  endpoint_vnet_name           = var.endpoint_vnet_name
  endpoint_vnet_resource_group = var.endpoint_vnet_resource_group
  dbs                          = var.dbs

  providers = { azurerm.dns = azurerm.dns }
}

# Assign custom CosmosDBReadWriteRole to the managed identity
resource "azurerm_cosmosdb_sql_role_assignment" "assign_rw_role" {
  count               = var.cosmos_documentdb_enabled == true && var.managed_identity_sp_object_id != null && var.cosmos_role_definition_id != null ? 1 : 0
  resource_group_name = var.resource_group_name
  account_name        = module.cosmosdb_documentdb[0].cosmosdb_name
  role_definition_id  = "${module.cosmosdb_documentdb[0].cosmosdb_id}/sqlRoleDefinitions/${var.cosmos_role_definition_id}"
  principal_id        = var.managed_identity_sp_object_id
  scope               = module.cosmosdb_documentdb[0].cosmosdb_id
}

module "ado_variablegroup" {
  source           = "git::https://dev.azure.com/bupaaunz/Internal%20Developer%20Portal/_git/IDP-terraform-patterns//ado_variablegroup?ref=matt"
  app_name         = var.app_name
  environment_name = var.environment_name
  TeamProjectName  = var.TeamProjectName
  variables        = local.ado_vars
  depends_on       = [module.keyvault_secrets]

  providers = { azuredevops = azuredevops }
}
