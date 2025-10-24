#!/usr/bin/env bash
# Deploy FastAPI container to Azure Container Apps (ACA)
# Works on macOS arm64 (M1/M2/M3) by building linux/amd64 images.
# Idempotent: creates ACR/LAW/Env/App if missing, otherwise updates.

set -euo pipefail

# --- Optional: auto-load .env (disable with NO_DOTENV=1) ----------------------
if [[ "${NO_DOTENV:-0}" != "1" && -f .env ]]; then
  echo "Loading .env ..."
  # export all variables defined in .env
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# --- Pre-flight ---------------------------------------------------------------
command -v az >/dev/null || { echo "Azure CLI not found. Install via 'brew install azure-cli'."; exit 1; }
az account show >/dev/null 2>&1 || az login >/dev/null

# --- Required secret/config envs (fail fast if missing) -----------------------
required_vars=(
  AZURE_GPT5_ENDPOINT
  AZURE_GPT5_API_KEY
  AZURE_MODEL_NAME_DEPLOYMENT
  AZURE_OPENAI_API_VERSION
  AZURE_STORAGE_ACCOUNT_URL
  AZURE_STORAGE_ACCOUNT_KEY
  AZURE_STORAGE_CONTAINER
  API_KEY
)
for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Missing required variable: $var" >&2
    echo "Tip: set it in .env or export it in your shell." >&2
    exit 1
  fi
done

# --- Parameters (override via env if you like) --------------------------------
RG=${RG:-"rg-fin-restructure-dev-eus"}
LOC=${LOC:-"eastus"}
ACR=${ACR:-"acrfinrestructdev"}                 # must be globally unique (lowercase alnum)
IMG=${IMG:-"finreport"}                         # repo name in ACR
TAG=${TAG:-"v1"}                                # image tag
LAW=${LAW:-"law-fin-restructure-dev-eus"}       # Log Analytics workspace
ENV=${ENV:-"cae-fin-restructure-dev-eus"}       # Container Apps environment
APP=${APP:-"api-fin-restructure-dev"}           # Container App name
HEALTH_PATH=${HEALTH_PATH:-"/health"}            # liveness probe path
CPU=${CPU:-"0.5"}
MEM=${MEM:-"1Gi"}
MIN_REPLICAS=${MIN_REPLICAS:-"0"}
MAX_REPLICAS=${MAX_REPLICAS:-"2"}
HTTP_CONCURRENCY=${HTTP_CONCURRENCY:-"50"}

# --- Create RG & ACR ----------------------------------------------------------
echo "Ensuring resource group $RG in $LOC ..."
az group create -n "$RG" -l "$LOC" >/dev/null

echo "Ensuring ACR $ACR ..."
if ! az acr show -n "$ACR" -g "$RG" >/dev/null 2>&1; then
  az acr create -g "$RG" -n "$ACR" --sku Basic --location "$LOC" >/dev/null
fi

# Enable admin access so Container Apps can pull images
echo "Enabling ACR admin access ..."
az acr update -n "$ACR" -g "$RG" --admin-enabled true >/dev/null

az acr login -n "$ACR" >/dev/null

# --- Build & push image (force linux/amd64 for Azure) -------------------------
IMAGE="$ACR.azurecr.io/$IMG:$TAG"
echo "Building Docker image for linux/amd64: $IMAGE ..."
docker build --platform linux/amd64 -t "$IMAGE" .
echo "Pushing $IMAGE ..."
docker push "$IMAGE" >/dev/null

# --- Log Analytics + Container Apps env --------------------------------------
echo "Ensuring Container Apps extension ..."
az extension add --name containerapp --upgrade -y >/dev/null || true

echo "Ensuring Log Analytics workspace $LAW ..."
if ! az monitor log-analytics workspace show -g "$RG" -n "$LAW" >/dev/null 2>&1; then
  az monitor log-analytics workspace create -g "$RG" -n "$LAW" -l "$LOC" >/dev/null
fi

# Get the CUSTOMER ID (not resource ID)
LAW_CUSTOMER_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query customerId -o tsv)

# Get the WORKSPACE KEY
LAW_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "$LAW" --query primarySharedKey -o tsv)

echo "Ensuring Container Apps environment $ENV ..."
if ! az containerapp env show -g "$RG" -n "$ENV" >/dev/null 2>&1; then
  az containerapp env create -g "$RG" -n "$ENV" -l "$LOC" \
    --logs-destination log-analytics \
    --logs-workspace-id "$LAW_CUSTOMER_ID" \
    --logs-workspace-key "$LAW_KEY" >/dev/null
fi

# --- Secrets & env vars -------------------------------------------------------
ACR_USER=$(az acr credential show -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR" --query passwords[0].value -o tsv)

COMMON_FLAGS=(
  --image "$IMAGE"
  --registry-server "$ACR.azurecr.io"
  --registry-username "$ACR_USER"
  --registry-password "$ACR_PASS"
  --ingress external --target-port 8000
  --cpu "$CPU" --memory "$MEM"
  --secrets aoai-key="$AZURE_GPT5_API_KEY" storage-key="$AZURE_STORAGE_ACCOUNT_KEY" fastapi-api-key="$API_KEY"
  --env-vars
    AZURE_GPT5_ENDPOINT="$AZURE_GPT5_ENDPOINT"
    AZURE_MODEL_NAME_DEPLOYMENT="$AZURE_MODEL_NAME_DEPLOYMENT"
    AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION"
    AZURE_STORAGE_ACCOUNT_URL="$AZURE_STORAGE_ACCOUNT_URL"
    AZURE_STORAGE_CONTAINER="$AZURE_STORAGE_CONTAINER"
    AZURE_GPT5_API_KEY=secretref:aoai-key
    AZURE_STORAGE_ACCOUNT_KEY=secretref:storage-key
    API_KEY=secretref:fastapi-api-key
)

# Create or update the Container App
if az containerapp show -g "$RG" -n "$APP" >/dev/null 2>&1; then
  echo "Updating Container App $APP ..."
  az containerapp update -g "$RG" -n "$APP" "${COMMON_FLAGS[@]}" >/dev/null
else
  echo "Creating Container App $APP ..."
  az containerapp create -g "$RG" -n "$APP" --environment "$ENV" "${COMMON_FLAGS[@]}" >/dev/null
fi

# Probe & scale
echo "Configuring liveness probe ($HEALTH_PATH) and autoscale ..."
az containerapp update -g "$RG" -n "$APP" \
  --set-probe liveness http-path="$HEALTH_PATH" http-port=8000 initial-delay=10 period=30 >/dev/null || true

az containerapp update -g "$RG" -n "$APP" --min-replicas "$MIN_REPLICAS" --max-replicas "$MAX_REPLICAS" \
  --scale-rules "[{\"name\":\"http\",\"http\":{\"concurrentRequests\":$HTTP_CONCURRENCY}}]" >/dev/null || true

# --- Output -------------------------------------------------------------------
URL=$(az containerapp show -g "$RG" -n "$APP" --query properties.configuration.ingress.fqdn -o tsv)
cat <<MSG
✅ Deployment complete: https://$URL

Health check:
  curl -s "https://$URL${HEALTH_PATH}"

Create a report:
  curl -s -X POST "https://$URL/v1/report" \\
    -H "Content-Type: application/json" \\
    -H "X-API-Key: ****" \\
    -d '{"customer_id":"CU-002"}' | jq

Logs (follow):
  az containerapp logs show -g "$RG" -n "$APP" --follow
MSG
