variable "location" {
  type        = string
  description = "The Azure Region in which all resources will be created."
  default     = "australiaeast"
}

variable "app_name" {
  type = string
}

variable "app_short_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "endpoint_subnet_name" {
  type = string
}

variable "endpoint_vnet_name" {
  type = string
}

variable "endpoint_vnet_resource_group" {
  type = string
}

variable "law_name" {
  type    = string
  default = "integrationfabric-test-law01"
}

variable "law_resource_group_name" {
  type    = string
  default = "integrationfabric-test-rg01"
}

variable "environment_name" {
  type = string
}

variable "identity_name" {
  type = string
}

variable "PAT" {
  type = string
}


variable "writer_keyvault_object_ids" {
  type        = list(string)
  default     = ["0b6bbb5e-a7c0-4e70-b8eb-2f4ff3de15a0"]
  description = "List of key permissions"
}


variable "reader_keyvault_object_ids" {
  type        = list(string)
  default     = []
  description = "List of key permissions"
}

variable "static_secrets" {
  type = list(object({
    key   = string
    value = string
  }))
  default     = []
  description = "static values to be stored in the keyvault secrets"
}



variable "TeamProjectName" {
  type = string
}

variable "service_connection_sp_object_id" {
  type        = string
  description = "service connection object id"
  default     = ""
}


variable "managed_identity_sp_object_id" {
  type        = string
  description = "Managed Identity object id"
  default     = null
}

variable "managed_identity_sp_client_id" {
  type        = string
  description = "Managed Identity client id"
  default     = null
}

variable "dns_subscription" {
  type        = string
  description = "The subscription holding the DNS Zone"
  default     = "966fb436-5647-427d-bc27-44d3be41dbb8"
}


variable "managed_identity_name" {
  type        = string
  description = "managed identity name"
  default     = null
}


variable "keyvault_enabled" {
  type        = bool
  description = "Enable KeyVault"
  default     = true
}

variable "appinsights_enabled" {
  type        = bool
  description = "Enable KeyVault"
  default     = true
}

variable "storage_account_enabled" {
  type        = bool
  description = "Enable KeyVault"
  default     = true
}

variable "namespace_name" {
  type        = string
  description = "Kubernetes namespace name"
  default     = null
}


variable "k8s_namespace_account_name" {
  type        = string
  description = "Kubernetes namespace Service account name"
  default     = null
}

variable "cosmos_documentdb_enabled" {
  type        = bool
  description = "Enable creation of documentDB/cosmos modules"
  default     = false
}

variable "dbs" {
  type = list(object({
    name       = string
    throughput = optional(number)
  }))
  default = []
}

variable "cosmos_role_definition_id" {
  type        = string
  description = "Cosmos DB custom role definition ID (unique per account)"
  default     = null
}
