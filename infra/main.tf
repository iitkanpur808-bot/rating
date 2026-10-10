terraform {
  required_version = ">= 1.5"
  backend "azurerm" {
    resource_group_name  = "IIT-smartclassroom"
    storage_account_name = "stclasspulsetf"
    container_name       = "tfstate"
    key                  = "ideation-scoring.tfstate"
  }
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "resource_group_name" { default = "IIT-smartclassroom" }
variable "location" { default = "southindia" }
variable "acr_name" { default = "classpulseacrbxev55" }
variable "image_tag" { default = "latest" }
variable "google_client_id" { sensitive = true }
variable "google_client_secret" { sensitive = true }
variable "secret_key" { sensitive = true }
variable "admin_emails" { description = "Comma-separated admin Gmail addresses" }

data "azurerm_resource_group" "rg" {
  name = var.resource_group_name
}

data "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = var.resource_group_name
}

resource "azurerm_storage_share" "data" {
  name               = "ideation-data"
  storage_account_id = azurerm_storage_account.data.id
  quota              = 5
}

resource "azurerm_storage_account" "data" {
  name                     = "stideationscoring"
  resource_group_name      = data.azurerm_resource_group.rg.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_container_app_environment" "env" {
  name                = "ideation-scoring-env"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg.name
}

resource "azurerm_container_app_environment_storage" "data" {
  name                         = "ideation-data"
  container_app_environment_id = azurerm_container_app_environment.env.id
  account_name                 = azurerm_storage_account.data.name
  share_name                   = azurerm_storage_share.data.name
  access_key                   = azurerm_storage_account.data.primary_access_key
  access_mode                  = "ReadWrite"
}

resource "azurerm_container_app" "app" {
  name                         = "ideation-scoring"
  resource_group_name          = data.azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  revision_mode                = "Single"

  registry {
    server               = data.azurerm_container_registry.acr.login_server
    username             = data.azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = data.azurerm_container_registry.acr.admin_password
  }
  secret {
    name  = "google-client-secret"
    value = var.google_client_secret
  }
  secret {
    name  = "flask-secret-key"
    value = var.secret_key
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    volume {
      name         = "data"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.data.name
    }

    container {
      name   = "app"
      image  = "${data.azurerm_container_registry.acr.login_server}/ideation-scoring:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      volume_mounts {
        name = "data"
        path = "/data"
      }

      env {
        name        = "SECRET_KEY"
        secret_name = "flask-secret-key"
      }
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_client_id
      }
      env {
        name        = "GOOGLE_CLIENT_SECRET"
        secret_name = "google-client-secret"
      }
      env {
        name  = "ADMIN_EMAILS"
        value = var.admin_emails
      }
      env {
        name  = "DB_PATH"
        value = "/data/ideation.db"
      }
      env {
        name  = "PORT"
        value = "8000"
      }
    }
  }
}

output "app_url" {
  value = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}
