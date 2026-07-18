output "artifact_registry_repository" {
  description = "Artifact Registry repository for immutable application images."
  value       = google_artifact_registry_repository.containers.name
}

output "artifact_bucket_name" {
  description = "Private bucket for sanitized, expiring artifacts."
  value       = google_storage_bucket.artifacts.name
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name; database URLs belong in Secret Manager, not output values."
  value       = google_sql_database_instance.postgres.connection_name
}

output "redis_host" {
  description = "Memorystore host; compose the Redis URL in Secret Manager outside Terraform state."
  value       = google_redis_instance.cache.host
}

output "worker_queue_name" {
  description = "Cloud Tasks queue name for controlled work."
  value       = google_cloud_tasks_queue.worker.name
}

output "api_service_account" {
  description = "API runtime service account email."
  value       = google_service_account.api.email
}

output "worker_service_account" {
  description = "Controlled worker service account email."
  value       = google_service_account.worker.email
}

output "task_oidc_service_account" {
  description = "Service account Cloud Tasks uses to invoke the internal worker."
  value       = google_service_account.task_invoker.email
}

output "github_workload_identity_provider" {
  description = "WIF provider resource name for GitHub Actions environment variables."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "terraform_service_account" {
  description = "Service account intended for GitHub Actions Terraform federation."
  value       = google_service_account.terraform.email
}

output "api_cloud_run_uri" {
  description = "API URI only when runtime services are intentionally enabled."
  value       = var.enable_runtime_services ? google_cloud_run_v2_service.api[0].uri : null
}
