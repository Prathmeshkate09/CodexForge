locals {
  resource_prefix = "${var.name_prefix}-${var.environment}"
  # IAM service-account IDs are limited to 30 characters. Keep room for the
  # longest suffix ("-terraform") and append a stable hash to prevent a
  # collision between long prefixes while resource names use the full prefix.
  service_account_id_prefix = "${substr(var.name_prefix, 0, 12)}-${substr(sha1(local.resource_prefix), 0, 7)}"
  # WIF pool IDs/display names have a 32-character limit, and GCS bucket names
  # must be globally unique and at most 63 characters. Keep the externally
  # visible names bounded even when callers choose the longest valid prefix.
  github_wif_pool_id  = "${substr(local.resource_prefix, 0, 20)}-${substr(sha1(local.resource_prefix), 0, 8)}"
  artifact_bucket_name = "${substr(local.resource_prefix, 0, 20)}-${substr(sha1("${var.project_id}:${local.resource_prefix}"), 0, 12)}-artifacts"
  # VPC connector names are especially short (hyphens count twice); use a
  # deterministic 20-character-effective name rather than the full prefix.
  vpc_connector_name = "${substr(local.resource_prefix, 0, 12)}-${substr(sha1(local.resource_prefix), 0, 6)}"
  labels = {
    application = "codexforge"
    environment = var.environment
    managed_by  = "terraform"
  }
  required_services = toset([
    "artifactregistry.googleapis.com",
    "cloudtasks.googleapis.com",
    "compute.googleapis.com",
    "iamcredentials.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "vpcaccess.googleapis.com",
    "iam.googleapis.com",
  ])
}

data "google_project" "current" {}

resource "google_project_service" "required" {
  for_each           = local.required_services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "private" {
  name                    = "${local.resource_prefix}-private"
  auto_create_subnetworks = true
  depends_on              = [google_project_service.required]
}

resource "google_compute_global_address" "private_services" {
  name          = "${local.resource_prefix}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.private.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.private.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

resource "google_vpc_access_connector" "run" {
  name          = local.vpc_connector_name
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.private.name
  min_instances = 2
  max_instances = 3
  depends_on    = [google_project_service.required]
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "${local.resource_prefix}-containers"
  description   = "Immutable CodexForge container images."
  format        = "DOCKER"
  labels        = local.labels
  depends_on    = [google_project_service.required]
}

resource "google_storage_bucket" "artifacts" {
  name                        = local.artifact_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = var.artifact_retention_days
    }
  }
}

resource "google_sql_database_instance" "postgres" {
  name                = "${local.resource_prefix}-postgres"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.enable_deletion_protection

  settings {
    tier              = var.cloud_sql_tier
    availability_type = var.environment == "production" ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = false
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.private.id
    }

    user_labels = local.labels
  }

  depends_on = [google_service_networking_connection.private_vpc]
}

resource "google_sql_database" "application" {
  name     = "codexforge"
  instance = google_sql_database_instance.postgres.name
}

resource "google_redis_instance" "cache" {
  name               = "${local.resource_prefix}-redis"
  tier               = "BASIC"
  memory_size_gb     = var.redis_memory_size_gb
  region             = var.region
  redis_version      = "REDIS_7_0"
  authorized_network = google_compute_network.private.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  display_name       = "CodexForge ${var.environment} cache"
  labels             = local.labels
  depends_on         = [google_service_networking_connection.private_vpc]
}

resource "google_cloud_tasks_queue" "worker" {
  name     = "${local.resource_prefix}-worker"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 2
  }

  retry_config {
    max_attempts       = 8
    max_retry_duration = "3600s"
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 5
  }
}

resource "google_service_account" "api" {
  account_id   = "${local.service_account_id_prefix}-api"
  display_name = "CodexForge API (${var.environment})"
}

resource "google_service_account" "worker" {
  account_id   = "${local.service_account_id_prefix}-worker"
  display_name = "CodexForge controlled worker (${var.environment})"
}

resource "google_service_account" "task_invoker" {
  account_id   = "${local.service_account_id_prefix}-tasks"
  display_name = "Cloud Tasks OIDC invoker (${var.environment})"
}

resource "google_service_account" "terraform" {
  account_id   = "${local.service_account_id_prefix}-terraform"
  display_name = "CodexForge Terraform deployer (${var.environment})"
}

