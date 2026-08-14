#!/usr/bin/env bash
#
# Deploy SusuBook to Cloud Run.
#
# Prerequisites (see deploy/README.md):
#   - gcloud CLI authenticated:  gcloud auth login
#   - PostgreSQL running on a Compute Engine VM in the default VPC
#   - Secrets created:  susubook-database-url, susubook-secret-key
#
# Usage:
#   PROJECT_ID=your-project ./deploy/deploy.sh            # build and deploy
#   PROJECT_ID=your-project ./deploy/deploy.sh setup      # one-time setup
#   PROJECT_ID=your-project ./deploy/deploy.sh db-init    # create schema
#   PROJECT_ID=your-project ./deploy/deploy.sh seed       # load demo data

set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID, e.g. PROJECT_ID=my-project ./deploy/deploy.sh}"

REGION="${REGION:-us-central1}"      # must match the VM's region so Cloud Run
SERVICE="${SERVICE:-susubook}"       # draws addresses from the same subnet as
REPO="${REPO:-susubook}"             # the firewall rule allows (10.128.0.0/20)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}"
TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"

# Direct VPC egress. Reaches the database's private address without a
# Serverless VPC Access connector, which would provision billable instances and
# defeat the point of a free-tier deployment.
VPC_FLAGS=(
  --network=default
  --subnet=default
  --vpc-egress=private-ranges-only
)

SECRET_FLAGS=(
  --set-secrets "DATABASE_URL=susubook-database-url:latest,SECRET_KEY=susubook-secret-key:latest"
)

green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
step()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

setup() {
  step "Enabling required APIs"
  gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com \
    --project "$PROJECT_ID"

  step "Creating Artifact Registry repository (ignored if it exists)"
  gcloud artifacts repositories create "$REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="SusuBook container images" \
    --project "$PROJECT_ID" 2>/dev/null || green "  already exists"

  step "Granting the runtime service account access to the secrets"
  local project_number sa
  project_number="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
  sa="${project_number}-compute@developer.gserviceaccount.com"
  for secret in susubook-database-url susubook-secret-key; do
    gcloud secrets add-iam-policy-binding "$secret" \
      --member="serviceAccount:${sa}" \
      --role=roles/secretmanager.secretAccessor \
      --project "$PROJECT_ID" >/dev/null
    green "  granted on ${secret}"
  done

  green "\nSetup complete. Next: ./deploy/deploy.sh"
}

build() {
  step "Building image ${IMAGE}:${TAG}"
  # Cloud Build rather than a local docker push: no local Docker credential
  # helper to configure, and the build runs on the same architecture as Cloud
  # Run regardless of what this machine is (an arm64 Mac would otherwise
  # produce an image Cloud Run cannot start).
  gcloud builds submit \
    --tag "${IMAGE}:${TAG}" \
    --project "$PROJECT_ID" \
    .
  gcloud artifacts docker tags add "${IMAGE}:${TAG}" "${IMAGE}:latest" \
    --project "$PROJECT_ID" >/dev/null 2>&1 || true
}

deploy_service() {
  step "Deploying Cloud Run service"
  gcloud run deploy "$SERVICE" \
    --image "${IMAGE}:${TAG}" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    "${VPC_FLAGS[@]}" \
    "${SECRET_FLAGS[@]}" \
    --set-env-vars "FLASK_ENV=production" \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 4 \
    --project "$PROJECT_ID"

  local url
  url="$(gcloud run services describe "$SERVICE" --region "$REGION" \
        --project "$PROJECT_ID" --format='value(status.url)')"
  green "\nLive at: ${url}"
  green "Health:  ${url}/healthz"
}

# Admin tasks run as Cloud Run Jobs from the same image, inside the same VPC.
# The database has only a private address, so nothing outside the VPC can reach
# it — including a developer laptop. This is how the schema gets created without
# an SSH tunnel and without the password ever leaving Secret Manager.
upsert_job() {
  local name="$1"; shift
  local verb="create"
  gcloud run jobs describe "$name" --region "$REGION" --project "$PROJECT_ID" \
    >/dev/null 2>&1 && verb="update"

  gcloud run jobs "$verb" "$name" \
    --image "${IMAGE}:${TAG}" \
    --region "$REGION" \
    "${VPC_FLAGS[@]}" \
    "${SECRET_FLAGS[@]}" \
    --set-env-vars "FLASK_ENV=production" \
    --command flask \
    --args "$*" \
    --max-retries 1 \
    --task-timeout 300 \
    --project "$PROJECT_ID" >/dev/null
}

run_job() {
  local name="$1"; shift
  step "Running job: ${name} (${*})"
  upsert_job "$name" "$@"
  gcloud run jobs execute "$name" --region "$REGION" --wait --project "$PROJECT_ID"
}

case "${1:-deploy}" in
  setup)   setup ;;
  build)   build ;;
  deploy)  build; deploy_service ;;
  db-init) run_job susubook-db-init --app app db-init ;;
  seed)    run_job susubook-seed --app app seed ;;
  url)     gcloud run services describe "$SERVICE" --region "$REGION" \
             --project "$PROJECT_ID" --format='value(status.url)' ;;
  logs)    gcloud run services logs read "$SERVICE" --region "$REGION" \
             --project "$PROJECT_ID" --limit 50 ;;
  *)       echo "Usage: PROJECT_ID=... $0 {setup|build|deploy|db-init|seed|url|logs}" >&2
           exit 1 ;;
esac
