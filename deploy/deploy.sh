#!/usr/bin/env bash
# deploy/deploy.sh — print the gcloud commands for the two Cloud Run services.
# Run interactively after: gcloud auth login && gcloud config set project <PROJECT>
# See docs/step7_cloud_deploy/DEPLOY.md for the full annotated runbook.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
IMAGE="gcr.io/${PROJECT}/hw6-mcp:latest"
COP_SVC="hw6-cop"
THIEF_SVC="hw6-thief"

echo "=== Step 1: build and push the image ==="
echo "docker build -t ${IMAGE} ."
echo "docker push ${IMAGE}"
echo ""
echo "=== Step 2: deploy Cop service ==="
echo "gcloud run deploy ${COP_SVC} \\"
echo "  --image=${IMAGE} \\"
echo "  --region=${REGION} \\"
echo "  --platform=managed \\"
echo "  --allow-unauthenticated \\"
echo "  --set-env-vars=MCP_ROLE=cop,COP_AUTH_TOKEN=\${COP_AUTH_TOKEN} \\"
echo "  --port=8080"
echo ""
echo "=== Step 3: deploy Thief service ==="
echo "gcloud run deploy ${THIEF_SVC} \\"
echo "  --image=${IMAGE} \\"
echo "  --region=${REGION} \\"
echo "  --platform=managed \\"
echo "  --allow-unauthenticated \\"
echo "  --set-env-vars=MCP_ROLE=thief,THIEF_AUTH_TOKEN=\${THIEF_AUTH_TOKEN} \\"
echo "  --port=8080"