resource "google_service_account_iam_member" "cloud_tasks_token_creator" {
  service_account_id = google_service_account.task_invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudtasks.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "api_cloud_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_tasks" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# The API creates OIDC-authenticated Cloud Tasks using this identity. Cloud
# Tasks requires the enqueuer to have iam.serviceAccounts.actAs on the named
# service account; grant it only on this task-invoker identity.
resource "google_service_account_iam_member" "api_uses_task_invoker" {
  service_account_id = google_service_account.task_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "api_artifact_reader" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "worker_artifact_writer" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_cloud_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${local.resource_prefix}-database-url"
  replication {
    auto {}
  }
  labels     = local.labels
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "redis_url" {
  secret_id = "${local.resource_prefix}-redis-url"
  replication {
    auto {}
  }
  labels     = local.labels
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "${local.resource_prefix}-jwt-secret"
  replication {
    auto {}
  }
  labels     = local.labels
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "github_app_private_key" {
  secret_id = "${local.resource_prefix}-github-app-private-key"
  replication {
    auto {}
  }
  labels     = local.labels
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "github_webhook_secret" {
  secret_id = "${local.resource_prefix}-github-webhook-secret"
  replication {
    auto {}
  }
  labels     = local.labels
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "${local.resource_prefix}-openai-api-key"
  replication {
    auto {}
  }
  labels     = local.labels
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "safety_identifier_salt" {
  secret_id = "${local.resource_prefix}-safety-identifier-salt"
  replication {
    auto {}
  }
  labels     = local.labels
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "api_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_redis_url" {
  secret_id = google_secret_manager_secret.redis_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_jwt_secret" {
  secret_id = google_secret_manager_secret.jwt_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_github_key" {
  secret_id = google_secret_manager_secret.github_app_private_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_github_webhook" {
  secret_id = google_secret_manager_secret.github_webhook_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_redis_url" {
  secret_id = google_secret_manager_secret.redis_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_github_key" {
  secret_id = google_secret_manager_secret.github_app_private_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_openai_key" {
  secret_id = google_secret_manager_secret.openai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_safety_identifier_salt" {
  secret_id = google_secret_manager_secret.safety_identifier_salt.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = local.github_wif_pool_id
  display_name              = "CodexForge GitHub ${var.environment}"
  description               = "Federates only the configured GitHub repository through OIDC."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions OIDC"
  attribute_condition                = "assertion.repository == '${var.github_repository}' && assertion.ref == '${var.github_wif_ref}'"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.ref"        = "assertion.ref"
    "attribute.repository" = "assertion.repository"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_terraform_wif" {
  service_account_id = google_service_account.terraform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# Bootstrap this identity with a separately reviewed administrator process. Then narrow
# its permissions to the resources managed here; do not use service-account JSON keys.

resource "google_cloud_run_v2_service" "api" {
  count    = var.enable_runtime_services ? 1 : 0
  name     = "${local.resource_prefix}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  labels   = local.labels

  template {
    service_account = google_service_account.api.email
    timeout         = "300s"

    scaling {
      min_instance_count = 0
      max_instance_count = var.api_max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.run.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name = "CODEXFORGE_ENVIRONMENT"
        value = var.environment
      }
      env {
        name = "CODEXFORGE_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CODEXFORGE_REDIS_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.redis_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CODEXFORGE_JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "CODEXFORGE_JWT_JWKS_URL"
        value = var.jwt_jwks_url
      }
      env {
        name  = "CODEXFORGE_JWT_ISSUER"
        value = var.jwt_issuer
      }
      env {
        name  = "CODEXFORGE_JWT_AUDIENCE"
        value = var.jwt_audience
      }
      env {
        name  = "CODEXFORGE_CORS_ALLOWED_ORIGINS"
        value = jsonencode(var.cors_allowed_origins)
      }
    }
  }

  lifecycle {
    precondition {
      condition     = length(trimspace(var.api_image)) > 0
      error_message = "api_image must be a digest-pinned immutable image URI when enable_runtime_services is true."
    }
    precondition {
      condition = !var.enable_runtime_services || (
        length(trimspace(var.jwt_jwks_url)) > 0 &&
        length(trimspace(var.jwt_issuer)) > 0 &&
        length(trimspace(var.jwt_audience)) > 0 &&
        length(var.cors_allowed_origins) > 0
      )
      error_message = "Runtime API deployment requires JWKS URL, issuer, audience, and at least one explicit CORS origin."
    }
  }
}

resource "google_cloud_run_v2_service" "worker" {
  count    = var.enable_runtime_services && var.enable_worker_service ? 1 : 0
  name     = "${local.resource_prefix}-worker"
  location = var.region
  # Cloud Tasks reaches this service using OIDC. It remains unauthenticated only
  # if an explicit allUsers IAM binding is added, which this configuration never does.
  ingress  = "INGRESS_TRAFFIC_ALL"
  labels   = local.labels

  template {
    service_account = google_service_account.worker.email
    timeout         = "900s"

    scaling {
      min_instance_count = 0
      max_instance_count = var.worker_max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.run.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.worker_image

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name = "CODEXFORGE_ENVIRONMENT"
        value = var.environment
      }
      env {
        name = "CODEXFORGE_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CODEXFORGE_OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openai_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CODEXFORGE_SAFETY_IDENTIFIER_SALT"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.safety_identifier_salt.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = length(trimspace(var.worker_image)) > 0
      error_message = "worker_image must be a digest-pinned immutable image URI when enable_runtime_services is true."
    }
  }
}

# A browser SPA cannot present Google IAM credentials to invoke Cloud Run. When
# deliberately enabled, this only opens the transport layer; FastAPI still
# validates every business request's Firebase/OAuth2 bearer token.
resource "google_cloud_run_v2_service_iam_member" "public_api_invoker" {
  count    = var.enable_runtime_services && var.allow_public_api_invocation ? 1 : 0
  name     = google_cloud_run_v2_service.api[0].name
  location = google_cloud_run_v2_service.api[0].location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "task_invokes_worker" {
  count    = var.enable_runtime_services && var.enable_worker_service ? 1 : 0
  name     = google_cloud_run_v2_service.worker[0].name
  location = google_cloud_run_v2_service.worker[0].location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.task_invoker.email}"
}
