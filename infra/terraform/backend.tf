# Remote state is required for a real environment. Supply the private bucket and
# environment-specific prefix at init time; CI validation uses -backend=false.
terraform {
  backend "gcs" {}
}
