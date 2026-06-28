# Step 7 — Cloud Deploy Runbook

End-to-end operator guide for deploying the HW6 Cop-and-Thief MCP servers to
Google Cloud Run. Follow every section top to bottom. Commands are copy-paste
ready for an operator who has never seen this project.

---

## Section 1 — Prerequisites

- `gcloud` CLI installed and authenticated:
  ```bash
  gcloud auth login
  gcloud config set project <PROJECT>
  ```
- Billing account enabled on the project (Cloud Run free tier: 2M requests/month,
  scale-to-zero — no cost for idle).
- Docker Desktop installed **or** Cloud Build available as an alternative.
- Generate two bearer tokens (run twice, record the outputs):
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
  Save the first as `COP_TOKEN` and the second as `THIEF_TOKEN` in your local
  `.env` (git-ignored). Never paste real token values into any committed file.

---

## Section 2 — Build and push

Build the container image and push it to Google Container Registry:

```bash
export PROJECT=$(gcloud config get-value project)
export IMAGE="gcr.io/${PROJECT}/hw6-mcp:latest"
docker build -t "${IMAGE}" .
docker push "${IMAGE}"
# Alternative if Docker not local:
# gcloud builds submit --tag "${IMAGE}" .
```

---

## Section 3 — Deploy Cop service

Deploy the Cop MCP server to Cloud Run:

```bash
export COP_TOKEN="<paste-first-token-here>"
gcloud run deploy hw6-cop \
  --image="${IMAGE}" \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="MCP_ROLE=cop,COP_AUTH_TOKEN=${COP_TOKEN}" \
  --port=8080
# Capture the output URL, e.g.: https://hw6-cop-XXXX-uc.a.run.app
export COP_URL="<paste-url-from-output>/mcp"
```

---

## Section 4 — Deploy Thief service

Deploy the Thief MCP server to Cloud Run:

```bash
export THIEF_TOKEN="<paste-second-token-here>"
gcloud run deploy hw6-thief \
  --image="${IMAGE}" \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="MCP_ROLE=thief,THIEF_AUTH_TOKEN=${THIEF_TOKEN}" \
  --port=8080
export THIEF_URL="<paste-url-from-output>/mcp"
```

---

## Section 5 — Curl smoke-test (prove 401 and 200)

Prove the auth gate works: a request without a token gets HTTP 401, and a
request with the correct bearer token gets HTTP 200.

```bash
# 401 without token:
curl -i "${COP_URL}" -X POST -H "Content-Type: application/json" -d '{}'
# Expected: HTTP/2 401 {"error":"Unauthorized"}

# 200 with correct token:
curl -i "${COP_URL}" \
  -X POST \
  -H "Authorization: Bearer ${COP_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ping","arguments":{}},"id":1}'
# Expected: HTTP/2 200 {"result":...}

# Repeat for THIEF_URL / THIEF_TOKEN
```

---

## Section 6 — Wire the orchestrator to the cloud

Point the orchestrator at the cloud endpoints by exporting the env vars it
reads via `gateway_from_env`:

```bash
export COP_SERVER_URL="${COP_URL}"
export THIEF_SERVER_URL="${THIEF_URL}"
export COP_AUTH_TOKEN="${COP_TOKEN}"
export THIEF_AUTH_TOKEN="${THIEF_TOKEN}"
uv run python -m src.orchestrator
```

---

## Section 7 — Record URLs in README

Add a `## Cloud Deployment` section to `README.md` with the two public URLs
and the curl proof showing 401 (no token) and 200 (correct token).

---

## Section 8 — Fallback: cloudflare tunnel / ngrok (if Cloud Run unavailable)

If Cloud Run is unavailable, expose the local servers via a tunnel:

```bash
# Start servers locally as today, then expose via tunnel:
# Terminal 1: python -m src.mcp_servers.cop_server
# Terminal 2: python -m src.mcp_servers.thief_server
# Terminal 3: cloudflared tunnel --url http://localhost:8001
# Terminal 4: cloudflared tunnel --url http://localhost:8002
# Note: tunnel URLs change on restart; prefer Cloud Run for the README artifact.
```
