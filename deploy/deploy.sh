#!/usr/bin/env bash
#
# Deploy SusuBook to Cloud Run.
#
# Prerequisites (see deploy/README.md):
#   - gcloud CLI authenticated:  gcloud auth login
#   - PostgreSQL running on a Compute Engine VM in the default VPC
#   - Secret holding the database password (default name: susu-db-password)
#
# The project defaults to the gcloud CLI's configured project; override with
# PROJECT_ID=... if needed.
#
# Usage:
#   ./deploy/deploy.sh setup      # one-time: APIs, registry, signing key, IAM
#   ./deploy/deploy.sh deploy     # build image and deploy the service
#   ./deploy/deploy.sh db-init    # create the schema
#   ./deploy/deploy.sh seed       # load demo accounts and data
#   ./deploy/deploy.sh url        # print the live URL

set -euo pipefail

# Defaults to the gcloud CLI's configured project.
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
: "${PROJECT_ID:?No project set. Run: gcloud config set project YOUR_PROJECT}"

REGION="${REGION:-us-central1}"      # must match the VM's region so Cloud Run
SERVICE="${SERVICE:-susubook}"       # draws addresses from the same subnet as
REPO="${REPO:-susubook}"             # the firewall rule allows (10.128.0.0/20)

# Database connection. Only the password is a secret; the rest is ordinary
# configuration and stays legible in the service definition.
DB_SECRET="${DB_SECRET:-susu-db-password}"
DB_HOST="${DB_HOST:-10.128.0.6}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-susu_book}"
DB_USER="${DB_USER:-susu_app}"
KEY_SECRET="${KEY_SECRET:-susubook-secret-key}"
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
  --set-secrets "DB_PASSWORD=${DB_SECRET}:latest,SECRET_KEY=${KEY_SECRET}:latest"
)

ENV_FLAGS=(
  --set-env-vars "FLASK_ENV=production,FLASK_APP=app,DB_HOST=${DB_HOST},DB_PORT=${DB_PORT},DB_NAME=${DB_NAME},DB_USER=${DB_USER}"
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

  step "Creating the session signing key if it does not exist"
  if gcloud secrets describe "$KEY_SECRET" --project "$PROJECT_ID" >/dev/null 2>&1; then
    green "  ${KEY_SECRET} already exists"
  else
    python3 -c "import secrets; print(secrets.token_hex(32))" | \
      gcloud secrets create "$KEY_SECRET" --data-file=- --project "$PROJECT_ID" >/dev/null
    green "  created ${KEY_SECRET}"
  fi

  step "Granting the runtime service account access to the secrets"
  local project_number sa
  project_number="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
  sa="${project_number}-compute@developer.gserviceaccount.com"
  for secret in "$DB_SECRET" "$KEY_SECRET"; do
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
    "${ENV_FLAGS[@]}" \
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
  local verb="create" args_csv
  args_csv="$(IFS=,; echo "$*")"   # gcloud --args wants a comma-separated list
  gcloud run jobs describe "$name" --region "$REGION" --project "$PROJECT_ID" \
    >/dev/null 2>&1 && verb="update"

  gcloud run jobs "$verb" "$name" \
    --image "${IMAGE}:${TAG}" \
    --region "$REGION" \
    "${VPC_FLAGS[@]}" \
    "${SECRET_FLAGS[@]}" \
    "${ENV_FLAGS[@]}" \
    --command flask \
    --args "$args_csv" \
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
  db-init) run_job susubook-db-init db-init ;;
  seed)    run_job susubook-seed seed ;;
  url)     gcloud run services describe "$SERVICE" --region "$REGION" \
             --project "$PROJECT_ID" --format='value(status.url)' ;;
  logs)    gcloud run services logs read "$SERVICE" --region "$REGION" \
             --project "$PROJECT_ID" --limit 50 ;;
  *)       echo "Usage: PROJECT_ID=... $0 {setup|build|deploy|db-init|seed|url|logs}" >&2
           exit 1 ;;
esac
