#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?Project ID required: ./scripts/deploy_cloud_run.sh <PROJECT_ID> <REGION> <OPENDART_API_KEY> <ADMIN_TOKEN>}"
REGION="${2:-asia-northeast3}"
OPENDART_API_KEY="${3:?provide opendart key}"
ADMIN_TOKEN="${4:?provide admin token}"
IMAGE_PREFIX="gcr.io/${PROJECT_ID}/fund-quiz"

set -x

gcloud builds submit --tag ${IMAGE_PREFIX}-api .

gcloud run deploy fund-quiz-api \
  --image ${IMAGE_PREFIX}-api \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars OPENDART_API_KEY=${OPENDART_API_KEY},ADMIN_TOKEN=${ADMIN_TOKEN},STORAGE_ROOT=/app/storage

# Worker service
gcloud run deploy fund-quiz-worker \
  --image ${IMAGE_PREFIX}-api \
  --region ${REGION} \
  --platform managed \
  --no-allow-unauthenticated \
  --command python \
  --args -m,app.workers.worker \
  --set-env-vars OPENDART_API_KEY=${OPENDART_API_KEY},ADMIN_TOKEN=${ADMIN_TOKEN},STORAGE_ROOT=/app/storage
