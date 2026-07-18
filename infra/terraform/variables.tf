variable "project_id" {
  description = "Google Cloud project ID for one isolated CodexForge environment."
  type        = string

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "project_id must be a non-empty Google Cloud project ID."
  }
}

variable "region" {
  description = "Primary Google Cloud region. Choose a region supported by Cloud Run, Cloud SQL, Memorystore, and Artifact Registry."
  type        = string
  default     = "asia-south1"
}

variable "environment" {
  description = "Deployment environment name used in resource names and labels."
  type        = string
  default     = "development"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "name_prefix" {
  description = "Short lowercase prefix for globally identifiable CodexForge resources."
  type        = string
  default     = "codexforge"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.name_prefix))
    error_message = "name_prefix must be 3-21 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "github_repository" {
  description = "Exact GitHub owner/repository permitted to federate GitHub Actions identities."
  type        = string
  default     = "Prathmeshkate09/CodexForge"
}

variable "github_wif_ref" {
  description = "Only this protected Git ref may federate the Terraform GitHub Actions identity."
  type        = string
  default     = "refs/heads/main"

  validation {
    condition     = can(regex("^refs/(heads|tags)/[A-Za-z0-9._/-]+$", var.github_wif_ref))
    error_message = "github_wif_ref must be an explicit Git ref such as refs/heads/main."
  }
}

variable "artifact_retention_days" {
  description = "Age at which sanitized private artifacts are automatically deleted."
  type        = number
  default     = 30

  validation {
    condition     = var.artifact_retention_days >= 1 && var.artifact_retention_days <= 365
    error_message = "artifact_retention_days must be between 1 and 365."
  }
}

variable "cloud_sql_tier" {
  description = "Cloud SQL tier. Size from measured load; use a production-appropriate HA tier before production apply."
  type        = string
  default     = "db-custom-2-7680"
}

variable "redis_memory_size_gb" {
  description = "Memorystore Redis memory capacity in GiB."
  type        = number
  default     = 1
}

variable "enable_deletion_protection" {
  description = "Protect Cloud SQL from accidental Terraform deletion. Keep true for every persistent environment."
  type        = bool
  default     = true
}

variable "enable_runtime_services" {
  description = "Create the Cloud Run API service. Keep false until immutable images and Secret Manager versions are reviewed."
  type        = bool
  default     = false
}

variable "enable_worker_service" {
  description = "Create the controlled Cloud Tasks worker only after its task receiver and isolation policy are implemented and reviewed."
  type        = bool
  default     = false
}

variable "allow_public_api_invocation" {
  description = "Allow public transport access to Cloud Run so a Firebase SPA can reach it; FastAPI bearer-token enforcement remains mandatory."
  type        = bool
  default     = false
}

variable "api_image" {
  description = "Immutable Artifact Registry image URI for the FastAPI API. Required when enable_runtime_services is true."
  type        = string
  default     = ""

  validation {
    condition = trimspace(var.api_image) == "" || can(
      regex("^.+@sha256:[a-f0-9]{64}$", trimspace(var.api_image))
    )
    error_message = "api_image must be empty or a digest-pinned image URI ending in @sha256:<64 lowercase hex characters>."
  }
}

variable "worker_image" {
  description = "Immutable Artifact Registry image URI for the controlled worker. Required only when enable_worker_service is true."
  type        = string
  default     = ""

  validation {
    condition = trimspace(var.worker_image) == "" || can(
      regex("^.+@sha256:[a-f0-9]{64}$", trimspace(var.worker_image))
    )
    error_message = "worker_image must be empty or a digest-pinned image URI ending in @sha256:<64 lowercase hex characters>."
  }
}

variable "jwt_jwks_url" {
  description = "Trusted HTTPS JWKS URL used to validate production OAuth2/Firebase RS256 bearer tokens."
  type        = string
  default     = ""

  validation {
    condition = trimspace(var.jwt_jwks_url) == "" || can(
      regex(
        "^https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?(?:/[A-Za-z0-9._~:/!$&'()*+,;=@%-]*)?$",
        trimspace(var.jwt_jwks_url)
      )
    )
    error_message = "jwt_jwks_url must be empty or an absolute HTTPS JWKS URL without userinfo, query, or fragment."
  }
}

variable "jwt_issuer" {
  description = "Exact trusted issuer for production bearer tokens."
  type        = string
  default     = ""
}

variable "jwt_audience" {
  description = "Exact trusted audience for production bearer tokens."
  type        = string
  default     = ""
}

variable "cors_allowed_origins" {
  description = "Explicit browser origins allowed to call the API; wildcards are forbidden by application configuration."
  type        = list(string)
  default     = []

  validation {
    condition     = !contains(var.cors_allowed_origins, "*")
    error_message = "cors_allowed_origins must not contain a wildcard."
  }
}

variable "api_max_instances" {
  description = "Cloud Run upper instance limit for the API."
  type        = number
  default     = 10
}

variable "worker_max_instances" {
  description = "Cloud Run upper instance limit for controlled worker jobs. Keep bounded to provider/test-runner capacity."
  type        = number
  default     = 10
}
